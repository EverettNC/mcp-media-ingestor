"""
mic_capture.py — Continuous mic → WebSocket bridge client
The Christman AI Project / Luma Cognify AI

Captures Mac microphone at 16kHz mono PCM16 and streams
base64-encoded chunks to the realtime_audio.py WebSocket server.

Usage:
    python mic_capture.py
    # or auto-start via LaunchAgent (see below)

Requires: sounddevice, websockets, numpy
    pip install sounddevice websockets numpy
"""

import asyncio
import base64
import json
import logging
import os
import signal
import sys

import numpy as np
import sounddevice as sd
import websockets

# ── Singleton lock — prevents multiple mic_capture instances ─────────────────
_LOCK_FILE = "/tmp/mic_capture.lock"

def _acquire_singleton():
    """Exit immediately if another mic_capture.py is already running."""
    if os.path.exists(_LOCK_FILE):
        try:
            with open(_LOCK_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # signal 0 = just check existence
            print(f"[mic_capture] Another instance already running (PID {pid}). Exiting.")
            sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # stale lock — proceed
    with open(_LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

def _release_singleton():
    try:
        os.remove(_LOCK_FILE)
    except FileNotFoundError:
        pass

# A log FILE, not stdout.
#
# WHY (2026-08-30): this process ran from Friday 06:47 to Sunday 01:40 with a
# dead socket — `lsof` on its PID showed no TCP connection at all — and produced
# ZERO evidence, because every line above went to a stdout nobody was reading.
# Two days of failure, invisible. The process being alive was the only signal
# available, and it said the opposite of the truth.
_LOG_PATH = os.path.expanduser("~/Library/Logs/mic_capture.log")
os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mic_capture] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(_LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
WS_URL = "ws://localhost:8765/ws/audio"
SAMPLE_RATE = 16000       # Hz — Porch / PCM16 mono
CHUNK_SECONDS = 2.0       # seconds per send
CHANNELS = 1              # mono
DTYPE = "int16"           # PCM16

# ── Audio capture queue ───────────────────────────────────────────────────────
audio_queue: asyncio.Queue = None  # set in main()
event_loop: asyncio.AbstractEventLoop = None  # set in main()
_frames_in = 0  # counts callbacks — proves the mic is actually delivering


def _enqueue(item) -> None:
    """Runs ON THE EVENT LOOP. Never call this from the audio thread directly."""
    if audio_queue is None:
        return
    try:
        audio_queue.put_nowait(item)
    except asyncio.QueueFull:
        try:
            audio_queue.get_nowait()   # drop oldest, keep the freshest audio
        except asyncio.QueueEmpty:
            pass
        try:
            audio_queue.put_nowait(item)
        except asyncio.QueueFull:
            pass


def mic_callback(indata: np.ndarray, frames: int, time, status):
    """sounddevice callback — runs on the AUDIO THREAD, not the event loop.

    THE BUG THIS FIXES (2026-08-30): this used to call audio_queue.put_nowait()
    directly. asyncio.Queue is NOT thread-safe. Putting from a foreign thread can
    leave a coroutine parked on `await audio_queue.get()` forever, because the
    waiter's future is never scheduled on the loop — no exception, no reconnect,
    no log line. A silent deadlock that looks exactly like a healthy process.

    call_soon_threadsafe is the whole fix: hand the item to the loop, let the
    loop do the put.
    """
    global _frames_in
    if status:
        logger.warning("Mic status: %s", status)
    if audio_queue is None or event_loop is None:
        return
    _frames_in += 1
    try:
        event_loop.call_soon_threadsafe(_enqueue, indata.copy())
    except RuntimeError:
        pass  # loop closing — shutdown in progress

# ── WebSocket sender ──────────────────────────────────────────────────────────
async def stream_mic_to_bridge():
    """Capture mic and stream to the WebSocket bridge. Reconnects on drop."""
    chunk_samples = int(SAMPLE_RATE * CHUNK_SECONDS)
    buffer = np.zeros((0,), dtype=np.int16)

    while True:
        try:
            logger.info(f"Connecting to {WS_URL} ...")
            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=120,
                open_timeout=15,
            ) as ws:
                logger.info("Connected — mic is live.")
                sent = 0
                while True:
                    # Bounded wait. A queue that goes quiet must surface as an
                    # event, never as an indefinite park — that silence is
                    # exactly what hid the last two days.
                    try:
                        chunk = await asyncio.wait_for(audio_queue.get(), timeout=10)
                    except asyncio.TimeoutError:
                        logger.warning(
                            "no audio from the mic for 10s (callbacks=%d, sent=%d) — "
                            "mic permission or device may be gone; reconnecting",
                            _frames_in, sent,
                        )
                        break
                    flat = chunk.flatten().astype(np.int16)
                    buffer = np.concatenate([buffer, flat])

                    if len(buffer) >= chunk_samples:
                        send_chunk = buffer[:chunk_samples]
                        buffer = buffer[chunk_samples:]
                        payload = {
                            "type": "audio",
                            "audio": base64.b64encode(send_chunk.tobytes()).decode("utf-8"),
                            "sample_rate": SAMPLE_RATE,
                        }
                        await ws.send(json.dumps(payload))
                        sent += 1
                        # Liveness that measures the OUTPUT, not the process.
                        if sent % 15 == 0:
                            logger.info("streaming — %d chunks sent, %d mic callbacks",
                                        sent, _frames_in)

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logger.warning(f"Bridge connection lost ({e}). Retrying in 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    global audio_queue, event_loop
    audio_queue = asyncio.Queue(maxsize=200)
    event_loop = asyncio.get_running_loop()

    blocksize = int(SAMPLE_RATE * 0.1)  # 100ms blocks into the queue
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=blocksize,
        callback=mic_callback,
    ):
        logger.info(f"Mic open at {SAMPLE_RATE}Hz mono PCM16. Streaming to bridge...")
        await stream_mic_to_bridge()

# NO in-process daemonize here, deliberately.
#
# I added one at 02:31 and it killed this process on launch. `import sounddevice`
# starts CoreAudio/PortAudio threads at import time, and fork() from a
# multi-threaded process is unsafe — Python warned in plain text
# ("This process is multi-threaded, use of fork() may lead to deadlocks in the
# child") and the child died between opening the mic and the first callback.
#
# Detaching has to happen BEFORE the audio library loads, which means from the
# outside. Use run_detached.py:
#     .venv/bin/python3 run_detached.py mic_capture.py
# It forks and setsid's while it is still single-threaded, then execs this file.

if __name__ == "__main__":
    _acquire_singleton()
    logger.info("mic_capture starting — PID %s, log %s", os.getpid(), _LOG_PATH)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Mic capture stopped.")
    finally:
        _release_singleton()
        sys.exit(0)
