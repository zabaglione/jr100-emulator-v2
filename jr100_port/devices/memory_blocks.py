"""JR-100 memory blocks ported from the Java implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import struct

from jr100_port.core.memory import Addressable


class DisplayLike(Protocol):
    def update_font(self, char_index: int, row: int, value: int) -> None:
        ...


@dataclass
class Memory(Addressable):
    start: int
    length: int

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError("length must be positive")
        self.start &= 0xFFFF
        self.data = bytearray(self.length)

    def getStartAddress(self) -> int:  # noqa: N802
        return self.start

    def getEndAddress(self) -> int:  # noqa: N802
        return (self.start + self.length - 1) & 0xFFFF

    def _offset(self, address: int) -> int:
        offset = (address & 0xFFFF) - self.start
        if offset < 0 or offset >= self.length:
            raise IndexError(f"address {address:#06x} outside {self.start:#06x}-{self.getEndAddress():#06x}")
        return offset

    def load8(self, address: int) -> int:
        return self.data[self._offset(address)]

    def load16(self, address: int) -> int:
        high = self.load8(address)
        low = self.load8(address + 1)
        return ((high << 8) | low) & 0xFFFF

    def store8(self, address: int, value: int) -> None:
        self.data[self._offset(address)] = value & 0xFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)


class RAM(Memory):
    pass


class MainRam(RAM):
    pass


class ROM(Memory):
    def store8(self, address: int, value: int) -> None:  # noqa: ARG002 - read-only
        return None

    def store16(self, address: int, value: int) -> None:  # noqa: ARG002 - read-only
        return None


class BasicRom(ROM):
    SECTION_PNAM = 0x4D414E50  # "PNAM"
    SECTION_PBAS = 0x53414250  # "PBAS"
    SECTION_PBIN = 0x4E494250  # "PBIN"
    SECTION_CMNT = 0x544E4D43  # "CMNT"

    def __init__(self, filename: Optional[str | Path], start: int, length: int) -> None:
        super().__init__(start, length)
        if filename:
            self._load_from_path(Path(filename))

    def _load_from_path(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(path)
        blob = path.read_bytes()
        if blob.startswith(b"PROG"):
            self._load_prog(blob)
        else:
            self._load_raw(blob)

    def _load_raw(self, blob: bytes) -> None:
        size = min(len(blob), self.length)
        self.data[:size] = blob[:size]

    def _load_prog(self, blob: bytes) -> None:
        if len(blob) < 16:
            raise ValueError("PROG file truncated")
        version = struct.unpack_from("<I", blob, 4)[0]
        if version == 1:
            self._load_prog_v1(blob)
        elif version == 2:
            self._load_prog_v2(blob)
        else:
            raise ValueError(f"Unsupported PROG version: {version}")

    def _load_prog_v1(self, blob: bytes) -> None:
        offset = 8
        if offset + 4 > len(blob):
            raise ValueError("PROG name length missing")
        name_len = struct.unpack_from("<I", blob, offset)[0]
        offset += 4
        if offset + name_len > len(blob):
            raise ValueError("PROG name section truncated")
        offset += name_len

        if offset + 12 > len(blob):
            raise ValueError("PROG header truncated")
        start_addr = struct.unpack_from("<I", blob, offset)[0]
        offset += 4
        payload_length = struct.unpack_from("<I", blob, offset)[0]
        offset += 4
        offset += 4  # flag (unused)

        end = offset + payload_length
        if end > len(blob):
            raise ValueError("PROG payload truncated")
        payload = blob[offset:end]
        self._write_payload(start_addr, payload)

    def _load_prog_v2(self, blob: bytes) -> None:
        offset = 8
        length = len(blob)
        while offset + 8 <= length:
            section_id = struct.unpack_from("<I", blob, offset)[0]
            offset += 4
            section_length = struct.unpack_from("<I", blob, offset)[0]
            offset += 4
            end = offset + section_length
            if end > length:
                raise ValueError("PROG section truncated")
            payload = memoryview(blob)[offset:end]
            offset = end

            if section_id == self.SECTION_PBIN:
                self._parse_pbin_section(payload)
            # PBAS (BASIC area) and other sections are ignored for ROM purposes

        if offset != length:
            if any(blob[offset:]):
                raise ValueError("Unexpected trailing data in PROG file")

    def _parse_pbin_section(self, payload: memoryview) -> None:
        if len(payload) < 8:
            raise ValueError("PBIN section too short")
        start_addr = struct.unpack_from("<I", payload, 0)[0]
        data_length = struct.unpack_from("<I", payload, 4)[0]
        expected = 8 + data_length
        if data_length < 0 or expected > len(payload):
            raise ValueError("PBIN section truncated")
        data = payload[8:8 + data_length]
        self._write_payload(start_addr, data.tobytes())

    def _write_payload(self, start_addr: int, payload: bytes) -> None:
        rom_offset = start_addr - self.start
        if rom_offset < 0 or rom_offset + len(payload) > self.length:
            raise ValueError("PROG payload does not fit ROM region")
        self.data[rom_offset:rom_offset + len(payload)] = payload

    def get_font_address(self) -> int:
        return self.start


class UserDefinedCharacterRam(RAM):
    def __init__(self, start: int, length: int, display: DisplayLike | None) -> None:
        super().__init__(start, length)
        self.display = display

    def store8(self, address: int, value: int) -> None:
        super().store8(address, value)
        if self.display is None:
            return
        offset = self._offset(address)
        self.display.update_font(offset // 8, offset % 8, value & 0xFF)

    def store16(self, address: int, value: int) -> None:
        super().store16(address, value)
        if self.display is None:
            return
        offset = self._offset(address)
        self.display.update_font(offset // 8, offset % 8, (value >> 8) & 0xFF)
        self.display.update_font((offset + 1) // 8, (offset + 1) % 8, value & 0xFF)

    def set_display(self, display: DisplayLike) -> None:
        self.display = display


class VideoRam(RAM):
    def __init__(self, start: int, length: int, display: DisplayLike | None) -> None:
        super().__init__(start, length)
        self.display = display

    def _font_offset(self, address: int) -> int:
        # Java: display.updateFont((address - (start - 0x100)) / 8, ...)
        return self._offset(address) + 0x100

    def store8(self, address: int, value: int) -> None:
        super().store8(address, value)
        if self.display is None:
            return
        offset = self._font_offset(address)
        self.display.update_font(offset // 8, offset % 8, value & 0xFF)

    def store16(self, address: int, value: int) -> None:
        super().store16(address, value)
        if self.display is None:
            return
        offset = self._font_offset(address)
        self.display.update_font(offset // 8, offset % 8, (value >> 8) & 0xFF)
        self.display.update_font((offset + 1) // 8, (offset + 1) % 8, value & 0xFF)

    def set_display(self, display: DisplayLike) -> None:
        self.display = display


class ExtendedIOPort(Addressable):
    def __init__(self, computer, start: int, gamepad_state=None) -> None:  # noqa: ANN001
        self.computer = computer
        self.start = start & 0xFFFF
        self.end = (self.start + 0x3FF) & 0xFFFF
        self.gamepad_status = 0
        self._gamepad_state = gamepad_state

    def getStartAddress(self) -> int:  # noqa: N802
        return self.start

    def getEndAddress(self) -> int:  # noqa: N802
        return self.end

    def load8(self, address: int) -> int:
        if (address & 0xFFFF) == 0xCC02:
            if self._gamepad_state is not None:
                return self._gamepad_state.to_byte()
            return self.gamepad_status
        return 0

    def store8(self, address: int, value: int) -> None:
        if (address & 0xFFFF) == 0xCC02:
            self.gamepad_status = value & 0xFF

    def load16(self, address: int) -> int:
        addr = address & 0xFFFF
        if addr == 0xCC01:
            return self.gamepad_status & 0x00FF
        if addr == 0xCC02:
            return (self.gamepad_status << 8) & 0xFF00
        return 0

    def store16(self, address: int, value: int) -> None:
        return None

    def set_gamepad_state(self, state) -> None:
        self._gamepad_state = state


__all__ = [
    "MainRam",
    "VideoRam",
    "UserDefinedCharacterRam",
    "ExtendedIOPort",
    "BasicRom",
]
