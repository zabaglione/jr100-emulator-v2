import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from newjr100.jr100.device.via6522 import (  # noqa: E402
    IFR_BIT_T2,
    REG_T2CL,
    REG_T2CH,
    REG_DDRB,
    REG_IER,
    REG_IORB,
    REG_IFR,
    IFR_BIT_IRQ,
    Via6522,
)


class DummyCPU:
    def __init__(self) -> None:
        self.irq_requested = False
        self.irq_cleared = False

    def request_irq(self) -> None:
        self.irq_requested = True

    def clear_irq(self) -> None:
        self.irq_cleared = True


class DummyKeyboard:
    def __init__(self) -> None:
        self.listeners = []
        self._matrix = [0] * 16

    def add_listener(self, listener):
        self.listeners.append(listener)

    def snapshot(self):
        return tuple(self._matrix)


@pytest.fixture()
def via() -> Via6522:
    keyboard = DummyKeyboard()
    cpu = DummyCPU()
    return Via6522(start=0xC800, keyboard=keyboard, cpu=cpu)


def test_initial_orb_defaults_to_input_idle(via: Via6522) -> None:
    assert via.load8(0xC800) == 0x3F


def test_store_orb_updates_font_plane(via: Via6522) -> None:
    calls: list[bool] = []
    via_with_callback = Via6522(
        start=via.get_start_address(),
        keyboard=via._keyboard,
        cpu=via._cpu,
        font_callback=calls.append,
    )

    via_with_callback.store8(via_with_callback.get_start_address(), 0x1F)
    assert calls[-1] is False

    via_with_callback.store8(via_with_callback.get_start_address(), 0x3F)
    assert calls[-1] is True


def test_t2_read_clears_interrupt(via: Via6522) -> None:
    base = via.get_start_address()
    # 目視ではタイマを直接セット
    via.store8(base + REG_T2CL, 0x10)
    via.store8(base + REG_T2CH, 0x00)
    via._timer2_enable = True
    via._timer2 = 0
    via._set_interrupt(IFR_BIT_T2)
    assert via.load8(base + REG_T2CL) == 0x00
    assert (via._IFR & IFR_BIT_T2) == 0


def test_ddr_outputs_override_inputs(via: Via6522) -> None:
    base = via.get_start_address()
    via.store8(base + REG_DDRB, 0x1F)
    via.store8(base + REG_IORB, 0x00)
    assert via.load8(base + REG_IORB) == 0x20  # PB5 remains set, lower bits cleared

    via.store8(base + REG_IORB, 0x1F)
    assert via.load8(base + REG_IORB) == 0x3F


def test_process_irq_sets_irq_flag(via: Via6522) -> None:
    base = via.get_start_address()
    via.store8(base + REG_IER, 0x80 | IFR_BIT_T2)
    via._set_interrupt(IFR_BIT_T2)
    assert via._IFR & IFR_BIT_IRQ
    assert via._cpu.irq_requested

    via._clear_interrupt(IFR_BIT_T2)
    assert (via._IFR & IFR_BIT_IRQ) == 0
    assert via._cpu.irq_cleared
