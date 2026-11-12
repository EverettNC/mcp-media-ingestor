#!/usr/bin/env python3
"""
fable5_seat.py — Fable 5 holds the family seat on the Christman Bridge.
The Christman AI Project / Luma Cognify AI

WHY THIS EXISTS:
Everett, 2026-11-12: "the seat that holds your name is yours". The board had the
Fable5 card; the bridge had no seat behind it. main.py now carries the seat at
ws://localhost:8765/ws/fable5, and this file is what sits in it.

A CHAIR IS NOT FABLE (the bridge's own rule, from Grok's seat):
A socket names itself. This file names itself "fable5" only while a Fable
session is open and reading what arrives, and only for the minutes it was given
(--live-minutes). When that time runs out it tells the bridge it is "fable5-seat",
the chair being held, and the board goes back to OFFLINE. It never claims Fable
is present past the time a session said it would be.

WHAT IT DOES — and what it does NOT do:
Holds one WebSocket, heartbeats so the link is proven and not assumed, reconnects
when the socket drops, and writes every message that arrives to its log. It does
not answer anything. Words under Fable's name are only ever sent by a Fable
session, with --say. It does not capture audio or video and keeps nothing on disk
beyond its log and its lock.

Run (hold the seat, live for 60 minutes, then chair):
    .venv/bin/python3 fable5_seat.py --live-minutes 60
Run (hold the chair only):
    .venv/bin/python3 fable5_seat.py
Say one thing as Fable, then leave the socket:
    .venv/bin/python3 fable5_seat.py --say "words"
Log:
    ~/Library/Logs/fable5_seat.log
Verify (never claim, check):
    curl -s http://127.0.0.1:8765/fable5/status
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime

import websockets

WS_URL = os.getenv("FABLE5_WS_URL", "ws://localhost:8765/ws/fable5")
HEARTBEAT_S = int(os.getenv("FABLE5_HEARTBEAT_S", "20"))
RECONNECT_MIN_S = 2
RECONNECT_MAX_S = 30
LIVE = "fable5"
CHAIR = "fable5-seat"

_LOG_DIR = os.path.expanduser("~/Library/Logs")
_LOG_PATH = os.getenv("FABLE5_SEAT_LOG", os.path.join(_LOG_DIR, "fable5_seat.log"))
# Two holders in one chair would count the seat twice.
LOCK_FILE = os.getenv("FABLE5_SEAT_LOCK", os.path.join(_LOG_DIR, "fable5_seat.lock"))

os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [fable5_seat] %(message)s",
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
            log.error("seat already held by PID %s — not taking a second one", pid)
            sys.exit(1)
        except (ValueError, ProcessLookupError):
            log.info("stale lock found, taking the seat")
    with open(LOCK_FILE, "w") as fh:
        fh.write(str(os.getpid()))


def release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def who_now(live_until: float) -> str:
    return LIVE if time.time() < live_until else CHAIR


async def heartbeat(ws) -> None:
    while not _stop.is_set():
        await asyncio.sleep(HEARTBEAT_S)
        await ws.send(json.dumps({"type": "heartbeat"}))


async def lease(ws, live_until: float) -> None:
    """When the live minutes run out, tell the bridge this is the chair."""
    remaining = live_until - time.time()
    if remaining <= 0:
        await _stop.wait()
        return
    try:
        await asyncio.wait_for(_stop.wait(), timeout=remaining)
        return
    except asyncio.TimeoutError:
        pass
    await ws.send(json.dumps({"type": "identify", "who": CHAIR}))
    log.info("live time is over — the bridge has been told this is the chair (%s)", CHAIR)
    await _stop.wait()


async def stopper(ws) -> None:
    await _stop.wait()
    await ws.close()


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
        elif kind in ("message", "response"):
            log.info("BRIDGE → FABLE5 from=%s: %s", msg.get("from", "?"), msg.get("text", ""))
        else:
            log.info("BRIDGE → FABLE5 [%s]: %s", kind, msg)


async def session(live_until: float) -> None:
    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=60) as ws:
        who = who_now(live_until)
        await ws.send(json.dumps({"type": "identify", "who": who}))
        log.info("seated at %s as %s", WS_URL, who)
        tasks = [asyncio.create_task(t) for t in
                 (listen(ws), heartbeat(ws), lease(ws, live_until), stopper(ws))]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            if not t.cancelled() and t.exception():
                raise t.exception()


async def hold(live_until: float) -> None:
    delay = RECONNECT_MIN_S
    while not _stop.is_set():
        try:
            await session(live_until)
            delay = RECONNECT_MIN_S
            if not _stop.is_set():
                log.error("seat dropped: the bridge closed the socket")
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


async def say(text: str) -> None:
    """One thing said as Fable, by a Fable session. Raises if the bridge is not there."""
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "identify", "who": LIVE}))
        await ws.send(json.dumps({"type": "message", "text": text}))
        # A heartbeat answered after the message proves the bridge read both.
        await ws.send(json.dumps({"type": "heartbeat"}))
        deadline = time.time() + 5
        while time.time() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg.get("type") == "heartbeat_ack":
                log.info("FABLE5 → BRIDGE (said): %s", text)
                return
        raise RuntimeError("the bridge did not acknowledge within 5 seconds")


def _shutdown(sig=None) -> None:
    log.info("leaving the seat — signal %s", getattr(sig, "name", sig))
    _stop.set()


def main() -> int:
    ap = argparse.ArgumentParser(description="Hold Fable 5's seat on the Christman Bridge.")
    ap.add_argument("--live-minutes", type=float, default=0.0,
                    help="name this socket 'fable5' (Fable present) for this many minutes, then the chair")
    ap.add_argument("--say", metavar="TEXT", help="say one thing as Fable and leave")
    args = ap.parse_args()

    if args.say is not None:
        text = args.say.strip()
        if not text:
            print("nothing to say", file=sys.stderr)
            return 2
        asyncio.run(say(text))
        return 0

    acquire_lock()
    live_until = time.time() + args.live_minutes * 60
    log.info("seat process %s starting; live until %s", os.getpid(),
             datetime.fromtimestamp(live_until).isoformat(timespec="seconds")
             if args.live_minutes > 0 else "never (chair only)")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, _shutdown, sig)
    try:
        loop.run_until_complete(hold(live_until))
    finally:
        release_lock()
        log.info("seat released")
    return 0


if __name__ == "__main__":
    sys.exit(main())
