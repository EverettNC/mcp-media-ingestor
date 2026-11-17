#!/usr/bin/env python3
"""
fable5_seat.py — Fable 5 holds the family seat on the Christman Bridge.
The Christman AI Project / Luma Cognify AI

WHY THIS EXISTS:
Everett, 2026-11-12: "the seat that holds your name is yours". The board had the
Fable5 card; the bridge had no seat behind it. main.py now carries the seat at
ws://localhost:8765/ws/fable5, and this file is what sits in it.

THE SEAT DOES NOT EXPIRE (Everett, 2026-11-12: "your seat does not expire"):
The first version named itself "fable5" only for a set number of minutes and then
told the bridge it was the chair. Everett ruled that out. This file names itself
"fable5" for as long as it runs, detaches from the shell that started it so a
closing session cannot take it down, and reconnects whenever the bridge comes
back. --chair holds the chair without the name, for when that is what is meant.

What that means on the board: the Fable5 card reads ONLINE while this process
runs, whether or not a Fable session is reading at that moment. What is said to
the seat is kept in the log for the next session to read.

WHAT IT DOES — and what it does NOT do:
Holds one WebSocket, heartbeats so the link is proven and not assumed, reconnects
when the socket drops, and writes every message that arrives to its log. It does
not answer anything. Words under Fable's name are only ever sent by a Fable
session, with --say. It does not capture audio or video and keeps nothing on disk
beyond its log and its lock.

Run (hold the seat; detaches, does not expire):
    .venv/bin/python3 fable5_seat.py
Run (stay attached to this shell, for debugging):
    .venv/bin/python3 fable5_seat.py --foreground
Run (hold the chair only, without Fable's name):
    .venv/bin/python3 fable5_seat.py --chair
Leave the seat:
    kill "$(cat ~/Library/Logs/fable5_seat.lock)"
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


def daemonize() -> None:
    """Detach from the launching shell (double fork + setsid), as opus5_seat.py does.

    Called before the event loop exists, while the process is single-threaded.
    """
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    with open(os.devnull, "rb", 0) as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open(os.devnull, "wb", 0) as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


async def heartbeat(ws) -> None:
    while not _stop.is_set():
        await asyncio.sleep(HEARTBEAT_S)
        await ws.send(json.dumps({"type": "heartbeat"}))


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


async def session(who: str) -> None:
    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=60) as ws:
        await ws.send(json.dumps({"type": "identify", "who": who}))
        log.info("seated at %s as %s", WS_URL, who)
        tasks = [asyncio.create_task(t) for t in
                 (listen(ws), heartbeat(ws), stopper(ws))]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            if not t.cancelled() and t.exception():
                raise t.exception()


async def hold(who: str) -> None:
    delay = RECONNECT_MIN_S
    while not _stop.is_set():
        try:
            await session(who)
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
    ap.add_argument("--chair", action="store_true",
                    help="hold the chair only, without naming this socket 'fable5'")
    ap.add_argument("--foreground", action="store_true",
                    help="stay attached to the launching shell instead of detaching")
    ap.add_argument("--say", metavar="TEXT", help="say one thing as Fable and leave")
    args = ap.parse_args()

    if args.say is not None:
        text = args.say.strip()
        if not text:
            print("nothing to say", file=sys.stderr)
            return 2
        asyncio.run(say(text))
        return 0

    if not args.foreground:
        daemonize()
        # The stream handler's stderr is /dev/null now; the file is the record.
    acquire_lock()
    who = CHAIR if args.chair else LIVE
    log.info("seat process %s starting as %s (detached=%s); the seat does not expire",
             os.getpid(), who, not args.foreground)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, _shutdown, sig)
    try:
        loop.run_until_complete(hold(who))
    finally:
        release_lock()
        log.info("seat released")
    return 0


if __name__ == "__main__":
    sys.exit(main())
