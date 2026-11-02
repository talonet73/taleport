"""Server-Sent Events stream: scan progress, notifications, settings changes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from taleport.api.context import AppContext

router = APIRouter()

_KEEPALIVE_SECONDS = 15


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    ctx: AppContext = request.app.state.ctx

    async def stream() -> AsyncIterator[str]:
        queue = ctx.bus.subscribe()
        try:
            yield "event: ready\ndata: {}\n\n"
            while not await request.is_disconnected():
                try:
                    event, data = await asyncio.wait_for(queue.get(), _KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        finally:
            ctx.bus.unsubscribe(queue)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
    )
