"""Integration tests for the STARFIRE title screen on the JR-100 emulator."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pyjr100.loader import load_prog
from pyjr100.system import MachineConfig, create_machine


ROM_PATH = Path("jr100rom.prg")
STARFIRE_PATH = Path("STARFIRE.prg")


EXPECTED_ROW10 = [
    0x28,
    0x29,
    0x27,
    0x28,
    0x00,
    0x33,
    0x23,
    0x2F,
    0x32,
    0x25,
    0x40,
    0x40,
    0x40,
    0x40,
    0x00,
    0x40,
    0x40,
    0x40,
    0x72,
    0x67,
    0x40,
    0x40,
    0x40,
    0x40,
    0x40,
    0x40,
    0x40,
    0x40,
    0x40,
    0x62,
    0x68,
    0x40,
]


def _step_machine(machine, cycles: int) -> None:
    cpu = machine.cpu
    via = machine.via
    executed = 0
    while executed < cycles:
        step = cpu.step()
        if step == 0:
            step = 1
        via.tick(step)
        executed += step


def _run_until_title(max_cycles: int = 1_200_000) -> tuple["Machine", bool]:
    machine = create_machine(MachineConfig(rom_image=None))
    load_prog(io.BytesIO(ROM_PATH.read_bytes()), machine.memory)
    machine.cpu.reset()
    load_prog(STARFIRE_PATH.open("rb"), machine.memory)

    machine.cpu.state.pc = 0x0D00  # entry used by A=USR($D00)

    executed = 0
    saw_user_plane = False
    title_detected = False
    while executed < max_cycles:
        step = machine.cpu.step()
        if step == 0:
            step = 1
        machine.via.tick(step)
        executed += step
        if machine.via._orb & 0x20:
            saw_user_plane = True
        if not title_detected and executed % 2048 == 0:
            vram = machine.video_ram.snapshot()
            row = [value & 0x7F for value in vram[10 * 32 : 11 * 32]]
            if row == EXPECTED_ROW10:
                title_detected = True
                break

    return machine, saw_user_plane and title_detected


@pytest.mark.skipif(
    not (ROM_PATH.exists() and STARFIRE_PATH.exists()),
    reason="STARFIRE title test requires jr100rom.prg and STARFIRE.prg",
)
def test_starfire_title_vram_snapshot() -> None:
    machine, saw_user_plane = _run_until_title()

    assert saw_user_plane, "user font plane should be asserted during title rendering"

    vram = machine.video_ram.snapshot()

    expected_rows = {
        10: EXPECTED_ROW10,
        13: [
            0x33,
            0x23,
            0x2F,
            0x32,
            0x25,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x00,
            0x40,
            0x40,
            0x40,
            0x40,
            0x64,
            0x62,
            0x72,
            0x40,
            0x40,
            0x61,
            0x54,
            0x73,
            0x40,
            0x40,
            0x68,
            0x67,
            0x66,
            0x40,
        ],
        14: [
            0x40,
            0x40,
            0x10,
            0x10,
            0x10,
            0x10,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x72,
            0x72,
            0x72,
            0x40,
            0x54,
            0x64,
            0x54,
            0x66,
            0x54,
            0x40,
            0x68,
            0x68,
            0x68,
            0x40,
        ],
        21: [
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x63,
            0x78,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x40,
            0x7A,
            0x76,
            0x40,
        ],
    }

    for row, expected in expected_rows.items():
        start = row * 32
        row_values = [value & 0x7F for value in vram[start : start + 32]]
        assert row_values == expected


@pytest.mark.skipif(
    not (ROM_PATH.exists() and STARFIRE_PATH.exists()),
    reason="STARFIRE title test requires jr100rom.prg and STARFIRE.prg",
)
def test_starfire_user_defined_glyphs_loaded() -> None:
    machine, saw_user_plane = _run_until_title()

    assert saw_user_plane
    udc = machine.udc_ram.snapshot()
    assert any(udc), "user-defined character RAM should not be empty"

    expected_glyphs = {
        0: [0x00, 0x00, 0x10, 0x38, 0x10, 0x00, 0x00, 0x00],
        4: [0xC3, 0xC3, 0xDB, 0xFF, 0xDB, 0xC3, 0xC3, 0x00],
        10: [0x3C, 0xFF, 0xFF, 0xC3, 0xC3, 0xFF, 0xFF, 0x3C],
        29: [0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF],
    }

    for index, expected in expected_glyphs.items():
        start = index * 8
        assert list(udc[start : start + 8]) == expected


@pytest.mark.skipif(
    not (ROM_PATH.exists() and STARFIRE_PATH.exists()),
    reason="STARFIRE title test requires jr100rom.prg and STARFIRE.prg",
)
def test_starfire_game_starts_on_z() -> None:
    machine, saw_user_plane = _run_until_title()

    assert saw_user_plane

    baseline_row = tuple(machine.video_ram.snapshot()[10 * 32 : 11 * 32])
    keyboard = machine.keyboard
    keyboard.press("z")
    _step_machine(machine, 2_000_000)
    keyboard.release("z")

    pc_reached = False
    for _ in range(400):
        _step_machine(machine, 20_000)
        pc = machine.cpu.state.pc & 0xFFFF
        if 0x0E45 <= pc <= 0x16C8 or 0xE400 <= pc <= 0xF800:
            pc_reached = True
            break

    # Allow additional settling time so that VRAM updates propagate.
    _step_machine(machine, 800_000)

    current_row = tuple(machine.video_ram.snapshot()[10 * 32 : 11 * 32])
    assert current_row != baseline_row

    assert pc_reached
