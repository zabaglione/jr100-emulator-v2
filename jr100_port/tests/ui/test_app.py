from pathlib import Path
from types import SimpleNamespace

import pytest

from jr100_port.ui.app import AppConfig, JR100App


def make_prog(path: Path, payload: bytes) -> None:
    buf = bytearray()
    buf += b"PROG"
    buf += (2).to_bytes(4, "little")
    name = b"ROMTEST"
    buf += b"PNAM" + (len(name) + 4).to_bytes(4, "little") + len(name).to_bytes(4, "little") + name
    pbin_payload = (0xE000).to_bytes(4, "little") + len(payload).to_bytes(4, "little") + payload
    buf += b"PBIN" + len(pbin_payload).to_bytes(4, "little") + pbin_payload
    path.write_bytes(buf)


def make_program(path: Path, payload: bytes) -> None:
    buf = bytearray()
    buf += b"PROG"
    buf += (2).to_bytes(4, "little")
    pbas_payload = len(payload).to_bytes(4, "little") + payload
    buf += b"PBAS" + len(pbas_payload).to_bytes(4, "little") + pbas_payload
    path.write_bytes(buf)


def test_app_run_initialises_machine(tmp_path: Path) -> None:
    rom_path = tmp_path / "rom.prog"
    make_prog(rom_path, bytes([0xAA, 0xBB]))

    program_path = tmp_path / "program.prog"
    make_program(program_path, bytes([0x10, 0x20, 0x30]))

    app = JR100App(
        AppConfig(
            rom_path=rom_path,
            program_path=program_path,
            use_extended_ram=False,
        )
    )

    machine = app.initialise_machine()
    assert machine is not None
    assert machine.program_image is not None
    memory = machine.getHardware().getMemory()
    start = 0x0246
    assert memory.load8(start) == 0x10
    assert memory.load8(0xE000) == 0xAA


def test_app_requires_rom(tmp_path: Path) -> None:
    app = JR100App(AppConfig(rom_path=None))
    with pytest.raises(RuntimeError):
        app.initialise_machine()


def test_handle_key_event_updates_matrix(tmp_path: Path) -> None:
    rom_path = tmp_path / "rom.prog"
    make_prog(rom_path, bytes([0xAA] * 8))
    app = JR100App(AppConfig(rom_path=rom_path))
    machine = app.initialise_machine()
    keyboard = machine.keyboard

    # simulate mapping setup
    app._keymap[999] = (2, 3)
    assert keyboard.matrix[2] == 0x00
    app._handle_key_event(SimpleNamespace(key=999, unicode=""), True)
    assert keyboard.matrix[2] == 0x08
    app._handle_key_event(SimpleNamespace(key=999, unicode=""), False)
    assert keyboard.matrix[2] == 0x00


def test_handle_colon_uses_cmode_key(tmp_path: Path) -> None:
    rom_path = tmp_path / "rom.prog"
    make_prog(rom_path, bytes([0xAA] * 8))
    app = JR100App(AppConfig(rom_path=rom_path))
    machine = app.initialise_machine()
    keyboard = machine.keyboard

    app._semicolon_key = 123
    app._handle_key_event(SimpleNamespace(key=123, unicode=":"), True)
    assert keyboard.matrix[8] == 0x04
    app._handle_key_event(SimpleNamespace(key=123, unicode=":"), False)
    assert keyboard.matrix[8] == 0x00


def test_debug_overlay_surface_dimensions(tmp_path: Path) -> None:
    rom_path = tmp_path / "rom.prog"
    make_prog(rom_path, bytes([0xAA] * 8))
    app = JR100App(AppConfig(rom_path=rom_path, debug_overlay=True, scale=2))
    machine = app.initialise_machine()

    pygame = app._initialise_pygame()
    try:
        app._create_window(pygame)
        overlay = app._draw_overlay(pygame, machine, app._base_size[1] * app._config.scale)
        assert overlay is not None
        assert overlay.get_width() == app._overlay_width
        assert overlay.get_height() == app._base_size[1] * app._config.scale
    finally:
        pygame.quit()

    rom_path = tmp_path / "missing.prog"
    app = JR100App(AppConfig(rom_path=rom_path))
    with pytest.raises(RuntimeError):
        app.initialise_machine()
