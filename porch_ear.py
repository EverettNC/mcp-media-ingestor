"""
porch_ear.py — the always-on Porch ear.
The Christman AI Project

Everett asked (2026-11-17): the ear on the 8765 board listens all the time,
not only while someone holds the orb on the porch page.

What it does, in order, all on this machine:
  1. Holds the default input mic open (16 kHz mono PCM16).
  2. Listens for a voice with a local energy gate (no model, no cloud).
  3. When a voice stops, hands the clip to THEWHOLEHOUSE at
     POST :9785/api/porch/stt. The house gives it to the Filament ear on
     :4850 (Vosk, keyless) and runs the dialect layer, so the take has the
     same shape the orb makes.
  4. Posts the take to the porch rack, POST :9785/api/porch/live, with
     listening true. 8765 pulls the porch from there, as it always has.

8765 still opens no mic. The house is still the supplier. This ear is a
separate process that feeds the house.

Honesty: the tape never leaves this machine and is never written to disk.
Each clip lives in memory until the Filament has heard it, then it is dropped.
The log keeps counts and lengths, never the words.

Off switch:   touch ~/.porch-ear/OFF     (mic closes, board says not listening)
On again:     rm ~/.porch-ear/OFF
Stop service: launchctl bootout gui/$(id -u)/com.thechristmanai.porch-ear
Log:          ~/Library/Logs/ChristmanAI/porch-ear.log
"""

from __future__ import annotations

import base64
import collections
import io
import json
import logging
import os
import queue
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
import wave

import numpy as np
import sounddevice as sd

# ── Config ────────────────────────────────────────────────────────────────────
HOUSE_URL = os.getenv("CHRISTMAN_HOUSE_URL", "http://127.0.0.1:9785").rstrip("/")
STT_URL = f"{HOUSE_URL}/api/porch/stt"
LIVE_URL = f"{HOUSE_URL}/api/porch/live"

HOME_DIR = os.path.expanduser("~/.porch-ear")
OFF_FILE = os.path.join(HOME_DIR, "OFF")
LOCK_FILE = os.path.join(HOME_DIR, "porch-ear.lock")
LOG_PATH = os.path.expanduser("~/Library/Logs/ChristmanAI/porch-ear.log")

DEVICE = os.getenv("PORCH_EAR_DEVICE") or None  # None = the Mac's default input
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples

# Voice gate. Levels are RMS on int16 samples.
START_RATIO = 3.0          # a voice is this many times louder than the room
END_RATIO = 2.0            # ...and stays above this while it goes on
ABS_FLOOR = 120.0          # never call anything below this a voice
START_FRAMES = 4           # 120 ms of voice to open a take
END_SILENCE_S = 0.8        # this much quiet closes a take
PRE_ROLL_S = 0.3           # keep the breath before the first word
MIN_VOICED_S = 0.5         # less voice than this is a bump, not speech
MAX_TAKE_S = 20.0          # a long talk is cut into takes this long

HEARTBEAT_S = 2.0          # re-say "listening" to the rack this often
STALL_S = 5.0              # no audio from the mic this long = not hearing
ZERO_S = 10.0              # pure digital zeros this long = mic is blocked

# Vosk says these alone when it hears a door or a cough.
NOISE_ALONE = {"the", "a", "huh", "uh", "um", "hmm", "mm"}

# ── Logging: a file, never only stdout (see mic_capture.py, 2026-08-30) ───────
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
os.makedirs(HOME_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [porch-ear] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    # launchd sends stderr to its own file; echo there only when run by hand.
    handlers=[logging.FileHandler(LOG_PATH)] + ([logging.StreamHandler()] if sys.stderr.isatty() else []),
)
log = logging.getLogger("porch-ear")

_stop = threading.Event()
_frames: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2000)
_clips: "queue.Queue[tuple[bytes, float]]" = queue.Queue(maxsize=8)
_state_lock = threading.Lock()
_hearing = False           # True only while the mic is delivering real sound
_last_audio = 0.0
_zero_since: float | None = None


# ── One ear at a time ─────────────────────────────────────────────────────────
def _acquire_singleton() -> None:
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            if pid != os.getpid():
                os.kill(pid, 0)
                log.info("another porch ear is already running (PID %s); leaving it be", pid)
                sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError):
            pass  # stale lock
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def _release_singleton() -> None:
    try:
        with open(LOCK_FILE) as f:
            if f.read().strip() == str(os.getpid()):
                os.remove(LOCK_FILE)
    except (FileNotFoundError, ValueError):
        pass


