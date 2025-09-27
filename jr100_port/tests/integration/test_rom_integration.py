import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jr100_port.core.memory import MemorySystem
from jr100_port.devices.memory_blocks import MainRam
from jr100_port.loader import load_prog_from_path
from jr100_port.ui.app import AppConfig, JR100App


def _require_file(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"required file not found: {path}")
    return path


def test_boot_with_real_rom(tmp_path: Path) -> None:
    rom_path = _require_file(REPO_ROOT / "jr100rom.prg")

    app = JR100App(AppConfig(rom_path=rom_path))
    machine = app.initialise_machine()

    cpu = machine.getCPU()
    memory = machine.getHardware().getMemory()

    restart_vector = memory.load16(0xFFFE)
    assert cpu.pc == restart_vector
    assert memory.load8(cpu.pc) == memory.load8(cpu.pc)


def test_load_sample_program(tmp_path: Path) -> None:
    rom_path = _require_file(REPO_ROOT / "jr100rom.prg")
    prog_path = _require_file(REPO_ROOT / "STARFIRE.prg")

    app = JR100App(AppConfig(rom_path=rom_path, program_path=prog_path))
    machine = app.initialise_machine()

    program = machine.program_image
    assert program is not None
    assert program.regions  # at least one PBIN region expected

    memory = machine.getHardware().getMemory()
    region = program.regions[0]
    start = region.start

    shadow = MemorySystem()
    shadow.allocateSpace(0x10000)
    shadow.registMemory(MainRam(0x0000, 0x10000))
    load_prog_from_path(prog_path, shadow)
    expected = shadow.load8(start)

    assert memory.load8(start) == expected
