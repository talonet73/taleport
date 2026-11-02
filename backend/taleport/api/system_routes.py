"""Error log, backup and import, update check, exported files, data clean-up."""

from __future__ import annotations

import platform
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taleport.api.context import AppContext
from taleport.core import exports
from taleport.core.errors import AppError
from taleport.core.logs import tail
from taleport.core.maintenance import cleanup
from taleport.core.paths import data_dir, logs_dir

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


# -- error log -----------------------------------------------------------------------


@router.get("/logs")
def logs(
    request: Request, limit: int = 200, level: Literal["info", "warning", "error"] | None = None
) -> dict[str, Any]:
    store = _ctx(request).logs
    return {"counts": store.counts(), "rows": store.recent(min(max(limit, 1), 1000), level)}


@router.delete("/logs", status_code=204)
def clear_logs(request: Request) -> None:
    _ctx(request).logs.clear()


@router.post("/logs/export")
def export_logs(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    header = {
        "version": ctx.version,
        "windows": platform.platform(),
        "python": platform.python_version(),
        "data": str(data_dir()),
    }
    text = ctx.logs.export_text(header, tail(logs_dir() / "taleport.log"))
    return exports.save(f"TALeport_registro_{exports.stamp()}.txt", text.encode("utf-8"))


# -- backup --------------------------------------------------------------------------


@router.post("/backup/export")
def export_backup(request: Request) -> dict[str, Any]:
    return _ctx(request).backup.export_all()


@router.post("/topics/{topic_id}/export")
def export_topic(request: Request, topic_id: int) -> dict[str, Any]:
    return _ctx(request).backup.export_topic(topic_id)


class ImportFile(BaseModel):
    text: str = Field(max_length=3_000_000)
    settings: bool = True


@router.post("/backup/preview")
def preview_import(request: Request, body: ImportFile) -> dict[str, Any]:
    return _ctx(request).backup.preview(body.text)


@router.post("/backup/import")
def import_backup(request: Request, body: ImportFile) -> dict[str, Any]:
    ctx = _ctx(request)
    result = ctx.backup.import_file(body.text, settings=body.settings)
    if result["settings"]:
        ctx.bus.publish("settings.changed", ctx.settings.get().model_dump())
    return result


# -- updates -------------------------------------------------------------------------


@router.get("/updates")
def update_status(request: Request) -> dict[str, Any]:
    return _ctx(request).updates.status()


@router.post("/updates/check")
def check_updates(request: Request) -> dict[str, Any]:
    return _ctx(request).updates.check()


@router.post("/updates/open", status_code=204)
def open_release(request: Request) -> None:
    """Opens the release page found by the last check (never a URL sent by the page)."""
    ctx = _ctx(request)
    latest = ctx.updates.status().get("latest")
    if not latest:
        raise AppError("updates.not_checked")
    ctx.open_url(latest["url"])


# -- exported files ------------------------------------------------------------------


@router.get("/exports")
def exported_files(request: Request, suffix: Literal[".pdf", ".json", ".txt"] | None = None):
    return exports.recent(suffix)


class OpenExport(BaseModel):
    name: str = Field(max_length=200)
    folder: bool = False


@router.post("/exports/open", status_code=204)
def open_export(body: OpenExport) -> None:
    exports.open_file(body.name, folder=body.folder)


# -- clean-up ------------------------------------------------------------------------


@router.post("/maintenance/cleanup")
def run_cleanup(request: Request) -> dict[str, Any]:
    ctx = _ctx(request)
    return cleanup(ctx.db, ctx.settings.get().retention_months)
