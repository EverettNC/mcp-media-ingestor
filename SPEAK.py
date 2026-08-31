"""
SPEAK.py — mouth for speak_text.

THEWHOLEHOUSE on :9785 is the supplier. Porch is /say.
CHRISTMAN_EAR_CANAL.SPEAK is only used if that package is on sys.path.
This file does not pretend to speak when the canal is not here.
"""
from _paths import ensure_family_paths

ensure_family_paths()

try:
    from CHRISTMAN_EAR_CANAL.SPEAK import speak  # noqa: F401
except ImportError:
    def speak(text: str, emotion: str = "neutral"):
        raise RuntimeError(
            "CHRISTMAN_EAR_CANAL is not on this machine. "
            "THEWHOLEHOUSE is the supplier — Porch lives at "
            "http://127.0.0.1:9785/say."
        )
