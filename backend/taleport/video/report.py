"""The PDF for the client: comparison with the competitors, strengths, weaknesses, actions.

Built from the saved project (measures, results and the AI analysis already validated):
creating the PDF never calls an AI.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from taleport.reports.builder import _number, format_day, translator
from taleport.reports.model import Report


def _pct(value: float | None, language: str) -> str:
    return "–" if value is None else f"{_number(round(value * 100, 1), language)}%"


def _sec(value: float | None, language: str) -> str:
    return "–" if value is None else f"{_number(round(value, 1), language)} s"


def build_video_report(project: dict[str, Any], language: str, today: date) -> Report:
    t = translator(language)
    client = project["client_name"]
    report = Report(
        kind="video",
        title=t("title.video", client=client),
        period=format_day(today, language),
        language=language,
    )
    videos = [v for v in project["videos"] if v["status"] == "ready"]
    by_id = {v["id"]: v for v in videos}
    analysis = project.get("analysis") or {}

    def label(video_id: int) -> str:
        video = by_id.get(video_id)
        return video["file_name"] if video else f"#{video_id}"

    groups = project["groups"]
    client_group = next((g for g in groups if g["kind"] == "client"), None)
    competitors = [g for g in groups if g["kind"] == "competitor"]

    summary = report.section(t("video.section.summary"))
    stats = [
        (
            t("video.stat.client_videos"),
            _number(client_group["summary"]["videos"] if client_group else 0, language),
        ),
        (t("video.stat.competitors"), _number(len(competitors), language)),
    ]
    if client_group and client_group["summary"].get("watched_ratio") is not None:
        stats.append(
            (t("video.stat.watched"), _pct(client_group["summary"]["watched_ratio"], language))
        )
    summary.add("stats", items=stats)
    if analysis.get("summary"):
        summary.add("text", text=analysis["summary"])
    else:
        summary.add("note", text=t("video.no_analysis"))

    compare = report.section(t("video.section.compare"))
    header = [
        t("video.col.profile"), t("video.col.videos"), t("video.col.length"),
        t("video.col.cuts"), t("video.col.first_words"), t("video.col.watched"),
        t("video.col.interactions"),
    ]  # fmt: skip
    rows = []
    for group in groups:
        s = group["summary"]
        rows.append(
            [
                client if group["kind"] == "client" else group["name"],
                _number(s["videos"], language),
                _sec(s["duration"], language),
                "–" if s["cuts_per_minute"] is None else _number(s["cuts_per_minute"], language),
                _sec(s["first_word_at"], language),
                _pct(s["watched_ratio"], language),
                _pct(s["interaction_rate"], language),
            ]
        )
    compare.add(
        "table",
        header=header,
        rows=rows,
        align=["left", "right", "right", "right", "right", "right", "right"],
        widths=[0.28, 0.1, 0.12, 0.12, 0.13, 0.12, 0.13],
    )
    compare.add("note", text=t("video.compare_note"))

    for key in ("strengths", "weaknesses"):
        points = analysis.get(key) or []
        if not points:
            continue
        section = report.section(t(f"video.section.{key}"))
        for point in points:
            examples = ", ".join(label(i) for i in point.get("videos", []))
            section.add(
                "theme",
                title=point["title"],
                meta=t("video.examples", videos=examples) if examples else "",
                summary=point.get("detail", ""),
            )

    if analysis.get("competitors"):
        section = report.section(t("video.section.competitors"))
        for item in analysis["competitors"]:
            text = item.get("what_works", "")
            if item.get("weak_spots"):
                text += f" {t('video.weak_spots')}: {item['weak_spots']}"
            section.add(
                "theme",
                title=item["name"],
                meta="",
                summary=text.strip(),
                angle=item.get("to_borrow", ""),
                angle_label=t("video.to_borrow"),
            )

    if analysis.get("recommendations"):
        section = report.section(t("video.section.recommendations"))
        section.add(
            "table",
            header=[t("video.col.action"), t("video.col.why"), t("video.col.priority")],
            rows=[
                [r["action"], r.get("why", ""), t(f"video.priority.{r.get('priority', 'medium')}")]
                for r in analysis["recommendations"]
            ],
            widths=[0.38, 0.47, 0.15],
        )

    verdicts = [v for v in analysis.get("videos") or [] if v["id"] in by_id]
    if verdicts:
        section = report.section(t("video.section.videos"))
        for verdict in verdicts:
            video = by_id[verdict["id"]]
            d = video["derived"]
            meta = [_sec(video["features"].get("duration"), language)]
            if video["stats"].get("views") is not None:
                meta.append(t("video.views", n=_number(video["stats"]["views"], language)))
            if d.get("watched_ratio") is not None:
                meta.append(t("video.watched", pct=_pct(d["watched_ratio"], language)))
            lines = [verdict.get("verdict", "")]
            if verdict.get("hook"):
                lines.append(f"{t('video.hook')}: {verdict['hook']}")
            if verdict.get("drop_off"):
                lines.append(f"{t('video.drop_off')}: {verdict['drop_off']}")
            section.add(
                "theme",
                title=video["file_name"],
                meta=" · ".join(meta),
                summary=" ".join(x for x in lines if x),
                angle=verdict.get("fix", ""),
                angle_label=t("video.fix"),
            )

    if analysis.get("ideas"):
        section = report.section(t("video.section.ideas"))
        for idea in analysis["ideas"]:
            section.add("text", text=f"• {idea}")

    method = report.section(t("video.section.method"))
    method.add("note", text=t("video.method"))
    return report
