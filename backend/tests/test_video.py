"""Video analysis: offline measurements, results, screenshots, AI analysis, PDF."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from taleport.ai import prompts
from taleport.ai.providers.base import Completion, ProviderError
from taleport.api.app import create_app
from taleport.api.context import AppContext, build_context
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.video import features as feat
from taleport.video import media
from taleport.video.report import build_video_report
from taleport.video.schemas import VideoStats
from taleport.video.service import videos_root
from tests.conftest import TEST_TOKEN

ANALYSIS = {
    "summary": "Il cliente parte lento rispetto ai concorrenti.",
    "strengths": [{"title": "Audio pulito", "detail": "volume medio -23 dB", "videos": [1, 999]}],
    "weaknesses": [{"title": "Gancio lento", "detail": "primo taglio a 2 s", "videos": [1]}],
    "competitors": [
        {"name": "Rivale", "what_works": "ritmo", "weak_spots": "audio", "to_borrow": "tagli"}
    ],
    "recommendations": [{"action": "Taglia prima", "why": "si perde gente", "priority": "alta"}],
    "videos": [{"id": 1, "verdict": "ok", "hook": "lento", "drop_off": "3 s", "fix": "taglia"},
               {"id": 999, "verdict": "sconosciuto"}],
    "ideas": ["Serie di consigli in 15 secondi"],
}  # fmt: skip


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """5 s vertical clip: red then blue (a cut at 2 s), a tone then 2 s of silence."""
    path = tmp_path_factory.mktemp("media") / "reel.mp4"
    subprocess.run(
        [
            media.ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=red:s=360x640:d=2,format=yuv420p",
            "-f", "lavfi", "-i", "color=blue:s=360x640:d=3,format=yuv420p",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=2",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v];[2:a][3:a]concat=n=2:v=0:a=1[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", "-y", str(path),
        ],
        check=True,
    )  # fmt: skip
    return path


class FakeProvider:
    name = "anthropic"
    model = "claude-opus-5-5"
    paid = True

    def __init__(self, answers: list[str], vision: bool = True, refuse_images: bool = False):
        self.answers = list(answers)
        self.vision = vision
        self.refuse_images = refuse_images
        self.calls: list[dict] = []

    def complete(self, system, user, *, json_output, max_tokens=0, images=None):
        self.calls.append({"user": user, "images": images})
        if images and self.refuse_images:
            raise ProviderError("ai.no_vision", model=self.model)
        return Completion(text=self.answers.pop(0), model=self.model, input_tokens=10)


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider([json.dumps(ANALYSIS)])


@pytest.fixture
def vctx(db: Database, provider: FakeProvider) -> AppContext:
    return build_context(
        db,
        TEST_TOKEN,
        collectors_factory=list,
        ai_provider_factory=lambda *_: provider,
        video_transcriber=None,
        start_video_worker=False,
    )


@pytest.fixture
def vclient(vctx: AppContext, static_dir: Path) -> Iterator[TestClient]:
    with TestClient(create_app(vctx, static_dir=static_dir), base_url="http://127.0.0.1") as c:
        c.headers["X-TALeport-Token"] = TEST_TOKEN
        yield c


def _upload(client: TestClient, project_id: int, video: Path, **form: str) -> list[dict]:
    with video.open("rb") as handle:
        response = client.post(
            f"/api/video-projects/{project_id}/videos",
            files=[("files", (video.name, handle, "video/mp4"))],
            data=form,
        )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def ready_project(vclient: TestClient, vctx: AppContext, sample_video: Path) -> dict:
    project = vclient.post(
        "/api/video-projects", json={"client_name": " Pizzeria  Da Mario "}
    ).json()
    mine = _upload(vclient, project["id"], sample_video, owner_kind="client", platform="instagram")
    rival = _upload(vclient, project["id"], sample_video, owner_kind="competitor",
                    owner_name="Rivale", platform="tiktok")  # fmt: skip
    for video in mine + rival:
        vctx.videos.process(video["id"])
    return vclient.get(f"/api/video-projects/{project['id']}").json()


# -- offline measurements ----------------------------------------------------------------


def test_media_measures_a_real_clip(sample_video: Path) -> None:
    info = media.probe(sample_video)
    assert round(info.duration) == 5 and info.orientation == "vertical" and info.has_audio
    assert media.scene_cuts(sample_video) == [2.0]
    levels = media.audio_levels(sample_video, info.duration)
    assert levels.silences and levels.silences[0][0] == pytest.approx(3.0, abs=0.2)
    assert levels.mean_volume is not None


def test_processing_stores_features_and_frames(ready_project: dict, vclient: TestClient) -> None:
    assert ready_project["client_name"] == "Pizzeria Da Mario"
    video = ready_project["videos"][0]
    assert video["status"] == "ready" and video["frames"] == 3
    features = video["features"]
    assert features["cut_count"] == 1 and features["first_cut_at"] == 2.0
    assert features["cuts_per_minute"] == 12.0 and features["silence_ratio"] > 0.3
    assert "word_count" not in features  # no transcriber in tests
    frame = vclient.get(f"/api/videos/{video['id']}/frames/0")
    assert frame.status_code == 200 and frame.content[:2] == b"\xff\xd8"
    kinds = [(g["kind"], g["name"]) for g in ready_project["groups"]]
    assert kinds == [("client", ""), ("competitor", "Rivale")]
    assert ready_project["groups"][0]["summary"]["duration"] == 5.0


def test_unreadable_file_fails_with_a_code(vclient: TestClient, vctx: AppContext, tmp_path: Path):
    project = vclient.post("/api/video-projects", json={"client_name": "X"}).json()
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    video = _upload(vclient, project["id"], broken)[0]
    vctx.videos.process(video["id"])
    again = vclient.get(f"/api/video-projects/{project['id']}").json()["videos"][0]
    assert again["status"] == "failed" and again["error_code"] == "video.unreadable"


def test_upload_checks(vclient: TestClient, sample_video: Path, tmp_path: Path) -> None:
    project = vclient.post("/api/video-projects", json={"client_name": "X"}).json()
    text = tmp_path / "notes.txt"
    text.write_text("hello")
    with text.open("rb") as handle:
        bad = vclient.post(f"/api/video-projects/{project['id']}/videos",
                           files=[("files", ("notes.txt", handle, "text/plain"))])  # fmt: skip
    assert bad.json()["error"]["code"] == "video.unsupported_file"
    with sample_video.open("rb") as handle:
        nameless = vclient.post(
            f"/api/video-projects/{project['id']}/videos",
            files=[("files", ("a.mp4", handle, "video/mp4"))],
            data={"owner_kind": "competitor", "owner_name": "  "},
        )
    assert nameless.json()["error"] == {"code": "validation", "params": {"fields": ["owner_name"]}}
    assert vclient.get(f"/api/video-projects/{project['id']}").json()["videos"] == []


# -- results -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("12,3K", 12300), ("1.2M", 1200000), ("4.512", 4512), ("1,234", 1234), ("850", 850),
     (640, 640), ("-", None), ("2,5 mln", 2500000)],
)  # fmt: skip
def test_counts_in_screenshot_formats(raw: object, expected: int | None) -> None:
    assert VideoStats.model_validate({"views": raw}).views == expected


def test_derived_ratios_and_biggest_drop() -> None:
    curve = [(0, 100), (2, 90), (4, 55), (10, 40)]
    stats = {
        "views": 1000, "likes": 40, "comments": 5, "shares": 5, "avg_watch_seconds": 6,
        "retention": [{"second": s, "percent": p} for s, p in curve],
    }  # fmt: skip
    derived = feat.derive({"duration": 12}, stats)
    assert derived["watched_ratio"] == 0.5 and derived["interaction_rate"] == 0.05
    assert derived["biggest_drop"] == {"from_second": 2, "to_second": 4, "lost_percent": 35}
    assert derived["kept_after_hook"] == 90


def test_manual_results_are_validated(ready_project: dict, vclient: TestClient) -> None:
    video_id = ready_project["videos"][0]["id"]
    saved = vclient.patch(
        f"/api/videos/{video_id}", json={"stats": {"views": "2,1K", "avg_watch_seconds": 2.5}}
    ).json()
    assert saved["stats"]["views"] == 2100 and saved["stats_via"] == "manual"
    assert saved["derived"]["watched_ratio"] == 0.5
    bad = vclient.patch(f"/api/videos/{video_id}", json={"stats": {"avg_watch_seconds": -3}})
    assert bad.status_code == 400


def test_screenshots_are_read_with_a_vision_model(
    ready_project: dict, vclient: TestClient, provider: FakeProvider
) -> None:
    video_id = ready_project["videos"][0]["id"]
    vclient.patch(f"/api/videos/{video_id}", json={"stats": {"saves": 9}})
    reading = {
        "platform": "Instagram", "views": "3,4K", "likes": 120,
        "retention": [{"second": 0, "percent": 100}, {"second": 3, "percent": 58}],
    }  # fmt: skip
    provider.answers = [json.dumps({"stats": reading})]
    response = vclient.post(
        f"/api/videos/{video_id}/stats/read",
        files=[("images", ("insight.png", b"\x89PNG fake", "image/png"))],
        data={"mode": "anthropic"},
    ).json()
    stats = response["video"]["stats"]
    assert stats["views"] == 3400 and stats["saves"] == 9 and stats["platform"] == "instagram"
    assert response["video"]["stats_via"] == "screenshot"
    assert provider.calls[-1]["images"] == [b"\x89PNG fake"]


def test_screenshots_without_vision_go_to_the_chat(
    ready_project: dict, vclient: TestClient, provider: FakeProvider
) -> None:
    provider.vision = False
    video_id = ready_project["videos"][0]["id"]
    response = vclient.post(
        f"/api/videos/{video_id}/stats/read",
        files=[("images", ("a.jpg", b"\xff\xd8 x", "image/jpeg"))],
        data={"mode": "anthropic"},
    ).json()
    assert response["mode"] == "chat" and response["fallback"] == "ai.no_vision"
    assert response["handoff"]["images"] == 1 and "reel.mp4" in response["handoff"]["prompt"]
    pasted = '```json\n{"stats": {"views": 77}}\n```'
    parsed = vclient.post(f"/api/videos/{video_id}/stats/parse", json={"text": pasted}).json()
    assert parsed["video"]["stats"]["views"] == 77


def test_screenshot_checks(ready_project: dict, vclient: TestClient) -> None:
    video_id = ready_project["videos"][0]["id"]
    response = vclient.post(f"/api/videos/{video_id}/stats/read",
                            files=[("images", ("a.gif", b"GIF89a", "image/gif"))])  # fmt: skip
    assert response.json()["error"]["code"] == "video.unsupported_image"


# -- AI analysis -------------------------------------------------------------------------


def test_analysis_with_a_provider(ready_project: dict, vclient: TestClient, provider: FakeProvider):
    response = vclient.post(f"/api/video-projects/{ready_project['id']}/analyze",
                            json={"mode": "anthropic"}).json()  # fmt: skip
    analysis = response["project"]["analysis"]
    client_id = ready_project["videos"][0]["id"]
    assert analysis["summary"].startswith("Il cliente")
    assert analysis["strengths"][0]["videos"] == [client_id]  # unknown id 999 dropped
    assert [v["id"] for v in analysis["videos"]] == [client_id]
    assert analysis["recommendations"][0]["priority"] == "high"
    call = provider.calls[0]
    assert "CLIENT Pizzeria Da Mario" in call["user"] and "COMPETITOR Rivale" in call["user"]
    assert "first cut 2s" in call["user"] and "Frames: 1=[" in call["user"]
    assert len(call["images"]) == 4  # two opening frames per video


def test_analysis_retries_without_images(ready_project: dict, vctx: AppContext) -> None:
    fake = FakeProvider([json.dumps(ANALYSIS)], refuse_images=True)
    vctx.ai._factory = lambda *_: fake
    project = vctx.videos.analyze(ready_project["id"], "ollama")["project"]
    assert project["analysis"]["summary"]
    assert fake.calls[-1]["images"] is None and "Frames:" not in fake.calls[-1]["user"]


def test_analysis_through_the_chat(ready_project: dict, vclient: TestClient) -> None:
    pid = ready_project["id"]
    handoff = vclient.post(f"/api/video-projects/{pid}/analyze", json={"mode": "chat"}).json()
    assert handoff["mode"] == "chat" and "Pizzeria Da Mario" in handoff["handoff"]["prompt"]
    bad = vclient.post(f"/api/video-projects/{pid}/analyze/parse", json={"text": "{}"})
    assert bad.json()["error"]["code"] == "ai.invalid_pasted"
    done = vclient.post(f"/api/video-projects/{pid}/analyze/parse",
                        json={"text": json.dumps(ANALYSIS)}).json()  # fmt: skip
    assert done["project"]["analysis_via"] == "chat"


def test_analysis_needs_client_videos(vclient: TestClient) -> None:
    project = vclient.post("/api/video-projects", json={"client_name": "Vuoto"}).json()
    response = vclient.post(f"/api/video-projects/{project['id']}/analyze", json={"mode": "chat"})
    assert response.json()["error"]["code"] == "video.no_client_videos"


@pytest.mark.parametrize("language", ["it", "en", "es"])
@pytest.mark.parametrize("name", ["video_analysis", "video_stats"])
def test_video_templates_render_fully(name: str, language: str) -> None:
    keys = ("client_name", "notes", "comparison", "videos", "frames_note", "file_name", "duration")
    prompt = prompts.render(name, language, **{k: "x" for k in keys})
    assert "{{" not in prompt.system + prompt.user


# -- PDF and clean-up ----------------------------------------------------------------------


def test_report_for_the_client(ready_project: dict, vclient: TestClient, vctx: AppContext) -> None:
    from datetime import date

    plain = build_video_report(ready_project, "it", date(2026, 11, 8))
    titles = [s.title for s in plain.sections]
    assert plain.title == "Analisi video · Pizzeria Da Mario"
    assert titles == ["Sintesi", "Confronto con la concorrenza", "Come è stata fatta l'analisi"]
    vclient.post(f"/api/video-projects/{ready_project['id']}/analyze", json={"mode": "anthropic"})
    saved = vclient.post(f"/api/video-projects/{ready_project['id']}/report").json()
    assert saved["name"].startswith("TALeport_analisi_video_") and saved["size"] > 5000
    full = build_video_report(vctx.videos.get_project(ready_project["id"]), "en", date(2026, 11, 8))
    assert "Strengths" in [s.title for s in full.sections]


def test_deleting_removes_files(ready_project: dict, vclient: TestClient) -> None:
    folder = videos_root() / str(ready_project["id"])
    assert any(folder.iterdir())
    one = ready_project["videos"][0]["id"]
    assert vclient.delete(f"/api/videos/{one}").status_code == 204
    assert not list(folder.glob(f"{one}[._]*"))
    assert vclient.delete(f"/api/video-projects/{ready_project['id']}").status_code == 204
    assert not folder.exists()
    assert vclient.get("/api/video-projects").json() == []


def test_resume_requeues_interrupted_videos(vctx: AppContext, ready_project: dict) -> None:
    vid = ready_project["videos"][0]["id"]
    with vctx.db.connect() as conn:
        conn.execute("UPDATE videos SET status = 'processing' WHERE id = ?", (vid,))
    vctx.videos.resume()
    assert vctx.videos.get_video(vid)["status"] == "queued"
    with pytest.raises(AppError):
        vctx.videos.get_video(123456)


def test_providers_send_images_in_their_formats() -> None:
    from taleport.ai.providers import anthropic_provider, openai_compat

    png, jpeg = b"\x89PNG\r\n", b"\xff\xd8\xff"
    blocks = anthropic_provider._content("hi", [png, jpeg])
    assert [b["type"] for b in blocks] == ["image", "image", "text"]
    assert blocks[0]["source"]["media_type"] == "image/png"
    assert blocks[1]["source"]["media_type"] == "image/jpeg"
    assert anthropic_provider._content("hi", None) == "hi"
    parts = openai_compat._user_content("hi", [jpeg])
    assert parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert parts[-1] == {"type": "text", "text": "hi"}
