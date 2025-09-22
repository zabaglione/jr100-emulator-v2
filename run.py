"""Command-line entry point for the Python JR-100 emulator port.

The real emulator pipeline is not implemented yet. This script currently checks
for basic CLI arguments and prints guidance so that the workflow can be
incrementally extended in line with ``AGENTS.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyjr100.ui.app import AppConfig, JR100App


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="JR-100 emulator (Python, WIP)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        help="Path to the JR-100 ROM or PROG image for bootstrapping",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=2,
        help="Integer window scale factor (default: 2)",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Launch the emulator in fullscreen mode",
    )
    parser.add_argument(
        "--program",
        type=Path,
        help="Optional PROG file to load after reset",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.rom and not args.rom.exists():
        parser.error(f"ROM file not found: {args.rom}")

    if args.program and not args.program.exists():
        parser.error(f"Program file not found: {args.program}")

    config = AppConfig(
        rom_path=args.rom,
        program_path=args.program,
        scale=args.scale,
        fullscreen=args.fullscreen,
    )
    app = JR100App(config)
    try:
        app.run()
    except RuntimeError as exc:
        parser.exit(1, f"run.py: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
