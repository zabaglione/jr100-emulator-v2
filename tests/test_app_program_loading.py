"""JR100App プログラムロード処理の検証。"""

from __future__ import annotations

import io
import struct

from pyjr100.system import MachineConfig, create_machine
from pyjr100.ui.app import AppConfig, JR100App


def _build_prog_basic(payload: bytes) -> bytes:
    stream = io.BytesIO()
    stream.write(b"PROG")
    stream.write(struct.pack("<I", 1))

    name = b"TEST"
    stream.write(struct.pack("<I", len(name)))
    stream.write(name)

    stream.write(struct.pack("<I", 0x0246))
    stream.write(struct.pack("<I", len(payload)))
    stream.write(struct.pack("<I", 0))
    stream.write(payload)
    return stream.getvalue()


def _build_prog_rom(start: int, payload: bytes) -> bytes:
    stream = io.BytesIO()
    stream.write(b"PROG")
    stream.write(struct.pack("<I", 1))

    # empty program name
    stream.write(struct.pack("<I", 0))

    stream.write(struct.pack("<I", start))
    stream.write(struct.pack("<I", len(payload)))
    stream.write(struct.pack("<I", 1))  # binary flag
    stream.write(payload)
    return stream.getvalue()


def test_app_load_program(tmp_path) -> None:
    rom_path = tmp_path / "rom.bin"
    rom_path.write_bytes(bytes(0x2000))

    prog_path = tmp_path / "sample.prog"
    prog_path.write_bytes(_build_prog_basic(b"\x01\x02\x03"))

    config = AppConfig(rom_path=rom_path, program_path=prog_path)
    machine = create_machine(MachineConfig(rom_image=rom_path.read_bytes()))
    app = JR100App(config)

    app._load_program(machine, prog_path)

    base = 0x0246
    for offset, value in enumerate(b"\x01\x02\x03"):
        assert machine.memory.load8(base + offset) == value


def test_app_accepts_prog_format_rom(tmp_path) -> None:
    payload = bytearray(0x2000)
    payload[0] = 0x01  # NOP opcode
    payload[-2] = 0xE0  # reset vector high byte
    payload[-1] = 0x00  # reset vector low byte

    rom_path = tmp_path / "jr100rom.prg"
    rom_path.write_bytes(_build_prog_rom(0xE000, bytes(payload)))

    app = JR100App(AppConfig(rom_path=rom_path))
    machine = app._create_machine(rom_path)

    assert machine.memory.load8(0xE000) == 0x01
    assert machine.cpu.state.pc == 0xE000
