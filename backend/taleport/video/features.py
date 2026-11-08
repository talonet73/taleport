"""Plain, explainable numbers about a video and its results. No AI involved.

`measure` turns the raw FFmpeg / transcription output into the features stored with the
video; `derive` adds the result ratios (share of the video watched, interaction rate);
`summarize` averages them per owner (the client, each competitor) for the comparison.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from taleport.video.media import AudioLevels, Probe
from taleport.video.transcribe import Transcript

HOOK_SECONDS = 3.0


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def measure(
    probe: Probe, cuts: list[float], audio: AudioLevels | None, transcript: Transcript | None
) -> dict[str, Any]:
    duration = max(probe.duration, 0.01)
    shots = [0.0, *cuts, duration]
    shot_lengths = [b - a for a, b in zip(shots, shots[1:], strict=False) if b > a]
    features: dict[str, Any] = {
        "duration": _round(duration),
        "width": probe.width,
        "height": probe.height,
        "orientation": probe.orientation,
        "has_audio": probe.has_audio,
        "cuts": cuts,
        "cut_count": len(cuts),
        "cuts_per_minute": _round(len(cuts) / duration * 60),
        "avg_shot_seconds": _round(mean(shot_lengths)) if shot_lengths else None,
        "first_cut_at": cuts[0] if cuts else None,
        "cuts_in_hook": sum(1 for c in cuts if c <= HOOK_SECONDS),
    }
    if audio is not None and probe.has_audio:
        silent = sum(end - start for start, end in audio.silences)
        features.update(
            silences=audio.silences,
            silence_ratio=_round(silent / duration, 2),
            longest_silence=_round(max((e - s for s, e in audio.silences), default=0.0)),
            mean_volume_db=audio.mean_volume,
            max_volume_db=audio.max_volume,
        )
    if transcript is not None:
        segments = transcript.segments
        words = sum(len(s.text.split()) for s in segments)
        speaking = sum(s.end - s.start for s in segments)
        hook = " ".join(s.text for s in segments if s.start < HOOK_SECONDS).strip()
        features.update(
            speech_language=transcript.language,
            word_count=words,
            first_word_at=segments[0].start if segments else None,
            hook_text=hook[:300],
            words_per_minute=round(words / speaking * 60) if speaking > 1 else None,
            speech_ratio=_round(speaking / duration, 2),
        )
    return features


def derive(features: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    """Ratios from the results the user typed or read from screenshots."""
    out: dict[str, Any] = {}
    duration = features.get("duration") or stats.get("duration")
    views = stats.get("views")
    avg_watch = stats.get("avg_watch_seconds")
    if avg_watch and duration:
        out["watched_ratio"] = round(min(avg_watch / duration, 1.5), 2)
    interactions = sum(stats.get(k) or 0 for k in ("likes", "comments", "shares", "saves"))
    if views:
        out["interactions"] = interactions
        out["interaction_rate"] = round(interactions / views, 4)
        if stats.get("shares") is not None:
            out["share_rate"] = round((stats.get("shares") or 0) / views, 4)
    retention = sorted(stats.get("retention") or [], key=lambda p: p["second"])
    if len(retention) >= 2:
        # The steepest fall between two consecutive points: where people skip.
        worst = max(
            zip(retention, retention[1:], strict=False),
            key=lambda pair: (
                (pair[0]["percent"] - pair[1]["percent"])
                / max(pair[1]["second"] - pair[0]["second"], 0.5)
            ),
        )
        out["biggest_drop"] = {
            "from_second": worst[0]["second"],
            "to_second": worst[1]["second"],
            "lost_percent": round(worst[0]["percent"] - worst[1]["percent"], 1),
        }
        at_3 = [p["percent"] for p in retention if p["second"] <= HOOK_SECONDS]
        if at_3:
            out["kept_after_hook"] = at_3[-1]
    return out


SUMMARY_KEYS = (
    "duration",
    "cuts_per_minute",
    "first_cut_at",
    "first_word_at",
    "words_per_minute",
    "silence_ratio",
)
RESULT_KEYS = ("views", "watched_ratio", "interaction_rate", "share_rate")


def summarize(videos: list[dict[str, Any]]) -> dict[str, Any]:
    """Medians per owner (medians resist one viral outlier better than averages)."""
    summary: dict[str, Any] = {"videos": len(videos)}
    for key in SUMMARY_KEYS:
        values = [v["features"].get(key) for v in videos if v["features"].get(key) is not None]
        summary[key] = _round(median(values), 2) if values else None
    for key in RESULT_KEYS:
        values = [
            (v["stats"].get(key) if key == "views" else v["derived"].get(key)) for v in videos
        ]
        values = [x for x in values if x is not None]
        summary[key] = round(median(values), 4) if values else None
    summary["vertical_share"] = (
        round(
            sum(1 for v in videos if v["features"].get("orientation") == "vertical") / len(videos),
            2,
        )
        if videos
        else None
    )
    return summary
