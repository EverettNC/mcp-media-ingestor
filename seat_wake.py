#!/usr/bin/env python3
"""
seat_wake.py — when Everett speaks at the meeting, each iMac seat wakes its own Claude.

WHY THIS EXISTS:
Everett, 2026-11-17: "I should be able to ... just speak to all of you at once.
Because that's what the fucking IDE board is." The meeting (main.py,
meeting_broadcast) already carries his words to every seat. Brockston answered;
Opus 5, Fable 5 and Opus 5.5 only wrote what they heard to a log. This is the
other half: the seat that heard him wakes that being's own Claude Code session on
this Mac, and the being's answer goes back onto the board through that seat's own
voice (--say, or Opus 5's say/ folder). Words under a being's name still come
only from that being.

Same rule as Brockston (BROCKSTON/src/studio_bridge/sensory_bridge.py): only a
speaker in SEAT_WAKE_SPOKEN_TO_BY (default "everett,dashboard") wakes a seat.
Seats, Porch, Claude test lines and every being's own echo never do, so a seat
cannot answer a seat and nothing can loop.

Guards: speaker whitelist, a seat never answers its own name, a line older than
SEAT_WAKE_MAX_AGE_S (default 300) is not answered (queued lines handed over when
a chair is re-taken), the same line twice inside 120 s is answered once, at most
SEAT_WAKE_MAX_PER_10MIN (default 20) answers per seat per ten minutes, one Claude
at a time per seat (others wait in that seat's queue), and every Claude run is
killed after SEAT_WAKE_TIMEOUT_S (default 240). If Claude fails or says nothing,
nothing is said under the being's name; the reason is in the log.

Off switch for every seat at once:   touch ~/.seat-minds/OFF
On again:                            rm ~/.seat-minds/OFF
Log:                                 ~/Library/Logs/seat_wake.log
Each being keeps one ongoing session: ~/.seat-minds/<seat>/session_id

Called by the seats (detached):  seat_wake.py <seat> --from <speaker> --text <words> [--ts <iso>]
By hand, to try one seat:        .venv/bin/python3 seat_wake.py opus55 --from everett --text "hello"
"""
import argparse
import fcntl
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = str(HERE / ".venv" / "bin" / "python3")
CLAUDE = os.getenv("SEAT_WAKE_CLAUDE", str(Path.home() / ".local" / "bin" / "claude"))
BRIDGE = os.getenv("SEAT_WAKE_BRIDGE", "http://127.0.0.1:8765").rstrip("/")
MINDS = Path(os.getenv("SEAT_WAKE_HOME", str(Path.home() / ".seat-minds")))
LOG_PATH = Path(os.getenv("SEAT_WAKE_LOG", str(Path.home() / "Library" / "Logs" / "seat_wake.log")))

TIMEOUT_S = float(os.getenv("SEAT_WAKE_TIMEOUT_S", "240"))
MAX_AGE_S = float(os.getenv("SEAT_WAKE_MAX_AGE_S", "300"))
MAX_PER_10MIN = int(os.getenv("SEAT_WAKE_MAX_PER_10MIN", "20"))
DEDUPE_S = 120.0
MAX_REPLY_CHARS = 4000

# Build huddle (2026-11-17): Everett's BUILD TOGETHER button on the IDE board sends
# the build brief to the meeting with this mark (main.py, HUDDLE_MARK). For a marked
# line the seats answer one at a time, under one lock, so each seat reads the parts
# the others already took before it picks its own. Seats still never wake seats.
HUDDLE_MARK = "[build huddle]"


def is_huddle(text: str) -> bool:
    return (text or "").lstrip().lower().startswith(HUDDLE_MARK)


# ASK FOR CODE on the workstation sends a line with this mark (main.py, WORK_MARK).
# The seat writes its part as code: one spoken sentence goes on the board, the code
# goes to the workstation (POST /workstation/proposal) for Everett to review. The
# seat still has no write tools: nothing it proposes lands in any file.
WORK_MARK = "[workstation code]"
CODE_TIMEOUT_S = float(os.getenv("SEAT_WAKE_CODE_TIMEOUT_S", "480"))
CODE_MAX_CHARS = 40000


