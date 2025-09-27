"""Pygame application bootstrap placeholder for the JR-100 emulator."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pyjr100.audio import SquareWaveBeeper
from pyjr100.bus.memory import Memory, MemorySystem
from pyjr100.loader import (
    BasicTextFormatError,
    ProgFormatError,
    load_basic_text_from_path,
    load_prog,
    load_prog_from_path,
)
from pyjr100.system import Machine, MachineConfig, create_machine
from pyjr100.io import GamepadState
from pyjr100.video import FontSet, Renderer
from pyjr100.video.font import GLYPH_BYTES
from pyjr100.cpu import IllegalOpcodeError
from pyjr100.utils import TraceRecorder, debug_enabled, debug_log


@dataclass
class AppConfig:
    """Configuration for the eventual JR-100 emulator frontend."""

    rom_path: Optional[Path] = None
    program_path: Optional[Path] = None
    scale: int = 2
    fullscreen: bool = False
    use_extended_ram: bool = False
    enable_gamepad: bool = True
    joystick_index: int = 0


class JR100App:
    """Thin wrapper around the Pygame event loop (not yet implemented)."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._running = False
        self._keyboard = None
        self._font_plane = 0
        self._buzzer_enabled = False
        self._buzzer_frequency = 0.0
        self._beeper: SquareWaveBeeper | None = None
        self._machine: Machine | None = None
        self._debug_overlay = debug_enabled("overlay")
        self._overlay_columns = 18
        self._overlay_font = None
        self._perf_enabled = debug_enabled("perf")
        self._perf_last_time = 0.0
        self._perf_frame = 0
        self._pygame = None
        self._gamepad_state = GamepadState()
        self._joystick = None
        self._joystick_instance_id: int | None = None
        self._joystick_axes = {"x": 0.0, "y": 0.0}
        self._joystick_hat = (0, 0)
        self._joystick_button = False
        self._joystick_pressed_buttons: set[int] = set()
        self._font_manager = None
        self._trace_recorder: TraceRecorder | None = None
        if debug_enabled("trace") or debug_enabled("freeze"):
            self._trace_recorder = TraceRecorder(512)
        self._last_freeze_report_frame: int | None = None
        self._frame_counter = 0
        self._last_wai_pc: int | None = None

    def run(self) -> None:
        try:
            import pygame  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pygame is required to run the UI") from exc

        pygame.mixer.pre_init(44_100, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("JR-100 Emulator (Python WIP)")
        self._pygame = pygame

        if pygame.mixer.get_init() is None:
            try:
                pygame.mixer.init(44_100, -16, 1)
            except pygame.error as exc:  # pragma: no cover - best-effort path
                if debug_enabled("audio"):
                    debug_log("audio", "mixer_init_failed=%s", exc)

        mixer_state = pygame.mixer.get_init()
        if mixer_state is not None:
            sample_rate = mixer_state[0]
            try:
                self._beeper = SquareWaveBeeper(sample_rate=sample_rate)
            except RuntimeError as exc:
                self._beeper = None
                if debug_enabled("audio"):
                    debug_log("audio", "beeper_init_failed=%s", exc)
        else:
            if debug_enabled("audio"):
                debug_log("audio", "mixer_unavailable")

        if not self._config.rom_path:
            raise RuntimeError("ROM image is required; pass --rom <path>")
        rom_path = self._config.rom_path
        if not rom_path.exists():
            raise RuntimeError(f"ROM file not found: {rom_path}")

        machine = self._create_machine(rom_path)
        self._machine = machine
        self._font_manager = machine.font_manager
        font_set = self._build_font_set(machine)
        renderer = Renderer(font_set, font_manager=machine.font_manager)

        if self._config.enable_gamepad:
            self._initialise_joystick(pygame)

        self._wait_for_basic_ready(machine)

        display_width = 32 * 8 * self._config.scale
        display_height = 24 * 8 * self._config.scale
        overlay_width = self._overlay_columns * 8 * self._config.scale if self._debug_overlay else 0

        surface_size = (display_width + overlay_width, display_height)
        flags = pygame.FULLSCREEN if self._config.fullscreen else 0
        screen = pygame.display.set_mode(surface_size, flags)

        clock = pygame.time.Clock()
        self._running = True
        self._keyboard = machine.keyboard

        if self._config.program_path is not None:
            self._load_program(machine, self._config.program_path)

        import time

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif self._config.enable_gamepad and event.type == pygame.JOYDEVICEADDED:
                    self._handle_joystick_device_added(pygame, event)
                elif self._config.enable_gamepad and event.type == pygame.JOYDEVICEREMOVED:
                    self._handle_joystick_device_removed(event)
                elif self._config.enable_gamepad and event.type == pygame.JOYAXISMOTION:
                    self._handle_joystick_axis(event)
                elif self._config.enable_gamepad and event.type == pygame.JOYHATMOTION:
                    self._handle_joystick_hat(event)
                elif self._config.enable_gamepad and event.type == pygame.JOYBUTTONDOWN:
                    self._handle_joystick_button(event, pressed=True)
                elif self._config.enable_gamepad and event.type == pygame.JOYBUTTONUP:
                    self._handle_joystick_button(event, pressed=False)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._enter_debug_shell(machine)
                elif event.type == pygame.KEYDOWN:
                    self._handle_key_event(pygame, event.key, pressed=True)
                elif event.type == pygame.KEYUP:
                    self._handle_key_event(pygame, event.key, pressed=False)

            frame_start_cycles = machine.cpu.cycle_count
            frame_start_time = time.perf_counter()

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

            if self._debug_overlay and overlay_width > 0:
                overlay_surface = self._draw_overlay(pygame, machine, display_height, overlay_width)
                if overlay_surface is not None:
                    screen.blit(overlay_surface, (display_width, 0))
            pygame.display.flip()

            frame_end_time = time.perf_counter()
            frame_cycles = machine.cpu.cycle_count - frame_start_cycles
            frame_duration = frame_end_time - frame_start_time

            if self._perf_enabled and frame_duration > 0:
                self._perf_frame += 1
                effective_khz = (frame_cycles / frame_duration) / 1000.0
                debug_log(
                    "perf",
                    "frame=%d cycles=%d frame_ms=%.3f effective_khz=%.2f",
                    self._perf_frame,
                    frame_cycles,
                    frame_duration * 1000.0,
                    effective_khz,
                )

            if frame_cycles == 0:
                self._handle_zero_cycle_frame(machine)

            clock.tick(_FRAME_RATE)
            self._frame_counter += 1

        if self._beeper is not None:
            self._beeper.shutdown()
        pygame.quit()

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

    # ------------------------------------------------------------------
    # Joystick handling

    def _initialise_joystick(self, pygame, device_index: int | None = None) -> None:
        if not self._config.enable_gamepad:
            return
        try:
            pygame.joystick.init()
        except pygame.error as exc:  # pragma: no cover - hardware dependent
            if debug_enabled("input"):
                debug_log("input", "joystick_init_failed=%s", exc)
            return

        count = pygame.joystick.get_count()
        if count <= 0:
            if debug_enabled("input"):
                debug_log("input", "joystick_none_available")
            return

        index = device_index if device_index is not None else self._config.joystick_index
        if index < 0 or index >= count:
            index = 0

        try:
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
        except pygame.error as exc:  # pragma: no cover - hardware dependent
            if debug_enabled("input"):
                debug_log("input", "joystick_open_failed index=%d error=%s", index, exc)
            return

        instance_id = joystick.get_instance_id() if hasattr(joystick, "get_instance_id") else index
        self._joystick = joystick
        self._joystick_instance_id = instance_id
        self._joystick_axes = {"x": 0.0, "y": 0.0}
        self._joystick_hat = (0, 0)
        self._joystick_pressed_buttons = set()
        self._joystick_button = False
        if self._gamepad_state is not None:
            self._gamepad_state.reset()
            self._update_gamepad_state()
        self._update_gamepad_state()
        if debug_enabled("input"):
            debug_log(
                "input",
                "joystick_attached index=%d id=%s name=%s",
                index,
                instance_id,
                joystick.get_name() if hasattr(joystick, "get_name") else "unknown",
            )

    def _detach_joystick(self) -> None:
        if self._joystick is None:
            return
        if debug_enabled("input"):
            debug_log("input", "joystick_detached id=%s", self._joystick_instance_id)
        try:  # pragma: no branch - defensive cleanup
            self._joystick.quit()
        except Exception:
            pass
        self._joystick = None
        self._joystick_instance_id = None
        self._joystick_axes = {"x": 0.0, "y": 0.0}
        self._joystick_hat = (0, 0)
        self._joystick_pressed_buttons = set()
        self._joystick_button = False
        if self._gamepad_state is not None:
            self._gamepad_state.reset()

    def _event_instance_id(self, event) -> int | None:
        if hasattr(event, "instance_id"):
            return event.instance_id
        if hasattr(event, "joy"):
            return event.joy
        return None

    def _handle_joystick_device_added(self, pygame, event) -> None:
        if not self._config.enable_gamepad or self._joystick is not None:
            return
        self._initialise_joystick(pygame, getattr(event, "device_index", None))

    def _handle_joystick_device_removed(self, event) -> None:
        if not self._config.enable_gamepad:
            return
        instance_id = self._event_instance_id(event)
        if instance_id is None:
            return
        if self._joystick_instance_id == instance_id:
            self._detach_joystick()

    def _handle_joystick_axis(self, event) -> None:
        if not self._config.enable_gamepad:
            return
        instance_id = self._event_instance_id(event)
        if instance_id is None or instance_id != self._joystick_instance_id:
            return
        if event.axis == 0:
            self._joystick_axes["x"] = event.value
        elif event.axis == 1:
            self._joystick_axes["y"] = event.value
        else:
            return
        self._update_gamepad_state()

    def _handle_joystick_hat(self, event) -> None:
        if not self._config.enable_gamepad:
            return
        instance_id = self._event_instance_id(event)
        if instance_id is None or instance_id != self._joystick_instance_id:
            return
        self._joystick_hat = event.value
        self._update_gamepad_state()

    def _handle_joystick_button(self, event, *, pressed: bool) -> None:
        if not self._config.enable_gamepad:
            return
        instance_id = self._event_instance_id(event)
        if instance_id is None or instance_id != self._joystick_instance_id:
            return
        self._joystick_pressed_buttons.add(event.button) if pressed else self._joystick_pressed_buttons.discard(event.button)
        self._joystick_button = bool(self._joystick_pressed_buttons)
        self._update_gamepad_state()

    def _update_gamepad_state(self) -> None:
        if not self._config.enable_gamepad or self._gamepad_state is None:
            return
        left = self._joystick_axes["x"] < -_JOYSTICK_AXIS_THRESHOLD or self._joystick_hat[0] < 0
        right = self._joystick_axes["x"] > _JOYSTICK_AXIS_THRESHOLD or self._joystick_hat[0] > 0
        up = self._joystick_axes["y"] < -_JOYSTICK_AXIS_THRESHOLD or self._joystick_hat[1] > 0
        down = self._joystick_axes["y"] > _JOYSTICK_AXIS_THRESHOLD or self._joystick_hat[1] < 0
        self._gamepad_state.set_directions(left=left, right=right, up=up, down=down)
        self._gamepad_state.set_button(self._joystick_button)

    def _create_machine(self, rom_path: Path) -> Machine:
        rom_payload, _ = _prepare_rom_image(rom_path)

        machine = create_machine(
            MachineConfig(
                use_extended_ram=self._config.use_extended_ram,
                rom_image=rom_payload,
                via_buzzer=self._handle_buzzer,
                via_font=self._handle_font_select,
                gamepad_state=self._gamepad_state if self._config.enable_gamepad else None,
            )
        )

        if self._config.enable_gamepad:
            self._gamepad_state = machine.gamepad

        return machine

    def _load_program(self, machine: Machine, program_path: Path) -> None:
        try:
            load_prog_from_path(program_path, machine.memory)
        except FileNotFoundError as exc:
            raise RuntimeError(f"Program file not found: {program_path}") from exc
        except ProgFormatError as prog_error:
            try:
                load_basic_text_from_path(program_path, machine.memory)
            except BasicTextFormatError as text_error:
                raise RuntimeError(
                    f"Failed to load program {program_path}: PROG error={prog_error}; BASIC error={text_error}"
                ) from text_error

    def _wait_for_basic_ready(self, machine: Machine, *, max_cycles: int = 2_000_000) -> None:
        start_ptr = _read_pointer(machine, 0x0006)
        if start_ptr != 0:
            return

        cycles = 0
        while cycles < max_cycles:
            executed = machine.cpu.step()
            if executed == 0:
                executed = 1
            machine.via.tick(executed)
            cycles += executed
            start_ptr = _read_pointer(machine, 0x0006)
            if start_ptr != 0:
                return

        raise RuntimeError("JR-100 BASIC initialisation timed out")

    def _draw_overlay(self, pygame, machine: Machine, height: int, width: int):
        surface = pygame.Surface((width, height))
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
        color = (255, 255, 255)
        line_height = font_size + 2

        label_width = 12

        def fmt(label: str, value: str) -> str:
            return f"{label:<{label_width}}: {value}"

        lines: list[str] = []
        cpu_state = machine.cpu.state
        lines.append(fmt("CPU PC", f"{cpu_state.pc:04X}"))
        lines.append(fmt("CPU SP", f"{cpu_state.sp:04X}"))
        lines.append(fmt("CPU IX", f"{cpu_state.x:04X}"))
        lines.append(fmt("CPU A", f"{cpu_state.a:02X}"))
        lines.append(fmt("CPU B", f"{cpu_state.b:02X}"))
        lines.append(fmt("CPU CC", f"{cpu_state.cc:02X}"))
        flag_defs = (("H", 0x20), ("I", 0x10), ("N", 0x08), ("Z", 0x04), ("V", 0x02), ("C", 0x01))
        flags = "".join(flag for flag, mask in flag_defs if cpu_state.cc & mask)
        lines.append(fmt("CPU FLAGS", flags or "-"))

        via_snapshot = machine.via.debug_snapshot()
        lines.append(" ")
        lines.append(fmt("VIA ORB", f"{via_snapshot['ORB']:02X}"))
        lines.append(fmt("VIA ORA", f"{via_snapshot['ORA']:02X}"))
        lines.append(fmt("VIA DDRB", f"{via_snapshot['DDRB']:02X}"))
        lines.append(fmt("VIA DDRA", f"{via_snapshot['DDRA']:02X}"))
        lines.append(fmt("VIA ACR", f"{via_snapshot['ACR']:02X}"))
        lines.append(fmt("VIA PCR", f"{via_snapshot['PCR']:02X}"))
        lines.append(fmt("VIA IFR", f"{via_snapshot['IFR']:02X}"))
        lines.append(fmt("VIA IER", f"{via_snapshot['IER']:02X}"))
        lines.append(fmt("VIA T1", f"{via_snapshot['T1']:04X}"))
        lines.append(fmt("VIA T2", f"{via_snapshot['T2']:04X}"))
        lines.append(fmt("VIA PB7", f"{via_snapshot['PB7']}"))

        y = 4
        for text in lines:
            rendered = font_obj.render(text, False, color)
            surface.blit(rendered, (4, y))
            y += line_height
            if y > height:
                break

        return surface

    def _build_font_set(self, machine: Machine) -> FontSet:
        font_data = bytearray(128 * GLYPH_BYTES)
        base = 0xE000

        for code in range(128):
            offset = base + code * GLYPH_BYTES
            for line in range(GLYPH_BYTES):
                font_data[code * GLYPH_BYTES + line] = machine.memory.load8(offset + line)

        if machine.font_manager is not None:
            manager = machine.font_manager
            manager.initialize_rom(bytes(font_data))
            manager.sync_from_memory(machine.video_ram.snapshot(), machine.udc_ram.snapshot())

        font_set = FontSet(bytes(font_data), machine.font_manager)
        return font_set

    def _step_cpu(self, machine) -> None:
        target_cycles = _CYCLES_PER_FRAME
        cycles = 0
        cpu = machine.cpu
        via = machine.via
        memory = machine.memory
        trace = self._trace_recorder
        trace_enabled = trace is not None

        try:
            while cycles < target_cycles:
                state_before = cpu.state.clone() if trace_enabled else None
                via_snapshot = via.debug_snapshot() if trace_enabled else None
                opcode_before = None
                mnemonic = ""
                if trace_enabled and state_before is not None:
                    opcode_before = memory.load8(state_before.pc)
                    if 0 <= opcode_before < len(cpu.instruction_table):
                        instr = cpu.instruction_table[opcode_before]
                        if instr is not None:
                            mnemonic = instr.mnemonic
                executed = cpu.step()
                if executed == 0:
                    remaining = target_cycles - cycles
                    idle_chunk = min(32, remaining)
                    if trace_enabled and state_before is not None and via_snapshot is not None:
                        if cpu.halted:
                            note = "halted"
                        elif cpu.wai_latch:
                            note = "wai-latch"
                        else:
                            note = "idle"
                        if note != "wai-latch":
                            self._last_wai_pc = None
                            trace.record_step(
                                state_before,
                                opcode_before,
                                0,
                                via_snapshot,
                                wai=cpu.wai_latch,
                                halted=cpu.halted,
                                mnemonic=mnemonic,
                                note=note,
                            )
                        elif note == "wai-latch":
                            if self._last_wai_pc != (state_before.pc & 0xFFFF):
                                trace.record_step(
                                    state_before,
                                    opcode_before,
                                    0,
                                    via_snapshot,
                                    wai=cpu.wai_latch,
                                    halted=cpu.halted,
                                    mnemonic=mnemonic,
                                    note=note,
                                )
                                self._last_wai_pc = state_before.pc & 0xFFFF
                    via.tick(idle_chunk)
                    cycles += idle_chunk
                    continue

                if trace_enabled and state_before is not None and via_snapshot is not None:
                    self._last_wai_pc = None
                    trace.record_step(
                        state_before,
                        opcode_before,
                        executed,
                        via_snapshot,
                        wai=cpu.wai_latch,
                        halted=cpu.halted,
                        mnemonic=mnemonic,
                    )

                via.tick(executed)
                cycles += executed
        except IllegalOpcodeError as exc:
            self._running = False
            raise RuntimeError(f"Illegal opcode encountered: {exc}")

    def _handle_zero_cycle_frame(self, machine: Machine) -> None:
        if not (debug_enabled("freeze") or debug_enabled("trace")):
            return
        frame_id = self._frame_counter
        if self._last_freeze_report_frame == frame_id:
            return
        self._last_freeze_report_frame = frame_id

        cpu = machine.cpu
        via_state = machine.via.debug_snapshot()
        debug_log(
            "freeze",
            "freeze frame=%d pc=%04X wai=%s halted=%s IFR=%02X IER=%02X ORB=%02X ORA=%02X DDRB=%02X DDRA=%02X ACR=%02X PCR=%02X T1=%04X T2=%04X",
            frame_id,
            cpu.state.pc,
            cpu.wai_latch,
            cpu.halted,
            via_state.get("IFR", 0) & 0xFF,
            via_state.get("IER", 0) & 0xFF,
            via_state.get("ORB", 0) & 0xFF,
            via_state.get("ORA", 0) & 0xFF,
            via_state.get("DDRB", 0) & 0xFF,
            via_state.get("DDRA", 0) & 0xFF,
            via_state.get("ACR", 0) & 0xFF,
            via_state.get("PCR", 0) & 0xFF,
            via_state.get("T1", 0) & 0xFFFF,
            via_state.get("T2", 0) & 0xFFFF,
        )
        keyboard_rows = machine.keyboard.snapshot()
        row_dump = " ".join(f"{value & 0x1F:02X}" for value in keyboard_rows)
        debug_log("freeze", "keyboard_rows=%s", row_dump)

        if self._trace_recorder is not None:
            self._trace_recorder.dump("freeze", limit=64)
        if hasattr(machine.via, "debug_recent_activity"):
            for line in machine.via.debug_recent_activity(limit=16):
                debug_log("freeze", f"via_activity {line}")

        pygame = self._pygame
        if pygame is not None:
            pygame.event.clear()
        self._enter_debug_shell(machine)

    def _handle_font_select(self, use_user_font: bool) -> None:
        self._font_plane = 1 if use_user_font else 0

    def _handle_buzzer(self, enabled: bool, frequency: float) -> None:
        self._buzzer_enabled = enabled
        self._buzzer_frequency = frequency
        if debug_enabled("audio"):
            debug_log("audio", "buzzer enabled=%s freq=%.2f", enabled, frequency)
        if self._beeper is not None:
            self._beeper.set_state(enabled, frequency)

    # ------------------------------------------------------------------
    # Debug shell

    def _enter_debug_shell(self, machine: Machine) -> None:
        print("\n=== JR-100 Debug Menu ===")
        print("Enter command: [c]pu, [v]ia, [r]ow dump, [m]em, [u]serchar, [t]race, [h]istory, [q]uit, [Enter] resume")
        try:
            import pygame  # type: ignore
        except Exception:  # pragma: no cover - debug path
            pygame = None  # type: ignore

        paused = True
        while paused and self._running:
            try:
                command = input("debug> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("Resuming emulator.")
                break

            if command == "" or command in {"resume"}:
                paused = False
            elif command in {"c", "cpu"}:
                self._dump_cpu(machine)
            elif command in {"v", "via"}:
                self._dump_via(machine)
            elif command in {"row", "rows", "display", "vr", "r"}:
                self._dump_vram(machine)
            elif command.startswith("r") and len(command) > 1:
                self._dump_vram(machine, command[1:])
            elif command in {"u", "udc", "char"}:
                self._dump_user_character(machine)
            elif command.startswith("u") and len(command) > 1:
                self._dump_user_character(machine, command[1:])
            elif command in {"t", "trace"}:
                self._dump_trace()
            elif command in {"h", "hist", "history"}:
                self._dump_via_history(machine)
            elif command.startswith("m"):
                spec = command[1:].strip()
                self._dump_memory(machine, spec if spec else None)
            elif command in {"q", "quit", "exit"}:
                print("Exiting emulator.")
                self._running = False
                paused = False
            else:
                print("Commands: [Enter]=resume, [c]pu, [v]ia, [r]ow, [m]em, [u]serchar, [t]race, [h]istory, [q]uit")

        if pygame is not None:
            pygame.event.clear()

    def _dump_cpu(self, machine: Machine) -> None:
        state = machine.cpu.state
        print(
            "CPU PC={:04X} SP={:04X} IX={:04X} A={:02X} B={:02X} CC={:02X}".format(
                state.pc,
                state.sp,
                state.x,
                state.a,
                state.b,
                state.cc,
            )
        )
        flags = [
            ("H", 0x20),
            ("I", 0x10),
            ("N", 0x08),
            ("Z", 0x04),
            ("V", 0x02),
            ("C", 0x01),
        ]
        active = "".join(name for name, mask in flags if (state.cc & mask))
        print(f"Flags set: {active if active else '-'}")

    def _dump_via(self, machine: Machine) -> None:
        via = machine.via
        snapshot = via.debug_snapshot()
        for name in ("ORB", "ORA", "DDRB", "DDRA", "ACR", "PCR", "IFR", "IER", "PB7", "T1", "T2"):
            value = snapshot.get(name)
            if value is None:
                continue
            if name == "PB7":
                print(f"VIA {name} = {value}")
            elif name in {"T1", "T2"}:
                print(f"VIA {name} = {value:04X}")
            else:
                print(f"VIA {name} = {value:02X}")
        print(f"Font plane active: {bool(snapshot.get('ORB', 0) & 0x20)}")

    def _dump_vram(self, machine: Machine, row_spec: str | None = None) -> None:
        vram = machine.video_ram.snapshot()
        if row_spec is None:
            try:
                value = input("Row number (0-23 or 'all') [all]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("Cancelled.")
                return
        else:
            value = row_spec.strip()
            if not value:
                value = "all"
            print(f"Row number (0-23 or 'all') [all]: {value}")

        if value in {"", "all"}:
            rows = range(24)
        else:
            try:
                rows = [int(value, 10)]
            except ValueError:
                print(f"Invalid row '{value}'. Enter 0-23 or 'all'.")
                return
        any_output = False
        for row in rows:
            if not 0 <= row < 24:
                print(f"Row {row} out of range")
                continue
            start = row * 32
            row_bytes = vram[start : start + 32]
            hex_part = " ".join(f"{byte:02X}" for byte in row_bytes)
            text_part = "".join(chr(byte & 0x7F) if 32 <= (byte & 0x7F) < 127 else '.' for byte in row_bytes)
            print(f"{row:02d}: {hex_part} | {text_part}")
            any_output = True
        if not any_output:
            print("No rows dumped.")

    def _dump_user_character(self, machine: Machine, index_spec: str | None = None) -> None:
        udc = machine.udc_ram.snapshot()
        if index_spec is None:
            try:
                value = input("User char index (0-127) [0]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("Cancelled.")
                return
        else:
            value = index_spec.strip()
            print(f"User char index (0-127) [0]: {value}")
        try:
            index = int(value or "0")
        except ValueError:
            print(f"Invalid index '{value}'.")
            return
        if not 0 <= index < 128:
            print("Index out of range")
            return
        start = index * 8
        glyph = udc[start : start + 8]
        print(f"UDC[{index}] bytes: {' '.join(f'{line:02X}' for line in glyph)}")
        for line in glyph:
            row = ''.join('#' if line & (1 << (7 - bit)) else '.' for bit in range(8))
            print(row)

    def _dump_trace(self, limit: int = 64) -> None:
        if self._trace_recorder is None:
            print("Trace recorder is disabled. Set JR100_DEBUG=trace または freeze を指定してください。")
            return
        lines = list(self._trace_recorder.format_entries(limit))
        if not lines:
            print("Trace buffer is empty.")
            return
        print("Last trace entries:")
        for line in lines:
            print(f"  {line}")

    def _dump_via_history(self, machine: Machine, limit: int = 16) -> None:
        via = machine.via
        if not hasattr(via, "debug_recent_activity"):
            print("VIA history is unavailable.")
            return
        entries = via.debug_recent_activity(limit)
        if not entries:
            print("VIA history is empty.")
            return
        print("Recent VIA register accesses:")
        for line in entries:
            print(f"  {line}")

    def _dump_memory(self, machine: Machine, spec: str | None = None) -> None:
        def parse_value(text: str, default: int) -> int:
            text = text.strip()
            if not text:
                return default
            lowered = text.lower()
            if lowered.startswith("0x"):
                return int(lowered, 16)
            if any(c in "abcdef" for c in lowered):
                return int(lowered, 16)
            return int(lowered, 10)

        start: int
        length: int
        if spec:
            parts = spec.split()
            try:
                start = parse_value(parts[0], 0)
                length = parse_value(parts[1], 0x80) if len(parts) > 1 else 0x80
            except (ValueError, IndexError):
                print("Usage: m [start_hex] [length]")
                return
        else:
            try:
                addr_input = input("Start address (hex) [0000]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("Cancelled.")
                return
            try:
                start = parse_value(addr_input or "0", 0)
            except ValueError:
                print(f"Invalid address '{addr_input}'.")
                return
            try:
                length_input = input("Length (decimal, default 128): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("Cancelled.")
                return
            try:
                length = parse_value(length_input or "128", 128)
            except ValueError:
                print(f"Invalid length '{length_input}'.")
                return

        if length <= 0:
            print("Length must be positive.")
            return

        end = start + length
        memory = machine.memory
        for addr in range(start, end, 16):
            chunk = [memory.load8((addr + offset) & 0xFFFF) for offset in range(16) if addr + offset < end]
            hex_part = " ".join(f"{value:02X}" for value in chunk)
            print(f"{addr & 0xFFFF:04X}: {hex_part}")


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


def _prepare_rom_image(rom_path: Path) -> tuple[bytes, bool]:
    raw = rom_path.read_bytes()
    if not _is_prog_image(raw):
        return raw, False

    scratch = MemorySystem()
    scratch.allocate_space(0x10000)
    backing = Memory(0x0000, 0x10000)
    scratch.register_memory(backing)

    try:
        load_prog(io.BytesIO(raw), scratch)
    except ProgFormatError as exc:
        raise RuntimeError(f"Failed to decode ROM PROG {rom_path}: {exc}") from exc

    snapshot = backing.snapshot()
    rom_start = 0xE000
    rom_end = 0x10000
    if len(snapshot) < rom_end:
        raise RuntimeError(f"Decoded ROM data truncated for {rom_path}")
    rom_data = snapshot[rom_start:rom_end]
    return bytes(rom_data), True


def _is_prog_image(image: bytes) -> bool:
    return len(image) >= 4 and image[:4] == b"PROG"


def _read_pointer(machine: Machine, address: int) -> int:
    high = machine.memory.load8(address) & 0xFF
    low = machine.memory.load8(address + 1) & 0xFF
    return (high << 8) | low


_CPU_FREQUENCY = 894_886  # Hz
_FRAME_RATE = 60
_CYCLES_PER_FRAME = _CPU_FREQUENCY // _FRAME_RATE
_MAX_IDLE_STEPS = 1000
_JOYSTICK_AXIS_THRESHOLD = 0.5
