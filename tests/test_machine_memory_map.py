"""Tests for the JR-100 machine assembly and memory map."""

from __future__ import annotations

import pytest

from pyjr100.system import MachineConfig, create_machine


def test_default_machine_memory_map() -> None:
    machine = create_machine(MachineConfig())

    assert machine.ram.get_start_address() == 0x0000
    assert machine.ram.length == 0x4000
    assert machine.udc_ram.get_start_address() == 0xC000
    assert machine.udc_ram.length == 0x0100
    assert machine.video_ram.get_start_address() == 0xC100
    assert machine.video_ram.length == 0x0300
    assert machine.via.get_start_address() == 0xC800
    assert machine.via.get_end_address() == 0xC80F
    assert machine.extended_io.get_start_address() == 0xCC00
    assert machine.extended_io.get_end_address() == 0xCFFF
    assert machine.rom.get_start_address() == 0xE000
    assert machine.rom.length == 0x2000

    assert machine.cpu.memory is machine.memory


def test_extended_ram_configuration() -> None:
    machine = create_machine(MachineConfig(use_extended_ram=True))

    assert machine.ram.length == 0x8000

    # Unmapped region should no longer respond differently inside RAM range.
    machine.memory.store8(0x7FFF, 0x12)
    assert machine.memory.load8(0x7FFF) == 0x12


def test_rom_image_initialises_restart_vector() -> None:
    image = bytearray(0x2000)
    image[-2] = 0x12
    image[-1] = 0x34
    machine = create_machine(MachineConfig(rom_image=bytes(image)))

    assert machine.cpu.state.pc == 0x1234
    assert machine.rom.load8(0xE000) == 0x00
    assert machine.rom.load8(0xFFFE) == 0x12
    assert machine.rom.load8(0xFFFF) == 0x34


def test_via_keyboard_scan_defaults_to_open_matrix() -> None:
    machine = create_machine(MachineConfig())
    assert machine.memory.load8(0xC800) == 0xDF


def test_extended_io_registers_gamepad_status() -> None:
    machine = create_machine(MachineConfig())
    machine.memory.store8(0xCC02, 0x9A)
    assert machine.memory.load8(0xCC02) == 0x9A
