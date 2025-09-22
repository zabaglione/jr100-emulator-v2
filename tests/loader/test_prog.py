"""Tests for the PROG loader implementation."""

from __future__ import annotations

import io
import struct

import pytest

from pyjr100.bus import Memory, MemorySystem
from pyjr100.loader import ProgFormatError, load_prog


def make_memory_system() -> tuple[MemorySystem, Memory]:
    ms = MemorySystem()
    ms.allocate_space(0x10000)
    ram = Memory(0x0000, 0x10000)
    ms.register_memory(ram)
    return ms, ram


def test_load_prog_v2_basic_section() -> None:
    ms, ram = make_memory_system()

    basic_data = bytes([0x01, 0x02, 0x03, 0x04])
    basic_start = 0x0246
    end_addr = basic_start + len(basic_data) - 1

    buf = io.BytesIO()
    buf.write(b"PROG")
    buf.write(struct.pack("<I", 2))

    # PNAM
    name = b"HELLO"
    pnam_payload = struct.pack("<I", len(name)) + name
    buf.write(b"PNAM")
    buf.write(struct.pack("<I", len(pnam_payload)))
    buf.write(pnam_payload)

    # PBAS
    pbas_payload = struct.pack("<I", len(basic_data)) + basic_data
    buf.write(b"PBAS")
    buf.write(struct.pack("<I", len(pbas_payload)))
    buf.write(pbas_payload)

    # CMNT
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

    assert ram.load8(0x0006) == (end_addr >> 8) & 0xFF
    assert ram.load8(0x0007) == end_addr & 0xFF
    assert ram.load8(0x0008) == ((end_addr + 1) >> 8) & 0xFF
    assert ram.load8(0x0009) == (end_addr + 1) & 0xFF
    assert ram.load8(0x000A) == ((end_addr + 2) >> 8) & 0xFF
    assert ram.load8(0x000B) == (end_addr + 2) & 0xFF
    assert ram.load8(0x000C) == ((end_addr + 3) >> 8) & 0xFF
    assert ram.load8(0x000D) == (end_addr + 3) & 0xFF


def test_load_prog_v2_binary_sections() -> None:
    ms, ram = make_memory_system()

    data = bytes([0xAA, 0xBB, 0xCC])
    start_addr = 0x4000

    buf = io.BytesIO()
    buf.write(b"PROG")
    buf.write(struct.pack("<I", 2))

    # PBIN section with comment
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


def test_load_prog_v2_binary_section_without_comment() -> None:
    ms, ram = make_memory_system()

    data = bytes(range(1, 9))
    start_addr = 0x6000

    buf = io.BytesIO()
    buf.write(b"PROG")
    buf.write(struct.pack("<I", 2))

    payload = (
        struct.pack("<I", start_addr)
        + struct.pack("<I", len(data))
        + data
    )
    buf.write(b"PBIN")
    buf.write(struct.pack("<I", len(payload)))
    buf.write(payload)

    buf.seek(0)
    program = load_prog(buf, ms)

    assert len(program.regions) == 1
    region = program.regions[0]
    assert region.start == start_addr
    assert region.end == start_addr + len(data) - 1
    assert region.comment == ""

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
    buf.write(struct.pack("<I", 1))  # flag != 0 -> binary
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
