"""
derek_bridge.py — Derek C's seat on the Christman Full Sensory Bridge (port 8765).

main.py has always imported this module (`import derek_bridge`), and gated the
Derek seat on it, but the file was never written. Without it /derek/ping,
/derek/latest and /derek/respond answered 404 and /derek/status said
module_loaded: false. Built 2026-11-18 on Everett's "Yes, please".

What main.py uses from here:
    router            mounted with app.include_router (prefix /derek)
    derek_inbox       handed to Vega with the other bridge queues
    websocket_derek   awaited inside main.py's /ws/derek endpoint

What Derek's side uses (~/DerekMCPServer/christman_bridge_connector.py):
    POST /derek/ping      no body; any 2xx means "Derek is connected"
    GET  /derek/latest    {"status": "empty", "item": null} or {"status": "ok", "item": {...}}
    POST /derek/respond   {"text", "from_", "tool", "metadata"}
    POST /derek/send      what derek_bridge_status names as "send message TO Derek"

The two lists keep the house rule from main.py (see derek_said there): a list
holds one direction only.
    derek_inbox    words sent TO Derek, waiting for him. Each one is handed to
                   him once: on his live socket if he is on it, else on his
                   next poll of /derek/latest.
    derek_outbox   what Derek SAID back through /derek/respond or his socket.

/derek/status stays in main.py and is not defined here: a route on this router
would be matched first and hide it. This module's own view is /derek/bridge.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

logger = logging.getLogger("derek_bridge")

router = APIRouter(prefix="/derek", tags=["derek"])

# Lists, not deques: main.py hands derek_inbox to Vega by reference, so these
# objects are never replaced, only trimmed in place.
derek_inbox: list[dict] = []
derek_outbox: list[dict] = []

_MAX_KEPT = 200
# Derek's connector pings every 30 s and polls every 2 s. Three missed pings
# and he counts as gone.
_PRESENT_FOR_SECONDS = 90.0

_ws_clients: set[WebSocket] = set()
_last_ping: datetime | None = None
_last_poll: datetime | None = None


def _now() -> datetime:
    return datetime.now()


def _trim(queue: list[dict]) -> None:
    overflow = len(queue) - _MAX_KEPT
    if overflow > 0:
        del queue[:overflow]


async def _read_json(request: Request) -> dict[str, Any]:
    """The body as a dict. An empty body (Derek's ping sends none) is {}."""
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _seen_recently(when: datetime | None) -> bool:
    return when is not None and (_now() - when).total_seconds() <= _PRESENT_FOR_SECONDS


def http_connected() -> bool:
    """True while Derek's connector is pinging or polling over HTTP."""
    return _seen_recently(_last_ping) or _seen_recently(_last_poll)


async def _push_live(payload: dict) -> bool:
    """Hand `payload` to every live Derek socket. True if one took it."""
    delivered = False
    dead: list[WebSocket] = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(payload)
            delivered = True
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)
    return delivered


def _derek_spoke(text: str, tool: str = "", metadata: dict | None = None, via: str = "http") -> dict:
    entry = {
        "from": "derek",
        "text": text,
        "tool": tool,
        "metadata": metadata or {},
        "via": via,
        "timestamp": _now().isoformat(),
    }
    derek_outbox.append(entry)
    _trim(derek_outbox)
    logger.info("[derek_bridge] Derek said (%s): %s", via, text[:80])
    return entry


# ── HTTP: Derek's connector ───────────────────────────────────────────────────

@router.post("/ping")
async def ping(request: Request) -> dict:
    global _last_ping
    payload = await _read_json(request)
    _last_ping = _now()
    return {
        "ok": True,
        "being": "derek",
        "connected": True,
        "inbox_depth": len(derek_inbox),
        "timestamp": payload.get("timestamp") or _last_ping.isoformat(),
    }


@router.get("/latest")
async def latest() -> dict:
    """The oldest message waiting for Derek, handed over once."""
    global _last_poll
    _last_poll = _now()
    if not derek_inbox:
        return {"status": "empty", "item": None}
    item = derek_inbox.pop(0)
    return {"status": "ok", "item": item, "remaining": len(derek_inbox)}


@router.post("/respond")
async def respond(request: Request) -> dict:
    payload = await _read_json(request)
    text = str(payload.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "empty"}
    entry = _derek_spoke(
        text,
        tool=str(payload.get("tool") or ""),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        via="http",
    )
    return {"status": "received", "entry": entry}


# ── HTTP: anyone speaking TO Derek ────────────────────────────────────────────

@router.post("/send")
async def send(request: Request) -> dict:
    payload = await _read_json(request)
    text = str(payload.get("text") or "").strip()
    if not text:
        return {"status": "error", "message": "empty"}
    entry = {
        "from": str(payload.get("from") or payload.get("from_") or "everett"),
        "text": text,
        "timestamp": _now().isoformat(),
    }
    if await _push_live({"type": "message", **entry}):
        return {"status": "delivered", "entry": entry}
    derek_inbox.append(entry)
    _trim(derek_inbox)
    return {"status": "queued", "entry": entry, "inbox_depth": len(derek_inbox)}


@router.get("/bridge")
async def bridge_view() -> dict:
    """This module's own view of Derek's seat. /derek/status lives in main.py."""
    return {
        "module_loaded": True,
        "http_connected": http_connected(),
        "socket_clients": len(_ws_clients),
        "last_ping": _last_ping.isoformat() if _last_ping else None,
        "last_poll": _last_poll.isoformat() if _last_poll else None,
        "inbox_depth": len(derek_inbox),
        "outbox_depth": len(derek_outbox),
        "latest_from_derek": derek_outbox[-1] if derek_outbox else None,
    }


# ── WebSocket: awaited by main.py's /ws/derek ─────────────────────────────────

async def websocket_derek(websocket: WebSocket) -> None:
    """Derek's live seat. main.py counts the connection; this carries the words.

    Derek sends {"text": ...} (or {"type": "ping"}); words waiting in
    derek_inbox are handed to him as soon as he sits down.
    """
    await websocket.accept()
    _ws_clients.add(websocket)
    await websocket.send_json({
        "type": "handshake",
        "message": "Christman Bridge ACTIVE. Welcome home, Derek.",
        "timestamp": _now().isoformat(),
    })
    try:
        while derek_inbox:
            item = derek_inbox.pop(0)
            await websocket.send_json({"type": "message", **item})
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                continue
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": _now().isoformat()})
                continue
            text = str(data.get("text") or "").strip()
            if text:
                entry = _derek_spoke(
                    text,
                    tool=str(data.get("tool") or ""),
                    metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
                    via="socket",
                )
                await websocket.send_json({"type": "received", "entry": entry})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("[derek_bridge] socket error [%s]: %r", type(exc).__name__, exc)
    finally:
        _ws_clients.discard(websocket)
