"""JR-100 machine assembly and memory map."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pyjr100.bus import Addressable, Memory, MemorySystem, UnmappedMemory, Via6522
from pyjr100.bus.via6522 import BuzzerCallback, FontCallback
from pyjr100.cpu import MB8861
from pyjr100.io import Keyboard


@dataclass
class MachineConfig:
    """Runtime configuration for the JR-100 machine."""

    use_extended_ram: bool = False
    rom_image: Optional[bytes] = None
    via_buzzer: Optional[BuzzerCallback] = None
    via_font: Optional[FontCallback] = None


@dataclass
class Machine:
    """Aggregates the core components of the JR-100."""

    memory: MemorySystem
    cpu: MB8861
    ram: Memory
    video_ram: Memory
    udc_ram: Memory
    extended_io: Addressable
    via: Via6522
    rom: Memory
    keyboard: Keyboard


class MainRam(Memory):
    """System RAM block."""


class VideoRam(Memory):
    """Video RAM block."""


class UserDefinedCharRam(Memory):
    """User defined character RAM block."""


class ExtendedIoPort(Addressable):
    """Placeholder for the JR-100 extended I/O port."""

    def __init__(self, start: int, length: int = 0x400) -> None:
        self._start = start
        self._end = start + length - 1
        self._gamepad_status = 0

    def get_start_address(self) -> int:
        return self._start

    def get_end_address(self) -> int:
        return self._end

    def load8(self, address: int) -> int:
        if address == self._start + 0x02:
            return self._gamepad_status
        return 0

    def store8(self, address: int, value: int) -> None:
        if address == self._start + 0x02:
            self._gamepad_status = value & 0xFF


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

    udc_ram = UserDefinedCharRam(0xC000, 0x0100)
    memory.register_memory(udc_ram)

    video_ram = VideoRam(0xC100, 0x0300)
    memory.register_memory(video_ram)

    extended_io = ExtendedIoPort(0xCC00)
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
    )
