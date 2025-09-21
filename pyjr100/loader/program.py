"""Program metadata structures for JR-100 loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AddressRegion:
    """Represents a contiguous address range within the JR-100 address space."""

    start: int
    end: int
    comment: str = ""

    def length(self) -> int:
        return self.end - self.start + 1


@dataclass
class ProgramImage:
    """Holds metadata extracted from a PROG file alongside the memory writes."""

    name: str = ""
    comment: str = ""
    basic_area: bool = False
    regions: List[AddressRegion] = field(default_factory=list)

    def add_region(self, start: int, end: int, comment: str = "") -> None:
        self.regions.append(AddressRegion(start, end, comment))
