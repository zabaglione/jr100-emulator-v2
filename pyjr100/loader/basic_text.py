"""Loader for JR-100 BASIC source (text) files."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterable, TextIO

from pyjr100.bus import MemorySystem

from .prog import ADDRESS_START_OF_BASIC_PROGRAM, SENTINEL_VALUE
from .program import ProgramImage


class BasicTextFormatError(RuntimeError):
    """Raised when a BASIC text file cannot be parsed."""


MAX_LINE_LENGTH = 72
MIN_LINE_NUMBER = 1
MAX_LINE_NUMBER = 32_767
BASIC_MEMORY_END = 0x7FFF
_HEX_PAIR = re.compile(r"^[0-9A-F]{2}$")


def load_basic_text(handle: TextIO, memory: MemorySystem) -> ProgramImage:
    """Load a JR-100 BASIC text program from ``handle`` into ``memory``."""

    program = ProgramImage()
    program.basic_area = True

    address = ADDRESS_START_OF_BASIC_PROGRAM
    for raw_line in handle:
        line = _canonicalize_line(raw_line)
        if not line:
            continue

        line_number, body = _split_line_number(line)
        if not MIN_LINE_NUMBER <= line_number <= MAX_LINE_NUMBER:
            raise BasicTextFormatError(f"Invalid line number: {line_number}")

        remaining = body.lstrip()

        _ensure_capacity(address, 2)
        memory.store16(address, line_number)
        address += 2
        line_length = 2

        for byte in _iter_line_bytes(remaining, raw_line.rstrip("\r\n")):
            _ensure_capacity(address, 1)
            memory.store8(address, byte)
            address += 1
            line_length += 1

        if line_length > MAX_LINE_LENGTH:
            raise BasicTextFormatError(f"Line too long (>{MAX_LINE_LENGTH} bytes): {raw_line.rstrip()}")

        _ensure_capacity(address, 1)
        memory.store8(address, 0x00)
        address += 1

    end_pointer = address + 1
    _ensure_capacity(address, 3)
    for _ in range(3):
        memory.store8(address, SENTINEL_VALUE)
        address += 1

    _write_basic_vectors(memory, ADDRESS_START_OF_BASIC_PROGRAM, end_pointer)

    return program


def load_basic_text_from_path(path: Path, memory: MemorySystem, *, encoding: str = "utf-8") -> ProgramImage:
    """Load a JR-100 BASIC text program from ``path``."""

    with path.open("r", encoding=encoding) as handle:
        return load_basic_text(handle, memory)


def _canonicalize_line(line: str) -> str:
    return line.strip().upper()


def _split_line_number(line: str) -> tuple[int, str]:
    index = 0
    for char in line:
        if not char.isdigit():
            break
        index += 1

    if index == 0:
        raise BasicTextFormatError("Line number is missing")

    try:
        number = int(line[:index])
    except ValueError as exc:  # pragma: no cover - defensive
        raise BasicTextFormatError("Line number is not numeric") from exc

    return number, line[index:]


def _iter_line_bytes(content: str, original: str) -> Iterable[int]:
    idx = 0
    length = len(content)
    while idx < length:
        char = content[idx]
        if char == "\\":
            if idx + 2 >= length:
                raise BasicTextFormatError(f"Incomplete escape at end of line: {original}")
            pair = content[idx + 1 : idx + 3]
            if not _HEX_PAIR.match(pair):
                raise BasicTextFormatError(f"Invalid escape sequence '\\{pair}' in line: {original}")
            yield int(pair, 16)
            idx += 3
        else:
            yield ord(char) & 0xFF
            idx += 1


def _ensure_capacity(address: int, needed: int) -> None:
    if address + needed - 1 > BASIC_MEMORY_END:
        raise BasicTextFormatError("BASIC program exceeds available memory")


def _write_basic_vectors(memory: MemorySystem, start_addr: int, end_addr: int) -> None:
    for offset, value in ((0x0002, start_addr), (0x0004, start_addr)):
        memory.store8(offset, (value >> 8) & 0xFF)
        memory.store8(offset + 1, value & 0xFF)

    addresses = [
        (0x0006, end_addr),
        (0x0008, end_addr + 1),
        (0x000A, end_addr + 2),
        (0x000C, end_addr + 3),
    ]
    for addr, value in addresses:
        memory.store8(addr, (value >> 8) & 0xFF)
        memory.store8(addr + 1, value & 0xFF)
