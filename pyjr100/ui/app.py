"""Pygame application bootstrap placeholder for the JR-100 emulator."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pyjr100.system import Machine, MachineConfig, create_machine
from pyjr100.video import FontSet, Renderer
from pyjr100.video.font import GLYPH_BYTES
from pyjr100.cpu import IllegalOpcodeError
from pyjr100.utils import debug_log, debug_enabled


@dataclass
class AppConfig:
    """Configuration for the eventual JR-100 emulator frontend."""

    rom_path: Optional[Path] = None
    program_path: Optional[Path] = None
    scale: int = 2
    fullscreen: bool = False


class JR100App:
    """Thin wrapper around the Pygame event loop (not yet implemented)."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._running = False
        self._keyboard = None
        self._font_plane = 0
        self._buzzer_enabled = False
        self._buzzer_frequency = 0.0
        self._machine: Machine | None = None

    def run(self) -> None:
        try:
            import pygame  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pygame is required to run the UI") from exc

        pygame.init()
        pygame.display.set_caption("JR-100 Emulator (Python WIP)")

        if not self._config.rom_path:
            raise RuntimeError("ROM image is required; pass --rom <path>")
        rom_path = self._config.rom_path
        if not rom_path.exists():
            raise RuntimeError(f"ROM file not found: {rom_path}")

        machine = self._create_machine(rom_path)
        self._machine = machine
        renderer = Renderer(self._build_font_set(machine))

        surface_size = (32 * 8 * self._config.scale, 24 * 8 * self._config.scale)
        flags = pygame.FULLSCREEN if self._config.fullscreen else 0
        screen = pygame.display.set_mode(surface_size, flags)

        clock = pygame.time.Clock()
        self._running = True
        self._keyboard = machine.keyboard

        if self._config.program_path is not None:
            self._load_program(machine, self._config.program_path)

        self._initialize_screen(machine)

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key_event(pygame, event.key, pressed=True)
                elif event.type == pygame.KEYUP:
                    self._handle_key_event(pygame, event.key, pressed=False)

            self._step_cpu(machine)

            vram_bytes = machine.video_ram.snapshot()
            user_chars = machine.udc_ram.snapshot()
            frame = renderer.render(
                vram_bytes,
                user_ram=user_chars,
                plane=self._font_plane,
                scale=self._config.scale,
            )

            pygame_surface = frame.to_surface()
            screen.blit(pygame_surface, (0, 0))
            pygame.display.flip()
            clock.tick(_FRAME_RATE)

        pygame.quit()

    def _initialize_screen(self, machine) -> None:
        base = machine.video_ram.get_start_address()
        message = "JR-100 PY PORT"
        for idx, char in enumerate(message):
            machine.memory.store8(base + idx, ord(char) & 0x7F)
        # Fill the rest of the line with spaces.
        for idx in range(len(message), 32):
            machine.memory.store8(base + idx, 0x20)

    def _handle_key_event(self, pygame, key_code: int, *, pressed: bool) -> None:
        if self._keyboard is None:
            return
        name = pygame.key.name(key_code)
        canonical = _canonical_name(name)
        if debug_enabled("input"):
            debug_log("input", "event=%s canonical=%s pressed=%s", name, canonical, pressed)
        if canonical is None:
            return
        if pressed:
            self._keyboard.press(canonical)
        else:
            self._keyboard.release(canonical)
            machine = getattr(self, "_machine", None)
            if machine is not None:
                machine.via.cancel_key_click()

    def _create_machine(self, rom_path: Path) -> Machine:
        rom_image = rom_path.read_bytes()
        is_prog = _is_prog_image(rom_image)

        machine = create_machine(
            MachineConfig(
                rom_image=None if is_prog else rom_image,
                via_buzzer=self._handle_buzzer,
                via_font=self._handle_font_select,
            )
        )

        if is_prog:
            self._load_rom_prog(machine, rom_image, rom_path)

        return machine

    def _load_program(self, machine: Machine, program_path: Path) -> None:
        from pyjr100.loader import ProgFormatError, load_prog_from_path

        try:
            load_prog_from_path(program_path, machine.memory)
        except FileNotFoundError as exc:
            raise RuntimeError(f"Program file not found: {program_path}") from exc
        except ProgFormatError as exc:
            raise RuntimeError(f"Failed to load PROG file {program_path}: {exc}") from exc

    def _load_rom_prog(self, machine: Machine, rom_image: bytes, rom_path: Path) -> None:
        from pyjr100.loader import ProgFormatError, load_prog

        try:
            load_prog(io.BytesIO(rom_image), machine.memory)
        except ProgFormatError as exc:
            raise RuntimeError(f"Failed to load ROM PROG {rom_path}: {exc}") from exc

        machine.cpu.reset()

    def _build_font_set(self, machine: Machine) -> FontSet:
        font_data = bytearray(128 * GLYPH_BYTES)
        base = 0xE000

        for code in range(128):
            offset = base + code * GLYPH_BYTES
            for line in range(GLYPH_BYTES):
                font_data[code * GLYPH_BYTES + line] = machine.memory.load8(offset + line)

        return FontSet(bytes(font_data))

    def _step_cpu(self, machine) -> None:
        target_cycles = _CYCLES_PER_FRAME
        cycles = 0

        try:
            while cycles < target_cycles:
                executed = machine.cpu.step()
                if executed == 0:
                    remaining = target_cycles - cycles
                    idle_chunk = min(32, remaining)
                    machine.via.tick(idle_chunk)
                    cycles += idle_chunk
                    continue

                machine.via.tick(executed)
                cycles += executed
        except IllegalOpcodeError as exc:
            self._running = False
            raise RuntimeError(f"Illegal opcode encountered: {exc}")

    def _handle_font_select(self, use_user_font: bool) -> None:
        self._font_plane = 1 if use_user_font else 0

    def _handle_buzzer(self, enabled: bool, frequency: float) -> None:
        self._buzzer_enabled = enabled
        self._buzzer_frequency = frequency


def _canonical_name(name: str) -> str | None:
    mapping = {
        "semicolon": ";",
        "minus": "-",
        "comma": ",",
        "period": ".",
        "space": "space",
        "return": "return",
        "enter": "return",
        "left shift": "shift",
        "right shift": "shift",
        "left ctrl": "control",
        "right ctrl": "control",
    }
    lowered = name.lower()
    ignored = {
        "英数",
        "かな",
        "henkan",
        "muhenkan",
        "kana",
    }
    if lowered in ignored:
        if debug_enabled("input"):
            debug_log("input", "ignored=%s", lowered)
        return None
    if lowered == " ":
        lowered = "space"
    if lowered in mapping:
        return mapping[lowered]
    if len(lowered) == 1:
        return lowered
    return mapping.get(lowered)


def _is_prog_image(image: bytes) -> bool:
    return len(image) >= 4 and image[:4] == b"PROG"


_CPU_FREQUENCY = 894_886  # Hz
_FRAME_RATE = 60
_CYCLES_PER_FRAME = _CPU_FREQUENCY // _FRAME_RATE
_MAX_IDLE_STEPS = 1000
