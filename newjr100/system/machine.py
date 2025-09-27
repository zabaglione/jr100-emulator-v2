"""Machine assembly using the reimplemented VIA core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pyjr100.bus import MemorySystem, UnmappedMemory
from pyjr100.bus.via6522 import BuzzerCallback, FontCallback
from pyjr100.cpu import MB8861
from pyjr100.io import GamepadState, Keyboard
from pyjr100.system.machine import (
    BasicRom,
    ExtendedIoPort,
    MainRam,
    UserDefinedCharRam,
    VideoRam,
)
from pyjr100.video import FontManager

from newjr100.jr100.device.via6522 import Via6522


@dataclass
class MachineConfig:
    """Runtime configuration for the new-core machine."""

    use_extended_ram: bool = False
    rom_image: Optional[bytes] = None
    via_buzzer: Optional[BuzzerCallback] = None
    via_font: Optional[FontCallback] = None
    gamepad_state: GamepadState | None = None


@dataclass
class Machine:
    """Aggregates the primary emulator components."""

    memory: MemorySystem
    cpu: MB8861
    ram: MainRam
    video_ram: VideoRam
    udc_ram: UserDefinedCharRam
    extended_io: ExtendedIoPort
    via: Via6522
    rom: BasicRom
    keyboard: Keyboard
    gamepad: GamepadState
    font_manager: FontManager


def create_machine(config: MachineConfig) -> Machine:
    """Instantiate the machine equipped with the rewritten VIA."""

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
        start=0xC800,
        keyboard=keyboard,
        cpu=cpu,
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


__all__ = [
    "Machine",
    "MachineConfig",
    "create_machine",
]
