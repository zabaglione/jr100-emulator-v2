from __future__ import annotations

from pyjr100.bus import Memory, MemorySystem
from pyjr100.cpu.core import FLAG_N, FLAG_V, FLAG_Z, MB8861


def _cpu_with_memory(value: int) -> MB8861:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    ram = Memory(0x0000, 0x10000)
    memory.register_memory(ram)
    cpu = MB8861(memory)
    cpu.state.pc = 0x0000
    cpu.state.x = 0x0100
    cpu.memory.store8(0x0105, value & 0xFF)
    return cpu


def test_nim_masks_bits_and_sets_flags() -> None:
    cpu = _cpu_with_memory(0x0F)
    cpu.memory.store8(0x0000, 0x71)  # NIM
    cpu.memory.store8(0x0001, 0x30)  # mask
    cpu.memory.store8(0x0002, 0x05)  # offset

    cpu.step()

    stored = cpu.memory.load8(0x0105)
    assert stored == 0x00
    assert cpu.state.cc & FLAG_Z
    assert not (cpu.state.cc & FLAG_N)
    assert not (cpu.state.cc & FLAG_V)


def test_oim_sets_bits_and_flags() -> None:
    cpu = _cpu_with_memory(0x01)
    cpu.memory.store8(0x0000, 0x72)  # OIM
    cpu.memory.store8(0x0001, 0x02)
    cpu.memory.store8(0x0002, 0x05)

    cpu.step()

    stored = cpu.memory.load8(0x0105)
    assert stored == 0x03
    assert not (cpu.state.cc & FLAG_Z)
    assert cpu.state.cc & FLAG_N
    assert not (cpu.state.cc & FLAG_V)


def test_xim_xors_bits_and_updates_flags() -> None:
    cpu = _cpu_with_memory(0xAA)
    cpu.memory.store8(0x0000, 0x75)  # XIM
    cpu.memory.store8(0x0001, 0xFF)
    cpu.memory.store8(0x0002, 0x05)

    cpu.step()

    stored = cpu.memory.load8(0x0105)
    assert stored == 0x55
    assert not (cpu.state.cc & FLAG_Z)
    assert cpu.state.cc & FLAG_N
    assert not (cpu.state.cc & FLAG_V)


def test_tmm_flag_patterns() -> None:
    cpu = _cpu_with_memory(0xFF)
    cpu.memory.store8(0x0000, 0x7B)  # TMM
    cpu.memory.store8(0x0001, 0x01)
    cpu.memory.store8(0x0002, 0x05)

    cpu.step()

    assert not (cpu.state.cc & FLAG_N)
    assert not (cpu.state.cc & FLAG_Z)
    assert cpu.state.cc & FLAG_V

    # When mask is zero, Z set and N cleared
    cpu.state.pc = 0x0003
    cpu.memory.store8(0x0003, 0x7B)
    cpu.memory.store8(0x0004, 0x00)
    cpu.memory.store8(0x0005, 0x05)

    cpu.step()

    assert not (cpu.state.cc & FLAG_N)
    assert cpu.state.cc & FLAG_Z
    assert not (cpu.state.cc & FLAG_V)
