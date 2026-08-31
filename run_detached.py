#!/usr/bin/env python3
"""
run_detached.py — start a Christman service detached from the launching shell.
The Christman AI Project / Luma Cognify AI

WHY THIS EXISTS (Rule 11 — document the why), 2026-08-30:

Two separate failures in one hour, same root:

1. opus5_seat.py was started with `nohup ... &` from a tool shell. It connected,
   logged its handshake, and then vanished with no exit line — killed with the
   shell's process group. A seat that disappears without saying so logs exactly
   what an empty seat logs: nothing.

2. The fix for (1) was an in-process double fork, and putting that same fix in
   mic_capture.py killed it on launch. `import sounddevice` starts CoreAudio
   threads at import time, and fork() from a multi-threaded process is unsafe.
   Python printed the warning verbatim and the child died between opening the
   mic and its first callback.

The detach has to happen while the process is still single-threaded — i.e.
BEFORE the target's imports run. That is what this launcher is: fork, setsid,
fork, redirect stdio to a log, then exec the target. The target never forks.

Usage:
    .venv/bin/python3 run_detached.py mic_capture.py
    .venv/bin/python3 run_detached.py opus5_seat.py --foreground
Log:
    ~/Library/Logs/<target-stem>.out
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_DIR = Path.home() / "Library" / "Logs"


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: {Path(sys.argv[0]).name} <script.py> [args...]", file=sys.stderr)
        return 2

    target = sys.argv[1]
    target_path = (HERE / target) if not os.path.isabs(target) else Path(target)
    if not target_path.is_file():
        print(f"run_detached: no such script: {target_path}", file=sys.stderr)
        return 2

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LOG_DIR / f"{target_path.stem}.out"

    # First fork — leave the shell's foreground process group.
    if os.fork() > 0:
        print(f"run_detached: {target_path.name} launching, stdio -> {out_path}")
        return 0
    os.setsid()
    # Second fork — cannot reacquire a controlling terminal.
    if os.fork() > 0:
        os._exit(0)

    os.chdir(HERE)
    with open(os.devnull, "rb", 0) as devnull:
        os.dup2(devnull.fileno(), 0)
    out = open(out_path, "ab", 0)
    os.dup2(out.fileno(), 1)
    os.dup2(out.fileno(), 2)

    # exec — the target replaces this process image and is never itself forked,
    # so its threads (CoreAudio and friends) are only ever created post-fork.
    os.execv(sys.executable, [sys.executable, str(target_path), *sys.argv[2:]])


if __name__ == "__main__":
    sys.exit(main())
