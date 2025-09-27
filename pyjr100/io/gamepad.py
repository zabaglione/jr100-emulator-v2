"""Gamepad state helpers for the JR-100 Python port."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GamepadState:
    """Track the logical state of the JR-100's extended I/O gamepad port."""

    _left: bool = False
    _right: bool = False
    _up: bool = False
    _down: bool = False
    _button: bool = False
    _base: int = 0xDF

    # Bit layout (active low):
    # bit7, bit6 : undefined (treated as 1)
    # bit5       : wired low (always 0)
    # bit4       : switch (button)
    # bit3       : down
    # bit2       : up
    # bit1       : left
    # bit0       : right
    _DEFAULT_STATUS = 0xDF
    _BIT_RIGHT = 0x01
    _BIT_LEFT = 0x02
    _BIT_UP = 0x04
    _BIT_DOWN = 0x08
    _BIT_BUTTON = 0x10

    def read(self) -> int:
        """Return the current 8-bit status presented on the bus."""

        status = self._base & 0xFF
        if self._right:
            status &= ~self._BIT_RIGHT
        if self._left:
            status &= ~self._BIT_LEFT
        if self._up:
            status &= ~self._BIT_UP
        if self._down:
            status &= ~self._BIT_DOWN
        if self._button:
            status &= ~self._BIT_BUTTON
        return status & 0xFF

    def write(self, value: int) -> None:
        """Update the baseline state as seen by the JR-100 CPU."""

        self._base = value & 0xFF

    def set_button(self, pressed: bool) -> None:
        """Update the primary button state (active low)."""

        self._button = pressed

    def set_directions(
        self,
        *,
        left: bool | None = None,
        right: bool | None = None,
        up: bool | None = None,
        down: bool | None = None,
    ) -> None:
        """Update one or more directional inputs (active low)."""

        if left is not None:
            self._left = left
        if right is not None:
            self._right = right
        if up is not None:
            self._up = up
        if down is not None:
            self._down = down

    def reset(self) -> None:
        """Clear any recorded input state."""

        self._base = self._DEFAULT_STATUS
        self._left = False
        self._right = False
        self._up = False
        self._down = False
        self._button = False


__all__ = ["GamepadState"]