def _is_off() -> bool:
    return os.path.exists(OFF_FILE)


def _set_hearing(value: bool, why: str = "") -> None:
    global _hearing
    with _state_lock:
        if _hearing == value:
            return
        _hearing = value
    log.info("%s%s", "hearing the room" if value else "not hearing", f" ({why})" if why else "")


# ── Talking to the house ──────────────────────────────────────────────────────
def _post_json(url: str, body: dict, timeout: float) -> dict:
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=raw, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:  # the house answers 503 with a reason
        try:
            return json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            return {"ok": False, "error": f"house answered {exc.code}"}


def _post_live(listening: bool, take: dict | None = None) -> bool:
    body: dict = {"listening": bool(listening)}
    if take is not None:
        body["take"] = take
    try:
        return bool(_post_json(LIVE_URL, body, timeout=2.0).get("ok"))
    except Exception as exc:
        log.warning("porch rack did not answer (%s)", str(exc)[:120])
        return False


def _heartbeat() -> None:
    """Tell the rack the truth: listening only while the mic delivers sound."""
    sent: bool | None = None
    sent_at = 0.0
    while not _stop.is_set():
        want = _hearing and not _is_off()
        now = time.monotonic()
        if want != sent or (want and now - sent_at >= HEARTBEAT_S):
            if _post_live(want):
                sent, sent_at = want, now
        _stop.wait(0.25)


# ── Hearing a take ────────────────────────────────────────────────────────────
def _wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def _hear_worker() -> None:
    while not _stop.is_set():
        try:
            pcm, voiced_s = _clips.get(timeout=1.0)
        except queue.Empty:
            continue
        body = {
            "audioBase64": base64.b64encode(_wav(pcm)).decode("ascii"),
            "mime": "audio/wav",
            "filename": "porch-ear.wav",
            "source": "mic",
        }
        pcm = b""  # the tape is not kept
        try:
            res = _post_json(STT_URL, body, timeout=60.0)
        except Exception as exc:
            log.warning("the house did not take the clip (%s)", str(exc)[:160])
            continue
        finally:
            body = {}
        if not res.get("ok"):
            log.warning("no take: %s", str(res.get("error") or "unknown")[:160])
            continue
        take = res.get("take") if isinstance(res.get("take"), dict) else None
        said = str((take or {}).get("asSaid") or "").strip()
        if not take or not said:
            log.info("clip of %.1fs voice: the Filament heard no words", voiced_s)
            continue
        if said.lower().strip(" .,!?") in NOISE_ALONE:
            log.info("clip of %.1fs voice: one filler word, set aside", voiced_s)
            continue
        ok = _post_live(_hearing and not _is_off(), take)
        log.info("take %s — %d chars from %.1fs of voice — %s",
                 str(take.get("id"))[:8], len(said), voiced_s,
                 "on the porch" if ok else "porch rack did not answer")


# ── The voice gate ────────────────────────────────────────────────────────────
class Gate:
    """Energy gate with a room floor that follows the room while nobody talks."""

    def __init__(self) -> None:
        self.floor: float | None = None
        self.pre: collections.deque = collections.deque(maxlen=max(1, int(PRE_ROLL_S * 1000 / FRAME_MS)))
        self.active = False
        self.buf: list[np.ndarray] = []
        self.run = 0
        self.voiced = 0
        self.quiet = 0
        self.peak = 0.0
        self.takes = 0

    def feed(self, block: np.ndarray) -> None:
        x = block.astype(np.float32)
        rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
        self.peak = max(self.peak, rms)
        if self.floor is None:
            self.floor = max(rms, 1.0)
        if not self.active:
            rate = 0.05 if rms < self.floor else 0.01
            self.floor = max(1.0, self.floor + rate * (rms - self.floor))
            self.pre.append(block)
            self.run = self.run + 1 if rms > max(self.floor * START_RATIO, ABS_FLOOR) else 0
            if self.run >= START_FRAMES:
                self.active = True
                self.buf = list(self.pre)
                self.voiced = self.run
                self.quiet = 0
            return
        self.buf.append(block)
        if rms > max(self.floor * END_RATIO, ABS_FLOOR * 0.8):
            self.voiced += 1
            self.quiet = 0
        else:
            self.quiet += 1
        if (self.quiet * FRAME_MS / 1000 >= END_SILENCE_S
                or len(self.buf) * FRAME_MS / 1000 >= MAX_TAKE_S):
            self.close()

    def close(self) -> None:
        voiced_s = self.voiced * FRAME_MS / 1000
        pcm = np.concatenate(self.buf).astype(np.int16).tobytes() if self.buf else b""
        self.active, self.buf, self.run, self.voiced, self.quiet = False, [], 0, 0, 0
        self.pre.clear()
        if voiced_s < MIN_VOICED_S or not pcm:
            return
        try:
            _clips.put_nowait((pcm, voiced_s))
            self.takes += 1
        except queue.Full:
            log.warning("the ear is behind; a %.1fs clip was dropped", voiced_s)


