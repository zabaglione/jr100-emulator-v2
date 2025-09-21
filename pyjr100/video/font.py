"""8x8 font handling for JR-100 rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

FONT_WIDTH = 8
FONT_HEIGHT = 8
GLYPH_BYTES = FONT_HEIGHT


@dataclass
class FontSet:
    """Stores ROM font data for the JR-100."""

    rom: bytes

    def __init__(self, rom: bytes | None = None) -> None:
        if rom is None:
            rom = bytes(128 * GLYPH_BYTES)
        if len(rom) < 128 * GLYPH_BYTES:
            raise ValueError("ROM font must contain at least 128 glyphs")
        # Normal characters are 0x00-0x7F, inverse characters reuse ROM data.
        self.rom = rom[:128 * GLYPH_BYTES]

    def get_glyph(self, code: int, user_ram: bytes | None = None, plane: int = 0) -> Iterable[int]:
        """Return an iterable of eight bytes representing the glyph bitmap."""

        # Plane 1 uses user RAM for characters >= 0x80; others reuse ROM.
        if code >= 128:
            if user_ram is None:
                return [0] * GLYPH_BYTES
            offset = (code - 128) * GLYPH_BYTES
            if offset + GLYPH_BYTES > len(user_ram):
                return [0] * GLYPH_BYTES
            return user_ram[offset : offset + GLYPH_BYTES]

        offset = code * GLYPH_BYTES
        return self.rom[offset : offset + GLYPH_BYTES]

