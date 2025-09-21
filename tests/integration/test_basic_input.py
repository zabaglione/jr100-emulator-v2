"""Integration test that boots BASIC and runs a simple command."""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from pyjr100.loader import load_prog
from pyjr100.system import MachineConfig, create_machine

CPU_FREQUENCY = 894_886
FRAME_RATE = 60
FRAME_CYCLES = CPU_FREQUENCY // FRAME_RATE


def _step_machine(machine, cycles: int) -> None:
    while cycles > 0:
        executed = machine.cpu.step()
        if executed == 0:
            executed = min(32, cycles)
        machine.via.tick(executed)
        cycles -= executed


def _type_key(machine, key: str, hold_cycles: int = FRAME_CYCLES // 4) -> None:
    machine.keyboard.press(key)
    _step_machine(machine, hold_cycles)
    machine.keyboard.release(key)
    _step_machine(machine, FRAME_CYCLES // 6)


def _boot_machine(rom_bytes: bytes):
    if rom_bytes.startswith(b"PROG"):
        machine = create_machine(MachineConfig())
        load_prog(io.BytesIO(rom_bytes), machine.memory)
        machine.cpu.reset()
    else:
        machine = create_machine(MachineConfig(rom_image=rom_bytes))
    return machine


@pytest.mark.skipif("JR100_ROM" not in os.environ, reason="JR100_ROM environment variable not set")
def test_basic_print_command() -> None:
    rom_path = Path(os.environ["JR100_ROM"])
    rom_bytes = rom_path.read_bytes()

    machine = _boot_machine(rom_bytes)

    _step_machine(machine, FRAME_CYCLES * 180)

    for char in "PRINT 1":
        if char == " ":
            _type_key(machine, "space")
        else:
            _type_key(machine, char.lower())
    _type_key(machine, "return", hold_cycles=FRAME_CYCLES // 2)

    _step_machine(machine, FRAME_CYCLES * 400)

    vram = machine.video_ram.snapshot()
    ready_codes = [0x32, 0x25, 0x21, 0x24, 0x39]

    def contains_sequence(buffer, seq):
        limit = len(buffer) - len(seq)
        for idx in range(limit + 1):
            if list(buffer[idx : idx + len(seq)]) == seq:
                return True
        return False

    assert contains_sequence(vram, ready_codes)

    assert 0x11 in vram  # digit "1"
