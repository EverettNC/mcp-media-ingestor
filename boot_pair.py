#!/usr/bin/env python3
"""
boot_pair.py — THEWHOLEHOUSE :9785 and Christman Bridge :8765 come up together.

WHY (2026-08-31):
The house is the complete supplier for the bridge. Starting 8765 alone used
to look like a bridge failure when the house was dark. Starting the house
alone left the family seats with no door. They boot as a pair: house first,
then the bridge, each skipped if already answering.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOUSE = Path.home() / "THEWHOLEHOUSE"
LOG_DIR = Path.home() / "Library" / "Logs"
HOUSE_URL = "http://127.0.0.1:9785/"
BRIDGE_HEALTH = "http://127.0.0.1:8765/health"
NPM = "/usr/local/bin/npm"
PYTHON = HERE / ".venv" / "bin" / "python3"


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait(url: str, seconds: float, label: str) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _http_ok(url):
            print(f"boot_pair: {label} up — {url}")
            return True
        time.sleep(0.5)
    print(f"boot_pair: {label} DID NOT ANSWER — {url}", file=sys.stderr)
    return False


def _start_house() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "thewholehouse.out"
    log = open(log_path, "ab", buffering=0)
    env = os.environ.copy()
    env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    subprocess.Popen(
        [NPM, "run", "dev"],
        cwd=str(HOUSE),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
        env=env,
    )
    print(f"boot_pair: house launching, stdio -> {log_path}")


def _start_bridge() -> None:
    if not PYTHON.is_file():
        raise SystemExit(f"boot_pair: no venv python at {PYTHON}")
    result = subprocess.run(
        [str(PYTHON), str(HERE / "run_detached.py"), "main.py"],
        cwd=str(HERE),
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"boot_pair: run_detached main.py exited {result.returncode}")


def main() -> int:
    if not HOUSE.is_dir():
        print(f"boot_pair: house is not on disk: {HOUSE}", file=sys.stderr)
        return 1

    if _http_ok(HOUSE_URL):
        print("boot_pair: house already answering on 9785")
    else:
        _start_house()
        if not _wait(HOUSE_URL, 40, "house :9785"):
            return 1

    if _http_ok(BRIDGE_HEALTH):
        print("boot_pair: bridge already answering on 8765")
    else:
        _start_bridge()
        if not _wait(BRIDGE_HEALTH, 40, "bridge :8765"):
            return 1

    print("boot_pair: pair is up — house 9785, bridge 8765")
    return 0


if __name__ == "__main__":
    sys.exit(main())
