"""WebSocket endpoint that streams orchestrator events to clients.

Protocol (one JSON message per text frame):

  Server → client:
    {"type": "snapshot", "run": <RunDetail JSON>}
      Sent once, immediately after the WS handshake. Includes all persisted
      steps + artifacts so a client connecting mid-run has a full picture.

    {"type": "event", "data": {"type": "<event_type>", "run_id": "...",
                               "payload": {...}, "ts": "<iso>"}}
      One per orchestrator event.

    {"type": "pong"}  in response to a client ping.

    No "end" frame — the server closes the WS cleanly when the run reaches a
    terminal state.

  Client → server:
    {"type": "ping"}  — keepalive ping; server replies with pong.

Close codes:
  1000  normal closure (run finished or already terminal).
  1008  policy violation — unknown run_id.
  1011  internal error.

Authentication: not enforced in this phase. Add a token check in `_authorize`
when the project gets deployed.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import Run, RunStatus
from app.orchestrator.events import Event, EventType, get_event_bus
from app.orchestrator.repository import RunRepository
from app.schemas.api import RunDetail

logger = get_logger(__name__)

router = APIRouter(tags=["ws"])

_TERMINAL_STATUSES: set[RunStatus] = {
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
}

_TERMINAL_EVENT_TYPES: set[EventType] = {
    EventType.RUN_COMPLETED,
    EventType.RUN_FAILED,
    EventType.RUN_CANCELLED,
}


def _snapshot_payload(run: Run) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "run": RunDetail.from_model(run).model_dump(mode="json"),
    }


def _event_payload(event: Event) -> dict[str, Any]:
    return {"type": "event", "data": event.to_json()}


async def _send_json(ws: WebSocket, payload: dict[str, Any]) -> None:
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_json(payload)


async def _drain_client_messages(ws: WebSocket, stop: asyncio.Event) -> None:
    """Consume client messages (pings, future commands) until disconnect.

    Runs as a sibling task to the event-pump so we react to disconnects
    immediately instead of only when the next event arrives.
    """
    try:
        while not stop.is_set():
            msg = await ws.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await _send_json(ws, {"type": "pong"})
    except WebSocketDisconnect:
        stop.set()
    except Exception:
        logger.exception("ws_client_recv_error")
        stop.set()


@router.websocket("/ws/runs/{run_id}")
async def stream_run(
    ws: WebSocket, run_id: str, token: str | None = Query(default=None)
) -> None:
    settings = get_settings()
    if settings.auth_required:
        import hmac

        expected = settings.api_key.get_secret_value()
        if not token or not hmac.compare_digest(token, expected):
            await ws.close(code=1008, reason="unauthorized")
            return

    bus = get_event_bus()
    repo = RunRepository()

    await ws.accept()
    log = logger.bind(run_id=run_id)

    # Subscribe BEFORE the snapshot so we don't miss events that fire during
    # snapshot construction. Clients should treat events whose contents
    # overlap the snapshot's steps/artifacts as idempotent.
    async with bus.subscribe(run_id) as event_q:
        run = await repo.get_run(run_id)
        if run is None:
            await ws.close(code=1008, reason=f"Unknown run '{run_id}'")
            log.info("ws_unknown_run_closed")
            return

        await _send_json(ws, _snapshot_payload(run))
        log.info("ws_snapshot_sent", status=run.status.value, subscriber_count=bus.subscriber_count(run_id))

        # If already terminal, no events will arrive — close cleanly.
        if run.status in _TERMINAL_STATUSES:
            await ws.close(code=1000, reason="run already terminal")
            return

        stop = asyncio.Event()
        recv_task = asyncio.create_task(
            _drain_client_messages(ws, stop), name=f"ws-recv:{run_id}"
        )

        try:
            while not stop.is_set():
                get_task = asyncio.create_task(event_q.get())
                stop_task = asyncio.create_task(stop.wait())
                done, pending = await asyncio.wait(
                    {get_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()

                if stop_task in done:
                    break

                event: Event = get_task.result()
                await _send_json(ws, _event_payload(event))
                if event.type in _TERMINAL_EVENT_TYPES:
                    break
        except WebSocketDisconnect:
            log.info("ws_client_disconnected")
        except Exception:
            log.exception("ws_stream_error")
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.close(code=1011, reason="internal error")
            return
        finally:
            stop.set()
            recv_task.cancel()
            # Suppress cancellation noise — we kicked off the cancel ourselves.
            try:
                await recv_task
            except (asyncio.CancelledError, WebSocketDisconnect):
                pass

        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close(code=1000, reason="run finished")
        log.info("ws_closed")
