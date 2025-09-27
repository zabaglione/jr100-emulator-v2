"""Beeper device that mirrors the Java sound processor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Beeper:
    computer: object | None
    sampling_rate: float
    frequency: float = 0.0
    line_on: bool = False
    _backend: Any = field(init=False, default=None)
    _backend_active: bool = field(init=False, default=False)
    _backend_frequency: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        # pygame.mixer の初期化が完了していないとバックエンド生成に失敗するため、
        # ここでは利用可能かどうかだけを試行し、失敗時は後続の呼び出しに委ねる。
        self._ensure_backend()

    def setFrequency(self, timestamp: int, frequency: float) -> None:  # noqa: N802
        self.frequency = max(0.0, float(frequency))
        if self.line_on:
            self._apply_state()

    def setLineOn(self) -> None:  # noqa: N802
        self.line_on = True
        self._apply_state()

    def setLineOff(self) -> None:  # noqa: N802
        self.line_on = False
        self._apply_state()

    def reset(self) -> None:
        self.frequency = 0.0
        self.line_on = False
        self._apply_state()

    def execute(self) -> None:
        if self.line_on and self.frequency > 0.0:
            self._apply_state()

    def shutdown(self) -> None:
        if self._backend is not None:
            try:
                self._backend.shutdown()
            except Exception:
                pass
        self._backend = None
        self._backend_active = False
        self._backend_frequency = 0.0

    def saveState(self, state_set) -> None:  # noqa: N802
        state_set["beep.frequency"] = self.frequency
        state_set["beep.line_on"] = self.line_on

    def loadState(self, state_set) -> None:  # noqa: N802
        self.frequency = state_set.get("beep.frequency", self.frequency)
        self.line_on = state_set.get("beep.line_on", self.line_on)
        self._apply_state()

    def _apply_state(self) -> None:
        backend = self._backend
        if backend is None:
            if not self._ensure_backend():
                self._backend_active = False
                self._backend_frequency = 0.0
                return
            backend = self._backend
            if backend is None:
                return
        enabled = self.line_on and self.frequency > 0.0
        if (
            enabled != self._backend_active
            or (enabled and abs(self.frequency - self._backend_frequency) > 0.5)
        ):
            try:
                backend.set_state(enabled, self.frequency)
            except Exception:
                return
            self._backend_active = enabled
            self._backend_frequency = self.frequency if enabled else 0.0

    def _ensure_backend(self) -> bool:
        """Instantiate the pygame-backed beeper when possible."""

        if self._backend is not None:
            return True
        try:
            import pygame  # type: ignore

            if pygame.mixer.get_init() is None:
                return False
            from pyjr100.audio import SquareWaveBeeper  # type: ignore

            self._backend = SquareWaveBeeper(sample_rate=int(self.sampling_rate))
            return True
        except Exception:
            self._backend = None
            return False


__all__ = ["Beeper"]
