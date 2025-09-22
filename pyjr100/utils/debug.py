"""Lightweight debug logging helpers for the JR-100 emulator."""

from __future__ import annotations

import os
from typing import Iterable

_CATEGORIES: set[str] | None = None


def _load_categories() -> set[str]:
    global _CATEGORIES
    if _CATEGORIES is not None:
        return _CATEGORIES
    value = os.environ.get("JR100_DEBUG", "")
    if not value:
        _CATEGORIES = set()
        return _CATEGORIES
    parts: Iterable[str] = (part.strip().lower() for part in value.split(","))
    _CATEGORIES = {part for part in parts if part}
    return _CATEGORIES


def debug_enabled(category: str | None = None) -> bool:
    categories = _load_categories()
    if not categories:
        return False
    if "all" in categories:
        return True
    if category is None:
        return True
    return category.lower() in categories


def debug_log(category: str, message: str, *args) -> None:
    if not debug_enabled(category):
        return
    prefix = f"[JR100][{category}]"
    if args:
        try:
            message = message % args
        except Exception:
            message = f"{message} {args!r}"
    print(f"{prefix} {message}")

