"""PDF reports: generate and save, recent files, custom templates, cover logo."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

from taleport.api.context import AppContext
from taleport.ask.scope import Filters, Period
from taleport.core.errors import AppError
from taleport.reports.service import CustomReport

router = APIRouter()

Theme = Literal["light", "dark"]


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


class Daily(BaseModel):
    day: date | None = None
    theme: Theme | None = None


@router.post("/reports/daily")
def daily(request: Request, body: Daily) -> dict[str, Any]:
    reports = _ctx(request).reports
    return reports.save(reports.build_daily(body.day), body.theme)


class Weekly(BaseModel):
    theme: Theme | None = None


@router.post("/reports/weekly")
def weekly(request: Request, body: Weekly) -> dict[str, Any]:
    reports = _ctx(request).reports
    return reports.save(reports.build_weekly(), body.theme)


class Trends(BaseModel):
    period: str = "last_7_days"
    start: date | None = None
    end: date | None = None
    topics: list[int] | None = None
    language: str | None = None
    theme: Theme | None = None


@router.post("/reports/trends")
def trends(request: Request, body: Trends) -> dict[str, Any]:
    try:
        period = Period(preset=body.period, start=body.start, end=body.end)  # type: ignore[arg-type]
        filters = Filters(
            topics=body.topics or None,
            languages=[body.language] if body.language else None,  # type: ignore[list-item]
        )
    except ValidationError as exc:
        raise AppError("validation", fields=["period"]) from exc
    reports = _ctx(request).reports
    return reports.save(reports.build_trends(period, filters), body.theme)


class AskReport(BaseModel):
    plan: dict[str, Any]
    question: str = Field("", max_length=1000)
    theme: Theme | None = None


@router.post("/reports/ask")
def ask(request: Request, body: AskReport) -> dict[str, Any]:
    reports = _ctx(request).reports
    return reports.save(reports.build_ask(body.plan, body.question), body.theme)


@router.post("/reports/custom")
def custom(request: Request, body: CustomReport) -> dict[str, Any]:
    reports = _ctx(request).reports
    return reports.save(reports.build_custom(body), body.theme)


# -- files ---------------------------------------------------------------------------


@router.get("/reports/files")
def files(request: Request) -> list[dict[str, Any]]:
    return _ctx(request).reports.recent_files()


@router.get("/reports/files/{name}")
def download(request: Request, name: str) -> FileResponse:
    """For the browser (dev mode); the desktop window opens files with the system viewer."""
    path = _ctx(request).reports.file_path(name)
    return FileResponse(
        path, media_type="application/pdf", filename=name, content_disposition_type="inline"
    )


class OpenFile(BaseModel):
    name: str = Field(max_length=200)
    folder: bool = False


@router.post("/reports/open", status_code=204)
def open_file(request: Request, body: OpenFile) -> None:
    _ctx(request).reports.open_file(body.name, folder=body.folder)


# -- templates -----------------------------------------------------------------------


class Template(BaseModel):
    name: str = Field(max_length=80)
    params: CustomReport


@router.get("/reports/templates")
def templates(request: Request) -> list[dict[str, Any]]:
    return _ctx(request).reports.templates()


@router.post("/reports/templates")
def create_template(request: Request, body: Template) -> dict[str, Any]:
    return _ctx(request).reports.save_template(body.name, body.params)


@router.put("/reports/templates/{template_id}")
def update_template(request: Request, template_id: int, body: Template) -> dict[str, Any]:
    return _ctx(request).reports.save_template(body.name, body.params, template_id)


@router.delete("/reports/templates/{template_id}", status_code=204)
def delete_template(request: Request, template_id: int) -> None:
    _ctx(request).reports.delete_template(template_id)


@router.post("/reports/templates/{template_id}/run")
def run_template(request: Request, template_id: int) -> dict[str, Any]:
    return _ctx(request).reports.run_template(template_id)


# -- cover logo ----------------------------------------------------------------------


@router.get("/reports/logo")
def logo(request: Request) -> dict[str, Any]:
    return _ctx(request).reports.logo_info()


class Logo(BaseModel):
    file_name: str = Field(max_length=200)
    file_base64: str = Field(max_length=3_000_000)


@router.put("/reports/logo")
def set_logo(request: Request, body: Logo) -> dict[str, Any]:
    return _ctx(request).reports.set_logo(body.file_name, body.file_base64)


@router.delete("/reports/logo", status_code=204)
def delete_logo(request: Request) -> None:
    _ctx(request).reports.delete_logo()
