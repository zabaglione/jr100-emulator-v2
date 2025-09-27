"""Scheduler for real-time events, mirroring the Java TimeManager."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, List


@dataclass(order=True)
class _ScheduledEvent:
    time_offset: int
    command: Callable[[], None]


class TimeManager:
    """Port of jp.asamomiji.emulator.TimeManager."""

    _POLL_INTERVAL_SECS = 100e-6  # 100 microseconds

    def __init__(self) -> None:
        self._events: List[_ScheduledEvent] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()

    def addEvent(self, time_offset: int, command: Callable[[], None]) -> None:  # noqa: N802
        event = _ScheduledEvent(time_offset, command)
        with self._lock:
            self._insert_sorted(event)
        self._wake.set()

    def addScheduledEvent(self, event: _ScheduledEvent) -> None:  # noqa: N802
        with self._lock:
            self._insert_sorted(event)
        self._wake.set()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=0.5)
            self._thread = None

    def dispatcher(self) -> None:
        now = time.monotonic_ns()
        commands: List[Callable[[], None]] = []
        with self._lock:
            while self._events and self._events[0].time_offset <= now:
                commands.append(self._events.pop(0).command)
        for command in commands:
            command()

    def _run_loop(self) -> None:
        while self._running:
            self.dispatcher()
            self._wake.wait(self._POLL_INTERVAL_SECS)
            self._wake.clear()

    def _insert_sorted(self, event: _ScheduledEvent) -> None:
        index = 0
        for index, existing in enumerate(self._events):
            if event.time_offset < existing.time_offset:
                self._events.insert(index, event)
                break
        else:
            self._events.append(event)


__all__ = ["TimeManager"]
