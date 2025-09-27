"""Font cache management mirroring the Java emulator behaviour."""

from __future__ import annotations

from dataclasses import dataclass, field

UDC_START = 0xC000
UDC_LENGTH = 0x0100
VRAM_FONT_START = 0xC100
VRAM_FONT_LENGTH = 0x0300
GLYPH_BYTES = 8


@dataclass
class FontManager:
    """Maintain CMODE1/UDC glyph data similar to the Java implementation."""

    _plane1: bytearray = field(default_factory=lambda: bytearray(256 * GLYPH_BYTES))
    _revision: int = 0

    def initialize_rom(self, rom_bytes: bytes) -> None:
        """Populate plane1 glyphs for codes 0x00-0x7F from ROM."""

        length = min(len(rom_bytes), 128 * GLYPH_BYTES)
        self._plane1[:length] = rom_bytes[:length]
        self._revision += 1

    def update_udc(self, address: int, value: int) -> None:
        if not 0 <= value <= 0xFF:
            raise ValueError("font byte out of range")
        offset = address - UDC_START
        if not 0 <= offset < UDC_LENGTH:
            return
        glyph = offset // GLYPH_BYTES
        line = offset % GLYPH_BYTES
        code = 0x80 + glyph
        index = code * GLYPH_BYTES + line
        self._plane1[index] = value & 0xFF
        self._revision += 1

    def update_vram_font(self, address: int, value: int) -> None:
        if not 0 <= value <= 0xFF:
            raise ValueError("font byte out of range")
        offset = address - VRAM_FONT_START
        if not 0 <= offset < VRAM_FONT_LENGTH:
            return
        glyph = offset // GLYPH_BYTES
        if glyph >= 96:
            return
        line = offset % GLYPH_BYTES
        code = 0xA0 + glyph
        index = code * GLYPH_BYTES + line
        self._plane1[index] = value & 0xFF
        self._revision += 1

    def sync_from_memory(self, vram: bytes, udc: bytes) -> None:
        self._sync_udc(udc)
        self._sync_vram(vram)

    def _sync_udc(self, udc: bytes) -> None:
        length = min(len(udc), 0x20 * GLYPH_BYTES)
        start = 0x80 * GLYPH_BYTES
        self._plane1[start : start + length] = udc[:length]
        self._revision += 1

    def _sync_vram(self, vram: bytes) -> None:
        length = min(len(vram), VRAM_FONT_LENGTH)
        glyph_count = min(length // GLYPH_BYTES, 96)
        for glyph in range(glyph_count):
            start = glyph * GLYPH_BYTES
            code = 0xA0 + glyph
            index = code * GLYPH_BYTES
            self._plane1[index : index + GLYPH_BYTES] = vram[start : start + GLYPH_BYTES]
        self._revision += 1

    def cmode1_bank(self) -> bytes:
        """Return a snapshot of the CMODE1 glyph plane."""

        return bytes(self._plane1)

    def get_plane1_glyph(self, code: int) -> bytes | None:
        if not 0 <= code < 256:
            return None
        start = code * GLYPH_BYTES
        glyph = self._plane1[start : start + GLYPH_BYTES]
        if code < 0x80 or any(glyph):
            return bytes(glyph)
        return None

    @property
    def revision(self) -> int:
        return self._revision