# ── The mic ───────────────────────────────────────────────────────────────────
def _mic_callback(indata: np.ndarray, frames: int, t, status) -> None:
    """Runs on the audio thread. queue.Queue is thread-safe; asyncio's is not."""
    global _last_audio
    if status:
        log.warning("mic status: %s", status)
    _last_audio = time.monotonic()
    try:
        _frames.put_nowait(indata[:, 0].copy())
    except queue.Full:
        pass  # the gate is behind; drop rather than block the audio thread


def _listen_once() -> None:
    """Open the mic, run the gate until OFF, stop, or the mic goes quiet."""
    global _zero_since
    while not _frames.empty():
        _frames.get_nowait()
    _zero_since = None
    gate = Gate()
    name = sd.query_devices(DEVICE, "input")["name"] if DEVICE else sd.query_devices(kind="input")["name"]
    log.info("opening the mic: %s", name)
    with sd.InputStream(device=DEVICE, samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        blocksize=FRAME, callback=_mic_callback):
        opened = time.monotonic()
        next_report = opened + 30.0
        log.info("mic open at %d Hz mono", SAMPLE_RATE)
        while not _stop.is_set():
            if _is_off():
                log.info("OFF switch is on; closing the mic")
                _set_hearing(False, "switched off")
                return
            try:
                block = _frames.get(timeout=1.0)
            except queue.Empty:
                since = time.monotonic() - max(_last_audio, opened)
                if since > STALL_S:
                    _set_hearing(False, f"no sound from the mic for {since:.0f}s")
                    return
                continue
            now = time.monotonic()
            if np.any(block):
                _zero_since = None
                _set_hearing(True)
            else:
                _zero_since = _zero_since or now
                if now - _zero_since > ZERO_S:
                    _set_hearing(False, "the mic gives only silence; microphone permission may be off")
            gate.feed(block)
            # Liveness that measures the output, not the process: what the mic
            # is giving and how many takes it made, 30 s in and every 5 min after.
            if now >= next_report:
                log.info("still hearing — room level %.0f, loudest %.0f, takes so far %d",
                         gate.floor or 0.0, gate.peak, gate.takes)
                gate.peak = 0.0
                next_report = now + 300.0


def main() -> None:
    _acquire_singleton()

    def _on_signal(signum, frame):
        log.info("signal %s; the ear is closing", signum)
        _stop.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    log.info("porch ear starting — PID %s, house %s, off switch %s", os.getpid(), HOUSE_URL, OFF_FILE)
    threading.Thread(target=_heartbeat, name="heartbeat", daemon=True).start()
    threading.Thread(target=_hear_worker, name="hear", daemon=True).start()

    announced_off = False
    try:
        while not _stop.is_set():
            if _is_off():
                if not announced_off:
                    log.info("OFF switch is on; the mic stays closed")
                    announced_off = True
                _set_hearing(False, "switched off")
                _stop.wait(2.0)
                continue
            announced_off = False
            try:
                _listen_once()
            except Exception as exc:
                _set_hearing(False, "mic error")
                log.error("mic error: %s", str(exc)[:200])
                _stop.wait(5.0)
    finally:
        _set_hearing(False, "stopping")
        _post_live(False)
        _release_singleton()
        log.info("porch ear stopped")


if __name__ == "__main__":
    main()
