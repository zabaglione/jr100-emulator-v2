"""Simple square-wave beeper driven by the VIA timer."""

from __future__ import annotations

from array import array
from typing import Optional


class SquareWaveBeeper:
    """Manage a looping square-wave tone using pygame's mixer."""

    def __init__(
        self,
        *,
        sample_rate: int = 44_100,
        volume: float = 0.35,
    ) -> None:
        try:
            import pygame  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pygame is required for audio output") from exc

        if pygame.mixer.get_init() is None:
            raise RuntimeError("pygame mixer must be initialised before creating SquareWaveBeeper")

        self._pygame = pygame
        self._sample_rate = max(1, sample_rate)
        self._volume = max(0.0, min(1.0, volume))
        self._channel: Optional[pygame.mixer.Channel] = None
        self._sound: Optional[pygame.mixer.Sound] = None
        self._frequency: float = 0.0

    # ------------------------------------------------------------------
    # Public API

    def set_state(self, enabled: bool, frequency: float) -> None:
        """Enable/disable the tone at ``frequency`` Hertz."""

        if not enabled or frequency <= 0.0:
            self._stop()
            return

        if self._sound is not None and abs(self._frequency - frequency) < 0.5:
            if self._channel is not None and not self._channel.get_busy():
                self._channel.play(self._sound, loops=-1)
                self._channel.set_volume(self._volume)
            return

        sound = self._build_sound(frequency)
        if sound is None:
            self._stop()
            return

        channel = self._channel
        if channel is None:
            channel = self._pygame.mixer.find_channel(True)
            if channel is None:
                return
            self._channel = channel

        channel.play(sound, loops=-1)
        channel.set_volume(self._volume)
        self._sound = sound
        self._frequency = frequency

    def shutdown(self) -> None:
        """Stop any active tone and release resources."""

        self._stop()
        self._channel = None

    # ------------------------------------------------------------------
    # Internals

    def _stop(self) -> None:
        if self._channel is not None:
            self._channel.stop()
        self._sound = None
        self._frequency = 0.0

    def _build_sound(self, frequency: float) -> Optional["pygame.mixer.Sound"]:
        samples_per_period = max(2, int(self._sample_rate / max(1.0, frequency)))
        half_period = max(1, samples_per_period // 2)

        buffer = array("h")
        high = 24_000
        low = -high
        for index in range(samples_per_period):
            buffer.append(high if index < half_period else low)

        try:
            sound = self._pygame.mixer.Sound(buffer=buffer)
        except Exception:  # pragma: no cover - pygame error path
            return None
        return sound


__all__ = ["SquareWaveBeeper"]

