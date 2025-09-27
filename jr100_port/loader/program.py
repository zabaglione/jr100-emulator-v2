"""Program metadata structures for JR-100 loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AddressRegion:
    start: int
    end: int
    comment: str = ""

    def length(self) -> int:
        return self.end - self.start + 1


@dataclass
class ProgramImage:
    name: str = ""
    comment: str = ""
    basic_area: bool = False
    regions: List[AddressRegion] = field(default_factory=list)

    def add_region(self, start: int, end: int, comment: str = "") -> None:
        self.regions.append(AddressRegion(start, end, comment))
