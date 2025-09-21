"""Palette definitions for JR-100 rendering."""

from __future__ import annotations

from typing import Sequence, Tuple

RGBColor = Tuple[int, int, int]


MONOCHROME: Tuple[RGBColor, RGBColor] = ((0, 0, 0), (0xFF, 0xFF, 0xFF))


def validate_palette(palette: Sequence[RGBColor]) -> Tuple[RGBColor, RGBColor]:
    if len(palette) != 2:
        raise ValueError("palette must contain exactly two colours (background and foreground)")
    if any(len(color) != 3 for color in palette):
        raise ValueError("palette entries must be RGB tuples")
    return tuple(tuple(int(channel) & 0xFF for channel in color) for color in palette)  # type: ignore[return-value]

