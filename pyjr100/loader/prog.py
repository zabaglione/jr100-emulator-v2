"""PROG format loader for JR-100 program images."""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import BinaryIO, Optional

from pyjr100.bus import MemorySystem

from .program import ProgramImage


class ProgFormatError(RuntimeError):
    """Raised when a PROG file violates the expected structure."""


MAGIC = 0x474F5250  # "PROG"
MIN_VERSION = 1
MAX_VERSION = 2

SECTION_PNAM = 0x4D414E50  # "PNAM"
SECTION_PBAS = 0x53414250  # "PBAS"
SECTION_PBIN = 0x4E494250  # "PBIN"
SECTION_CMNT = 0x544E4D43  # "CMNT"

PROG_MAX_PROGRAM_NAME_LENGTH = 256
PROG_MAX_PROGRAM_LENGTH = 65_536
PROG_MAX_COMMENT_LENGTH = 1_024
PROG_MAX_BINARY_SECTIONS = 256

ADDRESS_START_OF_BASIC_PROGRAM = 0x0246
SENTINEL_VALUE = 0xDF


def load_prog(stream: BinaryIO, memory: MemorySystem) -> ProgramImage:
    """Load a PROG image from ``stream`` into ``memory`` and return metadata."""

    loader = _ProgLoader(stream, memory)
    return loader.load()


def load_prog_from_path(path: Path, memory: MemorySystem) -> ProgramImage:
    """Load a PROG image from the filesystem."""

    with path.open("rb") as handle:
        return load_prog(handle, memory)


class _ProgLoader:
    def __init__(self, stream: BinaryIO, memory: MemorySystem) -> None:
        self._stream = stream
        self._memory = memory

    def load(self) -> ProgramImage:
        magic = self._read_u32_optional()
        if magic is None or magic != MAGIC:
            raise ProgFormatError("Invalid PROG magic header")

        version = self._read_u32()
        if version < MIN_VERSION or version > MAX_VERSION:
            raise ProgFormatError(f"Unsupported PROG version: {version}")

        program = ProgramImage()

        if version == 1:
            self._load_v1(program)
        else:
            self._load_v2(program)

        return program

    def _load_v1(self, program: ProgramImage) -> None:
        name = self._read_string(PROG_MAX_PROGRAM_NAME_LENGTH)
        start_addr = self._read_u32()
        length = self._read_u32()
        flag = self._read_u32()

        self._validate_bounds(start_addr, length)
        payload = self._read_exact(length)
        self._write_block(start_addr, payload)

        program.name = name

        end_addr = start_addr + length - 1 if length else start_addr - 1
        if flag == 0:
            if length:
                self._write_basic_trailer(end_addr)
            program.basic_area = True
        else:
            if length:
                program.add_region(start_addr, end_addr)

    def _load_v2(self, program: ProgramImage) -> None:
        binary_sections = 0

        while True:
            section_id = self._read_u32_optional()
            if section_id is None:
                break

            section_length = self._read_u32()
            section_payload = self._read_exact(section_length)
            reader = io.BytesIO(section_payload)

            if section_id == SECTION_PNAM:
                program.name = self._read_string_from(reader, PROG_MAX_PROGRAM_NAME_LENGTH)
                self._ensure_consumed(reader)
            elif section_id == SECTION_PBAS:
                program_length = self._read_u32_from(reader)
                self._validate_bounds(ADDRESS_START_OF_BASIC_PROGRAM, program_length)
                payload = self._read_exact_from(reader, program_length)
                self._write_block(ADDRESS_START_OF_BASIC_PROGRAM, payload)

                end_addr = ADDRESS_START_OF_BASIC_PROGRAM + program_length - 1 if program_length else ADDRESS_START_OF_BASIC_PROGRAM - 1
                if program_length:
                    self._write_basic_trailer(end_addr)
                program.basic_area = True

                self._ensure_consumed(reader)
            elif section_id == SECTION_PBIN:
                if binary_sections >= PROG_MAX_BINARY_SECTIONS:
                    continue

                start_addr = self._read_u32_from(reader)
                data_length = self._read_u32_from(reader)
                self._validate_bounds(start_addr, data_length)
                payload = self._read_exact_from(reader, data_length)
                self._write_block(start_addr, payload)
                comment = self._read_string_from(reader, PROG_MAX_COMMENT_LENGTH)
                program.add_region(start_addr, start_addr + data_length - 1, comment)

                binary_sections += 1
                self._ensure_consumed(reader)
            elif section_id == SECTION_CMNT:
                program.comment = self._read_string_from(reader, PROG_MAX_COMMENT_LENGTH)
                self._ensure_consumed(reader)
            else:
                # Unknown sections are skipped; payload already consumed.
                continue

    def _write_block(self, start_addr: int, payload: bytes) -> None:
        for offset, value in enumerate(payload):
            self._memory.store8(start_addr + offset, value)

    def _write_basic_trailer(self, end_addr: int) -> None:
        sentinel_base = end_addr + 1
        for offset in range(3):
            self._memory.store8(sentinel_base + offset, SENTINEL_VALUE)

        addresses = [
            (0x0006, end_addr),
            (0x0008, end_addr + 1),
            (0x000A, end_addr + 2),
            (0x000C, end_addr + 3),
        ]
        for addr, value in addresses:
            self._memory.store8(addr, (value >> 8) & 0xFF)
            self._memory.store8(addr + 1, value & 0xFF)

    def _validate_bounds(self, start: int, length: int) -> None:
        if length < 0:
            raise ProgFormatError("Negative length in PROG payload")
        if start < 0:
            raise ProgFormatError("Negative start address in PROG payload")
        if start + length > PROG_MAX_PROGRAM_LENGTH:
            raise ProgFormatError("PROG payload exceeds address space")

    def _ensure_consumed(self, reader: io.BytesIO) -> None:
        leftover = reader.read(1)
        if leftover:
            raise ProgFormatError("Section length mismatch in PROG payload")

    def _read_u32_optional(self) -> Optional[int]:
        data = self._stream.read(4)
        if not data:
            return None
        if len(data) < 4:
            raise ProgFormatError("Unexpected end of PROG file")
        return struct.unpack("<I", data)[0]

    def _read_u32(self) -> int:
        data = self._stream.read(4)
        if len(data) < 4:
            raise ProgFormatError("Unexpected end of PROG file")
        return struct.unpack("<I", data)[0]

    def _read_exact(self, length: int) -> bytes:
        data = self._stream.read(length)
        if len(data) < length:
            raise ProgFormatError("Unexpected end of PROG file")
        return data

    def _read_string(self, max_length: int) -> str:
        length = self._read_u32()
        if length > max_length:
            raise ProgFormatError("String exceeds maximum length in PROG file")
        data = self._read_exact(length)
        return data.decode("utf-8") if length else ""

    def _read_u32_from(self, reader: io.BytesIO) -> int:
        data = reader.read(4)
        if len(data) < 4:
            raise ProgFormatError("Unexpected end of section data")
        return struct.unpack("<I", data)[0]

    def _read_exact_from(self, reader: io.BytesIO, length: int) -> bytes:
        data = reader.read(length)
        if len(data) < length:
            raise ProgFormatError("Unexpected end of section data")
        return data

    def _read_string_from(self, reader: io.BytesIO, max_length: int) -> str:
        length = self._read_u32_from(reader)
        if length > max_length:
            raise ProgFormatError("String exceeds maximum length in section")
        data = self._read_exact_from(reader, length)
        return data.decode("utf-8") if length else ""

