"""JR-100 display model mirroring the Java implementation."""

from __future__ import annotations

from dataclasses import dataclass

from jr100_port.devices import BasicRom, UserDefinedCharacterRam, VideoRam


@dataclass(slots=True)
class Glyph:
    """Holds an 8x8 glyph encoded as eight bytes (MSB on the left)."""

    rows: tuple[int, ...]

    def line(self, index: int) -> int:
        return self.rows[index]


class JR100Display:
    FONT_NORMAL = 0
    FONT_USER_DEFINED = 1

    WIDTH_CHARS = 32
    HEIGHT_CHARS = 24
    PIXELS_PER_CHAR = 8

    def __init__(self, machine) -> None:
        self._machine = machine
        self._memory = machine.getHardware().getMemory()
        self._video_ram = self._memory.getMemory(VideoRam).getStartAddress()
        self._user_defined_ram = self._memory.getMemory(UserDefinedCharacterRam).getStartAddress()
        rom = self._memory.getMemory(BasicRom)
        self._character_rom = rom.get_font_address() if hasattr(rom, "get_font_address") else 0xE000

        self._color_map_bg = [0x000000] * 256
        self._color_map_fg = [0xFFFFFF] * 256

        self._rom_glyphs = self._load_rom_glyphs()
        self._current_plane = self.FONT_NORMAL

    @property
    def current_font_plane(self) -> int:
        return self._current_plane

    def setCurrentFont(self, plane: int) -> None:  # noqa: N802 - Java互換
        if plane not in (self.FONT_NORMAL, self.FONT_USER_DEFINED):
            return
        self._current_plane = plane

    # ------------------------------------------------------------------
    # Rendering helpers

    def resolve_glyph(self, code: int) -> tuple[Glyph, bool, int, int]:
        plane = self._current_plane
        if plane == self.FONT_NORMAL:
            if code < 128:
                glyph = self._rom_glyphs[code]
                inverted = False
                fg = self._color_map_fg[code]
                bg = self._color_map_bg[code]
            else:
                glyph = self._rom_glyphs[code - 128]
                inverted = True
                fg = self._color_map_bg[code - 128]
                bg = self._color_map_fg[code - 128]
        else:  # FONT_USER_DEFINED
            if code < 128:
                glyph = self._rom_glyphs[code]
                inverted = False
                fg = self._color_map_fg[code]
                bg = self._color_map_bg[code]
            else:
                glyph = self._load_user_glyph(code - 128)
                inverted = False
                fg = self._color_map_fg[code]
                bg = self._color_map_bg[code]
        return glyph, inverted, fg, bg

    def _load_rom_glyphs(self) -> tuple[Glyph, ...]:
        glyphs = []
        base = self._character_rom
        for code in range(128):
            rows = []
            for line in range(self.PIXELS_PER_CHAR):
                value = self._memory.load8(base + code * self.PIXELS_PER_CHAR + line)
                rows.append(value & 0xFF)
            glyphs.append(Glyph(tuple(rows)))
        return tuple(glyphs)

    def _load_user_glyph(self, index: int) -> Glyph:
        base = self._user_defined_ram + index * self.PIXELS_PER_CHAR
        rows = []
        for line in range(self.PIXELS_PER_CHAR):
            value = self._memory.load8(base + line)
            rows.append(value & 0xFF)
        return Glyph(tuple(rows))

    def update_font(self, code: int, line: int, value: int) -> None:
        # The renderer reads user-defined glyphs from memory on demand,
        # so no caching is required. This method is present to keep
        # compatibility with VideoRam/UserDefinedCharacterRam hooks.
        return

    def render_surface(self, surface, pygame_module, scale: int) -> None:
        surface.lock()
        try:
            for row in range(self.HEIGHT_CHARS):
                for col in range(self.WIDTH_CHARS):
                    code = self._memory.load8(self._video_ram + row * self.WIDTH_CHARS + col) & 0xFF
                    glyph, inverted, fg_color, bg_color = self.resolve_glyph(code)
                    self._blit_glyph(surface, pygame_module, col, row, glyph, inverted, fg_color, bg_color, scale)
        finally:
            surface.unlock()

    def _blit_glyph(
        self,
        surface,
        pygame_module,
        col: int,
        row: int,
        glyph: Glyph,
        inverted: bool,
        fg_color: int,
        bg_color: int,
        scale: int,
    ) -> None:
        fg_rgb = ((fg_color >> 16) & 0xFF, (fg_color >> 8) & 0xFF, fg_color & 0xFF)
        bg_rgb = ((bg_color >> 16) & 0xFF, (bg_color >> 8) & 0xFF, bg_color & 0xFF)
        for glyph_row in range(self.PIXELS_PER_CHAR):
            bits = glyph.line(glyph_row)
            if inverted:
                bits ^= 0xFF
            for glyph_col in range(self.PIXELS_PER_CHAR):
                mask = 1 << (7 - glyph_col)
                color = fg_rgb if bits & mask else bg_rgb
                x = col * self.PIXELS_PER_CHAR * scale + glyph_col * scale
                y = row * self.PIXELS_PER_CHAR * scale + glyph_row * scale
                pygame_module.draw.rect(
                    surface,
                    color,
                    (x, y, scale, scale),
                )


__all__ = ["JR100Display"]
