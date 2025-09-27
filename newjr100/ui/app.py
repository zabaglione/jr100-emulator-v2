"""Pygame front-end wiring for the new-core machine."""

from __future__ import annotations

from pathlib import Path

from pyjr100.ui.app import AppConfig, JR100App, _prepare_rom_image

from newjr100.system.machine import Machine, MachineConfig, create_machine


class NewJR100App(JR100App):
    """JR-100 application subclass that instantiates the new-core machine."""

    def _create_machine(self, rom_path: Path) -> Machine:  # type: ignore[override]
        rom_payload, _ = _prepare_rom_image(rom_path)

        machine = create_machine(
            MachineConfig(
                use_extended_ram=self._config.use_extended_ram,
                rom_image=rom_payload,
                via_buzzer=self._handle_buzzer,
                via_font=self._handle_font_select,
                gamepad_state=self._gamepad_state if self._config.enable_gamepad else None,
            )
        )

        if self._config.enable_gamepad:
            self._gamepad_state = machine.gamepad

        return machine


__all__ = [
    "AppConfig",
    "NewJR100App",
]
