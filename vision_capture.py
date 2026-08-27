"""
vision_capture.py — Continuous camera/screen → WebSocket bridge client (Total Vision)
The Christman AI Project / Luma Cognify AI

Captures live video frames (webcam or screen) via ffmpeg and streams
base64-encoded JPEGs to the main.py bridge at /ws/video.

This provides the "total vision" symmetric to the live audio hearing pipeline.

Usage:
    python vision_capture.py                # default webcam
    python vision_capture.py screen         # macOS screen capture
    # or set SOURCE=screen ; FPS=2

Requires: ffmpeg in PATH (already needed for the project).
On macOS: uses avfoundation. Adjust device index if needed (0=webcam, 1=screen usually).

The bridge (main.py) will make frames available as ImageContent to Claude
and other consumers via get_current_view() and /vision/latest.
"""

import asyncio
import base64
import json
import logging
import os
import signal
import subprocess
import sys
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vision_capture] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
WS_URL = os.getenv("VISION_WS_URL", "ws://localhost:8765/ws/video")
FPS = float(os.getenv("FPS", "2.0"))          # low rate to protect context / bandwidth
SOURCE = os.getenv("SOURCE", sys.argv[1] if len(sys.argv) > 1 else "webcam")
# Override with VIDEO_INPUT=... if needed; else auto-detect below
_VIDEO_INPUT_ENV = os.getenv("VIDEO_INPUT", "").strip()


