"""Transcribe a file through Filament on :4850. Whisper is not in this body."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from family_ear import correct_family_names

FILAMENT_EAR_URL = "http://127.0.0.1:4850/stt"


def test_transcribe(audio_file: str) -> str:
    print(f"Filament ear :4850 inhaling: {audio_file}")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_file, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_path],
            capture_output=True,
            text=True,
            check=True,
        )
        wav = Path(tmp_path).read_bytes()
        req = urllib.request.Request(
            FILAMENT_EAR_URL,
            data=wav,
            headers={"Content-Type": "audio/wav"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if body.get("seated") is False:
        raise RuntimeError(body.get("error") or "Filament ear unseated")
    text = correct_family_names((body.get("text") or body.get("transcript") or "").strip())
    print(text or "[empty ear]")
    return text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_audio.py <audio_or_video_file>")
        sys.exit(1)
    test_transcribe(sys.argv[1])
