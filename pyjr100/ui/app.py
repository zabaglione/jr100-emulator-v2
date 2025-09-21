"""Pygame application bootstrap placeholder for the JR-100 emulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pyjr100.system import MachineConfig, create_machine
from pyjr100.video import FontSet, Renderer


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
        self._running = False

    def run(self) -> None:
        try:
            import pygame  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pygame is required to run the UI") from exc

        pygame.init()
        pygame.display.set_caption("JR-100 Emulator (Python WIP)")

        rom_image = None
        if self._config.rom_path:
            rom_image = self._config.rom_path.read_bytes()

        machine = create_machine(MachineConfig(rom_image=rom_image))
        renderer = Renderer(FontSet())

        surface_size = (32 * 8 * self._config.scale, 24 * 8 * self._config.scale)
        flags = pygame.FULLSCREEN if self._config.fullscreen else 0
        screen = pygame.display.set_mode(surface_size, flags)

        clock = pygame.time.Clock()
        self._running = True

        self._initialize_screen(machine)

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._running = False

            vram_bytes = machine.video_ram.snapshot()
            user_chars = machine.udc_ram.snapshot()
            frame = renderer.render(vram_bytes, user_ram=user_chars, scale=self._config.scale)

            pygame_surface = frame.to_surface()
            screen.blit(pygame_surface, (0, 0))
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()

    def _initialize_screen(self, machine) -> None:
        base = machine.video_ram.get_start_address()
        message = "JR-100 PY PORT"
        for idx, char in enumerate(message):
            machine.memory.store8(base + idx, ord(char) & 0x7F)
        # Fill the rest of the line with spaces.
        for idx in range(len(message), 32):
            machine.memory.store8(base + idx, 0x20)
