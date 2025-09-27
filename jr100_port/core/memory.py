"""Memory system mirroring the Java implementation."""

from __future__ import annotations

from typing import Dict, Iterable, List, MutableSequence, Protocol, Type, TypeVar


class Addressable(Protocol):
    """Interface for address-mapped components."""

    def getStartAddress(self) -> int:
        ...

    def getEndAddress(self) -> int:
        ...

    def load8(self, address: int) -> int:
        ...

    def store8(self, address: int, value: int) -> None:
        ...

    def load16(self, address: int) -> int:
        ...

    def store16(self, address: int, value: int) -> None:
        ...


class UnmappedMemory:
    """Default memory region used to back unassigned address space."""

    def __init__(self, start: int, length: int) -> None:
        self._start = start & 0xFFFF
        self._length = length

    def getStartAddress(self) -> int:  # noqa: N802 - Java互換API
        return self._start

    def getEndAddress(self) -> int:  # noqa: N802 - Java互換API
        return (self._start + self._length - 1) & 0xFFFF

    def load8(self, address: int) -> int:
        return 0xAA if (address & 0xFFFF) == 0xD000 else 0x00

    def store8(self, address: int, value: int) -> None:  # noqa: ARG002 - intentional no-op
        return None

    def load16(self, address: int) -> int:
        if (address & 0xFFFF) == 0xD000:
            return 0xAA00
        return 0x0000

    def store16(self, address: int, value: int) -> None:  # noqa: ARG002 - intentional no-op
        return None


_AddressableT = TypeVar("_AddressableT", bound=Addressable)


class MemorySystem:
    """Port of jp.asamomiji.emulator.MemorySystem."""

    def __init__(self) -> None:
        self._space: MutableSequence[Addressable] = []
        self._map: Dict[Type[Addressable], Addressable] = {}
        self.debug = False

    def allocateSpace(self, capacity: int) -> None:  # noqa: N802 - Java互換API
        if capacity < 0 or capacity > 0x10000:
            raise ValueError(f"invalid capacity {capacity}")
        default = UnmappedMemory(0, capacity if capacity else 1)
        self._space = [default] * capacity
        self._map = {UnmappedMemory: default}

    def registMemory(self, memory: Addressable) -> None:  # noqa: N802 - Java互換API
        if not self._space:
            raise RuntimeError("memory space not allocated")
        start = memory.getStartAddress() & 0xFFFF
        end = memory.getEndAddress() & 0xFFFF
        if end < start:
            raise ValueError("end address precedes start address")
        if end >= len(self._space):
            raise ValueError("memory outside allocated space")
        for address in range(start, end + 1):
            self._space[address] = memory
        self._map[memory.__class__] = memory

    def getMemory(self, cls: Type[_AddressableT]) -> _AddressableT | None:  # noqa: N802
        memory = self._map.get(cls)
        if memory is not None:
            return memory  # type: ignore[return-value]
        for candidate in self._map.values():
            if isinstance(candidate, cls):
                return candidate
        return None

    def getMemories(self) -> Iterable[Addressable]:  # noqa: N802
        return tuple(self._map.values())

    def getStartAddress(self, cls: Type[_AddressableT]) -> int:  # noqa: N802
        memory = self.getMemory(cls)
        if memory is None:
            raise KeyError(cls)
        return memory.getStartAddress()

    def getEndAddress(self, cls: Type[_AddressableT]) -> int:  # noqa: N802
        memory = self.getMemory(cls)
        if memory is None:
            raise KeyError(cls)
        return memory.getEndAddress()

    def load8(self, address: int) -> int:
        if not self._space:
            raise RuntimeError("memory space not allocated")
        addr = address & 0xFFFF
        value = self._space[addr].load8(addr) & 0xFF
        if self.debug:
            print(f"load8: addr={addr:04X} val={value:02X}")
        return value

    def store8(self, address: int, value: int) -> None:
        if not self._space:
            raise RuntimeError("memory space not allocated")
        addr = address & 0xFFFF
        if self.debug:
            print(f"store8: addr={addr:04X} val={value & 0xFF:02X}")
        self._space[addr].store8(addr, value & 0xFF)

    def load16(self, address: int) -> int:
        high = self.load8(address)
        low = self.load8(address + 1)
        return ((high << 8) | low) & 0xFFFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)


__all__ = [
    "Addressable",
    "MemorySystem",
    "UnmappedMemory",
]
