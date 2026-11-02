"""PDF reports: build, render, save in the exports folder; custom report templates; cover logo.

Files are written to `%LOCALAPPDATA%\\TALeport\\exports\\` and opened with the default PDF
viewer: the app window never has to handle a download.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taleport.analysis.service import today_local
from taleport.ask.scope import Filters, Period
from taleport.ask.service import InsightsService
from taleport.core import exports
from taleport.core.errors import AppError
from taleport.core.i18n import tr
from taleport.core.paths import branding_dir
from taleport.core.settings import SettingsStore
from taleport.db.database import Database
from taleport.reports import pdf
from taleport.reports.builder import SECTIONS, ReportBuilder
from taleport.reports.model import Report
from taleport.results.service import ResultsService

ReportTheme = Literal["light", "dark"]
Section = Literal[
    "summary", "themes", "keywords", "changes", "trend", "compare", "posts", "results"
]
LOGO_TYPES = {".png", ".jpg", ".jpeg", ".svg"}
MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_TEMPLATES = 50

assert set(SECTIONS) == set(Section.__args__)  # type: ignore[attr-defined]


class CustomReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field("", max_length=120)
    period: Period = Field(default_factory=lambda: Period(preset="last_7_days"))
    filters: Filters = Field(default_factory=Filters)
    sections: list[Section] = Field(min_length=1)
    theme: ReportTheme | None = None


class ReportService:
    def __init__(
        self,
        db: Database,
        settings: SettingsStore,
        insights: InsightsService,
        results: ResultsService,
    ) -> None:
        self._db = db
        self._settings = settings
        self._insights = insights
        self._results = results

    # -- building ------------------------------------------------------------------------

    def _build(self, make: Any) -> Report:
        language = self._settings.get().language
        with self._db.connect() as conn:
            return make(ReportBuilder(conn, language, self._results))

    def build_daily(self, day: date | None = None) -> Report:
        return self._build(lambda b: b.daily(day or today_local()))

    def build_weekly(self) -> Report:
        return self._build(lambda b: b.weekly(today_local()))

    def build_trends(self, period: Period, filters: Filters | None) -> Report:
        return self._build(lambda b: b.trends(period, filters))

    def build_custom(self, params: CustomReport) -> Report:
        self._check_topics(params.filters)
        return self._build(
            lambda b: b.custom(params.title, params.period, params.filters, list(params.sections))
        )

    def build_ask(self, plan: dict[str, Any], question: str = "") -> Report:
        """Re-runs the validated plan (never trusts result data sent by the page)."""
        result = self._insights.run_plan_json(plan)
        return self._build(lambda b: b.ask(question, result))

    def _check_topics(self, filters: Filters) -> None:
        if filters.topics:
            with self._db.connect() as conn:
                known = {r[0] for r in conn.execute("SELECT id FROM topics")}
            if any(t not in known for t in filters.topics):
                raise AppError("ask.unknown_topic")

    # -- rendering and files -------------------------------------------------------------

    def _logo(self) -> Path | None:
        for path in sorted(branding_dir().glob("cover_logo.*")):
            if path.suffix.lower() in LOGO_TYPES:
                return path
        return None

    def render(self, report: Report, theme: ReportTheme | None = None) -> bytes:
        settings = self._settings.get()
        return pdf.render(
            report,
            theme=theme or settings.report_theme,
            cover_name=settings.report_cover_name,
            logo=self._logo(),
        )

    def save(self, report: Report, theme: ReportTheme | None = None) -> dict[str, Any]:
        label = tr(report.language, f"report.file.{report.kind}")
        name = f"TALeport_{label}_{exports.stamp()}.pdf"
        return {**exports.save(name, self.render(report, theme)), "title": report.title}

    def recent_files(self) -> list[dict[str, Any]]:
        return exports.recent(".pdf")

    def file_path(self, name: str) -> Path:
        return exports.file_path(name)

    def open_file(self, name: str, *, folder: bool = False) -> None:
        exports.open_file(name, folder=folder)

    # -- templates -----------------------------------------------------------------------

    def templates(self) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM report_templates ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [{**dict(r), "params": json.loads(r["params"])} for r in rows]

    def save_template(
        self, name: str, params: CustomReport, template_id: int | None = None
    ) -> dict:
        name = name.strip()
        if not name:
            raise AppError("reports.name_required")
        self._check_topics(params.filters)
        data = params.model_dump_json()
        with self._db.connect() as conn:
            if template_id is None:
                count = conn.execute("SELECT COUNT(*) FROM report_templates").fetchone()[0]
                if count >= MAX_TEMPLATES:
                    raise AppError("reports.too_many_templates", max=MAX_TEMPLATES)
                cursor = conn.execute(
                    "INSERT INTO report_templates (name, params) VALUES (?, ?)", (name, data)
                )
                template_id = int(cursor.lastrowid or 0)
            else:
                cursor = conn.execute(
                    "UPDATE report_templates SET name = ?, params = ? WHERE id = ?",
                    (name, data, template_id),
                )
                if not cursor.rowcount:
                    raise AppError("reports.template_not_found", status=404)
        return self.template(template_id)

    def template(self, template_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM report_templates WHERE id = ?", (template_id,)
            ).fetchone()
        if row is None:
            raise AppError("reports.template_not_found", status=404)
        return {**dict(row), "params": json.loads(row["params"])}

    def delete_template(self, template_id: int) -> None:
        with self._db.connect() as conn:
            conn.execute("DELETE FROM report_templates WHERE id = ?", (template_id,))

    def run_template(self, template_id: int) -> dict[str, Any]:
        """Regenerate a saved custom report with fresh data (relative periods move on)."""
        stored = self.template(template_id)
        try:
            params = CustomReport.model_validate(stored["params"])
        except ValidationError as exc:
            raise AppError("reports.template_invalid") from exc
        if not params.title:
            params = params.model_copy(update={"title": stored["name"]})
        saved = self.save(self.build_custom(params), params.theme)
        with self._db.connect() as conn:
            conn.execute(
                "UPDATE report_templates SET last_run_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                "WHERE id = ?",
                (template_id,),
            )
        return saved

    # -- cover logo ----------------------------------------------------------------------

    def logo_info(self) -> dict[str, Any]:
        logo = self._logo()
        return {"custom": logo is not None, "name": logo.name if logo else None}

    def set_logo(self, file_name: str, data_base64: str) -> dict[str, Any]:
        suffix = Path(file_name).suffix.lower()
        if suffix not in LOGO_TYPES:
            raise AppError("reports.logo_type")
        try:
            data = base64.b64decode(data_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise AppError("reports.logo_type") from exc
        if not data or len(data) > MAX_LOGO_BYTES:
            raise AppError("reports.logo_size", max_mb=MAX_LOGO_BYTES // (1024 * 1024))
        if not _readable_image(data, suffix):
            raise AppError("reports.logo_type")
        self.delete_logo()
        (branding_dir() / f"cover_logo{suffix}").write_bytes(data)
        return self.logo_info()

    def delete_logo(self) -> None:
        for path in branding_dir().glob("cover_logo.*"):
            path.unlink()


def _readable_image(data: bytes, suffix: str) -> bool:
    import io

    try:
        if suffix == ".svg":
            from svglib.svglib import svg2rlg

            return svg2rlg(io.BytesIO(data)) is not None
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        return True
    except Exception:  # any decoding error means "not a usable logo"
        return False
