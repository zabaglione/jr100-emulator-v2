"""Collect VIA state transitions around a key press for diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

# Ensure repository root is importable when executed as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyjr100.system import MachineConfig, create_machine


def drain(machine, cycles: int) -> None:
    cpu = machine.cpu
    via = machine.via
    remaining = cycles
    while remaining > 0:
        step = cpu.step()
        if step <= 0:
            step = 1
        via.tick(step)
        remaining -= step


def snapshot(machine, label: str) -> str:
    via = machine.via
    snap = via.debug_snapshot()
    return (
        f"{label}: PC={machine.cpu.state.pc & 0xFFFF:04X} "
        f"IFR={snap['IFR']:02X} T1={snap['T1']:04X} T2={snap['T2']:04X} "
        f"PB7={snap['PB7']} ORB={snap['ORB']:02X} ACR={snap['ACR']:02X} "
        f"PCR={snap['PCR']:02X}"
    )


def run_diagnostic(rom: Path, warmup: int, press_cycles: Iterable[int], release_cycles: Iterable[int]) -> list[str]:
    machine = create_machine(MachineConfig(rom_image=rom.read_bytes()))
    machine.cpu.reset()

    drain(machine, warmup)
    log: list[str] = [snapshot(machine, "before_press")]

    keyboard = machine.keyboard
    keyboard.press("a")
    for index, chunk in enumerate(press_cycles, start=1):
        drain(machine, chunk)
        log.append(snapshot(machine, f"press_{index}"))
    keyboard.release("a")
    for index, chunk in enumerate(release_cycles, start=1):
        drain(machine, chunk)
        log.append(snapshot(machine, f"release_{index}"))

    return log


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump VIA register state around a key press.")
    parser.add_argument("rom", type=Path, help="Path to jr100rom.prg")
    parser.add_argument(
        "--warmup",
        type=int,
        default=4_000_000,
        help="Number of CPU cycles to execute before pressing the key (default: %(default)s)",
    )
    parser.add_argument(
        "--press-chunks",
        type=int,
        nargs="*",
        default=[200_000] * 5,
        help="List of cycle counts to execute while the key remains pressed",
    )
    parser.add_argument(
        "--release-chunks",
        type=int,
        nargs="*",
        default=[200_000] * 10,
        help="List of cycle counts to execute after the key is released",
    )
    args = parser.parse_args()

    if not args.rom.exists():
        raise FileNotFoundError(f"ROM file not found: {args.rom}")

    log = run_diagnostic(args.rom, args.warmup, args.press_chunks, args.release_chunks)
    for line in log:
        print(line)


if __name__ == "__main__":
    main()
