"""JR-100 computer wiring based on the Java implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jr100_port.core.computer import Computer
from jr100_port.core.memory import UnmappedMemory
from jr100_port.cpu.mb8861 import MB8861
from jr100_port.devices import (
    BasicRom,
    Beeper,
    ExtendedIOPort,
    JR100Via6522,
    MainRam,
    UserDefinedCharacterRam,
    VideoRam,
)
from jr100_port.jr100.display import JR100Display
from jr100_port.jr100.keyboard import JR100Keyboard
from jr100_port.loader import ProgramImage, load_prog_from_path
from jr100_port.io.gamepad import GamepadState


DEFAULT_CPU_CLOCK = 894_000
REFRESH_RATE = 1.0 / 50.0
MEMORY_CAPACITY = 0x10000


@dataclass
class JR100MachineConfig:
    rom_path: Optional[Path] = None
    program_path: Optional[Path] = None
    use_extended_ram: bool = False
    sampling_rate: float = 44_100.0


class JR100Machine(Computer):
    """Faithful wiring of the JR-100 components."""

    def __init__(self, config: JR100MachineConfig) -> None:
        super().__init__(refresh_rate=REFRESH_RATE)
        self._clock_frequency = DEFAULT_CPU_CLOCK
        self.config = config
        self.program_image: Optional[ProgramImage] = None
        self.gamepad = GamepadState()

        hardware = self.getHardware()
        memory = hardware.getMemory()
        memory.allocateSpace(MEMORY_CAPACITY)

        self.keyboard = JR100Keyboard(self)
        hardware.setKeyboard(self.keyboard)

        self.sound = Beeper(self, config.sampling_rate)
        hardware.setSoundProcessor(self.sound)

        main_ram_length = 0x8000 if config.use_extended_ram else 0x4000
        memory.registMemory(MainRam(0x0000, main_ram_length))
        if not config.use_extended_ram:
            memory.registMemory(UnmappedMemory(0x4000, 0x4000))

        udc = UserDefinedCharacterRam(0xC000, 0x100, None)
        memory.registMemory(udc)

        video_ram = VideoRam(0xC100, 0x300, None)
        memory.registMemory(video_ram)

        ext_port = ExtendedIOPort(self, 0xCC00, self.gamepad)
        memory.registMemory(ext_port)

        rom_path = config.rom_path
        rom = BasicRom(rom_path, 0xE000, 0x2000)
        memory.registMemory(rom)

        self.display = JR100Display(self)
        hardware.setDisplay(self.display)
        udc.set_display(self.display)
        video_ram.set_display(self.display)

        self.via = JR100Via6522(self, 0xC800)
        memory.registMemory(self.via)

        cpu = MB8861(memory)
        self.setCPU(cpu)

        self.addDevice(self.via)
        self.addDevice(self.keyboard)
        self.addDevice(self.display)
        self.addDevice(self.sound)

        if config.program_path:
            self.program_image = self.load_program(config.program_path)

    def getClockFrequency(self) -> int:  # noqa: N802
        return self._clock_frequency

    def setClockFrequency(self, frequency: int) -> None:  # noqa: N802
        self._clock_frequency = frequency

    def load_program(self, path: Path) -> ProgramImage:
        memory = self.getHardware().getMemory()
        program = load_prog_from_path(path, memory)
        return program


__all__ = ["JR100Machine", "JR100MachineConfig"]
