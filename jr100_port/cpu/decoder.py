"""Opcode decoder for MB8861."""

from __future__ import annotations

from typing import Dict

from .instructions import AddressingMode, Instruction


class Decoder:
    def __init__(self) -> None:
        self._table: Dict[int, Instruction] = {}

    def register(self, instruction: Instruction) -> None:
        self._table[instruction.opcode] = instruction

    def lookup(self, opcode: int) -> Instruction:
        return self._table[opcode]


__all__ = ["Decoder"]
