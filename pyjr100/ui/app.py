"""Pygame application bootstrap placeholder for the JR-100 emulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    """Configuration for the eventual JR-100 emulator frontend."""

    rom_path: Optional[Path] = None
    scale: int = 2
    fullscreen: bool = False


class JR100App:
    """Thin wrapper around the Pygame event loop (not yet implemented)."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def run(self) -> None:
        """Entry-point for the Pygame UI.

        The real implementation will initialize Pygame, wire devices, and drive
        the emulation loop. For now, this method simply raises ``NotImplementedError``
        to make the missing functionality explicit.
        """

        raise NotImplementedError("JR-100 UI loop not yet implemented")
