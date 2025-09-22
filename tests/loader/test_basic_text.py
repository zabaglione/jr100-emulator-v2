"""Tests for the BASIC text loader."""

from __future__ import annotations

import io

import pytest

from pyjr100.bus import Memory, MemorySystem
from pyjr100.loader import BasicTextFormatError, load_basic_text


def make_memory_system() -> tuple[MemorySystem, Memory]:
    ms = MemorySystem()
    ms.allocate_space(0x10000)
    ram = Memory(0x0000, 0x10000)
    ms.register_memory(ram)
    return ms, ram


def test_load_basic_text_stores_program_and_updates_pointers() -> None:
    ms, ram = make_memory_system()

    source = io.StringIO("10 print \"hi\"\n20 \\81end\n")
    program = load_basic_text(source, ms)

    assert program.basic_area is True

    start = 0x0246
    expected = (
        [0x00, 0x0A]
        + list(b"PRINT \"HI\"")
        + [0x00]
        + [0x00, 0x14]
        + [0x81]
        + list(b"END")
        + [0x00]
    )

    for offset, value in enumerate(expected):
        assert ram.load8(start + offset) == value

    end_pointer = (ram.load8(0x0006) << 8) | ram.load8(0x0007)
    for idx in range(3):
        assert ram.load8(end_pointer - 1 + idx) == 0xDF

    assert (ram.load8(0x0002) << 8 | ram.load8(0x0003)) == 0x0246
    assert (ram.load8(0x0004) << 8 | ram.load8(0x0005)) == 0x0246

    assert (ram.load8(0x0008) << 8 | ram.load8(0x0009)) == end_pointer + 1


def test_load_basic_text_rejects_missing_line_number() -> None:
    ms, _ = make_memory_system()
    source = io.StringIO("PRINT 1")
    with pytest.raises(BasicTextFormatError):
        load_basic_text(source, ms)


def test_load_basic_text_rejects_incomplete_escape() -> None:
    ms, _ = make_memory_system()
    source = io.StringIO("10 A\\")
    with pytest.raises(BasicTextFormatError):
        load_basic_text(source, ms)


def test_load_basic_text_enforces_line_length() -> None:
    ms, _ = make_memory_system()
    payload = "A" * 71  # 71 characters + 2 bytes for line number = 73 > 72
    source = io.StringIO(f"10 {payload}")
    with pytest.raises(BasicTextFormatError):
        load_basic_text(source, ms)
