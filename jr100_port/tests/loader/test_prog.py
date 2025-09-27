"""Tests for the JR-100 PROG loader."""

from __future__ import annotations

import io
import struct

import pytest

from jr100_port.core.memory import MemorySystem
from jr100_port.loader import (
    ADDRESS_START_OF_BASIC_PROGRAM,
    ProgFormatError,
    load_prog,
)


class DummyMemory:
    def __init__(self, start: int, length: int) -> None:
        self.start = start
        self.end = start + length - 1
        self.data = bytearray(length)

    def getStartAddress(self) -> int:
        return self.start

    def getEndAddress(self) -> int:
        return self.end

    def load8(self, address: int) -> int:
        return self.data[address - self.start]

    def load16(self, address: int) -> int:
        high = self.load8(address)
        low = self.load8(address + 1)
        return ((high << 8) | low) & 0xFFFF

    def store8(self, address: int, value: int) -> None:
        self.data[address - self.start] = value & 0xFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)


def make_memory_system() -> tuple[MemorySystem, DummyMemory]:
    ms = MemorySystem()
    ms.allocateSpace(0x10000)
    ram = DummyMemory(0x0000, 0x10000)
    ms.registMemory(ram)
    return ms, ram


def test_load_prog_v2_basic_section() -> None:
    ms, ram = make_memory_system()

    basic_data = bytes([0x01, 0x02, 0x03, 0x04])
    basic_start = ADDRESS_START_OF_BASIC_PROGRAM
    end_addr = basic_start + len(basic_data) - 1

    buf = io.BytesIO()
    buf.write(b"PROG")
    buf.write(struct.pack("<I", 2))

    name = b"HELLO"
    pnam_payload = struct.pack("<I", len(name)) + name
    buf.write(b"PNAM")
    buf.write(struct.pack("<I", len(pnam_payload)))
    buf.write(pnam_payload)

    pbas_payload = struct.pack("<I", len(basic_data)) + basic_data
    buf.write(b"PBAS")
    buf.write(struct.pack("<I", len(pbas_payload)))
    buf.write(pbas_payload)

    comment = b"Sample"
    cmnt_payload = struct.pack("<I", len(comment)) + comment
    buf.write(b"CMNT")
    buf.write(struct.pack("<I", len(cmnt_payload)))
    buf.write(cmnt_payload)

    buf.seek(0)
    program = load_prog(buf, ms)

    assert program.name == "HELLO"
    assert program.comment == "Sample"
    assert program.basic_area is True
    assert program.regions == []

    for index, value in enumerate(basic_data):
        assert ram.load8(basic_start + index) == value

    for offset in range(3):
        assert ram.load8(end_addr + 1 + offset) == 0xDF

    lowptr = (ram.load8(0x0002) << 8) | ram.load8(0x0003)
    assert lowptr == basic_start

    end_vector = (ram.load8(0x0006) << 8) | ram.load8(0x0007)
    assert end_vector == end_addr


def test_load_prog_v2_binary_sections() -> None:
    ms, ram = make_memory_system()

    data = bytes([0xAA, 0xBB, 0xCC])
    start_addr = 0x4000

    buf = io.BytesIO()
    buf.write(b"PROG")
    buf.write(struct.pack("<I", 2))

    comment = b"CODE"
    payload = (
        struct.pack("<I", start_addr)
        + struct.pack("<I", len(data))
        + data
        + struct.pack("<I", len(comment))
        + comment
    )
    buf.write(b"PBIN")
    buf.write(struct.pack("<I", len(payload)))
    buf.write(payload)

    buf.seek(0)
    program = load_prog(buf, ms)

    assert program.basic_area is False
    assert len(program.regions) == 1
    region = program.regions[0]
    assert region.start == start_addr
    assert region.end == start_addr + len(data) - 1
    assert region.comment == "CODE"

    for index, value in enumerate(data):
        assert ram.load8(start_addr + index) == value


def test_load_prog_v1_binary_flag() -> None:
    ms, ram = make_memory_system()

    payload = bytes([0x10, 0x20])
    start_addr = 0x6000

    buf = io.BytesIO()
    buf.write(b"PROG")
    buf.write(struct.pack("<I", 1))

    name = b"BIN"
    buf.write(struct.pack("<I", len(name)))
    buf.write(name)
    buf.write(struct.pack("<I", start_addr))
    buf.write(struct.pack("<I", len(payload)))
    buf.write(struct.pack("<I", 1))
    buf.write(payload)

    buf.seek(0)
    program = load_prog(buf, ms)

    assert program.name == "BIN"
    assert program.basic_area is False
    assert len(program.regions) == 1
    region = program.regions[0]
    assert region.start == start_addr
    assert region.end == start_addr + len(payload) - 1

    for index, value in enumerate(payload):
        assert ram.load8(start_addr + index) == value


def test_load_prog_invalid_magic_raises() -> None:
    ms, _ = make_memory_system()
    buf = io.BytesIO(b"XXXX" + struct.pack("<I", 2))

    with pytest.raises(ProgFormatError):
        load_prog(buf, ms)
