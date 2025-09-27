"""Unit tests for the JR-100 video renderer."""

from __future__ import annotations

import pytest

from pyjr100.video import FontSet, Renderer, FontManager
from pyjr100.video.font import GLYPH_BYTES
from pyjr100.video.font_manager import UDC_START, VRAM_FONT_START


def build_font(pattern: int) -> bytes:
    data = bytearray(128 * GLYPH_BYTES)
    for line in range(GLYPH_BYTES):
        data[1 * GLYPH_BYTES + line] = pattern
    return bytes(data)


def test_render_single_character() -> None:
    font = FontSet(build_font(0b11110000))
    renderer = Renderer(font)
    vram = bytes([1] + [0] * (32 * 24 - 1))
    result = renderer.render(vram)

    assert result.width == 256
    assert result.height == 192

    # Upper-left glyph should render four white columns followed by four black columns.
    white = (255, 255, 255)
    black = (0, 0, 0)
    for y in range(8):
        assert result.get_pixel(0, y) == white
        assert result.get_pixel(3, y) == white
        assert result.get_pixel(4, y) == black


def test_render_inverted_character() -> None:
    font = FontSet(build_font(0b11110000))
    renderer = Renderer(font)
    vram = bytes([0x81] + [0] * (32 * 24 - 1))
    result = renderer.render(vram)

    # Inverted: first column black, last column white.
    assert result.get_pixel(0, 0) == (0, 0, 0)
    assert result.get_pixel(7, 0) == (255, 255, 255)


def test_render_scale_factor() -> None:
    font = FontSet(build_font(0b10000001))
    renderer = Renderer(font)
    vram = bytes([1] + [0] * (32 * 24 - 1))
    result = renderer.render(vram, scale=2)

    assert result.width == 512
    assert result.height == 384
    assert result.get_pixel(0, 0) == (255, 255, 255)
    assert result.get_pixel(1, 0) == (255, 255, 255)
    assert result.get_pixel(15, 0) == (255, 255, 255)
    assert result.get_pixel(16, 0) == (0, 0, 0)


def test_user_plane_uses_specific_udc_ranges() -> None:
    rom = bytes([i % 256 for i in range(128 * GLYPH_BYTES)])
    manager = FontManager()
    manager.initialize_rom(rom)
    font = FontSet(rom, manager)

    def write_udc(code: int, value: int) -> None:
        index = code - 0x80
        for line in range(GLYPH_BYTES):
            manager.update_udc(UDC_START + index * GLYPH_BYTES + line, value)

    def write_vram(code: int, value: int) -> None:
        index = code - 0xA0
        for line in range(GLYPH_BYTES):
            addr = VRAM_FONT_START + index * GLYPH_BYTES + line
            manager.update_vram_font(addr, value)

    write_udc(0x80, 0x11)
    write_vram(0xA0, 0x22)
    write_vram(0xB3, 0x33)

    glyph_rom = tuple(font.get_glyph(0x20, plane=1, font_manager=manager))
    assert glyph_rom == tuple(rom[0x20 * GLYPH_BYTES : (0x20 + 1) * GLYPH_BYTES])

    glyph_udc = tuple(font.get_glyph(0x80, plane=1, font_manager=manager))
    assert glyph_udc == tuple([0x11] * GLYPH_BYTES)

    glyph_vram = tuple(font.get_glyph(0xA0, plane=1, font_manager=manager))
    assert glyph_vram == tuple([0x22] * GLYPH_BYTES)


def test_user_plane_falls_back_when_udc_blank() -> None:
    rom = bytes([i % 256 for i in range(128 * GLYPH_BYTES)])
    manager = FontManager()
    manager.initialize_rom(rom)
    font = FontSet(rom, manager)

    glyph_20 = tuple(font.get_glyph(0x20, plane=1, font_manager=manager))
    assert glyph_20 == tuple(rom[0x20 * GLYPH_BYTES : (0x20 + 1) * GLYPH_BYTES])

    glyph_60 = tuple(font.get_glyph(0x60, plane=1, font_manager=manager))
    assert glyph_60 == tuple(rom[0x60 * GLYPH_BYTES : (0x60 + 1) * GLYPH_BYTES])
