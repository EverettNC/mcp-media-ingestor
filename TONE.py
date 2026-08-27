"""
TONE.py — re-export from GitHub Christman-Sound CHRISTMAN_EAR_CANAL.

Do not keep a second tone analyzer in this repo. Canal TONE is the source.
"""
from _paths import ensure_family_paths

ensure_family_paths()

from CHRISTMAN_EAR_CANAL.TONE import analyze_tone  # noqa: F401
