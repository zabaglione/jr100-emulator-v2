"""Computer orchestrator mirroring the Java implementation."""

from __future__ import annotations

import time
from typing import List, Optional, Protocol

from .event_queue import EventQueue, PauseEvent, PowerOffEvent, ResetEvent, ResumeEvent
from .hardware import Hardware
from .time_manager import TimeManager


class CpuLike(Protocol):
    def reset(self) -> None:
        ...

    def execute(self, clocks: int) -> int:
        ...

    def saveState(self, state_set) -> None:  # noqa: N802
        ...

    def loadState(self, state_set) -> None:  # noqa: N802
        ...


class DeviceLike(Protocol):
    def reset(self) -> None:
        ...

    def execute(self) -> None:
        ...

    def saveState(self, state_set) -> None:  # noqa: N802
        ...

    def loadState(self, state_set) -> None:  # noqa: N802
        ...


class Computer:
    """Base class for the JR-100 computer system."""

    STATUS_RUNNING = 0
    STATUS_PAUSED = 1
    STATUS_STOPPED = 2

    def __init__(self, refresh_rate: float) -> None:
        self.refreshRate = refresh_rate  # noqa: N815 - Java互換API
        self.clockCount = 0  # noqa: N815 - Java互換API
        self._clock_adjustment = 0
        self._cpu: Optional[CpuLike] = None
        self._hardware = Hardware()
        self._devices: List[DeviceLike] = []
        self._event_queue = EventQueue()
        self._time_manager = TimeManager()
        self._running_status = self.STATUS_STOPPED
        self._interval_clocks = 0
        self._base_time_ns = 0

    # ------------------------------------------------------------------
    # Abstract members

    def getClockFrequency(self) -> int:  # noqa: N802 - Must be overridden
        raise NotImplementedError

    def setClockFrequency(self, frequency: int) -> None:  # noqa: N802
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Accessors

    def getCPU(self) -> Optional[CpuLike]:  # noqa: N802
        return self._cpu

    def setCPU(self, cpu: CpuLike) -> None:  # noqa: N802
        self._cpu = cpu

    def getHardware(self) -> Hardware:  # noqa: N802
        return self._hardware

    def getDevices(self) -> List[DeviceLike]:  # noqa: N802
        return self._devices

    def addDevice(self, device: DeviceLike) -> None:  # noqa: N802
        self._devices.append(device)

    def getEventQueue(self) -> EventQueue:  # noqa: N802
        return self._event_queue

    def getTimeManager(self) -> TimeManager:  # noqa: N802
        return self._time_manager

    def getRunningStatus(self) -> int:  # noqa: N802
        return self._running_status

    def setRunningStatus(self, status: int) -> None:  # noqa: N802
        self._running_status = status

    def setClockCount(self, value: int) -> None:  # noqa: N802
        self.clockCount = max(0, value)

    def getClockCount(self) -> int:  # noqa: N802
        return self.clockCount

    def getBaseTime(self) -> int:  # noqa: N802
        return self._base_time_ns

    def getIntervalClocks(self) -> int:  # noqa: N802
        return self._interval_clocks

    # ------------------------------------------------------------------
    # Lifecycle control

    def powerOn(self) -> None:  # noqa: N802
        self.setClockFrequency(self.getClockFrequency())
        self._interval_clocks = int(self.refreshRate * self.getClockFrequency())
        self._running_status = self.STATUS_RUNNING
        self.clockCount = 0
        self._clock_adjustment = 0
        self._base_time_ns = time.perf_counter_ns()
        self._event_queue.add(ResetEvent(self.clockCount))

    def powerOff(self) -> None:  # noqa: N802
        self._event_queue.add(PowerOffEvent(self.clockCount))

    def pause(self) -> None:
        if self._running_status == self.STATUS_RUNNING:
            self._event_queue.add(PauseEvent(self.clockCount))

    def resume(self) -> None:
        if self._running_status == self.STATUS_PAUSED:
            self._event_queue.add(ResumeEvent(self.clockCount))

    def reset(self) -> None:
        if self._running_status in (self.STATUS_RUNNING, self.STATUS_PAUSED):
            self._event_queue.add(ResetEvent(self.clockCount))

    # ------------------------------------------------------------------
    # Execution helpers

    def runFrame(self) -> None:  # noqa: N802
        if self._running_status == self.STATUS_STOPPED:
            return
        interval = self._interval_clocks if self._running_status == self.STATUS_RUNNING else 0
        end_clock = self.clockCount + interval - self._clock_adjustment
        self._process_events(end_clock)
        if self._running_status == self.STATUS_RUNNING:
            self._clock_adjustment = self._execute_if_possible(end_clock - self.clockCount)
        display = self._hardware.getDisplay()
        if display is not None and hasattr(display, "refresh"):
            display.refresh()

    def _process_events(self, end_clock: int) -> None:
        while not self._event_queue.isEmpty() and self._event_queue.first().clock <= end_clock:
            event = self._event_queue.pop_first()
            delta = max(0, event.clock - self.clockCount)
            self._clock_adjustment = self._execute_if_possible(delta)
            event.dispatch(self)
            if self._running_status != self.STATUS_RUNNING:
                break

    def _execute_if_possible(self, clocks: int) -> int:
        if clocks <= 0 or self._running_status != self.STATUS_RUNNING:
            return 0
        if self._cpu is None:
            raise RuntimeError("CPU not attached")
        leftover = self._cpu.execute(clocks)
        consumed = clocks - leftover
        if consumed < 0:
            raise ValueError("execute returned more than requested")
        self.clockCount += consumed
        for device in self._devices:
            device.execute()
        return leftover

    # ------------------------------------------------------------------
    # State persistence

    def saveState(self, state_set) -> None:  # noqa: N802
        if self._cpu is not None:
            self._cpu.saveState(state_set)
        self._hardware.saveState(state_set)
        for device in self._devices:
            if hasattr(device, "saveState"):
                device.saveState(state_set)

    def loadState(self, state_set) -> None:  # noqa: N802
        if self._cpu is not None:
            self._cpu.loadState(state_set)
        self._hardware.loadState(state_set)
        for device in self._devices:
            if hasattr(device, "loadState"):
                device.loadState(state_set)


__all__ = ["Computer", "CpuLike", "DeviceLike"]
