"""Integration tests covering Stage C opcode interactions (TMM/ADX)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _require_file(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"required file not found: {path}")
    return path


def test_font_plane_switch_and_adx_pointer_math() -> None:
    """Verify TMM/ADX opcodes drive VIA + UDC updates within the full machine."""

    from jr100_port.jr100.machine import JR100Machine, JR100MachineConfig

    rom_path = _require_file(REPO_ROOT / "jr100rom.prg")

    machine = JR100Machine(JR100MachineConfig(rom_path=rom_path))
    machine.powerOn()

    queue = machine.getEventQueue()
    while not queue.isEmpty():
        queue.pop_first().dispatch(machine)

    cpu = machine.getCPU()
    assert cpu is not None
    memory = machine.getHardware().getMemory()

    program_origin = 0x0200
    program = [
        0xCE, 0xC0, 0x00,  # LDX #$C000 (UDC base)
        0x86, 0xAA,        # LDAA #$AA
        0xA7, 0x00,        # STAA ,X
        0xEC, 0x01,        # ADX #$01 (IX -> 0xC001)
        0x86, 0x55,        # LDAA #$55
        0xA7, 0x00,        # STAA ,X
        0x86, 0xFF,        # LDAA #$FF
        0xB7, 0xC8, 0x02,  # STAA $C802 (DDRB)
        0x86, 0x20,        # LDAA #$20 (select user font plane)
        0xB7, 0xC8, 0x00,  # STAA $C800 (ORB)
        0xCE, 0x25, 0x00,  # LDX #$2500 (TMM target area)
        0x7B, 0x01, 0x04,  # TMM #$01,4
        0x20, 0xFE,        # BRA * (hold execution)
    ]

    for offset, byte in enumerate(program):
        memory.store8(program_origin + offset, byte)

    # Prepare memory observed by TMM (#$01 against 0x7F => negative set only)
    memory.store8(0x2504, 0x7F)

    cpu.ci = True  # mask IRQs during the synthetic program
    cpu.pc = program_origin

    for _ in range(len(program) + 4):
        cpu.step()

    assert memory.load8(0xC000) == 0xAA
    assert memory.load8(0xC001) == 0x55

    via = machine.via
    display = machine.display
    assert display.current_font_plane == via.FONT_USER_DEFINED

    glyph, inverted, *_ = display.resolve_glyph(128)
    assert not inverted
    assert glyph.line(0) == 0xAA
    assert glyph.line(1) == 0x55

    assert cpu.cn is True
    assert cpu.cz is False
    assert cpu.cv is False
    assert cpu.pc == 0x021D
