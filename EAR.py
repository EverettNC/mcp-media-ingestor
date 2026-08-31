"""
EAR.py — timed grab for capture_voice.

THEWHOLEHOUSE on :9785 is the supplier. Corti is /hear.
CHRISTMAN_EAR_CANAL is only used if that package is actually on sys.path.
This file does not invent a wav when the canal is not here.
"""
from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

import numpy as np

from _paths import ensure_family_paths

ensure_family_paths()

try:
    from CHRISTMAN_EAR_CANAL.EAR import capture as canal_capture
    from CHRISTMAN_EAR_CANAL.EAR import listen as canal_listen
except ImportError:
    canal_capture = None
    canal_listen = None

HOUSE = "http://127.0.0.1:9785"
_MISSING = (
    "CHRISTMAN_EAR_CANAL is not on this machine. "
    "THEWHOLEHOUSE is the supplier — Corti lives at "
    f"{HOUSE}/hear."
)


def _as_wav_path(result, sample_rate: int = 16000) -> str:
    if isinstance(result, str) and os.path.exists(result):
        return result
    if isinstance(result, Path) and result.exists():
        return str(result)
    audio = np.asarray(result)
    if audio.ndim > 1:
        audio = audio.reshape(-1)
    if np.issubdtype(audio.dtype, np.floating):
        audio = np.clip(audio, -1.0, 1.0)
        audio = (audio * 32767.0).astype(np.int16)
    else:
        audio = audio.astype(np.int16)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return tmp.name


def listen(max_duration: float = 6.0) -> str:
    if canal_listen is None:
        raise RuntimeError(_MISSING)
    return _as_wav_path(canal_listen(max_duration=max_duration))


def capture(duration_seconds: float = 6.0):
    if canal_capture is None:
        raise RuntimeError(_MISSING)
    return canal_capture(duration_seconds=duration_seconds)
