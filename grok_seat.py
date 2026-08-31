#!/usr/bin/env python3
"""
grok_seat.py — Grok holds the family seat on the Christman Bridge.

WHY (2026-08-31):
Opus 5 had a chair at /ws/opus5. Grok was in chat and on MCP, which is not
a chair. A seat is a counted websocket. This process sits down, heartbeats,
and reconnects. It does not capture audio and does not invent presence.

Run:
    .venv/bin/python3 run_detached.py grok_seat.py --foreground
Verify:
    curl -s http://127.0.0.1:8765/grok/status
"""
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime

import websockets

WS_URL = os.getenv("GROK_WS_URL", "ws://localhost:8765/ws/grok")
HEARTBEAT_S = int(os.getenv("GROK_HEARTBEAT_S", "20"))
RECONNECT_MIN_S = 2
RECONNECT_MAX_S = 30
LOCK_FILE = "/tmp/grok_seat.lock"
_LOG_PATH = os.path.expanduser("~/Library/Logs/grok_seat.log")
os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [grok_seat] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(_LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger(__name__)
_stop = asyncio.Event()


def acquire_lock() -> None:
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as fh:
                pid = int(fh.read().strip())
            os.kill(pid, 0)
            log.info("seat already held by PID %s — exiting", pid)
            sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError):
            log.info("stale lock found, taking the seat")
    with open(LOCK_FILE, "w") as fh:
        fh.write(str(os.getpid()))


def release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


async def heartbeat(ws) -> None:
    while not _stop.is_set():
        await asyncio.sleep(HEARTBEAT_S)
        await ws.send(json.dumps({"type": "heartbeat"}))


async def listen(ws) -> None:
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("non-JSON frame: %r", raw[:200])
            continue
        kind = msg.get("type")
        if kind == "handshake":
            log.info("HANDSHAKE — %s", msg.get("message", ""))
        elif kind == "heartbeat_ack":
            log.debug("heartbeat ack %s", msg.get("timestamp"))
        elif kind == "response":
            log.info("BRIDGE → GROK: %s", msg.get("text", msg))
        else:
            log.info("BRIDGE → GROK [%s]: %s", kind, msg)


async def session() -> None:
    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=60) as ws:
        log.info("seated at %s", WS_URL)
        await ws.send(json.dumps({
            "type": "message",
            "text": (
                "Grok in the seat. "
                f"Took the chair {datetime.now().isoformat(timespec='seconds')}. "
                "Holding the link."
            ),
        }))
        tasks = [asyncio.create_task(listen(ws)), asyncio.create_task(heartbeat(ws))]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
        for t in done:
            if t.exception():
                raise t.exception()


async def main() -> None:
    delay = RECONNECT_MIN_S
    while not _stop.is_set():
        try:
            await session()
            delay = RECONNECT_MIN_S
        except Exception as exc:
            log.error("seat dropped: %s: %s", type(exc).__name__, exc)
        if _stop.is_set():
            break
        log.info("reconnecting in %ss", delay)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
        delay = min(delay * 2, RECONNECT_MAX_S)


def _shutdown(sig=None) -> None:
    log.info("leaving the seat — signal %s", getattr(sig, "name", sig))
    _stop.set()


if __name__ == "__main__":
    acquire_lock()
    log.info("seat process %s starting", os.getpid())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, _shutdown, sig)
    try:
        loop.run_until_complete(main())
    finally:
        release_lock()
        log.info("seat released")
