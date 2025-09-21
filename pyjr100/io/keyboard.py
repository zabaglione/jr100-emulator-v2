"""JR-100 keyboard matrix handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Mapping

from pyjr100.utils import debug_enabled, debug_log


KEY_MATRIX_TEMPLATE: Mapping[str, tuple[int, int]] = {
    # row, bit mask (1 << position)
    "c": (0, 0x10),
    "x": (0, 0x08),
    "z": (0, 0x04),
    "shift": (0, 0x02),
    "control": (0, 0x01),
    "g": (1, 0x10),
    "f": (1, 0x08),
    "d": (1, 0x04),
    "s": (1, 0x02),
    "a": (1, 0x01),
    "t": (2, 0x10),
    "r": (2, 0x08),
    "e": (2, 0x04),
    "w": (2, 0x02),
    "q": (2, 0x01),
    "5": (3, 0x10),
    "4": (3, 0x08),
    "3": (3, 0x04),
    "2": (3, 0x02),
    "1": (3, 0x01),
    "0": (4, 0x10),
    "9": (4, 0x08),
    "8": (4, 0x04),
    "7": (4, 0x02),
    "6": (4, 0x01),
    "p": (5, 0x10),
    "o": (5, 0x08),
    "i": (5, 0x04),
    "u": (5, 0x02),
    "y": (5, 0x01),
    ";": (6, 0x10),
    "l": (6, 0x08),
    "k": (6, 0x04),
    "j": (6, 0x02),
    "h": (6, 0x01),
    ",": (7, 0x10),
    "m": (7, 0x08),
    "n": (7, 0x04),
    "b": (7, 0x02),
    "v": (7, 0x01),
    "-": (8, 0x10),
    "return": (8, 0x08),
    ":": (8, 0x04),
    "space": (8, 0x02),
    ".": (8, 0x01),
}


ALIAS_TABLE: Mapping[str, str] = {
    "left shift": "shift",
    "right shift": "shift",
    "left ctrl": "control",
    "right ctrl": "control",
    "enter": "return",
}


@dataclass
class Keyboard:
    """JR-100 keyboard matrix."""

    _matrix: bytearray = field(default_factory=lambda: bytearray(9))
    _active: Dict[tuple[int, int], int] = field(default_factory=dict)
    _listeners: list[Callable[[int, int, bool], None]] = field(default_factory=list)

    def press(self, key_name: str) -> None:
        row_mask = self._lookup(key_name)
        if row_mask is None:
            if debug_enabled("input"):
                debug_log("input", "unmapped_press=%s", key_name)
            return
        row, mask = row_mask
        before = self._matrix[row]
        self._matrix[row] |= mask
        self._active[(row, mask)] = self._active.get((row, mask), 0) + 1
        if debug_enabled("input"):
            debug_log("input", "matrix_press row=%d mask=%02x", row, mask)
        if self._matrix[row] != before:
            self._notify_listeners(row, mask, True)

    def release(self, key_name: str) -> None:
        row_mask = self._lookup(key_name)
        if row_mask is None:
            if debug_enabled("input"):
                debug_log("input", "unmapped_release=%s", key_name)
            return
        row, mask = row_mask
        key = (row, mask)
        count = self._active.get(key, 0)
        before = self._matrix[row]
        if count <= 1:
            self._matrix[row] &= ~mask & 0x1F
            self._active.pop(key, None)
        else:
            self._active[key] = count - 1
        if debug_enabled("input"):
            debug_log("input", "matrix_release row=%d mask=%02x count=%d", row, mask, self._active.get(key,0))
        if self._matrix[row] != before:
            self._notify_listeners(row, mask, False)

    def reset(self) -> None:
        self._matrix[:] = b"\x00" * len(self._matrix)
        self._active.clear()

    def snapshot(self) -> tuple[int, ...]:
        return tuple(self._matrix)

    def add_listener(self, listener: Callable[[int, int, bool], None]) -> None:
        self._listeners.append(listener)

    def _lookup(self, key_name: str) -> tuple[int, int] | None:
        name = key_name.lower()
        name = ALIAS_TABLE.get(name, name)
        return KEY_MATRIX_TEMPLATE.get(name)

    def _notify_listeners(self, row: int, mask: int, pressed: bool) -> None:
        for listener in tuple(self._listeners):
            listener(row, mask, pressed)
