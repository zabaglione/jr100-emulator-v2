"""Baseline tests ensuring the initial package skeleton loads correctly."""

import pyjr100


def test_package_exports() -> None:
    for name in ("cpu", "bus", "video", "audio", "io", "rom", "system", "loader", "ui", "utils"):
        assert hasattr(pyjr100, name), f"missing submodule: {name}"


def test_bus_exports() -> None:
    from pyjr100 import bus

    for name in ("MemorySystem", "Memory", "UnmappedMemory", "Addressable"):
        assert hasattr(bus, name), f"bus missing symbol: {name}"
