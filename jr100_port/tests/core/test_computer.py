import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jr100_port.core.computer import Computer


class DummyCPU:
    def __init__(self) -> None:
        self.reset_count = 0
        self.executed_cycles = 0

    def reset(self) -> None:
        self.reset_count += 1

    def execute(self, clocks: int) -> int:
        consume = min(clocks, 6)
        self.executed_cycles += consume
        return clocks - consume

    def saveState(self, state) -> None:  # noqa: N802
        state["cpu"] = "saved"

    def loadState(self, state) -> None:  # noqa: N802
        state.get("cpu")


class DummyDevice:
    def __init__(self) -> None:
        self.reset_count = 0
        self.executed = 0

    def reset(self) -> None:
        self.reset_count += 1

    def execute(self) -> None:
        self.executed += 1

    def saveState(self, state) -> None:  # noqa: N802
        state["device"] = "saved"

    def loadState(self, state) -> None:  # noqa: N802
        state.get("device")


class TestComputer(Computer):
    def __init__(self) -> None:
        super().__init__(refresh_rate=1 / 60)
        self._clock_frequency = 894_000

    def getClockFrequency(self) -> int:
        return self._clock_frequency

    def setClockFrequency(self, frequency: int) -> None:
        self._clock_frequency = frequency


TestComputer.__test__ = False


@pytest.fixture()
def computer() -> TestComputer:
    comp = TestComputer()
    cpu = DummyCPU()
    device = DummyDevice()
    comp.setCPU(cpu)
    comp.addDevice(device)
    return comp


def test_power_on_queues_reset(computer: TestComputer) -> None:
    computer.powerOn()
    assert computer.getRunningStatus() == Computer.STATUS_RUNNING
    assert not computer.getEventQueue().isEmpty()
    computer.runFrame()
    cpu = computer.getCPU()
    assert cpu is not None and cpu.reset_count == 1
    device = computer.getDevices()[0]
    assert device.reset_count == 1


def test_run_frame_updates_clock(computer: TestComputer) -> None:
    computer.powerOn()
    computer.runFrame()  # consume reset
    initial = computer.clockCount
    computer.runFrame()
    assert computer.clockCount >= initial


def test_pause_and_resume(computer: TestComputer) -> None:
    computer.powerOn()
    computer.runFrame()
    computer.pause()
    computer.runFrame()
    assert computer.getRunningStatus() == Computer.STATUS_PAUSED
    computer.resume()
    computer.runFrame()
    assert computer.getRunningStatus() == Computer.STATUS_RUNNING


def test_power_off(computer: TestComputer) -> None:
    computer.powerOn()
    computer.runFrame()
    computer.powerOff()
    computer.runFrame()
    assert computer.getRunningStatus() == Computer.STATUS_STOPPED


def test_save_and_load_state(computer: TestComputer) -> None:
    computer.powerOn()
    computer.runFrame()
    state = {}
    computer.saveState(state)
    assert state["cpu"] == "saved"
    assert state["device"] == "saved"
    computer.loadState(state)


def test_execute_without_cpu_raises() -> None:
    comp = TestComputer()
    comp.powerOn()
    with pytest.raises(RuntimeError):
        comp.runFrame()
