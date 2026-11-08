"""Speech-to-text on the user's PC with faster-whisper (open source, MIT).

The model is downloaded once, the first time a video is transcribed, into
`%LOCALAPPDATA%\\TALeport\\models\\`; after that transcription works offline. When the
package or the model is not available the analysis goes on without the transcript.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from taleport.core.paths import data_dir

log = logging.getLogger(__name__)

MODEL_SIZE = "base"  # multilingual, ~145 MB, good enough for hooks and speaking pace
MODEL_DOWNLOAD_MB = 145

_lock = threading.Lock()
_model = None


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    language: str | None
    segments: list[Segment]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()


def models_dir() -> Path:
    path = data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def package_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def model_downloaded() -> bool:
    return any(models_dir().glob(f"models--Systran--faster-whisper-{MODEL_SIZE}/snapshots/*"))


def _load():
    global _model
    if _model is None:
        # The packaged app has no console: progress bars would write to a missing stderr.
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 (process-wide)
        from faster_whisper import WhisperModel

        _model = WhisperModel(
            MODEL_SIZE, device="cpu", compute_type="int8", download_root=str(models_dir())
        )
    return _model


def transcribe(wav: Path) -> Transcript:
    """Raises on any failure: the caller records it and continues without speech data."""
    with _lock:  # one transcription at a time: the model is big and CPU-bound
        model = _load()
        segments, info = model.transcribe(str(wav), beam_size=1, vad_filter=False)
        found = [
            Segment(round(s.start, 2), round(s.end, 2), s.text.strip())
            for s in segments
            if s.text.strip()
        ]
    return Transcript(language=getattr(info, "language", None), segments=found)
