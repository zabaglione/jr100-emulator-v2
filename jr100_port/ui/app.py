"""Minimal CLI-facing application wrapper for the JR-100 machine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jr100_port.jr100.display import JR100Display
from jr100_port.jr100.machine import JR100Machine, JR100MachineConfig
from jr100_port.io.gamepad import GamepadState


@dataclass
class AppConfig:
    """Configuration parameters accepted by the CLI entry point."""

    rom_path: Optional[Path]
    program_path: Optional[Path] = None
    use_extended_ram: bool = False
    scale: int = 2
    fullscreen: bool = False
    debug_overlay: bool = False


class JR100App:
    """Creates the JR-100 machine and performs initial program loading."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._machine: JR100Machine | None = None
        self._surface = None
        self._screen_size = (0, 0)
        self._base_size = (0, 0)
        self._overlay_width = 0
        self._keymap: dict[int, tuple[int, int]] = {}
        self._semicolon_key: int | None = None
        self._active_keys: dict[int, tuple[int, int]] = {}
        self._gamepad_state: GamepadState | None = None
        self._debug_overlay = config.debug_overlay
        self._overlay_columns = 18
        self._overlay_font = None

    @property
    def machine(self) -> JR100Machine | None:
        return self._machine

    def initialise_machine(self) -> JR100Machine:
        if self._machine is not None:
            return self._machine

        if self._config.rom_path is None:
            raise RuntimeError("ROM image is required; specify --rom <path>")
        rom_path = self._config.rom_path
        if not rom_path.exists():
            raise RuntimeError(f"ROM file not found: {rom_path}")

        machine = JR100Machine(
            JR100MachineConfig(
                rom_path=rom_path,
                program_path=self._config.program_path,
                use_extended_ram=self._config.use_extended_ram,
            )
        )

        machine.powerOn()
        queue = machine.getEventQueue()
        while not queue.isEmpty():
            queue.pop_first().dispatch(machine)

        self._machine = machine
        self._gamepad_state = machine.gamepad
        return machine

    def run(self) -> None:
        machine = self.initialise_machine()

        pygame = self._initialise_pygame()
        screen = self._create_window(pygame)
        clock = pygame.time.Clock()

        fps = 50
        target_cycles = machine.getClockFrequency() / fps
        cycle_accumulator = 0.0

        running = True
        cpu = machine.getCPU()
        via = machine.via
        base_width, base_height = self._base_size
        scale = max(1, self._config.scale)
        main_width = base_width * scale

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key_event(event, True)
                elif event.type == pygame.KEYUP:
                    self._handle_key_event(event, False)

            cycle_accumulator += target_cycles
            executed_cycles = 0
            while cycle_accumulator > 0:
                consumed = cpu.step()
                if consumed <= 0:
                    break
                executed_cycles += consumed
                machine.setClockCount(machine.getClockCount() + consumed)
                cycle_accumulator -= consumed
            if cycle_accumulator < -target_cycles:
                cycle_accumulator = -target_cycles

            via.execute()
            for device in machine.getDevices():
                if hasattr(device, "execute"):
                    device.execute()

            frame_surface = self._render_frame(machine)
            screen.blit(frame_surface, (0, 0))
            if self._debug_overlay and self._overlay_width > 0:
                overlay_surface = self._draw_overlay(pygame, machine, base_height * scale)
                if overlay_surface is not None:
                    screen.blit(overlay_surface, (main_width, 0))
            pygame.display.flip()
            clock.tick(fps)

        pygame.quit()
        if hasattr(machine, "sound") and hasattr(machine.sound, "shutdown"):
            machine.sound.shutdown()

    def _initialise_pygame(self):
        try:
            import pygame  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pygame is required to run the UI") from exc

        if "SDL_VIDEODRIVER" not in os.environ and os.environ.get("PYTEST_CURRENT_TEST"):
            os.environ["SDL_VIDEODRIVER"] = "dummy"

        pygame.init()
        try:
            pygame.mixer.pre_init(44_100, -16, 1, 512)
            pygame.mixer.init()
        except pygame.error:
            pass

        return pygame

    def _create_window(self, pygame):
        base_width = JR100Display.WIDTH_CHARS * JR100Display.PIXELS_PER_CHAR
        base_height = JR100Display.HEIGHT_CHARS * JR100Display.PIXELS_PER_CHAR
        scale = max(1, self._config.scale)
        overlay_width = self._overlay_columns * JR100Display.PIXELS_PER_CHAR * scale if self._debug_overlay else 0

        width = base_width * scale + overlay_width
        height = base_height * scale
        flags = pygame.FULLSCREEN if self._config.fullscreen else 0
        screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("JR-100 Emulator (Python)")

        self._base_size = (base_width, base_height)
        self._screen_size = (width, height)
        self._overlay_width = overlay_width
        self._surface = pygame.Surface((base_width, base_height))
        self._keymap = self._build_keymap(pygame)
        return screen

    def _render_frame(self, machine: JR100Machine):
        import pygame  # type: ignore

        base_width, base_height = self._base_size
        scale = max(1, self._config.scale)

        surface = self._surface
        if surface is None or surface.get_size() != (base_width, base_height):
            surface = pygame.Surface((base_width, base_height))
            self._surface = surface

        surface.fill((0, 0, 0))
        machine.display.render_surface(surface, pygame, 1)

        if scale == 1:
            return surface
        return pygame.transform.scale(surface, (base_width * scale, base_height * scale))

    def _build_keymap(self, pygame) -> dict[int, tuple[int, int]]:
        mapping: dict[int, tuple[int, int]] = {}

        def register(key: int, row: int, bit: int) -> None:
            mapping[key] = (row, bit)

        register(pygame.K_MINUS, 8, 4)
        register(pygame.K_RETURN, 8, 3)
        register(pygame.K_SPACE, 8, 1)
        register(pygame.K_PERIOD, 8, 0)

        register(pygame.K_COMMA, 7, 4)
        register(pygame.K_m, 7, 3)
        register(pygame.K_n, 7, 2)
        register(pygame.K_b, 7, 1)
        register(pygame.K_v, 7, 0)

        register(pygame.K_SEMICOLON, 6, 4)
        register(pygame.K_l, 6, 3)
        register(pygame.K_k, 6, 2)
        register(pygame.K_j, 6, 1)
        register(pygame.K_h, 6, 0)

        register(pygame.K_p, 5, 4)
        register(pygame.K_o, 5, 3)
        register(pygame.K_i, 5, 2)
        register(pygame.K_u, 5, 1)
        register(pygame.K_y, 5, 0)

        register(pygame.K_0, 4, 4)
        register(pygame.K_9, 4, 3)
        register(pygame.K_8, 4, 2)
        register(pygame.K_7, 4, 1)
        register(pygame.K_6, 4, 0)

        register(pygame.K_c, 0, 4)
        register(pygame.K_x, 0, 3)
        register(pygame.K_z, 0, 2)
        register(pygame.K_LSHIFT, 0, 1)
        register(pygame.K_RSHIFT, 0, 1)
        register(pygame.K_LCTRL, 0, 0)
        register(pygame.K_RCTRL, 0, 0)

        register(pygame.K_g, 1, 4)
        register(pygame.K_f, 1, 3)
        register(pygame.K_d, 1, 2)
        register(pygame.K_s, 1, 1)
        register(pygame.K_a, 1, 0)

        register(pygame.K_t, 2, 4)
        register(pygame.K_r, 2, 3)
        register(pygame.K_e, 2, 2)
        register(pygame.K_w, 2, 1)
        register(pygame.K_q, 2, 0)

        register(pygame.K_5, 3, 4)
        register(pygame.K_4, 3, 3)
        register(pygame.K_3, 3, 2)
        register(pygame.K_2, 3, 1)
        register(pygame.K_1, 3, 0)

        self._semicolon_key = pygame.K_SEMICOLON
        return mapping

    def _handle_key_event(self, event, pressed: bool) -> None:
        key = event.key
        if self._machine is None:
            return
        import pygame  # type: ignore

        if getattr(event, "mod", 0) & pygame.KMOD_MODE:
            return
        keyboard = self._machine.keyboard
        mapping: tuple[int, int] | None
        if pressed:
            if self._semicolon_key is not None and key == self._semicolon_key and getattr(event, "unicode", "") == ":":
                mapping = (8, 2)
            else:
                mapping = self._keymap.get(key)
            if mapping is None:
                self._handle_gamepad_keys(key, True)
                return
            self._active_keys[key] = mapping
            row, bit = mapping
            keyboard.set_key_state(row, bit, True)
            self._handle_gamepad_keys(key, True)
        else:
            mapping = self._active_keys.pop(key, self._keymap.get(key))
            if mapping is not None:
                row, bit = mapping
                keyboard.set_key_state(row, bit, False)
            self._handle_gamepad_keys(key, False)

    def _handle_gamepad_keys(self, key: int, pressed: bool) -> None:
        if self._gamepad_state is None:
            return
        import pygame  # type: ignore

        if key == pygame.K_RIGHT:
            self._gamepad_state.set_direction(right=pressed)
        elif key == pygame.K_LEFT:
            self._gamepad_state.set_direction(left=pressed)
        elif key == pygame.K_UP:
            self._gamepad_state.set_direction(up=pressed)
        elif key == pygame.K_DOWN:
            self._gamepad_state.set_direction(down=pressed)
        elif key in (pygame.K_LALT, pygame.K_RALT, pygame.K_RETURN):
            self._gamepad_state.set_button(pressed)

    def _draw_overlay(self, pygame, machine: JR100Machine, height: int):
        if not self._debug_overlay or self._overlay_width <= 0:
            return None

        surface = pygame.Surface((self._overlay_width, height))
        surface.fill((0, 0, 0))

        font_size = max(8, 6 * self._config.scale)
        if self._overlay_font is None or self._overlay_font[0] != font_size:
            pygame.font.init()
            font_name = pygame.font.match_font("menlo,dejavusansmono,couriernew,consolas,monospace")
            if not font_name:
                font_name = pygame.font.get_default_font()
            font_obj = pygame.font.Font(font_name, font_size)
            self._overlay_font = (font_size, font_obj)
        else:
            font_obj = self._overlay_font[1]

        cpu = machine.getCPU()
        lines = [
            f"PC {cpu.pc:04X}",
            f"SP {cpu.sp:04X} IX {cpu.ix:04X}",
            f"A {cpu.a:02X} B {cpu.b:02X}",
            "Flags "
            f"H{int(cpu.ch)} I{int(cpu.ci)} N{int(cpu.cn)} Z{int(cpu.cz)} V{int(cpu.cv)} C{int(cpu.cc)}",
        ]

        color = (0, 255, 0)
        line_height = font_size + 2
        for index, text in enumerate(lines):
            rendered = font_obj.render(text, True, color)
            surface.blit(rendered, (2, index * line_height))

        return surface


__all__ = ["AppConfig", "JR100App"]
