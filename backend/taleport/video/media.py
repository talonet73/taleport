"""Offline video measurements with the FFmpeg binary bundled by `imageio-ffmpeg`.

Everything here runs on the user's PC: duration and format, scene cuts, silences, loudness,
a few still frames for the AI, and a 16 kHz mono WAV for the transcription.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from taleport.core.errors import AppError

log = logging.getLogger(__name__)

SCENE_THRESHOLD = 0.32  # FFmpeg scene score above which a frame starts a new shot
SILENCE_DB = -35  # quieter than this counts as silence
SILENCE_MIN_SECONDS = 0.6
FRAME_WIDTH = 480
TIMEOUT_SECONDS = 900

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}

_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_STREAM = re.compile(r"Stream #\S+.*?: Video: .*?(\d{2,5})x(\d{2,5})")
_FPS = re.compile(r"(\d+(?:\.\d+)?) fps")
_ROTATE = re.compile(r"rotate\s*:\s*(-?\d+)|rotation of (-?\d+(?:\.\d+)?) degrees")
_PTS_TIME = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(\d+(?:\.\d+)?)")
_MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")
_MAX_VOLUME = re.compile(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB")


@cache
def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # missing package or binary
        raise AppError("video.ffmpeg_missing", status=500) from exc


def ffmpeg_available() -> bool:
    try:
        ffmpeg_exe()
    except AppError:
        return False
    return True


def _run(args: list[str], timeout: int = TIMEOUT_SECONDS) -> str:
    """Runs FFmpeg and returns its log (stderr). No console window on Windows."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # type: ignore[attr-defined]
    try:
        done = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
            capture_output=True,
            timeout=timeout,
            creationflags=flags,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError("video.timeout", status=500) from exc
    return done.stderr.decode("utf-8", errors="replace")


@dataclass
class Probe:
    duration: float
    width: int
    height: int
    fps: float | None
    has_audio: bool

    @property
    def orientation(self) -> str:
        if self.width and self.height:
            ratio = self.width / self.height
            if ratio < 0.9:
                return "vertical"
            if ratio > 1.1:
                return "horizontal"
            return "square"
        return "unknown"


def probe(path: Path) -> Probe:
    out = _run(["-i", str(path)], timeout=60)
    duration_match = _DURATION.search(out)
    video_match = _VIDEO_STREAM.search(out)
    if not duration_match or not video_match:
        raise AppError("video.unreadable")
    hours, minutes, seconds = duration_match.groups()
    width, height = int(video_match.group(1)), int(video_match.group(2))
    rotate = _ROTATE.search(out)
    if rotate:
        angle = abs(float(rotate.group(1) or rotate.group(2) or 0)) % 180
        if angle == 90:
            width, height = height, width
    fps_match = _FPS.search(out[video_match.start() :])
    return Probe(
        duration=int(hours) * 3600 + int(minutes) * 60 + float(seconds),
        width=width,
        height=height,
        fps=float(fps_match.group(1)) if fps_match else None,
        has_audio=bool(re.search(r"Stream #\S+.*?: Audio:", out)),
    )


def scene_cuts(path: Path, threshold: float = SCENE_THRESHOLD) -> list[float]:
    """Seconds at which a new shot starts (hard cuts and big visual changes)."""
    out = _run(
        [
            "-i", str(path), "-an", "-sn",
            "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ]
    )  # fmt: skip
    cuts = [round(float(m.group(1)), 2) for m in _PTS_TIME.finditer(out)]
    # Fades can produce several detections in a row: keep one per half second.
    kept: list[float] = []
    for cut in cuts:
        if cut > 0.2 and (not kept or cut - kept[-1] >= 0.5):
            kept.append(cut)
    return kept


@dataclass
class AudioLevels:
    silences: list[tuple[float, float]] = field(default_factory=list)
    mean_volume: float | None = None
    max_volume: float | None = None


def audio_levels(path: Path, duration: float) -> AudioLevels:
    out = _run(
        [
            "-i", str(path), "-vn", "-sn",
            "-af", f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN_SECONDS},volumedetect",
            "-f", "null", "-",
        ]
    )  # fmt: skip
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in out.splitlines():
        if (m := _SILENCE_START.search(line)) is not None:
            start = max(0.0, float(m.group(1)))
        elif (m := _SILENCE_END.search(line)) is not None and start is not None:
            silences.append((round(start, 2), round(float(m.group(1)), 2)))
            start = None
    if start is not None:
        silences.append((round(start, 2), round(duration, 2)))
    mean = _MEAN_VOLUME.search(out)
    peak = _MAX_VOLUME.search(out)
    return AudioLevels(
        silences=silences,
        mean_volume=float(mean.group(1)) if mean else None,
        max_volume=float(peak.group(1)) if peak else None,
    )


def frame_times(duration: float) -> list[float]:
    """The hook (0.5 s and 2.5 s), the middle and the last second."""
    if duration <= 0:
        return [0.0]
    times = [min(0.5, duration / 4), min(2.5, duration / 2), duration / 2, max(0.0, duration - 1)]
    unique: list[float] = []
    for t in times:
        if all(abs(t - u) > 0.4 for u in unique):
            unique.append(round(t, 2))
    return unique


def extract_frame(path: Path, second: float, target: Path) -> bool:
    _run(
        [
            "-ss", f"{second:.2f}", "-i", str(path), "-frames:v", "1",
            "-vf", f"scale={FRAME_WIDTH}:-2", "-q:v", "4", "-y", str(target),
        ],
        timeout=60,
    )  # fmt: skip
    return target.is_file() and target.stat().st_size > 0


def extract_wav(path: Path, target: Path) -> bool:
    _run(["-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-y", str(target)])
    return target.is_file() and target.stat().st_size > 1000
