import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jr100_port.jr100.machine import JR100Machine, JR100MachineConfig
from jr100_port.ui.app import AppConfig, JR100App


@pytest.fixture()
def machine() -> JR100Machine:
    config = JR100MachineConfig(rom_path=None, use_extended_ram=False)
    machine = JR100Machine(config)
    machine.powerOn()
    queue = machine.getEventQueue()
    if not queue.isEmpty():
        queue.pop_first().dispatch(machine)
    return machine


def _create_basic_prog(path: Path, payload: bytes) -> None:
    buf = bytearray()
    buf += b"PROG"
    buf += (2).to_bytes(4, "little")
    pnam_payload = (len(b"PROGTEST")).to_bytes(4, "little") + b"PROGTEST"
    buf += b"PNAM" + len(pnam_payload).to_bytes(4, "little") + pnam_payload
    pbas_payload = len(payload).to_bytes(4, "little") + payload
    buf += b"PBAS" + len(pbas_payload).to_bytes(4, "little") + pbas_payload
    path.write_bytes(buf)


def test_cpu_attached(machine: JR100Machine) -> None:
    assert machine.getCPU() is not None


def test_main_ram_write_and_read(machine: JR100Machine) -> None:
    memory = machine.getHardware().getMemory()
    memory.store8(0x0001, 0x5A)
    assert memory.load8(0x0001) == 0x5A


def test_via_mapping(machine: JR100Machine) -> None:
    memory = machine.getHardware().getMemory()
    memory.store8(0xC800, 0x12)
    assert machine.via.orb == 0x12


def test_devices_registered(machine: JR100Machine) -> None:
    device_types = {device.__class__.__name__ for device in machine.getDevices()}
    assert {"JR100Via6522", "JR100Keyboard", "JR100Display", "Beeper"}.issubset(device_types)


def test_program_path_loads_basic_area(tmp_path: Path) -> None:
    payload = bytes([0x10, 0x20, 0x30])
    prog_path = tmp_path / "program.prog"
    _create_basic_prog(prog_path, payload)

    config = JR100MachineConfig(rom_path=None, program_path=prog_path)
    machine = JR100Machine(config)

    memory = machine.getHardware().getMemory()
    start = 0x0246
    for index, value in enumerate(payload):
        assert memory.load8(start + index) == value

    sentinel_start = start + len(payload)
    for offset in range(3):
        assert memory.load8(sentinel_start + offset) == 0xDF

    assert machine.program_image is not None
    assert machine.program_image.basic_area is True


def test_gamepad_state_updates_extended_io(tmp_path: Path) -> None:
    rom_path = tmp_path / "rom.prog"
    _create_basic_prog(rom_path, bytes([0xAA] * 8))

    app = JR100App(AppConfig(rom_path=rom_path))
    machine = app.initialise_machine()

    gamepad = machine.gamepad
    memory = machine.getHardware().getMemory()

    assert memory.load8(0xCC02) == 0
    gamepad.set_direction(right=True)
    assert memory.load8(0xCC02) & 0x01 == 0x01
    gamepad.set_direction(right=False, left=True)
    assert memory.load8(0xCC02) & 0x02 == 0x02
