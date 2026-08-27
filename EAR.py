"""
EAR.py — live-bridge adapter over GitHub Christman-Sound CHRISTMAN_EAR_CANAL.

Canal listen() currently returns capture_audio() output (a numpy array).
main.py capture_voice expects a WAV path. This file keeps that contract.
It does not implement VAD. Corti is the ear; this is a timed grab.
"""
from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

import numpy as np

from _paths import ensure_family_paths

ensure_family_paths()

from CHRISTMAN_EAR_CANAL.EAR import capture as canal_capture
from CHRISTMAN_EAR_CANAL.EAR import listen as canal_listen


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
    return _as_wav_path(canal_listen(max_duration=max_duration))


def capture(duration_seconds: float = 6.0):
    return canal_capture(duration_seconds=duration_seconds)
