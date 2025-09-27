"""JR-100 keyboard matrix handler (simplified)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class JR100Keyboard:
    """Maintains the 16x8 key matrix expected by the VIA."""

    computer: object | None = None
    matrix: List[int] = field(default_factory=lambda: [0x00] * 16)

    def getKeyMatrix(self) -> List[int]:  # noqa: N802
        return self.matrix

    def reset(self) -> None:
        self.matrix = [0x00] * 16

    def execute(self) -> None:
        return None

    def set_key_state(self, row: int, column: int, pressed: bool) -> None:
        if not (0 <= row < len(self.matrix) and 0 <= column < 8):
            return
        mask = 1 << column
        if pressed:
            self.matrix[row] |= mask
        else:
            self.matrix[row] &= ~mask

    def saveState(self, state_set) -> None:  # noqa: N802
        state_set["keyboard.matrix"] = list(self.matrix)

    def loadState(self, state_set) -> None:  # noqa: N802
        self.matrix = list(state_set.get("keyboard.matrix", self.matrix))


__all__ = ["JR100Keyboard"]
