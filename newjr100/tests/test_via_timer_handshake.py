import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from newjr100.jr100.device.via6522 import (  # noqa: E402
    IFR_BIT_CA1,
    IFR_BIT_CA2,
    IFR_BIT_CB1,
    IFR_BIT_CB2,
    IFR_BIT_T1,
    IFR_BIT_T2,
    PB6_MASK,
    PB7_MASK,
    REG_ACR,
    REG_IER,
    REG_IFR,
    REG_IORB,
    REG_IORA,
    REG_PCR,
    REG_T1CH,
    REG_T1CL,
    REG_T1LH,
    REG_T1LL,
    REG_T2CH,
    REG_T2CL,
    Via6522,
)


class DummyCPU:
    def __init__(self) -> None:
        self.irq_requests: list[bool] = []

    def request_irq(self) -> None:
        self.irq_requests.append(True)

    def clear_irq(self) -> None:
        self.irq_requests.append(False)


class DummyKeyboard:
    def __init__(self) -> None:
        self.listeners = []
        self._matrix = [0] * 16

    def add_listener(self, listener) -> None:
        self.listeners.append(listener)

    def snapshot(self):
        return tuple(self._matrix)

    def press(self, row: int, mask: int) -> None:
        self._matrix[row] |= mask
        for listener in list(self.listeners):
            listener(row, mask, True)

    def release(self, row: int, mask: int) -> None:
        self._matrix[row] &= ~mask & 0x1F
        for listener in list(self.listeners):
            listener(row, mask, False)


@pytest.fixture()
def via() -> Via6522:
    keyboard = DummyKeyboard()
    cpu = DummyCPU()
    device = Via6522(start=0xC800, keyboard=keyboard, cpu=cpu)
    setattr(device, "_test_keyboard", keyboard)
    return device


def test_timer1_square_wave_toggles_pb7_and_sets_irq(via: Via6522) -> None:
    base = via.get_start_address()

    via.store8(base + REG_ACR, 0xC0)
    via.store8(base + REG_IER, 0x80 | IFR_BIT_T1)
    via.store8(base + REG_T1LL, 0x10)
    via.store8(base + REG_T1LH, 0x00)
    via.store8(base + REG_T1CL, 0x10)
    via.store8(base + REG_T1CH, 0x00)

    initial_port = via.load8(base + REG_IORB)
    assert (initial_port & PB7_MASK) == 0
    assert (initial_port & PB6_MASK) == 0

    via.tick(0x14)

    port_after = via.load8(base + REG_IORB)
    assert (port_after & PB7_MASK) == PB7_MASK
    assert (port_after & PB6_MASK) == PB6_MASK
    assert via.load8(base + REG_IFR) & IFR_BIT_T1
    assert via._cpu.irq_requests  # noqa: SLF001

    via.tick(0x14)
    port_second = via.load8(base + REG_IORB)
    assert (port_second & PB7_MASK) == 0
    assert (port_second & PB6_MASK) == 0


def test_ca2_handshake_clears_ifr_and_restores_high(via: Via6522) -> None:
    base = via.get_start_address()
    via.store8(base + REG_PCR, 0x0A)
    via.store8(base + REG_IER, 0x80 | IFR_BIT_CA1 | IFR_BIT_CA2)

    via._set_interrupt(IFR_BIT_CA1 | IFR_BIT_CA2)  # noqa: SLF001

    before = via.debug_snapshot()
    assert before["CA2"] == 1

    via.load8(base + REG_IORA)
    mid = via.debug_snapshot()
    assert mid["CA2"] == 0
    assert (via.load8(base + REG_IFR) & (IFR_BIT_CA1 | IFR_BIT_CA2)) == 0

    via.tick(2)
    after = via.debug_snapshot()
    assert after["CA2"] == 1


def test_timer2_pulse_count_uses_pb6_falling_edge(via: Via6522) -> None:
    base = via.get_start_address()
    via.store8(base + REG_ACR, 0xE0)
    via.store8(base + REG_T1LL, 0x04)
    via.store8(base + REG_T1LH, 0x00)
    via.store8(base + REG_T1CL, 0x04)
    via.store8(base + REG_T1CH, 0x00)
    via.store8(base + REG_T2CL, 0x02)
    via.store8(base + REG_T2CH, 0x00)
    via.store8(base + REG_IER, 0x80 | IFR_BIT_T2)

    for _ in range(256):
        via.tick(1)
        if via.load8(base + REG_IFR) & IFR_BIT_T2:
            snap = via.debug_snapshot()
            assert snap["timer2"] == 2
            assert via._cpu.irq_requests  # noqa: SLF001
            break
    else:
        pytest.fail("Timer2 pulse mode did not trigger interrupt")


def test_cb1_handshake_releases_cb2_and_sets_interrupt(via: Via6522) -> None:
    base = via.get_start_address()
    via.store8(base + REG_PCR, 0x90)
    via.store8(base + REG_IER, 0x80 | IFR_BIT_CB1)

    via.store8(base + REG_IORB, 0x3F)
    assert via.debug_snapshot()["CB2_OUT"] == 0

    via.set_cb1_input(1)
    assert via.debug_snapshot()["CB2_OUT"] == 1
    assert via.load8(base + REG_IFR) & IFR_BIT_CB1
    assert via._cpu.irq_requests  # noqa: SLF001


def test_cb2_input_edge_sets_irq(via: Via6522) -> None:
    base = via.get_start_address()
    via.store8(base + REG_PCR, 0x40)
    via.store8(base + REG_IER, 0x80 | IFR_BIT_CB2)

    via.set_cb2_input(0)
    via.set_cb2_input(1)

    assert via.load8(base + REG_IFR) & IFR_BIT_CB2
    assert via._cpu.irq_requests  # noqa: SLF001


def test_keyboard_press_updates_portb_and_ca1(via: Via6522) -> None:
    keyboard: DummyKeyboard = getattr(via, "_test_keyboard")  # type: ignore[assignment]
    base = via.get_start_address()

    via.store8(base + REG_IORA, 0x00)
    via.load8(base + REG_IFR)

    keyboard.press(0, 0x04)

    port = via.load8(base + REG_IORB)
    assert (port & 0x04) == 0
    assert via.load8(base + REG_IFR) & IFR_BIT_CA1
    assert via._cpu.irq_requests  # noqa: SLF001

    via.load8(base + REG_IORA)
    assert (via.load8(base + REG_IFR) & IFR_BIT_CA1) == 0


def test_keyboard_row_switch_reflects_existing_press(via: Via6522) -> None:
    keyboard: DummyKeyboard = getattr(via, "_test_keyboard")  # type: ignore[assignment]
    base = via.get_start_address()

    via.store8(base + REG_IORA, 0x00)
    keyboard.press(1, 0x10)
    via.store8(base + REG_IORA, 0x01)

    port = via.load8(base + REG_IORB)
    assert (port & 0x10) == 0

    keyboard.release(1, 0x10)
    port_after = via.load8(base + REG_IORB)
    assert (port_after & 0x10) == 0x10
