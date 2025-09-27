"""Unit tests for the JR-100 gamepad state helper."""

from __future__ import annotations

from pyjr100.io import GamepadState


def test_default_state_is_idle() -> None:
    state = GamepadState()
    assert state.read() == 0xDF


def test_direction_bits_are_active_low() -> None:
    state = GamepadState()
    state.set_directions(left=True, up=True)
    assert state.read() == 0xD9  # 0xDF with bit1 and bit2 cleared
    state.set_directions(left=False)
    assert state.read() == 0xDB


def test_button_bit_is_active_low() -> None:
    state = GamepadState()
    state.set_button(True)
    assert state.read() == 0xCF
    state.set_button(False)
    assert state.read() == 0xDF


def test_override_can_force_bus_value() -> None:
    state = GamepadState()
    state.write(0xDF)
    assert state.read() == 0xDF
    state.set_directions(right=True)
    assert state.read() == 0xDE
