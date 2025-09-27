"""Event queue ported from the Java TreeSet implementation."""

from __future__ import annotations

import itertools
from bisect import insort
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Protocol, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .computer import Computer


class EmulatorEvent(Protocol):
    """Interface for events scheduled on the computer clock."""

    clock: int

    def dispatch(self, computer: "Computer") -> None:
        ...


@dataclass(order=True)
class _QueueEntry:
    sort_key: Tuple[int, int] = field(init=False, repr=False)
    clock: int
    sequence: int
    event: EmulatorEvent

    def __post_init__(self) -> None:
        self.sort_key = (self.clock, self.sequence)


class EventQueue:
    """Sorted event queue equivalent to the Java TreeSet variant."""

    def __init__(self) -> None:
        self._entries: List[_QueueEntry] = []
        self._sequence = itertools.count()

    def add(self, event: EmulatorEvent) -> None:
        entry = _QueueEntry(clock=max(0, int(event.clock)), sequence=next(self._sequence), event=event)
        insort(self._entries, entry)

    def first(self) -> EmulatorEvent:
        if not self._entries:
            raise IndexError("event queue is empty")
        return self._entries[0].event

    def pop_first(self) -> EmulatorEvent:
        if not self._entries:
            raise IndexError("event queue is empty")
        entry = self._entries.pop(0)
        return entry.event

    def remove(self, event: EmulatorEvent) -> None:
        for index, entry in enumerate(self._entries):
            if entry.event is event:
                del self._entries[index]
                return
        raise ValueError("event not found")

    def isEmpty(self) -> bool:  # noqa: N802 - Java互換API
        return not self._entries

    def __iter__(self) -> Iterator[EmulatorEvent]:
        return (entry.event for entry in list(self._entries))


@dataclass
class BaseEvent:
    """Simple dataclass to host the clock attribute."""

    clock: int

    def dispatch(self, computer: "Computer") -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class ResetEvent(BaseEvent):
    def dispatch(self, computer: "Computer") -> None:
        cpu = computer.getCPU()
        if cpu is not None:
            cpu.reset()
        for device in computer.getDevices():
            if hasattr(device, "reset"):
                device.reset()


class PauseEvent(BaseEvent):
    def dispatch(self, computer: "Computer") -> None:
        computer.setRunningStatus(computer.STATUS_PAUSED)


class ResumeEvent(BaseEvent):
    def dispatch(self, computer: "Computer") -> None:
        computer.setRunningStatus(computer.STATUS_RUNNING)


class PowerOffEvent(BaseEvent):
    def dispatch(self, computer: "Computer") -> None:
        computer.setRunningStatus(computer.STATUS_STOPPED)


__all__ = [
    "EmulatorEvent",
    "EventQueue",
    "ResetEvent",
    "PauseEvent",
    "ResumeEvent",
    "PowerOffEvent",
]
