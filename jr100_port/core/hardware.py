"""Hardware aggregation equivalent to Java AbstractHardware."""

from __future__ import annotations

from typing import Any

from .memory import MemorySystem


class Hardware:
    """Container for memory and I/O devices."""

    def __init__(self) -> None:
        self._memory = MemorySystem()
        self._display: Any = None
        self._sound_processor: Any = None
        self._keyboard: Any = None
        self._gamepad: Any = None
        self._application: Any = None

    def getMemory(self) -> MemorySystem:  # noqa: N802
        return self._memory

    def setDisplay(self, display: Any) -> None:  # noqa: N802
        self._display = display

    def getDisplay(self) -> Any:  # noqa: N802
        return self._display

    def setSoundProcessor(self, sound: Any) -> None:  # noqa: N802
        self._sound_processor = sound

    def getSoundProcessor(self) -> Any:  # noqa: N802
        return self._sound_processor

    def setKeyboard(self, keyboard: Any) -> None:  # noqa: N802
        self._keyboard = keyboard

    def getKeyboard(self) -> Any:  # noqa: N802
        return self._keyboard

    def setGamepad(self, gamepad: Any) -> None:  # noqa: N802
        self._gamepad = gamepad

    def getGamepad(self) -> Any:  # noqa: N802
        return self._gamepad

    def setApplication(self, application: Any) -> None:  # noqa: N802
        self._application = application

    def getApplication(self) -> Any:  # noqa: N802
        return self._application

    def saveState(self, state_set: Any) -> None:  # noqa: N802
        for memory in self._memory.getMemories():
            if hasattr(memory, "saveState"):
                memory.saveState(state_set)
        for component in (self._display, self._sound_processor, self._keyboard):
            if component is not None and hasattr(component, "saveState"):
                component.saveState(state_set)

    def loadState(self, state_set: Any) -> None:  # noqa: N802
        for memory in self._memory.getMemories():
            if hasattr(memory, "loadState"):
                memory.loadState(state_set)
        for component in (self._display, self._sound_processor, self._keyboard):
            if component is not None and hasattr(component, "loadState"):
                component.loadState(state_set)


__all__ = ["Hardware"]
