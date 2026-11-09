"""Video analysis for clients: their videos and their competitors', side by side.

Flow: the user creates a client, drops the client's videos and the competitors' videos
(files: no account, no scraping), optionally adds each video's results (typed, or read
by the AI from screenshots of Insights / TikTok Studio), then asks for the analysis.

- Every video is measured offline in a background worker (FFmpeg + faster-whisper).
- The analysis uses the AI chosen by the user, with the usual "Open in chat" fallback.
- A PDF for the client comes from `video.report`.
"""

from __future__ import annotations

import json
import logging
import queue
import re
import shutil
import threading
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import ValidationError

from taleport.ai import prompts
from taleport.ai.providers.base import LLMProvider, ProviderError
from taleport.ai.service import AIService
from taleport.ai.structured import parse_answer, run_structured
from taleport.core.errors import AppError
from taleport.core.events import EventBus
from taleport.core.paths import data_dir
from taleport.db.database import Database
from taleport.video import features as feat
from taleport.video import media, transcribe
from taleport.video.schemas import PLATFORMS, StatsReading, VideoAnalysis, VideoStats

log = logging.getLogger(__name__)

MAX_PROJECTS = 200
MAX_VIDEOS_PER_PROJECT = 60
MAX_VIDEO_BYTES = 2 * 1024**3
MAX_SCREENSHOTS = 6
MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024
MAX_FRAMES_TO_AI = 12
NAME_MAX = 80
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def videos_root() -> Path:
    path = data_dir() / "videos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _project_dir(project_id: int) -> Path:
    path = videos_root() / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_name(value: str, field: str) -> str:
    name = re.sub(r"\s+", " ", value or "").strip()[:NAME_MAX]
    if not name:
        raise AppError("validation", fields=[field])
    return name


def _seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:g}s"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


