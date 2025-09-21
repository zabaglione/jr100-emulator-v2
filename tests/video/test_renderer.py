"""Unit tests for the JR-100 video renderer."""

from __future__ import annotations

import pytest

from pyjr100.video import FontSet, Renderer


def build_font(pattern: int) -> bytes:
    data = bytearray(128 * 8)
    for line in range(8):
        data[1 * 8 + line] = pattern
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

