"""Background task runtime for orchestrator runs.

Why this exists: `asyncio.create_task` doesn't hold a strong reference to the
task. If we just do `asyncio.create_task(orch.run(id))` and return, the task
can be garbage-collected mid-flight (rare, but real). The runtime keeps a set
of live tasks until they complete.

Also provides graceful cancellation on app shutdown via the FastAPI lifespan.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.orchestrator.runner import Orchestrator

logger = get_logger(__name__)


class OrchestratorRuntime:
    def __init__(self, orchestrator_factory: Callable[[], Orchestrator]) -> None:
        self._orchestrator_factory = orchestrator_factory
        self._tasks: set[asyncio.Task[None]] = set()
        self._shutting_down = False

    def spawn(self, run_id: str) -> asyncio.Task[None]:
        if self._shutting_down:
            raise RuntimeError("Runtime is shutting down; refusing new tasks")
        orchestrator = self._orchestrator_factory()
        task = asyncio.create_task(
            self._wrapped_run(orchestrator, run_id), name=f"run:{run_id}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _wrapped_run(self, orchestrator: Orchestrator, run_id: str) -> None:
        try:
            await orchestrator.run(run_id)
        except asyncio.CancelledError:
            logger.info("orchestrator_task_cancelled", run_id=run_id)
            raise
        except Exception:  # pragma: no cover — orchestrator.run() should not raise
            logger.exception("orchestrator_task_unhandled_exception", run_id=run_id)

    async def wait_for(
        self, run_id: str, *, timeout: float | None = None
    ) -> None:
        """Helper for tests and synchronous callers — block until task done."""
        task = next((t for t in self._tasks if t.get_name() == f"run:{run_id}"), None)
        if task is None:
            return
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    async def shutdown(self, *, timeout: float = 30.0) -> None:
        """Cancel all running tasks and wait up to `timeout` seconds."""
        self._shutting_down = True
        if not self._tasks:
            return
        logger.info("orchestrator_runtime_shutdown", pending=len(self._tasks))
        for t in list(self._tasks):
            t.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout=timeout
            )
        except TimeoutError:
            logger.warning(
                "orchestrator_runtime_shutdown_timeout", pending=len(self._tasks)
            )


# Process-wide runtime.
_runtime: OrchestratorRuntime | None = None


def get_runtime() -> OrchestratorRuntime:
    global _runtime
    if _runtime is None:
        _runtime = OrchestratorRuntime(orchestrator_factory=Orchestrator)
    return _runtime


def set_runtime(runtime: OrchestratorRuntime) -> None:
    """Used by lifespan to install a configured runtime, and by tests to override."""
    global _runtime
    _runtime = runtime


def _reset_runtime() -> None:
    global _runtime
    _runtime = None
