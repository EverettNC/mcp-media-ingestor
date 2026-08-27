"""
SPEAK.py — re-export from GitHub Christman-Sound CHRISTMAN_EAR_CANAL.

Do not keep a second synthesizer in this repo. Canal SPEAK is the source:
XTTS first, macOS say as a declared fallback.
"""
from _paths import ensure_family_paths

ensure_family_paths()

from CHRISTMAN_EAR_CANAL.SPEAK import speak  # noqa: F401
