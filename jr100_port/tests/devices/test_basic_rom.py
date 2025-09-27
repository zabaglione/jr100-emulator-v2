import struct
from pathlib import Path

import pytest

from jr100_port.devices import BasicRom


def create_prog_payload(start: int, payload: bytes, name: bytes = b"BASICROM") -> bytes:
    data = bytearray()
    data += b"PROG"
    data += struct.pack("<I", 1)
    data += struct.pack("<I", len(name))
    data += name
    data += struct.pack("<I", start)
    data += struct.pack("<I", len(payload))
    data += struct.pack("<I", 1)
    data += payload
    return bytes(data)


def test_basic_rom_loads_prog(tmp_path: Path) -> None:
    payload = bytes(range(16))
    prog = create_prog_payload(0xE000, payload)
    rom_path = tmp_path / "rom.prg"
    rom_path.write_bytes(prog)

    rom = BasicRom(rom_path, 0xE000, 0x2000)

    assert rom.load8(0xE000) == payload[0]
    assert rom.load8(0xE00F) == payload[-1]


def test_basic_rom_fallback_raw(tmp_path: Path) -> None:
    raw = bytes(range(32))
    rom_path = tmp_path / "rom.bin"
    rom_path.write_bytes(raw)

    rom = BasicRom(rom_path, 0xE000, 0x2000)

    assert rom.load8(0xE000) == 0
    assert rom.load8(0xE01F) == 31


def test_basic_rom_rejects_out_of_range_prog(tmp_path: Path) -> None:
    payload = bytes(range(8))
    prog = create_prog_payload(0xD000, payload)
    rom_path = tmp_path / "rom_bad.prg"
    rom_path.write_bytes(prog)

    with pytest.raises(ValueError):
        BasicRom(rom_path, 0xE000, 0x2000)


def test_basic_rom_loads_prog_v2_pbin(tmp_path: Path) -> None:
    def make_section(tag: bytes, payload: bytes) -> bytes:
        return struct.pack("<I", int.from_bytes(tag, "little")) + struct.pack("<I", len(payload)) + payload

    name_payload = b"ROMV2\x00"
    pnam_payload = struct.pack("<I", len(name_payload)) + name_payload
    pbin_payload = (
        struct.pack("<I", 0xE100)
        + struct.pack("<I", 4)
        + bytes([0xAA, 0xBB, 0xCC, 0xDD])
    )

    prog = b"PROG" + struct.pack("<I", 2) + make_section(b"PNAM", pnam_payload) + make_section(b"PBIN", pbin_payload)
    rom_path = tmp_path / "rom_v2.prg"
    rom_path.write_bytes(prog)

    rom = BasicRom(rom_path, 0xE000, 0x2000)

    assert rom.load8(0xE100) == 0xAA
    assert rom.load8(0xE103) == 0xDD
