"""Tests for the JR-100 VIA implementation."""

from __future__ import annotations

from pyjr100.bus import Memory, MemorySystem, Via6522
from pyjr100.bus.via6522 import TIMER1_INTERRUPT_BIT
from pyjr100.cpu import MB8861
from pyjr100.io import Keyboard


def make_cpu() -> tuple[MB8861, MemorySystem]:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    ram = Memory(0x0000, 0x10000)
    memory.register_memory(ram)
    ram.store16(0xFFFE, 0x2000)
    cpu = MB8861(memory)
    cpu.reset()
    return cpu, memory


def test_via_timer1_sets_irq_flag() -> None:
    cpu, _ = make_cpu()
    keyboard = Keyboard()
    via = Via6522(0xC800, keyboard, cpu)

    via.store8(0xC80E, 0xC0)  # enable T1 interrupt
    via.store8(0xC804, 0x04)
    via.store8(0xC805, 0x00)

    via.tick(4)

    assert via.load8(0xC80D) & TIMER1_INTERRUPT_BIT
    assert cpu.irq_pending


def test_via_keyboard_scan_returns_open_bits() -> None:
    cpu, _ = make_cpu()
    keyboard = Keyboard()
    via = Via6522(0xC800, keyboard, cpu)

    assert via.load8(0xC800) == 0xDF


def test_via_keyboard_sets_ca1_interrupt_on_press() -> None:
    cpu, _ = make_cpu()
    keyboard = Keyboard()
    via = Via6522(0xC800, keyboard, cpu)

    keyboard.press("a")
    via.store8(0xC803, 0x0F)  # set row select lines to output
    via.store8(0xC801, 0x01)  # select row 1 (A row)

    assert via.load8(0xC80D) & 0x02  # IFR_BIT_CA1 set

    via.load8(0xC800)  # read port clears CA1
    assert (via.load8(0xC80D) & 0x02) == 0
