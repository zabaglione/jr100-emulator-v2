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

    via.tick(7)

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
    assert via.load8(0xC80D) & 0x02  # CA1 asserted on press
    keyboard.release("a")
    via.cancel_key_click()
    assert (via.load8(0xC80D) & 0x02) == 0


def test_via_port_b_font_bit_updates_even_without_ddr() -> None:
    cpu, _ = make_cpu()
    keyboard = Keyboard()
    toggles: list[bool] = []

    def font_callback(use_user: bool) -> None:
        toggles.append(use_user)

    via = Via6522(0xC800, keyboard, cpu, font_callback=font_callback)

    via.store8(0xC800, 0x20)
    via.store8(0xC800, 0x00)

    assert toggles[-2:] == [True, False]


def test_via_timer1_buzzer_frequency_and_stop() -> None:
    cpu, _ = make_cpu()
    keyboard = Keyboard()
    events: list[tuple[bool, float]] = []

    via = Via6522(0xC800, keyboard, cpu, buzzer_callback=lambda e, f: events.append((e, f)))

    via.store8(0xC80B, 0xC0)
    via.store8(0xC804, 0x04)
    via.store8(0xC805, 0x00)

    assert events
    enabled, freq = events[-1]
    assert enabled is True
    assert 70_000.0 < freq < 90_000.0

    via.store8(0xC80B, 0x00)
    via.store8(0xC804, 0x04)
    via.store8(0xC805, 0x00)

    assert events[-1] == (False, 0.0)


def test_via_cancel_key_click_silences_buzzer() -> None:
    cpu, _ = make_cpu()
    keyboard = Keyboard()
    events: list[tuple[bool, float]] = []

    via = Via6522(0xC800, keyboard, cpu, buzzer_callback=lambda e, f: events.append((e, f)))

    via.store8(0xC80B, 0xC0)
    via.store8(0xC804, 0x04)
    via.store8(0xC805, 0x00)

    assert events and events[-1][0] is True

    via.cancel_key_click()

    assert events[-1] == (False, 0.0)
