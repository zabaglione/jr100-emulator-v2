"""Memory system for the JR-100 Python port.

This module mirrors the behaviour of the original Java ``MemorySystem`` along
with its default ``Memory`` and ``UnmappedMemory`` implementations. The goal is
parity with the 16-bit address space used by the JR-100 while providing a Python-
centric API that stays close enough for direct translation of the remaining
components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Type, TypeVar


def _mask16(value: int) -> int:
    """Clamp ``value`` to the 16-bit address space expected by the JR-100."""

    return value & 0xFFFF


class MemoryError(Exception):
    """Raised when the memory system is misconfigured or used incorrectly."""


class Addressable:
    """Interface for objects mapped into the CPU address space."""

    def get_start_address(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def get_end_address(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def load8(self, address: int) -> int:  # pragma: no cover - interface
        raise NotImplementedError

    def store8(self, address: int, value: int) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def load16(self, address: int) -> int:
        high = self.load8(address)
        low = self.load8(address + 1)
        return ((high & 0xFF) << 8) | (low & 0xFF)

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)


@dataclass
class Memory(Addressable):
    """Simple byte-addressable memory region."""

    start: int
    length: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.length <= 0:
            raise MemoryError("memory region must have a positive length and non-negative start")
        self._data = bytearray(self.length)

    def get_start_address(self) -> int:
        return self.start

    def get_end_address(self) -> int:
        return self.start + self.length - 1

    def _offset(self, address: int) -> int:
        offset = address - self.start
        if not 0 <= offset < self.length:
            raise MemoryError(f"address {address:#06x} outside region {self.start:#06x}-{self.get_end_address():#06x}")
        return offset

    def load8(self, address: int) -> int:
        return self._data[self._offset(address)]

    def store8(self, address: int, value: int) -> None:
        self._data[self._offset(address)] = value & 0xFF


class UnmappedMemory(Addressable):
    """Fallback region used for addresses without a mapped device."""

    def __init__(self, start: int, length: int) -> None:
        self._start = start
        self._length = length

    def get_start_address(self) -> int:
        return self._start

    def get_end_address(self) -> int:
        return self._start + self._length - 1

    def load8(self, address: int) -> int:
        masked = _mask16(address)
        if masked == 0xD000:
            return 0xAA
        return 0x00

    def store8(self, address: int, value: int) -> None:  # noqa: D401 - intentionally empty
        """Ignore writes to unmapped memory."""

    # ``load16``/``store16`` inherit the default behaviour from Addressable.


T_Addressable = TypeVar("T_Addressable", bound=Addressable)


class MemorySystem:
    """16-bit wide memory map that dispatches reads/writes to devices."""

    def __init__(self) -> None:
        self._space: list[Addressable] | None = None
        self._registry: Dict[Type[Addressable], Addressable] = {}
        self._debug = False

    def allocate_space(self, capacity: int) -> None:
        if capacity <= 0 or capacity > 0x10000:
            raise MemoryError(f"capacity {capacity} out of range (1-65536)")
        filler = UnmappedMemory(0, capacity)
        self._space = [filler for _ in range(capacity)]

    def register_memory(self, memory: Addressable) -> None:
        if self._space is None:
            raise MemoryError("memory space not allocated")
        start = _mask16(memory.get_start_address())
        end = _mask16(memory.get_end_address())
        if end < start:
            raise MemoryError("memory end precedes start")
        if end >= len(self._space):
            raise MemoryError(f"memory region {start:#06x}-{end:#06x} exceeds allocated space")
        for address in range(start, end + 1):
            self._space[address] = memory
        self._registry[type(memory)] = memory

    def get_memory(self, cls: Type[T_Addressable]) -> T_Addressable | None:
        memory = self._registry.get(cls)
        if memory is None:
            return None
        return memory  # type: ignore[return-value]

    def get_memories(self) -> Iterable[Addressable]:
        return self._registry.values()

    def get_start_address(self, cls: Type[T_Addressable]) -> int:
        memory = self._require_memory(cls)
        return memory.get_start_address()

    def get_end_address(self, cls: Type[T_Addressable]) -> int:
        memory = self._require_memory(cls)
        return memory.get_end_address()

    def _require_memory(self, cls: Type[T_Addressable]) -> T_Addressable:
        memory = self.get_memory(cls)
        if memory is None:
            raise MemoryError(f"memory {cls.__name__} not registered")
        return memory

    def load8(self, address: int) -> int:
        space = self._ensure_space()
        addr = _mask16(address)
        value = space[addr].load8(addr)
        if self._debug:
            print(f"load8: addr={addr:04x} val={value:02x}")
        return value & 0xFF

    def store8(self, address: int, value: int) -> None:
        space = self._ensure_space()
        addr = _mask16(address)
        if self._debug:
            print(f"store8: addr={addr:04x} val={value & 0xFF:02x}")
        space[addr].store8(addr, value)

    def load16(self, address: int) -> int:
        high = self.load8(address)
        low = self.load8(address + 1)
        value = ((high & 0xFF) << 8) | (low & 0xFF)
        if self._debug:
            print(f"load16: addr={address & 0xFFFF:04x} val={value:04x}")
        return value

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)

    def set_debug(self, enabled: bool) -> None:
        self._debug = enabled

    def _ensure_space(self) -> list[Addressable]:
        if self._space is None:
            raise MemoryError("memory space not allocated")
        return self._space
