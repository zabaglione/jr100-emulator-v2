"""JR-100 machine assembly and memory map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pyjr100.bus import Addressable, Memory, MemorySystem, UnmappedMemory, Via6522
from pyjr100.bus.via6522 import BuzzerCallback, FontCallback
from pyjr100.cpu import MB8861
from pyjr100.io import GamepadState, Keyboard
from pyjr100.video import FontManager


@dataclass
class MachineConfig:
    """Runtime configuration for the JR-100 machine."""

    use_extended_ram: bool = False
    rom_image: Optional[bytes] = None
    via_buzzer: Optional[BuzzerCallback] = None
    via_font: Optional[FontCallback] = None
    gamepad_state: GamepadState | None = None


@dataclass
class Machine:
    """Aggregates the core components of the JR-100."""

    memory: MemorySystem
    cpu: MB8861
    ram: Memory
    video_ram: Memory
    udc_ram: Memory
    extended_io: "ExtendedIoPort"
    via: Via6522
    rom: Memory
    keyboard: Keyboard
    gamepad: GamepadState
    font_manager: FontManager


class MainRam(Memory):
    """System RAM block."""


class VideoRam(Memory):
    """Video RAM block that notifies the font manager on updates."""

    def __init__(self, start: int, length: int, font_manager: FontManager) -> None:
        super().__init__(start, length)
        self._font_manager = font_manager

    def store8(self, address: int, value: int) -> None:
        super().store8(address, value)
        self._font_manager.update_vram_font(address, value & 0xFF)


class UserDefinedCharRam(Memory):
    """User defined character RAM block that updates the font manager."""

    def __init__(self, start: int, length: int, font_manager: FontManager) -> None:
        super().__init__(start, length)
        self._font_manager = font_manager

    def store8(self, address: int, value: int) -> None:
        super().store8(address, value)
        self._font_manager.update_udc(address, value & 0xFF)


class ExtendedIoPort(Addressable):
    """JR-100 extended I/O block that exposes the gamepad register."""

    _GAMEPAD_OFFSET = 0x02

    def __init__(self, start: int, *, length: int = 0x400, gamepad: GamepadState | None = None) -> None:
        self._start = start
        self._end = start + length - 1
        self._gamepad = gamepad or GamepadState()

    def get_start_address(self) -> int:
        return self._start

    def get_end_address(self) -> int:
        return self._end

    def get_gamepad_state(self) -> GamepadState:
        return self._gamepad

    def attach_gamepad(self, gamepad: GamepadState) -> None:
        self._gamepad = gamepad

    def load8(self, address: int) -> int:
        if address == self._start + self._GAMEPAD_OFFSET:
            return self._gamepad.read()
        return 0x00

    def store8(self, address: int, value: int) -> None:
        if address == self._start + self._GAMEPAD_OFFSET:
            self._gamepad.write(value)

    def load16(self, address: int) -> int:
        if address == self._start + self._GAMEPAD_OFFSET - 1:
            return self._gamepad.read() & 0x00FF
        if address == self._start + self._GAMEPAD_OFFSET:
            return (self._gamepad.read() << 8) & 0xFF00
        return super().load16(address)

    def store16(self, address: int, value: int) -> None:
        if address in (
            self._start + self._GAMEPAD_OFFSET - 1,
            self._start + self._GAMEPAD_OFFSET,
        ):
            self._gamepad.write(value & 0xFF)
        else:
            super().store16(address, value)


class BasicRom(Memory):
    """Simple ROM block that can be initialised with image data."""

    def load_image(self, data: bytes) -> None:
        length = min(len(data), len(self._data))
        self._data[:length] = data[:length]


def create_machine(config: MachineConfig) -> Machine:
    """Instantiate a JR-100 machine with the requested configuration."""

    memory = MemorySystem()
    memory.allocate_space(0x10000)

    ram_length = 0x8000 if config.use_extended_ram else 0x4000
    ram = MainRam(0x0000, ram_length)
    memory.register_memory(ram)

    if ram_length < 0x8000:
        unmapped = UnmappedMemory(0x4000, 0x4000)
        memory.register_memory(unmapped)

    font_manager = FontManager()

    udc_ram = UserDefinedCharRam(0xC000, 0x0100, font_manager)
    memory.register_memory(udc_ram)

    video_ram = VideoRam(0xC100, 0x0300, font_manager)
    memory.register_memory(video_ram)

    gamepad_state = config.gamepad_state or GamepadState()

    extended_io = ExtendedIoPort(0xCC00, gamepad=gamepad_state)
    memory.register_memory(extended_io)

    rom = BasicRom(0xE000, 0x2000)
    if config.rom_image:
        rom.load_image(config.rom_image)
    memory.register_memory(rom)

    keyboard = Keyboard()
    cpu = MB8861(memory, strict_illegal=False)
    cpu.reset()

    via = Via6522(
        0xC800,
        keyboard,
        cpu,
        buzzer_callback=config.via_buzzer,
        font_callback=config.via_font,
    )
    memory.register_memory(via)

    font_manager.sync_from_memory(video_ram.snapshot(), udc_ram.snapshot())

    return Machine(
        memory=memory,
        cpu=cpu,
        ram=ram,
        video_ram=video_ram,
        udc_ram=udc_ram,
        extended_io=extended_io,
        via=via,
        rom=rom,
        keyboard=keyboard,
        gamepad=gamepad_state,
        font_manager=font_manager,
    )
