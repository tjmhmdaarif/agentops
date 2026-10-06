"""Server-Sent Events stream — the dashboard's single live connection."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/events", tags=["events"])

HEARTBEAT_SECONDS = 15


def _format(event: dict) -> str:
    return (
        f"id: {event['seq']}\n"
        f"event: {event['type']}\n"
        f"data: {json.dumps(event['data'], default=str)}\n\n"
    )


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    bus = request.app.state.runtime.bus
    queue = bus.subscribe(replay_history=True)

    async def generate():
        try:
            yield "event: connected\ndata: {\"ok\": true}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield _format(event)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
