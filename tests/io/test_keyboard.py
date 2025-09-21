"""Tests for the JR-100 keyboard matrix handling."""

from __future__ import annotations

from pyjr100.io import Keyboard


def test_key_down_and_up() -> None:
    kb = Keyboard()

    kb.press("a")
    assert kb.snapshot()[1] & 0x01

    kb.release("a")
    assert kb.snapshot()[1] & 0x01 == 0


def test_modifier_keys_map_to_same_bit() -> None:
    kb = Keyboard()
    kb.press("left shift")
    kb.press("right shift")

    assert kb.snapshot()[0] & 0x02

    kb.release("left shift")
    assert kb.snapshot()[0] & 0x02

    kb.release("right shift")
    assert kb.snapshot()[0] & 0x02 == 0


def test_reset_clears_matrix() -> None:
    kb = Keyboard()
    kb.press("q")
    kb.reset()
    assert all(value == 0 for value in kb.snapshot())
