"""8x8 font handling for JR-100 rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .font_manager import FontManager

FONT_WIDTH = 8
FONT_HEIGHT = 8
GLYPH_BYTES = FONT_HEIGHT


@dataclass
class FontSet:
    """Stores ROM font data for the JR-100."""

    rom: bytes
    font_manager: FontManager | None

    def __init__(self, rom: bytes | None = None, font_manager: FontManager | None = None) -> None:
        if rom is None:
            rom = bytes(128 * GLYPH_BYTES)
        if len(rom) < 128 * GLYPH_BYTES:
            raise ValueError("ROM font must contain at least 128 glyphs")
        self.rom = rom[:128 * GLYPH_BYTES]
        self.font_manager = font_manager

    def get_glyph(
        self,
        value: int,
        user_ram: bytes | None = None,
        plane: int = 0,
        font_manager: FontManager | None = None,
    ) -> Iterable[int]:
        """Return an iterable of eight bytes representing the glyph bitmap."""

        value &= 0xFF
        code = value & 0x7F

        manager = font_manager or self.font_manager
        if plane == 1 and manager is not None:
            glyph = manager.get_plane1_glyph(value)
            if glyph is not None:
                return glyph

        offset = code * GLYPH_BYTES
        return self.rom[offset : offset + GLYPH_BYTES]
