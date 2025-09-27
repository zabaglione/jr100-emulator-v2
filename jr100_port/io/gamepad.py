"""Gamepad state helpers mirroring the JR-100 behaviour."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GamepadState:
    """Tracks joystick direction and button state.

    Bit layout (mirrors ExtendedIOPort comment):
    bit0: Right, bit1: Left, bit2: Up, bit3: Down, bit4: Switch (button), bit5: 0, bit6-7: undefined.
    """

    right: bool = False
    left: bool = False
    up: bool = False
    down: bool = False
    button: bool = False

    def set_direction(
        self,
        *,
        right: bool | None = None,
        left: bool | None = None,
        up: bool | None = None,
        down: bool | None = None,
    ) -> None:
        if right is not None:
            self.right = right
        if left is not None:
            self.left = left
        if up is not None:
            self.up = up
        if down is not None:
            self.down = down

    def set_button(self, pressed: bool) -> None:
        self.button = pressed

    def clear(self) -> None:
        self.right = self.left = self.up = self.down = self.button = False

    def to_byte(self) -> int:
        value = 0
        if self.right:
            value |= 0x01
        if self.left:
            value |= 0x02
        if self.up:
            value |= 0x04
        if self.down:
            value |= 0x08
        if self.button:
            value |= 0x10
        return value & 0xFF


__all__ = ["GamepadState"]
