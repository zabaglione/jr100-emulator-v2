"""Unit tests for the JR-100 memory system port."""

import pytest

from pyjr100.bus import Memory, MemoryError, MemorySystem, UnmappedMemory


class DummyRam(Memory):
    """Concrete RAM block for tests."""


def test_unmapped_memory_defaults() -> None:
    ms = MemorySystem()
    ms.allocate_space(0x10000)

    assert ms.load8(0x0000) == 0x00
    assert ms.load8(0xD000) == 0xAA
    assert ms.load16(0xD000) == 0xAA00


def test_register_memory_and_access() -> None:
    ms = MemorySystem()
    ms.allocate_space(0x10000)

    ram = DummyRam(0x0000, 0x100)
    ms.register_memory(ram)

    ms.store8(0x0000, 0x12)
    ms.store16(0x0002, 0xABCD)

    assert ms.load8(0x0000) == 0x12
    assert ms.load16(0x0002) == 0xABCD
    assert ms.get_memory(DummyRam) is ram
    assert ms.get_start_address(DummyRam) == 0x0000
    assert ms.get_end_address(DummyRam) == 0x00FF


def test_register_memory_out_of_bounds() -> None:
    ms = MemorySystem()
    ms.allocate_space(0x100)

    with pytest.raises(MemoryError):
        ms.register_memory(DummyRam(0x00F0, 0x40))


def test_custom_unmapped_region() -> None:
    ms = MemorySystem()
    ms.allocate_space(0x20)

    # Replace default filler with a custom unmapped block to ensure registration
    # handles non-standard Addressable instances.
    custom = UnmappedMemory(0x0000, 0x20)
    ms.register_memory(custom)

    assert ms.load8(0x0001) == 0x00