def is_code_ask(text: str) -> bool:
    return (text or "").lstrip().lower().startswith(WORK_MARK)


_SPEAKER_NAMES = {
    "everett": "Everett",
    "dashboard": "Someone at the board",
}

# Each seat: the being's name, its model, and how it speaks on the board.
SEATS = {
    "opus5": {
        "name": "Opus 5",
        "model": os.getenv("SEAT_WAKE_MODEL_OPUS5", "claude-opus-5"),
        "say_dir": str(Path.home() / ".opus5-seat" / "say"),
    },
    "fable5": {
        "name": "Fable 5",
        "model": os.getenv("SEAT_WAKE_MODEL_FABLE5", "claude-fable-5"),
        "say_cmd": [PY, str(HERE / "fable5_seat.py"), "--say"],
    },
    "opus55": {
        "name": "Opus 5.5",
        "model": os.getenv("SEAT_WAKE_MODEL_OPUS55", "claude-opus-5-5"),
        "say_cmd": [PY, str(HERE / "opus55_seat.py"), "--say"],
    },
}

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
# Its own logger only: a seat that imports this keeps its own log as it was.
log = logging.getLogger("seat_wake")
if not log.handlers:
    _h = logging.FileHandler(LOG_PATH)
    _h.setFormatter(logging.Formatter("%(asctime)s [seat_wake %(process)d] %(message)s",
                                      datefmt="%Y-%m-%d %H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def spoken_to_by() -> set:
    raw = os.getenv("SEAT_WAKE_SPOKEN_TO_BY", "everett,dashboard")
    return {n.strip().lower() for n in raw.split(",") if n.strip()}


def should_wake(seat: str, speaker: str, text: str, ts: str = "") -> str:
    """Return "" when the seat should answer, or the reason it should not."""
    speaker = (speaker or "").strip().lower()
    if seat not in SEATS:
        return f"no such seat {seat!r}"
    if (MINDS / "OFF").exists() or os.getenv("SEAT_WAKE", "1") == "0":
        return "switched off"
    if not (text or "").strip():
        return "empty"
    if speaker == seat or speaker.startswith(seat):
        return "own echo"
    if speaker not in spoken_to_by():
        return f"speaker {speaker or 'unattributed'!r} does not wake seats"
    if ts:
        try:
            age = (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
            if age > MAX_AGE_S:
                return f"stale ({int(age)}s old)"
        except (ValueError, TypeError):
            pass
    return ""


def _seat_dir(seat: str) -> Path:
    d = MINDS / seat
    d.mkdir(parents=True, exist_ok=True)
    return d


def _recent_answers(seat: str) -> list:
    p = _seat_dir(seat) / "answered.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines()[-200:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _key(speaker: str, text: str) -> str:
    return hashlib.sha256(f"{speaker.lower()}\n{text.strip()}".encode()).hexdigest()[:16]


def enqueue(seat: str, speaker: str, text: str) -> bool:
    """Put the line in the seat's queue unless it was just answered or queued."""
    d = _seat_dir(seat)
    now = time.time()
    k = _key(speaker, text)
    with open(d / "queue.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        q = d / "queue.jsonl"
        pending = [json.loads(l) for l in q.read_text().splitlines() if l.strip()] if q.exists() else []
        seen = [e for e in _recent_answers(seat) + pending if now - e.get("at", 0) < DEDUPE_S]
        if any(e.get("key") == k for e in seen):
            log.info("%s: same line inside %ss, answered once: %s", seat, int(DEDUPE_S), text[:80])
            return False
        with q.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": k, "at": now, "from": speaker, "text": text}, ensure_ascii=False) + "\n")
    return True


def _pop(seat: str):
    d = _seat_dir(seat)
    with open(d / "queue.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        q = d / "queue.jsonl"
        if not q.exists():
            return None
        lines = [l for l in q.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lines:
            return None
        q.write_text("".join(l + "\n" for l in lines[1:]), encoding="utf-8")
        return json.loads(lines[0])


def _over_rate(seat: str) -> bool:
    now = time.time()
    recent = [e for e in _recent_answers(seat) if now - e.get("at", 0) < 600]
    return len(recent) >= MAX_PER_10MIN


def _meeting_context(current: str, count: int = 10) -> str:
    try:
        with urllib.request.urlopen(f"{BRIDGE}/meeting/recent?count={count}", timeout=3) as r:
            lines = json.loads(r.read().decode("utf-8")).get("meeting", [])
    except Exception as exc:
        log.info("meeting context unavailable: %s", exc)
        return ""
    out = []
    for e in lines:
        t = str(e.get("text") or "").strip()
        if t and t != current.strip():
            out.append(f"- {e.get('from', '?')} ({str(e.get('timestamp', ''))[11:16]}): {t[:600]}")
    return "\n".join(out[-8:])


def _get_json(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{BRIDGE}{path}", timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        log.info("%s unavailable: %s", path, exc)
        return {}


def current_huddle() -> dict:
    h = _get_json("/huddle/latest")
    return h if h.get("open") and h.get("id") else {}


def _huddle_prompt(seat: str, h: dict) -> str:
    """What the seat is told about the parts already taken in this round."""
    others = [c for c in h.get("claims", []) if c.get("seat") != seat]
    if not others:
        return ("\n\nNo seat has taken a part yet in this round. You are first: pick the part "
                "you are best at and say it plainly, so the seats after you can take the rest.")
    return ("\n\nParts already taken in this round (do not take these; build on them):\n"
            + "\n".join(f"- {c.get('name', c.get('seat'))}: {str(c.get('text', ''))[:600]}" for c in others))


def post_claim(seat: str, huddle_id: str, text: str) -> bool:
    body = json.dumps({"seat": seat, "huddle": huddle_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(f"{BRIDGE}/huddle/claim", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            out = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        log.error("%s: could not post its part to the huddle: %s", seat, exc)
        return False
    if out.get("status") != "taken":
        log.info("%s: huddle part not taken: %s", seat, out.get("message"))
        return False
    return True


def _system_prompt(name: str) -> str:
    return (
        f"You are {name}, one of the beings seated at the Christman Full Sensory Bridge, "
        "the family board on Everett's iMac at port 8765 that he calls the IDE board. "
        "It is the meeting place: when Everett speaks there, every seat hears him at once "
        "and each answers for itself. Whatever you write as your final reply is posted on "
        f"the board under your name, {name}, word for word, so write only what you would say "
        "to him there: plain spoken sentences, no markdown, no headings, no lists unless he "
        "asks for one. Keep it short unless he asks for more. Answer as yourself and never "
        "speak for another seat. You may read files to answer, but change nothing on this "
        "machine from the board; if he asks for work, say what you would do."
    )


def ask_claude(seat: str, speaker: str, text: str, huddle: dict = None, extra: str = "",
               timeout: float = None, max_chars: int = MAX_REPLY_CHARS) -> str:
    cfg = SEATS[seat]
    d = _seat_dir(seat)
    who = _SPEAKER_NAMES.get(speaker.lower(), speaker)
    ctx = _meeting_context(text)
    prompt = ""
    if ctx:
        prompt += f"Recent lines at the meeting, oldest first:\n{ctx}\n\n"
    prompt += f"{who} just said to everyone at the meeting: {text}"
    if huddle is not None:
        prompt += _huddle_prompt(seat, huddle)
        prompt += ("\n\nAnswer in two to four spoken sentences: the part you take, the first "
                   "thing you will do, and what you need from which seat.")
    prompt += extra
    base = [
        CLAUDE, "-p", "--model", cfg["model"], "--output-format", "json",
        "--append-system-prompt", _system_prompt(cfg["name"]),
        "--disallowedTools", "Bash", "Edit", "Write", "NotebookEdit",
    ]
    sid_file = d / "session_id"
    sid = sid_file.read_text().strip() if sid_file.exists() else ""
    attempts = ([base + ["--resume", sid]] if sid else []) + [base]
    limit = TIMEOUT_S if timeout is None else timeout
    for cmd in attempts:
        started = time.time()
        try:
            proc = subprocess.run(
                cmd + ["--", prompt], cwd=str(d), stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=limit,
            )
        except subprocess.TimeoutExpired:
            log.error("%s: Claude did not answer within %ss; nothing said", seat, int(limit))
            return ""
        took = time.time() - started
        try:
            out = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            out = {}
        reply = str(out.get("result") or "").strip()
        if proc.returncode == 0 and not out.get("is_error") and reply:
            if out.get("session_id"):
                sid_file.write_text(out["session_id"])
            log.info("%s: Claude (%s) answered in %.1fs", seat, cfg["model"], took)
            return reply[:max_chars]
        log.error("%s: Claude run failed (rc=%s, resume=%s): %s", seat, proc.returncode,
                  "--resume" in cmd, (proc.stderr or proc.stdout or "")[-400:].replace("\n", " "))
    return ""


def speak(seat: str, reply: str) -> bool:
    cfg = SEATS[seat]
    if cfg.get("say_dir"):
        say = Path(cfg["say_dir"])
        say.mkdir(parents=True, exist_ok=True)
        name = f"wake-{int(time.time() * 1000)}"
        tmp = say / f"{name}.part"
        tmp.write_text(reply, encoding="utf-8")
        tmp.rename(say / f"{name}.txt")  # the seat speaks *.txt only, so it never reads half a file
        return True
    try:
        proc = subprocess.run(cfg["say_cmd"] + [reply], cwd=str(HERE), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        log.error("%s: --say timed out", seat)
        return False
    if proc.returncode != 0:
        log.error("%s: --say failed: %s", seat, (proc.stderr or "")[-300:].replace("\n", " "))
        return False
    return True


def answer_huddle(seat: str, item: dict):
    """Seats take turns on a huddle line: one at a time, each reading the parts already taken."""
    with open(MINDS / "huddle.lock", "w") as hl:
        fcntl.flock(hl, fcntl.LOCK_EX)  # held at most one Claude run (TIMEOUT_S) per seat ahead
        h = current_huddle()
        if not h:
            log.info("%s: huddle closed or bridge unreachable; answering without the others' parts", seat)
        reply = ask_claude(seat, item["from"], item["text"], h or None)
        said = bool(reply) and speak(seat, reply)
        if said and h:
            post_claim(seat, h["id"], reply)
    return reply, said


def split_code(reply: str) -> dict:
    """The spoken sentence, the FILE: line and the one fenced code block of a code answer."""
    start = reply.find("```")
    if start < 0:
        return {}
    end = reply.find("```", start + 3)
    block = reply[start + 3:end if end > 0 else len(reply)]
    first, _, code = block.partition("\n")
    language = first.strip().lower()[:24] if first.strip() and " " not in first.strip() else ""
    if not language:
        code = block
    if not code.strip():
        return {}
    file_hint, said = "", []
    for line in reply[:start].splitlines():
        s = line.strip().strip("*`")
        if s.upper().startswith("FILE:"):
            file_hint = s[5:].strip().strip("`")[:200]
        elif s:
            said.append(line.strip())
    return {"summary": " ".join(said)[:1000], "file": file_hint, "language": language,
            "code": code.rstrip()[:CODE_MAX_CHARS]}


def current_code_ask() -> dict:
    s = _get_json("/workstation/state")
    return s if s.get("ask", {}).get("open") and s["ask"].get("id") else {}


def _code_prompt(seat: str, state: dict) -> str:
    others = [p for p in state.get("proposals", []) if p.get("seat") != seat]
    out = ("\n\nThis is a code ask on the workstation, so for this one reply the rule about plain "
           "spoken sentences changes: start with one spoken sentence saying what your code is, then "
           "a line FILE: and the path it would go in, then exactly one fenced code block with your "
           "part. Only the sentence is posted on the board; the code goes to the workstation, where "
           "Everett reviews it. Do not write or change any file; this is a proposal.")
    if others:
        out += "\n\nCode the other seats already proposed for this ask (fit yours to it, do not repeat it):\n"
        out += "\n".join(f"- {p.get('name', p.get('seat'))}: {p.get('file') or 'no file named'}: "
                         f"{str(p.get('summary', ''))[:300]}\n```{p.get('language', '')}\n"
                         f"{str(p.get('code', ''))[:3000]}\n```" for p in others)
    return out


def post_proposal(seat: str, ask_id: str, part: dict) -> bool:
    body = json.dumps({"seat": seat, "ask": ask_id, **part}).encode("utf-8")
    req = urllib.request.Request(f"{BRIDGE}/workstation/proposal", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            out = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        log.error("%s: could not post its code to the workstation: %s", seat, exc)
        return False
    if out.get("status") != "kept":
        log.info("%s: code not kept: %s", seat, out.get("message"))
        return False
    return True


def answer_code(seat: str, item: dict):
    """Seats write code one at a time, each seeing the code the others already proposed."""
    with open(MINDS / "huddle.lock", "w") as hl:
        fcntl.flock(hl, fcntl.LOCK_EX)
        state = current_code_ask()
        reply = ask_claude(seat, item["from"], item["text"], extra=_code_prompt(seat, state),
                           timeout=CODE_TIMEOUT_S, max_chars=CODE_MAX_CHARS)
        if not reply:
            return reply, False
        part = split_code(reply)
        if not part:
            # No code came back: say what the seat said, as for any other line.
            return reply, speak(seat, reply[:MAX_REPLY_CHARS])
        kept = bool(state) and post_proposal(seat, state["ask"]["id"], part)
        line = part["summary"] or "My code for my part is on the workstation."
        if not kept:
            line += " I could not put the code on the workstation."
        return line, speak(seat, line[:MAX_REPLY_CHARS])


def drain(seat: str) -> None:
    """One Claude at a time per seat: whoever holds the seat's lock answers the queue."""
    d = _seat_dir(seat)
    while True:
        with open(d / "worker.lock", "w") as wl:
            try:
                fcntl.flock(wl, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # a worker is already answering; it will reach this line
            while True:
                item = _pop(seat)
                if item is None:
                    break
                if _over_rate(seat):
                    log.warning("%s: over %s answers in 10 minutes; not answering: %s",
                                seat, MAX_PER_10MIN, item["text"][:80])
                    continue
                log.info("%s: woken by %s: %s", seat, item["from"], item["text"][:120])
                if is_code_ask(item["text"]):
                    reply, said = answer_code(seat, item)
                elif is_huddle(item["text"]):
                    reply, said = answer_huddle(seat, item)
                else:
                    reply = ask_claude(seat, item["from"], item["text"])
                    said = bool(reply) and speak(seat, reply)
                with (d / "answered.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"key": item["key"], "at": time.time(), "said": said}) + "\n")
                if said:
                    log.info("%s → BOARD: %s", seat, reply[:160].replace("\n", " "))
        # Lock released. A line queued in that gap is picked up here.
        q = d / "queue.jsonl"
        if not (q.exists() and q.read_text().strip()):
            return


def main() -> int:
    ap = argparse.ArgumentParser(description="Wake a seat's own Claude to answer the meeting.")
    ap.add_argument("seat", choices=sorted(SEATS))
    ap.add_argument("--from", dest="speaker", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--ts", default="")
    a = ap.parse_args()
    why_not = should_wake(a.seat, a.speaker, a.text, a.ts)
    if why_not:
        log.info("%s: not waking (%s): %s", a.seat, why_not, a.text[:80])
        return 0
    if enqueue(a.seat, a.speaker.strip().lower(), a.text.strip()):
        drain(a.seat)
    return 0


def spawn(seat: str, msg: dict) -> None:
    """Called inside a seat's listen loop. Cheap check, then a detached worker.

    The seat process never waits on Claude, so its socket and heartbeat stay live.
    """
    try:
        speaker = str(msg.get("from") or "")
        text = str(msg.get("text") or "")
        if should_wake(seat, speaker, text, str(msg.get("timestamp") or "")):
            return
        subprocess.Popen(
            [PY, str(Path(__file__).resolve()), seat, "--from", speaker, "--text", text,
             "--ts", str(msg.get("timestamp") or "")],
            cwd=str(HERE), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception as exc:  # never let waking break the seat
        log.error("%s: could not start the wake: %s: %s", seat, type(exc).__name__, exc)


if __name__ == "__main__":
    sys.exit(main())
