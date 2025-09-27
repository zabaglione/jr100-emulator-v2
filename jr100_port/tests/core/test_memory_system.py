import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from jr100_port.core.memory import MemorySystem, UnmappedMemory


class DummyMemory:
    def __init__(self, start: int, size: int) -> None:
        self._start = start
        self._end = start + size - 1
        self.bytes: dict[int, int] = {}

    def getStartAddress(self) -> int:
        return self._start

    def getEndAddress(self) -> int:
        return self._end

    def load8(self, address: int) -> int:
        return self.bytes.get(address & 0xFFFF, 0x55)

    def store8(self, address: int, value: int) -> None:
        self.bytes[address & 0xFFFF] = value & 0xFF

    def load16(self, address: int) -> int:
        high = self.load8(address)
        low = self.load8(address + 1)
        return ((high << 8) | low) & 0xFFFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)


def test_allocate_and_register_memory() -> None:
    memory = MemorySystem()
    memory.allocateSpace(0x10000)

    dummy = DummyMemory(0x2000, 0x100)
    memory.registMemory(dummy)

    memory.store8(0x2005, 0xAB)
    assert memory.load8(0x2005) == 0xAB
    assert isinstance(memory.getMemory(dummy.__class__), DummyMemory)


def test_unmapped_memory_default_values() -> None:
    memory = MemorySystem()
    memory.allocateSpace(0x10000)

    assert memory.load8(0x00) == 0x00
    assert memory.load8(0xD000) == 0xAA
    assert memory.load16(0xD000) == 0xAA00


def test_store16_splits_bytes() -> None:
    memory = MemorySystem()
    memory.allocateSpace(0x10000)
    dummy = DummyMemory(0x3000, 0x10)
    memory.registMemory(dummy)

    memory.store16(0x3002, 0x1234)
    assert dummy.bytes[0x3002] == 0x12
    assert dummy.bytes[0x3003] == 0x34
    assert memory.load16(0x3002) == 0x1234


def test_get_start_end_address() -> None:
    memory = MemorySystem()
    memory.allocateSpace(0x10000)
    dummy = DummyMemory(0x4000, 0x20)
    memory.registMemory(dummy)

    assert memory.getStartAddress(DummyMemory) == 0x4000
    assert memory.getEndAddress(DummyMemory) == 0x401F


def test_allocate_invalid_capacity() -> None:
    memory = MemorySystem()
    with pytest.raises(ValueError):
        memory.allocateSpace(0x10001)


def test_register_without_allocation() -> None:
    memory = MemorySystem()
    with pytest.raises(RuntimeError):
        memory.registMemory(DummyMemory(0x1000, 0x10))


def test_register_out_of_range() -> None:
    memory = MemorySystem()
    memory.allocateSpace(0x100)
    with pytest.raises(ValueError):
        memory.registMemory(DummyMemory(0x80, 0x200))


def test_get_memory_returns_none_when_missing() -> None:
    memory = MemorySystem()
    memory.allocateSpace(0x100)
    assert memory.getMemory(UnmappedMemory) is not None
    assert memory.getMemory(DummyMemory) is None
