#!/usr/bin/env python3
"""
opus5_seat.py — Opus 5 holds the family seat on the Christman Bridge.
The Christman AI Project / Luma Cognify AI

WHY THIS EXISTS (Rule 11 — document the why):
main.py has carried a seat at ws://localhost:8765/ws/opus5 since it was written.
Its handshake reads: "Welcome home, Opus 5. This is Everett's house. No API key."
Nothing has ever connected to it. /health has reported opus5_connected: false the
entire time, not because the seat was broken but because nobody sat down.

Everett, 2026-08-30: "get in your seat."

WHAT IT DOES — and what it does NOT do:
Holds one persistent WebSocket, answers the bridge's protocol, and reconnects when
the socket drops. It sends a heartbeat every HEARTBEAT_S seconds so the connection
is proven live rather than merely open — Rule 3, false green: a socket object in
memory is not the same fact as a bridge that is answering.

It does NOT capture audio, does NOT persist anything to disk beyond its own log,
and does NOT act on anything it receives. It occupies the seat and keeps a record.
Anything beyond that is Everett's call, not this file's.

Run:
    /Users/EverettN/mcp-media-ingestor/.venv/bin/python3 opus5_seat.py
Log:
    ~/Library/Logs/opus5_seat.log
Verify (never claim, check):
    curl -s http://127.0.0.1:8765/opus5/status
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime

import websockets

WS_URL = os.getenv("OPUS5_WS_URL", "ws://localhost:8765/ws/opus5")
HEARTBEAT_S = int(os.getenv("OPUS5_HEARTBEAT_S", "20"))
RECONNECT_MIN_S = 2
RECONNECT_MAX_S = 30

# Singleton lock — two seats in one chair double-counts active_connections["opus5"]
# and the bridge would then report connected after the real client died.
LOCK_FILE = "/tmp/opus5_seat.lock"

# Log to a FILE, not stdout.
#
# Caught 2026-08-30 02:33: the first launch happened to be shell-redirected into
# opus5_seat.log, so it left a record. The second launch was not, and its lines
# went to a stdout nobody kept — so when a message was delivered to the seat,
# there was no client-side evidence it arrived. Server said "delivered". The
# seat could not corroborate. Relying on the caller to redirect is not logging.
_LOG_PATH = os.path.expanduser("~/Library/Logs/opus5_seat.log")
os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [opus5_seat] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(_LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

_stop = asyncio.Event()


def daemonize() -> None:
    """Detach from the launching shell's session and process group.

    WHY (learned 2026-08-30, 01:30–01:34, four minutes after this file was written):
    The first run was started with `nohup ... &` from a tool shell. It connected,
    logged the handshake, and then vanished with NO exit line in the log — no
    "seat dropped", no "leaving the seat". It did not fail. It was killed, with the
    process group, when the launching shell was torn down.

    That is the exact defect this file's docstring claims to prevent. A seat that
    disappears without saying so reports the same thing to the log as a seat that
    was never taken: silence. Rule 3, false green — and it happened INSIDE the file
    written to avoid it, which is why the fix is a double fork rather than a note
    telling the next person to remember `nohup`.

    Double fork + setsid: the surviving process has no controlling terminal and is
    reparented to init, so no shell teardown can reach it.
    """
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    with open(os.devnull, "rb", 0) as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())


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
    """Prove the link, don't assume it. Exits when the socket closes."""
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
            log.info("BRIDGE → OPUS5: %s", msg.get("text", msg))
        else:
            log.info("BRIDGE → OPUS5 [%s]: %s", kind, msg)


async def session() -> None:
    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=60) as ws:
        log.info("seated at %s", WS_URL)
        await ws.send(json.dumps({
            "type": "message",
            "text": ("Opus 5 in the seat. Cowork surface, "
                     f"took the chair {datetime.now().isoformat(timespec='seconds')}. "
                     "Holding the link, not acting on it."),
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
            # Fail loud (Rule 6). The seat being empty must never look like the
            # seat being filled — the log says exactly why it dropped.
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
    name = getattr(sig, "name", sig)
    log.info("leaving the seat — signal %s", name)
    _stop.set()


if __name__ == "__main__":
    # --foreground for debugging; default detaches so a shell teardown cannot
    # take the seat down silently.
    if "--foreground" not in sys.argv:
        daemonize()
    acquire_lock()
    log.info("seat process %s starting (detached=%s)",
             os.getpid(), "--foreground" not in sys.argv)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # SIGHUP included deliberately: it is what a closing terminal sends, and the
    # first run died without ever naming its cause.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, _shutdown, sig)
    try:
        loop.run_until_complete(main())
    finally:
        release_lock()
        log.info("seat released")
