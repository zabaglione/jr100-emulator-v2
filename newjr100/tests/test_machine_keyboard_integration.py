import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from newjr100.jr100.device.via6522 import (  # noqa: E402
    IFR_BIT_CA1,
    REG_IFR,
    REG_IORB,
    REG_IORA,
)
from newjr100.system.machine import MachineConfig, create_machine  # noqa: E402


@pytest.fixture()
def machine():
    return create_machine(MachineConfig())


def test_keyboard_press_triggers_ca1_and_updates_port(machine) -> None:
    base = machine.via.get_start_address()

    machine.keyboard.press("z")

    port = machine.via.load8(base + REG_IORB)
    assert (port & 0x04) == 0
    assert machine.via.load8(base + REG_IFR) & IFR_BIT_CA1

    machine.via.load8(base + REG_IORA)
    assert (machine.via.load8(base + REG_IFR) & IFR_BIT_CA1) == 0

    machine.keyboard.release("z")
    port_after = machine.via.load8(base + REG_IORB)
    assert (port_after & 0x04) == 0x04


def test_keyboard_row_switch_preserves_pressed_state(machine) -> None:
    base = machine.via.get_start_address()

    machine.keyboard.press("a")
    machine.via.store8(base + REG_IORA, 0x01)

    port = machine.via.load8(base + REG_IORB)
    assert (port & 0x01) == 0

    machine.keyboard.release("a")
    port_after = machine.via.load8(base + REG_IORB)
    assert (port_after & 0x01) == 0x01

    machine.via.cancel_key_click()
