"""Lightweight execution trace buffer for diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .debug import debug_log


@dataclass
class TraceEntry:
    pc: int
    opcode: int | None
    mnemonic: str
    cycles: int
    a: int
    b: int
    x: int
    sp: int
    cc: int
    via_ifr: int
    via_ier: int
    via_orb: int
    via_ddrb: int
    via_t1: int
    via_t2: int
    wai: bool
    halted: bool
    note: str = ""


class TraceRecorder:
    """Ring buffer that stores recent CPU/VIA snapshots."""

    def __init__(self, capacity: int = 256) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._entries: List[TraceEntry | None] = [None] * capacity
        self._index = 0
        self._size = 0

    def record_step(
        self,
        cpu_state,
        opcode: int | None,
        cycles: int,
        via_snapshot: dict[str, int],
        *,
        wai: bool,
        halted: bool,
        mnemonic: str = "",
        note: str = "",
    ) -> None:
        entry = TraceEntry(
            pc=cpu_state.pc & 0xFFFF,
            opcode=None if opcode is None else opcode & 0xFF,
            mnemonic=mnemonic,
            cycles=cycles,
            a=cpu_state.a & 0xFF,
            b=cpu_state.b & 0xFF,
            x=cpu_state.x & 0xFFFF,
            sp=cpu_state.sp & 0xFFFF,
            cc=cpu_state.cc & 0xFF,
            via_ifr=via_snapshot.get("IFR", 0) & 0xFF,
            via_ier=via_snapshot.get("IER", 0) & 0xFF,
            via_orb=via_snapshot.get("ORB", 0) & 0xFF,
            via_ddrb=via_snapshot.get("DDRB", 0) & 0xFF,
            via_t1=via_snapshot.get("T1", 0) & 0xFFFF,
            via_t2=via_snapshot.get("T2", 0) & 0xFFFF,
            wai=wai,
            halted=halted,
            note=note,
        )
        self._append(entry)

    def entries(self, limit: int | None = None) -> Iterable[TraceEntry]:
        count = self._size if limit is None else min(self._size, max(limit, 0))
        for offset in range(count):
            index = (self._index - count + offset) % self._capacity
            entry = self._entries[index]
            if entry is not None:
                yield entry

    def last_entry(self) -> TraceEntry | None:
        if self._size == 0:
            return None
        index = (self._index - 1) % self._capacity
        return self._entries[index]

    def format_entries(self, limit: int | None = None) -> Sequence[str]:
        lines: list[str] = []
        for entry in self.entries(limit):
            opcode = "--" if entry.opcode is None else f"{entry.opcode:02X}"
            mnemonic = entry.mnemonic or "?"
            flags: list[str] = []
            if entry.wai:
                flags.append("WAI")
            if entry.halted:
                flags.append("HALT")
            if entry.note:
                flags.append(entry.note)
            flag_repr = ",".join(flags) if flags else "-"
            line = (
                f"pc={entry.pc:04X} opcode={opcode} {mnemonic:<4} cycles={entry.cycles:02d} "
                f"A={entry.a:02X} B={entry.b:02X} X={entry.x:04X} SP={entry.sp:04X} CC={entry.cc:02X} "
                f"IFR={entry.via_ifr:02X} IER={entry.via_ier:02X} ORB={entry.via_orb:02X} DDRB={entry.via_ddrb:02X} "
                f"T1={entry.via_t1:04X} T2={entry.via_t2:04X} flags={flag_repr}"
            )
            lines.append(line)
        return lines

    def dump(self, category: str, limit: int | None = None) -> None:
        for line in self.format_entries(limit):
            debug_log(category, line)

    def _append(self, entry: TraceEntry) -> None:
        self._entries[self._index] = entry
        self._index = (self._index + 1) % self._capacity
        if self._size < self._capacity:
            self._size += 1
