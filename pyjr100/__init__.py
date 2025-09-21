"""Python port of the JR-100 emulator (skeleton package).

This package will host the CPU, memory, video, audio, and UI layers used by
``run.py``. Submodules are currently placeholders that will be filled as the
port progresses.
"""

from __future__ import annotations

from . import audio, bus, cpu, io, loader, rom, ui, utils, video

__all__: list[str] = [
    "cpu",
    "bus",
    "video",
    "audio",
    "io",
    "rom",
    "loader",
    "ui",
    "utils",
]
