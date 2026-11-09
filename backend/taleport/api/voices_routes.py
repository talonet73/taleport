"""Tone-of-voice profiles: list, create (by hand or from documents), edit, delete."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from taleport.api.context import AppContext
from taleport.voices.schemas import VoiceProfileIn

router = APIRouter()


def _ctx(request: Request) -> AppContext:
    return request.app.state.ctx


@router.get("/voices")
def list_voices(request: Request) -> list[dict[str, Any]]:
    return _ctx(request).voices.list()


@router.post("/voices")
def create_voice(request: Request, body: VoiceProfileIn) -> dict[str, Any]:
    return _ctx(request).voices.create(body)


@router.put("/voices/{profile_id}")
def update_voice(request: Request, profile_id: int, body: VoiceProfileIn) -> dict[str, Any]:
    return _ctx(request).voices.update(profile_id, body)


@router.delete("/voices/{profile_id}", status_code=204)
def delete_voice(request: Request, profile_id: int) -> None:
    _ctx(request).voices.delete(profile_id)


class Document(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    text: str = Field(max_length=400_000)


class VoiceAnalysisRequest(BaseModel):
    documents: list[Document] = Field(min_length=1, max_length=5)
    mode: str | None = None


class VoiceAnalysisParse(BaseModel):
    names: list[str] = Field(default_factory=list, max_length=5)
    text: str = Field(max_length=200_000)


@router.post("/voices/analyze")
def analyze_voice(request: Request, body: VoiceAnalysisRequest) -> dict[str, Any]:
    documents = [d.model_dump() for d in body.documents]
    return _ctx(request).voices.analyze(documents, body.mode)


@router.post("/voices/analyze/parse")
def parse_voice(request: Request, body: VoiceAnalysisParse) -> dict[str, Any]:
    return _ctx(request).voices.parse_analysis(body.names, body.text)
