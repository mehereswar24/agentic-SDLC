"""In-process event bus for orchestrator → WebSocket streaming.

Per-run topic with multiple subscribers (each gets their own `asyncio.Queue`).
Events are typed enums + JSON-safe dicts so the WebSocket layer can serialize
them directly.

Intentionally in-process: this is a single-server design. A future multi-node
deployment would swap this for Redis pub/sub or NATS without changing the
producer/consumer API.
"""
from __future__ import annotations

import asyncio
import enum
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, enum.Enum):
    RUN_STARTED = "run.started"
    STEP_STARTED = "step.started"
    STEP_PROGRESS = "step.progress"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    ARTIFACT_CREATED = "artifact.created"
    RUN_AWAITING_APPROVAL = "run.awaiting_approval"
    RUN_RESUMED = "run.resumed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"


@dataclass(slots=True)
class Event:
    type: EventType
    run_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "run_id": self.run_id,
            "payload": self.payload,
            "ts": self.ts.isoformat(),
        }


class EventBus:
    """Per-run fanout. Subscribers receive every event published after they subscribe."""

    def __init__(self, *, queue_max_size: int = 1024) -> None:
        self._subs: dict[str, set[asyncio.Queue[Event]]] = {}
        self._lock = asyncio.Lock()
        self._queue_max_size = queue_max_size

    async def publish(self, event: Event) -> None:
        async with self._lock:
            queues = list(self._subs.get(event.run_id, ()))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow subscriber — drop event rather than block the producer.
                logger.warning(
                    "event_dropped_slow_subscriber",
                    run_id=event.run_id,
                    event_type=event.type.value,
                )

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[asyncio.Queue[Event]]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_max_size)
        async with self._lock:
            self._subs.setdefault(run_id, set()).add(q)
        try:
            yield q
        finally:
            async with self._lock:
                subs = self._subs.get(run_id)
                if subs is not None:
                    subs.discard(q)
                    if not subs:
                        del self._subs[run_id]

    def subscriber_count(self, run_id: str) -> int:
        return len(self._subs.get(run_id, ()))


# Process-wide singleton.
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def _reset_event_bus() -> None:
    """Test hook."""
    global _bus
    _bus = None
