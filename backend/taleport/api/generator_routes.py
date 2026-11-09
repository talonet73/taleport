"""Post generator, long content and drafts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taleport.api.context import AppContext
from taleport.generator.extract import extract_text, limit_content

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


class ThemeGeneration(BaseModel):
    theme_id: int
    platforms: list[str]
    languages: list[str]
    variants: int = 1
    tone: str | None = Field(None, max_length=300)
    mode: str | None = None
    voice_id: int | None = None


class ThemeGenerationParse(ThemeGeneration):
    text: str = Field(max_length=200_000)


@router.post("/generator/theme")
def generate_from_theme(request: Request, body: ThemeGeneration) -> dict[str, Any]:
    return _ctx(request).generator.generate_from_theme(
        body.theme_id, body.platforms, body.languages, body.variants, body.tone, body.mode,
        body.voice_id,
    )  # fmt: skip


@router.post("/generator/theme/parse")
def parse_from_theme(request: Request, body: ThemeGenerationParse) -> dict[str, Any]:
    return _ctx(request).generator.parse_from_theme(
        body.theme_id, body.platforms, body.languages, body.text, body.voice_id
    )


class LongGeneration(BaseModel):
    content: str = Field(max_length=400_000)
    title: str = Field("", max_length=200)
    count: int = 3
    platforms: list[str]
    language: str
    topic_id: int | None = None
    mode: str | None = None
    voice_id: int | None = None


class LongGenerationParse(LongGeneration):
    text: str = Field(max_length=300_000)


@router.post("/generator/long")
def generate_long(request: Request, body: LongGeneration) -> dict[str, Any]:
    return _ctx(request).generator.generate_long(
        body.content,
        body.title,
        body.count,
        body.platforms,
        body.language,
        body.topic_id,
        body.mode,
        body.voice_id,
    )


@router.post("/generator/long/parse")
def parse_long(request: Request, body: LongGenerationParse) -> dict[str, Any]:
    return _ctx(request).generator.parse_long(
        body.content, body.title, body.platforms, body.language, body.topic_id, body.text,
        body.voice_id,
    )  # fmt: skip


class FileUpload(BaseModel):
    file_name: str = Field(max_length=300)
    file_base64: str = Field(max_length=21_000_000)  # ~15 MB of data


@router.post("/content/extract")
def extract(body: FileUpload) -> dict[str, Any]:
    text, truncated = limit_content(extract_text(body.file_name, body.file_base64))
    return {"text": text, "truncated": truncated, "characters": len(text)}


@router.get("/drafts")
def list_drafts(
    request: Request, limit: int = 50, batch_id: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    return _ctx(request).generator.list_drafts(min(max(limit, 1), 500), batch_id, status)


@router.get("/drafts/{draft_id}")
def get_draft(request: Request, draft_id: int) -> dict[str, Any]:
    return _ctx(request).generator.get(draft_id)


class DraftText(BaseModel):
    text: str = Field(max_length=50_000)


@router.patch("/drafts/{draft_id}")
def update_draft(request: Request, draft_id: int, body: DraftText) -> dict[str, Any]:
    return _ctx(request).generator.update_text(draft_id, body.text)


class Regenerate(BaseModel):
    mode: str | None = None


@router.post("/drafts/{draft_id}/regenerate")
def regenerate(request: Request, draft_id: int, body: Regenerate) -> dict[str, Any]:
    return _ctx(request).generator.regenerate(draft_id, body.mode)


@router.post("/drafts/{draft_id}/regenerate/parse")
def regenerate_parse(request: Request, draft_id: int, body: DraftText) -> dict[str, Any]:
    return _ctx(request).generator.parse_regenerate(draft_id, body.text)


class Schedule(BaseModel):
    scheduled_at: str | None = None


@router.put("/drafts/{draft_id}/schedule")
def schedule(request: Request, draft_id: int, body: Schedule) -> dict[str, Any]:
    return _ctx(request).generator.schedule(draft_id, body.scheduled_at)


class Publish(BaseModel):
    url: str | None = Field(None, max_length=1000)
    published_at: str | None = None


@router.post("/drafts/{draft_id}/publish")
def publish(request: Request, draft_id: int, body: Publish) -> dict[str, Any]:
    ctx = _ctx(request)
    draft = ctx.generator.publish(draft_id, body.url, body.published_at)
    ctx.bus.publish("drafts.changed", {"id": draft_id})
    return draft


@router.delete("/drafts/{draft_id}/publish")
def unpublish(request: Request, draft_id: int) -> dict[str, Any]:
    ctx = _ctx(request)
    draft = ctx.generator.unpublish(draft_id)
    ctx.bus.publish("drafts.changed", {"id": draft_id})
    return draft


@router.delete("/drafts/{draft_id}", status_code=204)
def delete_draft(request: Request, draft_id: int) -> None:
    _ctx(request).generator.delete(draft_id)


class ReferenceDocument(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    text: str = Field(max_length=400_000)


class ReferenceGeneration(BaseModel):
    documents: list[ReferenceDocument] = Field(min_length=1, max_length=5)
    platforms: list[str]
    languages: list[str]
    count: int = 1
    title: str = Field("", max_length=200)
    voice: str = "reference"  # 'reference', 'profile' or 'topic'
    voice_id: int | None = None
    topic_id: int | None = None
    save_voice: str | None = Field(None, max_length=80)  # set: save the documents' voice
    mode: str | None = None

    def args(self) -> dict[str, Any]:
        return {
            "documents": [d.model_dump() for d in self.documents],
            "platforms": self.platforms, "languages": self.languages, "count": self.count,
            "title": self.title, "voice": self.voice, "voice_id": self.voice_id,
            "topic_id": self.topic_id, "save_voice": self.save_voice,
        }  # fmt: skip


class ReferenceGenerationParse(ReferenceGeneration):
    text: str = Field(max_length=300_000)


@router.post("/generator/reference")
def generate_from_reference(request: Request, body: ReferenceGeneration) -> dict[str, Any]:
    return _ctx(request).generator.generate_from_reference(**body.args(), mode=body.mode)


@router.post("/generator/reference/parse")
def parse_reference(request: Request, body: ReferenceGenerationParse) -> dict[str, Any]:
    return _ctx(request).generator.parse_reference(**body.args(), text=body.text)
