"""FIFO queue that limits concurrent, resource-heavy AI grading requests."""
from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


class GradingQueueFull(Exception):
    """Raised when the waiting room has reached its configured limit."""


@dataclass
class _Task:
    work: Callable[[], Any]
    start_cooldown_seconds: float = 0
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None


class GradingQueue:
    """Run grading jobs in FIFO order with a fixed number of worker threads."""

    def __init__(self, max_concurrent: int = 3, max_queued: int = 24):
        self.max_concurrent = max(1, int(max_concurrent))
        self.max_queued = max(1, int(max_queued))
        self._tasks: queue.Queue[_Task] = queue.Queue(maxsize=self.max_queued)
        self._active = 0
        self._lock = threading.Lock()
        self._pacing_lock = threading.Lock()
        self._next_start_at = 0.0
        for index in range(self.max_concurrent):
            threading.Thread(target=self._worker, name=f"scratch-grader-{index + 1}", daemon=True).start()

    def submit(self, work: Callable[[], Any], start_cooldown_seconds: float = 0) -> tuple[Any, dict]:
        """Wait for a queued job to finish and return its result plus queue metadata."""
        try:
            cooldown_seconds = max(0, float(start_cooldown_seconds or 0))
        except (TypeError, ValueError):
            cooldown_seconds = 0
        task = _Task(work=work, start_cooldown_seconds=cooldown_seconds)
        with self._lock:
            active = self._active
            queued_before = self._tasks.qsize()
        try:
            self._tasks.put_nowait(task)
        except queue.Full as exc:
            raise GradingQueueFull from exc

        task.done.wait()
        if task.error is not None:
            raise task.error
        return task.result, {
            "max_concurrent": self.max_concurrent,
            "queued_ahead": max(0, active + queued_before - self.max_concurrent),
        }

    def stats(self) -> dict:
        with self._lock:
            active = self._active
        return {
            "active": active,
            "waiting": self._tasks.qsize(),
            "max_concurrent": self.max_concurrent,
            "max_queued": self.max_queued,
        }

    def _worker(self):
        while True:
            task = self._tasks.get()
            with self._lock:
                self._active += 1
            try:
                self._wait_for_start_slot(task.start_cooldown_seconds)
                task.result = task.work()
            except BaseException as exc:
                task.error = exc
            finally:
                with self._lock:
                    self._active -= 1
                task.done.set()
                self._tasks.task_done()

    def _wait_for_start_slot(self, cooldown_seconds: float):
        """Space API calls globally so a free-tier model is not burst-requested."""
        if cooldown_seconds <= 0:
            return
        with self._pacing_lock:
            now = time.monotonic()
            start_at = max(now, self._next_start_at)
            self._next_start_at = start_at + cooldown_seconds
        wait_seconds = start_at - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


grading_queue = GradingQueue(
    max_concurrent=_positive_int_env("MAX_CONCURRENT_GRADES", 3),
    max_queued=_positive_int_env("MAX_QUEUED_GRADES", 24),
)
