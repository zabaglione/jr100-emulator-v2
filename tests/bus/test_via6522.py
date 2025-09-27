"""VIA 6522 behaviour regression tests."""

from __future__ import annotations

from pyjr100.bus.via6522 import IFR_BIT_CA1, IFR_BIT_T2
from pyjr100.system.machine import MachineConfig, create_machine


def _snapshot_ifr(machine) -> int:
    return machine.via.debug_snapshot()["IFR"]


def test_timer2_interrupt_triggers_once() -> None:
    machine = create_machine(MachineConfig())
    via = machine.via
    base = via.get_start_address()

    # Ensure IFR is clear before programming the timer.
    machine.memory.store8(base + 0x0D, 0x7F)

    # Program Timer2 with a small interval (16 cycles).
    machine.memory.store8(base + 0x08, 0x10)
    machine.memory.store8(base + 0x09, 0x00)

    assert (_snapshot_ifr(machine) & IFR_BIT_T2) == 0

    via.tick(0x11)
    assert (_snapshot_ifr(machine) & IFR_BIT_T2) == IFR_BIT_T2

    # Reading T2 low byte should acknowledge the interrupt.
    machine.memory.load8(base + 0x08)
    assert (_snapshot_ifr(machine) & IFR_BIT_T2) == 0

    # Without re-arming the timer, additional ticks must not raise new interrupts.
    via.tick(0x10)
    assert (_snapshot_ifr(machine) & IFR_BIT_T2) == 0


def test_ca1_interrupt_does_not_set_timer2_flag() -> None:
    machine = create_machine(MachineConfig())
    via = machine.via
    keyboard = machine.keyboard
    base = via.get_start_address()

    machine.memory.store8(base + 0x0D, 0x7F)

    # Select the row that contains the 'A' key.
    machine.memory.store8(base + 0x01, 0x01)

    keyboard.press("a")

    ifr = _snapshot_ifr(machine)
    assert (ifr & IFR_BIT_CA1) == IFR_BIT_CA1
    assert (ifr & IFR_BIT_T2) == 0

    # Reading the port should clear the CA1 interrupt.
    machine.memory.load8(base + 0x01)
    assert (_snapshot_ifr(machine) & IFR_BIT_CA1) == 0

    keyboard.release("a")


def test_font_plane_defaults_to_user_font() -> None:
    calls: list[bool] = []

    config = MachineConfig(via_font=calls.append)
    machine = create_machine(config)

    orb = machine.via.debug_snapshot()["ORB"]
    assert (orb & 0x20) == 0x20

    # The font callback should have been notified at least once with CMODE1 active.
    assert calls and calls[-1] is True


def test_portb5_remains_high_until_explicitly_cleared() -> None:
    machine = create_machine(MachineConfig())
    via = machine.via
    base = via.get_start_address()

    def has_cmode1() -> bool:
        return bool(via.debug_snapshot()["ORB"] & 0x20)

    # Default state uses CMODE1 (bit 5 high).
    assert has_cmode1()

    # Writing ORB before DDRB config should not drop PB5.
    machine.memory.store8(base + 0x00, 0x00)
    assert has_cmode1()

    # Enabling PB5 as output still retains the high level.
    machine.memory.store8(base + 0x02, 0x20)
    assert has_cmode1()

    # Once PB5 is configured as output, an explicit clear should switch to CMODE0.
    machine.memory.store8(base + 0x00, 0x00)
    assert not has_cmode1()
