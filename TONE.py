"""
TONE.py — tone for analyze_tone.

THEWHOLEHOUSE on :9785 is the supplier. Corti is /hear.
CHRISTMAN_EAR_CANAL.TONE is only used if that package is on sys.path.
This file does not invent a tone when the canal is not here.
"""
from _paths import ensure_family_paths

ensure_family_paths()

try:
    from CHRISTMAN_EAR_CANAL.TONE import analyze_tone  # noqa: F401
except ImportError:
    def analyze_tone(audio_path: str):
        raise RuntimeError(
            "CHRISTMAN_EAR_CANAL is not on this machine. "
            "THEWHOLEHOUSE is the supplier — Corti lives at "
            "http://127.0.0.1:9785/hear."
        )
