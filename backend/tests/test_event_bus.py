from __future__ import annotations

import asyncio

import pytest

from app.orchestrator.events import Event, EventBus, EventType


async def test_subscriber_receives_events() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def consumer() -> None:
        async with bus.subscribe("r1") as q:
            for _ in range(2):
                received.append(await q.get())

    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)  # let the subscriber register
    await bus.publish(Event(EventType.RUN_STARTED, "r1", {"k": 1}))
    await bus.publish(Event(EventType.RUN_COMPLETED, "r1", {"k": 2}))
    await task

    assert [e.type for e in received] == [EventType.RUN_STARTED, EventType.RUN_COMPLETED]
    assert [e.payload for e in received] == [{"k": 1}, {"k": 2}]


async def test_unsubscribed_run_drops_silently() -> None:
    bus = EventBus()
    await bus.publish(Event(EventType.RUN_STARTED, "ghost", {}))
    assert bus.subscriber_count("ghost") == 0


async def test_multiple_subscribers_get_fanout() -> None:
    bus = EventBus()

    async def consume(out: list[Event]) -> None:
        async with bus.subscribe("r2") as q:
            out.append(await q.get())

    a: list[Event] = []
    b: list[Event] = []
    t1 = asyncio.create_task(consume(a))
    t2 = asyncio.create_task(consume(b))
    await asyncio.sleep(0)
    await bus.publish(Event(EventType.STEP_STARTED, "r2", {"node": "draft"}))
    await asyncio.gather(t1, t2)
    assert len(a) == 1
    assert len(b) == 1
    assert a[0].payload == b[0].payload


async def test_subscriber_unregisters_on_exit() -> None:
    bus = EventBus()
    async with bus.subscribe("r3"):
        assert bus.subscriber_count("r3") == 1
    assert bus.subscriber_count("r3") == 0


async def test_slow_subscriber_does_not_block_publisher() -> None:
    bus = EventBus(queue_max_size=2)
    async with bus.subscribe("r4"):
        # Fill the queue then publish one more; the extra must drop silently.
        await bus.publish(Event(EventType.STEP_STARTED, "r4", {"i": 1}))
        await bus.publish(Event(EventType.STEP_STARTED, "r4", {"i": 2}))
        await asyncio.wait_for(
            bus.publish(Event(EventType.STEP_STARTED, "r4", {"i": 3})), timeout=0.5
        )