class VideoService:
    def __init__(
        self,
        db: Database,
        ai: AIService,
        bus: EventBus,
        *,
        transcriber: Any = transcribe,  # None in tests: no speech-to-text
        start_worker: bool = True,
    ) -> None:
        self._db = db
        self._ai = ai
        self._bus = bus
        self._transcriber = transcriber
        self._queue: queue.Queue[int] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._start_worker = start_worker
        self._lock = threading.Lock()

    # -- tools -----------------------------------------------------------------------------

    def tools(self) -> dict[str, Any]:
        whisper = self._transcriber is not None and transcribe.package_available()
        return {
            "ffmpeg": media.ffmpeg_available(),
            "transcription": whisper,
            "model_downloaded": whisper and transcribe.model_downloaded(),
            "model_mb": transcribe.MODEL_DOWNLOAD_MB,
        }

    # -- projects (one per client) ------------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT p.id, p.client_name, p.analyzed_at, p.updated_at, p.created_at, "
                "COUNT(v.id) AS videos, "
                "SUM(CASE WHEN v.owner_kind = 'client' THEN 1 ELSE 0 END) AS client_videos, "
                "COUNT(DISTINCT CASE WHEN v.owner_kind = 'competitor' THEN v.owner_name END) "
                "AS competitors, "
                "SUM(CASE WHEN v.status IN ('queued', 'processing') THEN 1 ELSE 0 END) AS busy "
                "FROM video_projects p LEFT JOIN videos v ON v.project_id = p.id "
                "GROUP BY p.id ORDER BY p.updated_at DESC"
            ).fetchall()
        return [
            {**dict(r), "client_videos": r["client_videos"] or 0, "busy": r["busy"] or 0}
            for r in rows
        ]

    def create_project(self, client_name: str, notes: str = "") -> dict[str, Any]:
        name = _clean_name(client_name, "client_name")
        with self._db.connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM video_projects").fetchone()[0] >= MAX_PROJECTS:
                raise AppError("video.too_many_projects", max=MAX_PROJECTS)
            project_id = conn.execute(
                "INSERT INTO video_projects (client_name, notes) VALUES (?, ?)",
                (name, notes.strip()[:2000]),
            ).lastrowid
        return self.get_project(int(project_id))

    def update_project(
        self, project_id: int, client_name: str | None, notes: str | None
    ) -> dict[str, Any]:
        self._project_row(project_id)
        with self._db.connect() as conn:
            if client_name is not None:
                conn.execute(
                    "UPDATE video_projects SET client_name = ? WHERE id = ?",
                    (_clean_name(client_name, "client_name"), project_id),
                )
            if notes is not None:
                conn.execute(
                    "UPDATE video_projects SET notes = ? WHERE id = ?",
                    (notes.strip()[:2000], project_id),
                )
            self._touch(conn, project_id)
        return self.get_project(project_id)

    def delete_project(self, project_id: int) -> None:
        self._project_row(project_id)
        with self._db.connect() as conn:
            conn.execute("DELETE FROM video_projects WHERE id = ?", (project_id,))
        shutil.rmtree(videos_root() / str(project_id), ignore_errors=True)

    def _project_row(self, project_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM video_projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise AppError("video.project_not_found", status=404)
        return dict(row)

    @staticmethod
    def _touch(conn: Any, project_id: int) -> None:
        conn.execute(
            "UPDATE video_projects SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE id = ?",
            (project_id,),
        )

    def get_project(self, project_id: int) -> dict[str, Any]:
        project = self._project_row(project_id)
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM videos WHERE project_id = ? ORDER BY owner_kind, owner_name, id",
                (project_id,),
            ).fetchall()
        videos = [self._video_dict(r) for r in rows]
        project["analysis"] = json.loads(project["analysis"]) if project["analysis"] else None
        project["videos"] = videos
        project["groups"] = self._groups(videos)
        return project

    @staticmethod
    def _video_dict(row: Any) -> dict[str, Any]:
        video = dict(row)
        video["features"] = json.loads(video["features"] or "{}")
        video["stats"] = json.loads(video["stats"] or "{}")
        video["transcript"] = json.loads(video["transcript"]) if video["transcript"] else None
        video["derived"] = feat.derive(video["features"], video["stats"])
        video["frames"] = len(video["features"].get("frame_times") or [])
        video.pop("stored_name", None)
        return video

    @staticmethod
    def _groups(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The client first, then each competitor, with medians of the ready videos."""
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for video in videos:
            key = (
                video["owner_kind"],
                video["owner_name"] if video["owner_kind"] != "client" else "",
            )
            groups.setdefault(key, []).append(video)
        ordered = sorted(groups.items(), key=lambda kv: (kv[0][0] != "client", kv[0][1].lower()))
        return [
            {
                "kind": kind,
                "name": name,
                "video_ids": [v["id"] for v in items],
                "summary": feat.summarize([v for v in items if v["status"] == "ready"]),
            }
            for (kind, name), items in ordered
        ]

    # -- videos -------------------------------------------------------------------------

    def add_video(
        self,
        project_id: int,
        owner_kind: str,
        owner_name: str,
        platform: str,
        file_name: str,
        stream: BinaryIO,
    ) -> dict[str, Any]:
        self._project_row(project_id)
        if owner_kind not in ("client", "competitor"):
            raise AppError("validation", fields=["owner_kind"])
        owner = _clean_name(owner_name, "owner_name") if owner_kind == "competitor" else ""
        platform = platform if platform in PLATFORMS else "other"
        suffix = Path(file_name).suffix.lower()
        if suffix not in media.VIDEO_EXTENSIONS:
            raise AppError("video.unsupported_file", name=file_name[:120])
        with self._db.connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE project_id = ?", (project_id,)
            ).fetchone()[0]
            if count >= MAX_VIDEOS_PER_PROJECT:
                raise AppError("video.too_many_videos", max=MAX_VIDEOS_PER_PROJECT)
            video_id = int(
                conn.execute(
                    "INSERT INTO videos (project_id, owner_kind, owner_name, platform, file_name, "
                    "stored_name) VALUES (?, ?, ?, ?, ?, '')",
                    (project_id, owner_kind, owner, platform, Path(file_name).name[:200]),
                ).lastrowid
            )
        stored = f"{video_id}{suffix}"
        target = _project_dir(project_id) / stored
        size = 0
        try:
            with target.open("wb") as out:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_VIDEO_BYTES:
                        raise AppError("video.too_big", max_gb=MAX_VIDEO_BYTES // 1024**3)
                    out.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            with self._db.connect() as conn:
                conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            raise
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE videos SET stored_name = ?, size = ? WHERE id = ?", (stored, size, video_id)
            )
            self._touch(conn, project_id)
        self.enqueue(video_id)
        return self.get_video(video_id)

    def _video_row(self, video_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if row is None:
            raise AppError("video.not_found", status=404)
        return dict(row)

    def get_video(self, video_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        if row is None:
            raise AppError("video.not_found", status=404)
        return self._video_dict(row)

    def update_video(self, video_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        row = self._video_row(video_id)
        sets: dict[str, Any] = {}
        if "owner_kind" in changes or "owner_name" in changes:
            kind = changes.get("owner_kind", row["owner_kind"])
            if kind not in ("client", "competitor"):
                raise AppError("validation", fields=["owner_kind"])
            name = changes.get("owner_name", row["owner_name"])
            sets["owner_kind"] = kind
            sets["owner_name"] = _clean_name(name, "owner_name") if kind == "competitor" else ""
        if "platform" in changes:
            sets["platform"] = changes["platform"] if changes["platform"] in PLATFORMS else "other"
        if "stats" in changes:
            try:
                stats = VideoStats.model_validate(changes["stats"] or {})
            except ValidationError as exc:
                fields = sorted({str(e["loc"][0]) for e in exc.errors() if e.get("loc")})
                raise AppError("validation", fields=fields) from exc
            sets["stats"] = stats.model_dump_json(exclude_none=True)
            sets["stats_via"] = "manual"
            if stats.platform:
                sets["platform"] = stats.platform
        if sets:
            with self._db.connect() as conn:
                conn.execute(
                    f"UPDATE videos SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?",  # noqa: S608 (fixed keys)
                    (*sets.values(), video_id),
                )
                self._touch(conn, row["project_id"])
        return self.get_video(video_id)

    def delete_video(self, video_id: int) -> None:
        row = self._video_row(video_id)
        with self._db.connect() as conn:
            conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
            self._touch(conn, row["project_id"])
        folder = videos_root() / str(row["project_id"])
        for path in folder.glob(f"{video_id}[._]*"):
            path.unlink(missing_ok=True)

    def video_file(self, video_id: int) -> Path:
        row = self._video_row(video_id)
        path = videos_root() / str(row["project_id"]) / row["stored_name"]
        if not row["stored_name"] or not path.is_file():
            raise AppError("video.not_found", status=404)
        return path

    def frame_file(self, video_id: int, index: int) -> Path:
        row = self._video_row(video_id)
        path = videos_root() / str(row["project_id"]) / f"{video_id}_f{index}.jpg"
        if not path.is_file():
            raise AppError("video.not_found", status=404)
        return path

    # -- background processing ------------------------------------------------------------

    def enqueue(self, video_id: int) -> None:
        self._queue.put(video_id)
        self._publish(video_id, "queued")
        self._ensure_worker()

    def retry(self, video_id: int) -> dict[str, Any]:
        self._video_row(video_id)
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE videos SET status = 'queued', error_code = NULL, step = NULL WHERE id = ?",
                (video_id,),
            )
        self.enqueue(video_id)
        return self.get_video(video_id)

    def resume(self) -> None:
        """At startup: videos left half-processed when the app was closed start again."""
        with self._db.connect() as conn:
            conn.execute("UPDATE videos SET status = 'queued' WHERE status = 'processing'")
            pending = [r[0] for r in conn.execute("SELECT id FROM videos WHERE status = 'queued'")]
        for video_id in pending:
            self.enqueue(video_id)

    def _ensure_worker(self) -> None:
        if not self._start_worker:
            return
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._work, name="video-worker", daemon=True)
                self._worker.start()

    def _work(self) -> None:
        while True:
            try:
                video_id = self._queue.get(timeout=30)
            except queue.Empty:
                return  # idle: the thread ends, the next enqueue starts a new one
            try:
                self.process(video_id)
            except Exception:
                log.exception("Video %s: unexpected processing error", video_id)
            finally:
                self._queue.task_done()

    def _publish(self, video_id: int, status: str, step: str | None = None) -> None:
        try:
            project_id = self._video_row(video_id)["project_id"]
        except AppError:
            return
        self._bus.publish(
            "videos.changed",
            {"project_id": project_id, "video_id": video_id, "status": status, "step": step},
        )

    def _step(self, video_id: int, step: str) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE videos SET status = 'processing', step = ? WHERE id = ?", (step, video_id)
            )
        self._publish(video_id, "processing", step)

    def process(self, video_id: int) -> None:
        """Measure one video. Runs in the worker thread (directly in tests)."""
        try:
            row = self._video_row(video_id)
        except AppError:
            return  # deleted while waiting
        if row["status"] == "ready":
            return
        path = videos_root() / str(row["project_id"]) / row["stored_name"]
        try:
            self._step(video_id, "probe")
            info = media.probe(path)
            self._step(video_id, "cuts")
            cuts = media.scene_cuts(path)
            audio = None
            if info.has_audio:
                self._step(video_id, "audio")
                audio = media.audio_levels(path, info.duration)
            self._step(video_id, "frames")
            times = media.frame_times(info.duration)
            saved_times = []
            for index, second in enumerate(times):
                target = path.parent / f"{video_id}_f{index}.jpg"
                if media.extract_frame(path, second, target):
                    saved_times.append(second)
            transcript, speech_error = None, None
            if info.has_audio and self._transcriber is not None:
                self._step(video_id, "speech")
                transcript, speech_error = self._transcribe(path)
            features = feat.measure(info, cuts, audio, transcript)
            features["frame_times"] = saved_times
            if speech_error:
                features["speech_error"] = speech_error
            segments = (
                [{"start": s.start, "end": s.end, "text": s.text} for s in transcript.segments]
                if transcript
                else None
            )
            with self._db.connect() as conn:
                conn.execute(
                    "UPDATE videos SET status = 'ready', step = NULL, error_code = NULL, "
                    "features = ?, transcript = ? WHERE id = ?",
                    (json.dumps(features), json.dumps(segments) if segments else None, video_id),
                )
            self._publish(video_id, "ready")
        except AppError as exc:
            self._fail(video_id, exc.code)
        except Exception:
            log.exception("Video %s: processing failed", video_id)
            self._fail(video_id, "video.process_failed")

    def _transcribe(self, path: Path) -> tuple[Any, str | None]:
        wav = path.with_name(f"{path.stem}_audio.wav")
        try:
            if not self._transcriber.package_available():
                return None, "video.speech_unavailable"
            if not media.extract_wav(path, wav):
                return None, None
            return self._transcriber.transcribe(wav), None
        except Exception as exc:  # model download blocked, out of memory...
            log.warning("Transcription failed for %s: %r", path.name, exc)
            return None, "video.speech_failed"
        finally:
            wav.unlink(missing_ok=True)

    def _fail(self, video_id: int, code: str) -> None:
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE videos SET status = 'failed', step = NULL, error_code = ? WHERE id = ?",
                (code, video_id),
            )
        self._publish(video_id, "failed")

    # -- results from screenshots ---------------------------------------------------------

    def _stats_prompt(self, row: dict[str, Any]) -> prompts.Prompt:
        duration = json.loads(row["features"] or "{}").get("duration")
        return prompts.render(
            "video_stats",
            self._ai.language(),
            file_name=row["file_name"],
            duration="-" if duration is None else f"{duration:g}",
        )

    @staticmethod
    def check_screenshots(images: list[tuple[str, bytes]]) -> list[bytes]:
        if not images:
            raise AppError("video.no_screenshots")
        if len(images) > MAX_SCREENSHOTS:
            raise AppError("video.too_many_screenshots", max=MAX_SCREENSHOTS)
        out = []
        for name, data in images:
            if Path(name).suffix.lower() not in _IMAGE_SUFFIXES:
                raise AppError("video.unsupported_image", name=name[:120])
            if len(data) > MAX_SCREENSHOT_BYTES:
                raise AppError("video.image_too_big", name=name[:120])
            out.append(data)
        return out

    def read_stats(self, video_id: int, images: list[bytes], mode: str | None) -> dict[str, Any]:
        row = self._video_row(video_id)
        prompt = self._stats_prompt(row)
        mode, provider, fallback = self._ai.resolve(mode)
        if provider is not None and not getattr(provider, "vision", False):
            provider, fallback = None, "ai.no_vision"
        if provider is None:
            handoff = self._ai.handoff(prompt)
            return {
                "mode": "chat",
                "fallback": fallback,
                "handoff": {**handoff, "images": len(images)},
            }
        try:
            reading = run_structured(
                provider,
                prompt,
                StatsReading,
                self._ai.recorder(provider, "video_stats"),
                images=images,
                max_tokens=2000,
            )
        except ProviderError as exc:
            raise AppError.from_provider(exc) from exc
        return {"mode": mode, "video": self._save_stats(video_id, reading.stats)}

    def parse_stats(self, video_id: int, text: str) -> dict[str, Any]:
        self._video_row(video_id)
        reading = parse_answer(text, StatsReading)
        return {"mode": "chat", "video": self._save_stats(video_id, reading.stats)}

    def _save_stats(self, video_id: int, stats: VideoStats) -> dict[str, Any]:
        row = self._video_row(video_id)
        current = VideoStats.model_validate(json.loads(row["stats"] or "{}"))
        # Values read now win; fields the screenshots did not show keep what was there.
        merged = {**current.model_dump(exclude_none=True), **stats.model_dump(exclude_none=True)}
        if not stats.retention and current.retention:
            merged["retention"] = current.model_dump()["retention"]
        final = VideoStats.model_validate(merged)
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE videos SET stats = ?, stats_via = 'screenshot', platform = ? WHERE id = ?",
                (
                    final.model_dump_json(exclude_none=True),
                    final.platform or row["platform"],
                    video_id,
                ),
            )
            self._touch(conn, row["project_id"])
        return self.get_video(video_id)

    # -- AI analysis ------------------------------------------------------------------------

    def _ready_project(self, project_id: int) -> dict[str, Any]:
        project = self.get_project(project_id)
        ready = [v for v in project["videos"] if v["status"] == "ready"]
        if not any(v["owner_kind"] == "client" for v in ready):
            raise AppError("video.no_client_videos")
        if any(v["status"] in ("queued", "processing") for v in project["videos"]):
            raise AppError("video.still_processing")
        project["videos"] = ready
        project["groups"] = self._groups(ready)
        return project

    @staticmethod
    def _owner_label(video: dict[str, Any], client: str) -> str:
        return client if video["owner_kind"] == "client" else video["owner_name"]

    def _comparison_text(self, project: dict[str, Any]) -> str:
        lines = []
        for group in project["groups"]:
            s = group["summary"]
            label = project["client_name"] if group["kind"] == "client" else group["name"]
            role = "CLIENT" if group["kind"] == "client" else "COMPETITOR"
            lines.append(
                f"- {role} {label}: videos {s['videos']} · length {_seconds(s['duration'])} · "
                f"cuts/min {s['cuts_per_minute'] if s['cuts_per_minute'] is not None else '-'} · "
                f"first cut {_seconds(s['first_cut_at'])} · "
                f"first words {_seconds(s['first_word_at'])}"
                f" · words/min {s['words_per_minute'] or '-'} · silence {_pct(s['silence_ratio'])}"
                f" · views {s['views'] if s['views'] is not None else '-'}"
                f" · watched {_pct(s['watched_ratio'])}"
                f" · interactions {_pct(s['interaction_rate'])}"
            )
        return "\n".join(lines)

    def _video_text(self, video: dict[str, Any], client: str) -> str:
        f, st, d = video["features"], video["stats"], video["derived"]
        role = "CLIENT" if video["owner_kind"] == "client" else "COMPETITOR"
        parts = [
            f"[{video['id']}] {role} {self._owner_label(video, client)} · {video['platform']} · "
            f"«{video['file_name']}»",
            f"  file: length {_seconds(f.get('duration'))}, {f.get('orientation')}, "
            f"cuts {f.get('cut_count')} ({f.get('cuts_per_minute')}/min, first at "
            f"{_seconds(f.get('first_cut_at'))}, avg shot {_seconds(f.get('avg_shot_seconds'))}), "
            f"cut times {', '.join(f'{c:g}' for c in (f.get('cuts') or [])[:25]) or '-'}",
        ]
        if f.get("has_audio"):
            silences = ", ".join(f"{a:g}-{b:g}" for a, b in (f.get("silences") or [])[:10])
            parts.append(
                f"  audio: silence {_pct(f.get('silence_ratio'))} (pauses {silences or '-'}), "
                f"mean volume {f.get('mean_volume_db', '-')} dB"
            )
        else:
            parts.append("  audio: none")
        if f.get("word_count") is not None:
            parts.append(
                f"  speech: first words at {_seconds(f.get('first_word_at'))}, "
                f"{f.get('words_per_minute') or '-'} words/min, "
                f"hook text «{f.get('hook_text') or ''}»"
            )
        if video.get("transcript"):
            text = " ".join(f"({s['start']:g}s) {s['text']}" for s in video["transcript"])
            parts.append(f"  transcript: {text[:1200]}")
        result_bits = [
            f"{key} {st[key]}"
            for key in ("views", "reach", "likes", "comments", "shares", "saves", "follows")
            if st.get(key) is not None
        ]
        if st.get("avg_watch_seconds") is not None:
            result_bits.append(f"avg watch {_seconds(st['avg_watch_seconds'])}")
        if d.get("watched_ratio") is not None:
            result_bits.append(f"watched {_pct(d['watched_ratio'])}")
        if d.get("interaction_rate") is not None:
            result_bits.append(f"interactions {_pct(d['interaction_rate'])}")
        parts.append(f"  results: {' · '.join(result_bits) if result_bits else 'not provided'}")
        if st.get("retention"):
            curve = ", ".join(f"{p['second']:g}s={p['percent']:g}%" for p in st["retention"])
            parts.append(f"  retention: {curve}")
            if d.get("biggest_drop"):
                b = d["biggest_drop"]
                parts.append(
                    f"  biggest drop: {b['from_second']:g}s→{b['to_second']:g}s "
                    f"(-{b['lost_percent']:g} points)"
                )
        if st.get("notes"):
            parts.append(f"  notes: {st['notes']}")
        return "\n".join(parts)

    def _frames(self, project: dict[str, Any]) -> tuple[list[bytes], str]:
        """Opening frames (the hook), client videos first, at most MAX_FRAMES_TO_AI."""
        ordered = sorted(project["videos"], key=lambda v: v["owner_kind"] != "client")
        images: list[bytes] = []
        labels: list[str] = []
        folder = videos_root() / str(project["id"])
        for video in ordered:
            times = video["features"].get("frame_times") or []
            for index in range(min(2, len(times))):
                if len(images) >= MAX_FRAMES_TO_AI:
                    break
                path = folder / f"{video['id']}_f{index}.jpg"
                if path.is_file():
                    images.append(path.read_bytes())
                    labels.append(f"{len(images)}=[{video['id']}]@{times[index]:g}s")
        note = f"Frames: {', '.join(labels)}" if labels else ""
        return images, note

    def _analysis_prompt(self, project: dict[str, Any], frames_note: str) -> prompts.Prompt:
        client = project["client_name"]
        return prompts.render(
            "video_analysis",
            self._ai.language(),
            client_name=client,
            notes=project["notes"] or "-",
            comparison=self._comparison_text(project),
            videos="\n\n".join(self._video_text(v, client) for v in project["videos"]),
            frames_note=frames_note,
        )

    def analyze(self, project_id: int, mode: str | None) -> dict[str, Any]:
        project = self._ready_project(project_id)
        mode, provider, fallback = self._ai.resolve(mode)
        if provider is None:
            prompt = self._analysis_prompt(project, "")
            return {"mode": "chat", "fallback": fallback, "handoff": self._ai.handoff(prompt)}
        images, note = self._frames(project) if getattr(provider, "vision", False) else ([], "")
        try:
            analysis = self._run_analysis(provider, project, images, note)
        except ProviderError as exc:
            raise AppError.from_provider(exc) from exc
        return {"mode": mode, "project": self._save_analysis(project_id, analysis, mode)}

    def _run_analysis(
        self, provider: LLMProvider, project: dict[str, Any], images: list[bytes], note: str
    ) -> VideoAnalysis:
        record = self._ai.recorder(provider, "video_analysis")
        try:
            return run_structured(
                provider, self._analysis_prompt(project, note), VideoAnalysis, record,
                images=images or None, max_tokens=8000,
            )  # fmt: skip
        except ProviderError as exc:
            if exc.code != "ai.no_vision" or not images:
                raise
            # A local model that cannot see images: same analysis on the numbers alone.
            return run_structured(
                provider, self._analysis_prompt(project, ""), VideoAnalysis, record, max_tokens=8000
            )

    def parse_analysis(self, project_id: int, text: str) -> dict[str, Any]:
        self._ready_project(project_id)
        analysis = parse_answer(text, VideoAnalysis)
        return {"mode": "chat", "project": self._save_analysis(project_id, analysis, "chat")}

    def _save_analysis(self, project_id: int, analysis: VideoAnalysis, via: str) -> dict[str, Any]:
        with self._db.connect() as conn:
            known = {
                r[0]
                for r in conn.execute("SELECT id FROM videos WHERE project_id = ?", (project_id,))
            }
        data = analysis.model_dump()
        data["videos"] = [v for v in data["videos"] if v["id"] in known]
        for key in ("strengths", "weaknesses"):
            for point in data[key]:
                point["videos"] = [i for i in point["videos"] if i in known]
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE video_projects SET analysis = ?, analysis_via = ?, "
                "analyzed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                (json.dumps(data, ensure_ascii=False), via, project_id),
            )
            self._touch(conn, project_id)
        return self.get_project(project_id)
