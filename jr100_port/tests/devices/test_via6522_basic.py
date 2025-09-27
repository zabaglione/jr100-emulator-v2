import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jr100_port.devices.via6522 import JR100Via6522, Via6522  # noqa: E402


class DummyDisplay:
    def __init__(self) -> None:
        self.current_font = "normal"

    def setCurrentFont(self, font: str) -> None:  # noqa: N802 - Java互換API
        self.current_font = font


class DummyKeyboard:
    def __init__(self) -> None:
        self.matrix = [0xFF] * 16

    def getKeyMatrix(self) -> list[int]:  # noqa: N802
        return self.matrix


class DummySoundProcessor:
    def __init__(self) -> None:
        self.frequency_calls: list[tuple[int, float]] = []
        self.line_state: list[bool] = []

    def setFrequency(self, timestamp: int, frequency: float) -> None:  # noqa: N802
        self.frequency_calls.append((timestamp, frequency))

    def setLineOn(self) -> None:  # noqa: N802
        self.line_state.append(True)

    def setLineOff(self) -> None:  # noqa: N802
        self.line_state.append(False)


class DummyHardware:
    def __init__(self) -> None:
        self.display = DummyDisplay()
        self.keyboard = DummyKeyboard()
        self.sound = DummySoundProcessor()

    def getDisplay(self) -> DummyDisplay:  # noqa: N802
        return self.display

    def getKeyboard(self) -> DummyKeyboard:  # noqa: N802
        return self.keyboard

    def getSoundProcessor(self) -> DummySoundProcessor:  # noqa: N802
        return self.sound


class DummyComputer:
    def __init__(self) -> None:
        self.clock_count = 0
        self.hardware = DummyHardware()
        self.base_time = 0

    def getClockCount(self) -> int:  # noqa: N802
        return self.clock_count

    def advance(self, cycles: int) -> None:
        self.clock_count += cycles

    def getHardware(self) -> DummyHardware:  # noqa: N802
        return self.hardware

    def getBaseTime(self) -> int:  # noqa: N802
        return self.base_time


def make_device(cls: type[Via6522]) -> tuple[Via6522, DummyComputer]:
    computer = DummyComputer()
    device = cls(computer, 0xC000)
    device.reset()
    return device, computer


@pytest.fixture()
def via() -> Via6522:
    device, _ = make_device(Via6522)
    return device


def test_reset_clears_registers(via: Via6522) -> None:
    assert via.ifr == 0
    assert via.ier == 0
    assert via.orb == 0
    assert via.ora == 0
    assert via.ddrb == 0
    assert via.ddra == 0
    assert via.timer1 == 0
    assert via.timer2 == 0


def test_store_and_load_basic_registers(via: Via6522) -> None:
    base = via.start_address

    via.store8(base + Via6522.VIA_REG_DDRB, 0xFF)
    via.store8(base + Via6522.VIA_REG_DDRA, 0x00)

    assert via.ddrb == 0xFF
    assert via.ddra == 0x00

    assert via.load8(base + Via6522.VIA_REG_DDRB) == 0xFF
    assert via.load8(base + Via6522.VIA_REG_DDRA) == 0x00

    via.store8(base + Via6522.VIA_REG_IORB, 0xAA)
    assert via.orb == 0xAA
    assert via.load8(base + Via6522.VIA_REG_IORB) == 0xAA

    via.store8(base + Via6522.VIA_REG_IORA, 0x55)
    assert via.ora == 0x55


def test_timer1_square_wave_toggles_pb7() -> None:
    via, computer = make_device(Via6522)
    base = via.start_address

    via.store8(base + Via6522.VIA_REG_ACR, 0xC0)
    via.store8(base + Via6522.VIA_REG_T1LL, 0x00)
    via.store8(base + Via6522.VIA_REG_T1LH, 0x00)
    via.store8(base + Via6522.VIA_REG_T1CH, 0x00)

    for _ in range(40):
        computer.advance(1)
        via.execute()
        if via.ifr & Via6522.IFR_BIT_T1:
            break

    assert via.ifr & Via6522.IFR_BIT_T1
    assert via.inputPortBBit(7) == 1


def test_timer2_pulse_count_uses_pb6_falling_edge() -> None:
    via, computer = make_device(Via6522)
    base = via.start_address

    via.store8(base + Via6522.VIA_REG_ACR, 0x20)
    via.store8(base + Via6522.VIA_REG_T2CL, 0x01)
    via.store8(base + Via6522.VIA_REG_T2CH, 0x00)

    via.setPortB(6, 1)

    for _ in range(4):
        computer.advance(1)
        via.execute()
        via.setPortB(6, 0)
        computer.advance(1)
        via.execute()
        via.setPortB(6, 1)

    assert via.ifr & Via6522.IFR_BIT_T2


def test_jr100_store_iorb_updates_font_and_pb6() -> None:
    via, _ = make_device(JR100Via6522)
    base = via.start_address

    via.store8(base + Via6522.VIA_REG_DDRB, 0x20)

    via.store8(base + Via6522.VIA_REG_IORB, 0x20)
    assert via.computer.getHardware().getDisplay().current_font == JR100Via6522.FONT_USER_DEFINED
    assert via.inputPortBBit(6) == via.inputPortBBit(7)

    via.store8(base + Via6522.VIA_REG_IORB, 0xA0)
    assert via.inputPortBBit(6) == via.inputPortBBit(7)

    via.store8(base + Via6522.VIA_REG_IORB, 0x00)
    assert via.computer.getHardware().getDisplay().current_font == JR100Via6522.FONT_NORMAL


def test_jr100_keyboard_scan_updates_lower_bits() -> None:
    via, _ = make_device(JR100Via6522)
    base = via.start_address

    hardware = via.computer.getHardware()
    hardware.keyboard.matrix[0x03] = 0b11110

    via.store8(base + Via6522.VIA_REG_IORB, 0xE0)
    via.store8(base + Via6522.VIA_REG_IORA, 0x03)

    assert via.inputPortB() & 0x1F == 0x01


def test_jr100_timer1_sets_sound_frequency() -> None:
    via, computer = make_device(JR100Via6522)
    base = via.start_address

    via.store8(base + Via6522.VIA_REG_ACR, 0xC0)
    via.store8(base + Via6522.VIA_REG_T1LL, 0x10)
    via.store8(base + Via6522.VIA_REG_T1LH, 0x00)
    via.store8(base + Via6522.VIA_REG_T1CH, 0x00)

    sound = via.computer.getHardware().getSoundProcessor()
    assert sound.frequency_calls
    assert sound.line_state[-1] is True

    computer.advance(10)
    via.execute()

    via.store8(base + Via6522.VIA_REG_ACR, 0x00)
    via.store8(base + Via6522.VIA_REG_T1CH, 0x00)
    assert sound.line_state[-1] is False
