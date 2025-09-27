"""Instruction metadata for MB8861 CPU."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable


class AddressingMode(Enum):
    IMPLIED = auto()
    IMMEDIATE = auto()
    DIRECT = auto()
    RELATIVE = auto()


@dataclass(frozen=True)
class Instruction:
    opcode: int
    name: str
    mode: AddressingMode
    cycles: int
    handler: Callable[["MB8861", AddressingMode], int]


__all__ = ["AddressingMode", "Instruction"]
