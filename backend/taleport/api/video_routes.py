"""Video analysis: clients, their videos and competitors' videos, results, AI analysis, PDF."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from taleport.analysis.service import today_local
from taleport.api.context import AppContext
from taleport.video.report import build_video_report

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


@router.get("/video/tools")
def tools(request: Request) -> dict[str, Any]:
    return _ctx(request).videos.tools()


@router.get("/video-projects")
def list_projects(request: Request) -> list[dict[str, Any]]:
    return _ctx(request).videos.list_projects()


class NewProject(BaseModel):
    client_name: str = Field(max_length=200)
    notes: str = Field("", max_length=4000)


@router.post("/video-projects")
def create_project(request: Request, body: NewProject) -> dict[str, Any]:
    return _ctx(request).videos.create_project(body.client_name, body.notes)


@router.get("/video-projects/{project_id}")
def get_project(request: Request, project_id: int) -> dict[str, Any]:
    return _ctx(request).videos.get_project(project_id)


class ProjectChanges(BaseModel):
    client_name: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=4000)


@router.patch("/video-projects/{project_id}")
def update_project(request: Request, project_id: int, body: ProjectChanges) -> dict[str, Any]:
    return _ctx(request).videos.update_project(project_id, body.client_name, body.notes)


@router.delete("/video-projects/{project_id}", status_code=204)
def delete_project(request: Request, project_id: int) -> None:
    _ctx(request).videos.delete_project(project_id)


@router.post("/video-projects/{project_id}/videos")
def add_videos(
    request: Request,
    project_id: int,
    files: Annotated[list[UploadFile], File()],
    owner_kind: Annotated[str, Form()] = "client",
    owner_name: Annotated[str, Form()] = "",
    platform: Annotated[str, Form()] = "other",
) -> list[dict[str, Any]]:
    service = _ctx(request).videos
    return [
        service.add_video(
            project_id,
            owner_kind,
            owner_name,
            platform,
            upload.filename or "video.mp4",
            upload.file,
        )
        for upload in files
    ]


class VideoChanges(BaseModel):
    owner_kind: str | None = None
    owner_name: str | None = Field(None, max_length=200)
    platform: str | None = None
    stats: dict[str, Any] | None = None


@router.patch("/videos/{video_id}")
def update_video(request: Request, video_id: int, body: VideoChanges) -> dict[str, Any]:
    return _ctx(request).videos.update_video(video_id, body.model_dump(exclude_unset=True))


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(request: Request, video_id: int) -> None:
    _ctx(request).videos.delete_video(video_id)


@router.post("/videos/{video_id}/retry")
def retry_video(request: Request, video_id: int) -> dict[str, Any]:
    return _ctx(request).videos.retry(video_id)


@router.get("/videos/{video_id}/frames/{index}")
def frame(request: Request, video_id: int, index: int) -> FileResponse:
    return FileResponse(
        _ctx(request).videos.frame_file(video_id, index),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/videos/{video_id}/stats/read")
async def read_stats(
    request: Request,
    video_id: int,
    images: Annotated[list[UploadFile], File()],
    mode: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    service = _ctx(request).videos
    data = [(u.filename or "image.png", await u.read()) for u in images]
    checked = service.check_screenshots(data)
    # The AI call is blocking: run it off the event loop.
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(service.read_stats, video_id, checked, mode)


class PastedAnswer(BaseModel):
    text: str = Field(max_length=300_000)


@router.post("/videos/{video_id}/stats/parse")
def parse_stats(request: Request, video_id: int, body: PastedAnswer) -> dict[str, Any]:
    return _ctx(request).videos.parse_stats(video_id, body.text)


class Analyze(BaseModel):
    mode: str | None = None


@router.post("/video-projects/{project_id}/analyze")
def analyze(request: Request, project_id: int, body: Analyze) -> dict[str, Any]:
    return _ctx(request).videos.analyze(project_id, body.mode)


@router.post("/video-projects/{project_id}/analyze/parse")
def parse_analysis(request: Request, project_id: int, body: PastedAnswer) -> dict[str, Any]:
    return _ctx(request).videos.parse_analysis(project_id, body.text)


@router.post("/video-projects/{project_id}/report")
def report(request: Request, project_id: int) -> dict[str, Any]:
    ctx = _ctx(request)
    project = ctx.videos.get_project(project_id)
    built = build_video_report(project, ctx.settings.get().language, today_local())
    return ctx.reports.save(built)