def _list_avfoundation_video_devices() -> list[tuple[int, str]]:
    """Parse `ffmpeg -f avfoundation -list_devices` → [(index, name), ...]."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True,
            text=True,
            timeout=15,
        )
        text = (r.stderr or "") + (r.stdout or "")
    except Exception as exc:
        logger.warning("Could not list avfoundation devices: %s", exc)
        return []
    devices: list[tuple[int, str]] = []
    in_video = False
    for line in text.splitlines():
        if "AVFoundation video devices" in line:
            in_video = True
            continue
        if "AVFoundation audio devices" in line:
            break
        if not in_video:
            continue
        # e.g. [5] Capture screen 0
        if "] " in line and "[" in line:
            try:
                bracket = line[line.rfind("[") + 1 : line.rfind("]")]
                idx = int(bracket)
                name = line.split("]", 1)[-1].strip()
                devices.append((idx, name))
            except ValueError:
                continue
    return devices


def resolve_video_input(source: str) -> tuple[str, str]:
    """
    Return (ffmpeg -i value, resolution).
    Screen on this Mac is often index 5+ ("Capture screen 0"), NOT 1.
    Webcam is usually index 0 (FaceTime).
    """
    if _VIDEO_INPUT_ENV:
        res = os.getenv("RES", "1280x720" if source.lower() in ("screen", "desktop", "capture") else "640x480")
        return _VIDEO_INPUT_ENV, res

    devices = _list_avfoundation_video_devices()
    src = source.lower().strip()

    if src in ("screen", "desktop", "capture"):
        # Prefer "Capture screen 0" (main display)
        for idx, name in devices:
            if "capture screen 0" in name.lower():
                logger.info("Auto screen device [%s] %s", idx, name)
                return f"{idx}:none", os.getenv("RES", "1280x720")
        for idx, name in devices:
            if "capture screen" in name.lower():
                logger.info("Auto screen device [%s] %s", idx, name)
                return f"{idx}:none", os.getenv("RES", "1280x720")
        # Last resort names work as avfoundation inputs on recent ffmpeg
        logger.warning("No Capture screen in device list — trying name 'Capture screen 0'")
        return "Capture screen 0:none", os.getenv("RES", "1280x720")

    # Webcam / camera: FaceTime first, else first non-screen device
    for idx, name in devices:
        if "facetime" in name.lower() or "built-in" in name.lower():
            logger.info("Auto webcam device [%s] %s", idx, name)
            return str(idx), os.getenv("RES", "640x480")
    for idx, name in devices:
        if "capture screen" not in name.lower() and "iphone" not in name.lower():
            logger.info("Auto camera device [%s] %s", idx, name)
            return str(idx), os.getenv("RES", "640x480")
    return "0", os.getenv("RES", "640x480")


VIDEO_INPUT, RESOLUTION = resolve_video_input(SOURCE)

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_ffmpeg_cmd() -> list[str]:
    """Build ffmpeg command for mjpeg pipe. Works on macOS; adapt for linux/windows."""
    # -f avfoundation on mac. For other OS use v4l2 / dshow etc.
    # Do not force -video_size for Capture screen (can fail); optional via FORCE_VIDEO_SIZE=1
    cmd = [
        "ffmpeg",
        "-f", "avfoundation",
        "-framerate", str(FPS),
    ]
    if os.getenv("FORCE_VIDEO_SIZE", "").strip() in ("1", "true", "yes"):
        cmd.extend(["-video_size", RESOLUTION])
    cmd.extend(
        [
            "-i", VIDEO_INPUT,
            "-f", "mjpeg",
            "-q:v", "7",
            "-",
        ]
    )
    return cmd

async def stream_frames_to_bridge(ws):
    """Run ffmpeg, parse mjpeg stream into individual JPEGs, send as base64 frames."""
    cmd = build_ffmpeg_cmd()
    logger.info(f"Starting ffmpeg vision source={SOURCE} input={VIDEO_INPUT} @ {FPS}fps -> {RESOLUTION}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert proc.stdout is not None
    buffer = bytearray()
    SOI = b"\xff\xd8"  # JPEG start
    EOI = b"\xff\xd9"  # JPEG end

    frames_sent = 0
    try:
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                # ffmpeg exited — surface stderr so we know why (permissions / bad device)
                err = b""
                if proc.stderr is not None:
                    try:
                        err = await asyncio.wait_for(proc.stderr.read(4000), timeout=1.0)
                    except Exception:
                        pass
                logger.error(
                    "ffmpeg ended (frames_sent=%s) stderr=%s",
                    frames_sent,
                    (err or b"").decode("utf-8", errors="replace")[-500:],
                )
                break
            buffer.extend(chunk)

            # Extract complete JPEGs from the mjpeg stream
            while True:
                start = buffer.find(SOI)
                if start == -1:
                    break
                end = buffer.find(EOI, start + 2)
                if end == -1:
                    break

                jpeg = bytes(buffer[start : end + 2])
                # remove consumed bytes (keep tail for next)
                del buffer[: end + 2]

                if len(jpeg) < 1024:  # too small, skip garbage
                    continue

                b64 = base64.b64encode(jpeg).decode("utf-8")
                payload = {
                    "type": "frame",
                    "image": b64,
                    "source": SOURCE,
                    "timestamp": asyncio.get_event_loop().time(),
                }
                await ws.send(json.dumps(payload))
                frames_sent += 1
                if frames_sent == 1 or frames_sent % 30 == 0:
                    logger.info("Vision frames sent: %s (%d KB)", frames_sent, len(jpeg) // 1024)
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                proc.kill()

async def stream_vision_to_bridge():
    """Connect/reconnect loop, feed frames."""
    while True:
        try:
            logger.info(f"Connecting vision to {WS_URL} ...")
            async with websockets.connect(WS_URL) as ws:
                logger.info("Connected — vision is live.")
                await stream_frames_to_bridge(ws)
        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logger.warning(f"Bridge connection lost ({e}). Retrying in 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Unexpected vision error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    # Note: first run on mac will trigger camera / screen recording permission prompts
    logger.info(f"Vision source: {SOURCE} | target FPS ~{FPS}")
    await stream_vision_to_bridge()

if __name__ == "__main__":
    import websockets  # import here so error is clear if missing

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Vision capture stopped.")
        sys.exit(0)
