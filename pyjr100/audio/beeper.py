"""Simple square-wave beeper driven by the VIA timer."""

from __future__ import annotations

from array import array
import math
from typing import Optional


class SquareWaveBeeper:
    """Manage a looping square-wave tone using pygame's mixer."""

    def __init__(
        self,
        *,
        sample_rate: int = 44_100,
        volume: float = 0.35,
        min_play_ms: int = 35,
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
        self._min_play_ms = max(0, min_play_ms)
        self._channel: Optional[pygame.mixer.Channel] = None
        self._sound: Optional[pygame.mixer.Sound] = None
        self._frequency: float = 0.0
        self._last_start_ms: int = 0

    # ------------------------------------------------------------------
    # Public API

    def set_state(self, enabled: bool, frequency: float) -> None:
        """Enable/disable the tone at ``frequency`` Hertz."""

        if not enabled or frequency <= 0.0:
            self._stop()
            return

        now = self._pygame.time.get_ticks()
        if self._sound is not None and abs(self._frequency - frequency) < 0.5:
            if self._channel is not None and not self._channel.get_busy():
                self._channel.play(self._sound, loops=-1)
                self._channel.set_volume(self._volume)
                self._last_start_ms = now
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
        self._last_start_ms = now

    def shutdown(self) -> None:
        """Stop any active tone and release resources."""

        self._stop()
        self._channel = None

    # ------------------------------------------------------------------
    # Internals

    def _stop(self) -> None:
        if self._channel is not None:
            if self._min_play_ms > 0:
                elapsed = self._pygame.time.get_ticks() - self._last_start_ms
                remaining = self._min_play_ms - elapsed
                if remaining > 0:
                    self._channel.fadeout(int(max(10, remaining)))
                else:
                    self._channel.stop()
            else:
                self._channel.stop()
        self._sound = None
        self._frequency = 0.0

    def _build_sound(self, frequency: float) -> Optional["pygame.mixer.Sound"]:
        if frequency <= 0.0:
            return None

        period_samples = max(32, int(round(self._sample_rate / frequency)))
        rank = int(((self._sample_rate / (2.0 * frequency)) + 1.0) / 2.0)
        rank = max(1, min(30, rank))

        buffer = array("h")
        amplitude = 12_000
        scale = (4.0 / math.pi) * amplitude
        for index in range(period_samples):
            phase = (2.0 * math.pi * index) / period_samples
            total = 0.0
            for harmonic in range(rank):
                k = 2 * harmonic + 1
                total += math.sin(k * phase) / k
            value = total * scale
            value = max(-amplitude, min(amplitude, value))
            sample = int(value)
            buffer.append(sample)

        try:
            sound = self._pygame.mixer.Sound(buffer=buffer.tobytes())
        except Exception:  # pragma: no cover - pygame error path
            return None
        return sound


__all__ = ["SquareWaveBeeper"]
