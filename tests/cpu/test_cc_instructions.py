from __future__ import annotations

from pyjr100.bus import Memory, MemorySystem
from pyjr100.cpu.core import FLAG_I, MB8861


def _create_cpu() -> MB8861:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    ram = Memory(0x0000, 0x10000)
    memory.register_memory(ram)
    cpu = MB8861(memory)
    cpu.state.pc = 0x0000
    return cpu


def test_orcc_sets_interrupt_mask() -> None:
    cpu = _create_cpu()
    cpu.memory.store8(0x0000, 0x1A)  # ORCC
    cpu.memory.store8(0x0001, 0x10)  # set I flag

    cpu.step()

    assert cpu.state.cc & FLAG_I
    assert (cpu.state.cc & 0xC0) == 0xC0


def test_andcc_clears_interrupt_mask() -> None:
    cpu = _create_cpu()
    # ORCC #$10 followed by ANDCC #$EF
    cpu.memory.store8(0x0000, 0x1A)
    cpu.memory.store8(0x0001, 0x10)
    cpu.memory.store8(0x0002, 0x1C)
    cpu.memory.store8(0x0003, 0xEF)

    cpu.step()
    assert cpu.state.cc & FLAG_I

    cpu.step()

    assert not (cpu.state.cc & FLAG_I)
    assert (cpu.state.cc & 0xC0) == 0xC0


def test_brn_skips_operand_without_branching() -> None:
    cpu = _create_cpu()
    cpu.memory.store8(0x0000, 0x21)  # BRN
    cpu.memory.store8(0x0001, 0x10)  # offset that should be ignored
    cpu.memory.store8(0x0002, 0x20)  # BRA to ensure execution continues
    cpu.memory.store8(0x0003, 0x02)

    cpu.step()  # BRN
    assert cpu.state.pc == 0x0002

    cpu.step()  # BRA should execute next (offset applied)
    assert cpu.state.pc == 0x0006
