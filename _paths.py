"""
_paths.py — Christman Family Path Bootstrap

CORTI, Christman-Sound, and LUCENT are the EverettNC GitHub clones at:

    /Users/EverettN/CORTI              https://github.com/EverettNC/CORTI.git
    /Users/EverettN/Christman-Sound    https://github.com/EverettNC/Christman-Sound.git
    /Users/EverettN/LUCENT             https://github.com/EverettNC/LUCENT.git

CORTI and LUCENT are TypeScript organs (ear / cornea). They are not on
sys.path. Christman-Sound is the Python SDK this bridge imports.
"""
import os
import sys

SOUND_ROOT = "/Users/EverettN/Christman-Sound"
CORTI_ROOT = "/Users/EverettN/CORTI"
LUCENT_ROOT = "/Users/EverettN/LUCENT"

FAMILY_ROOTS = [SOUND_ROOT]


def ensure_family_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    for root in FAMILY_ROOTS + [here, cwd]:
        if os.path.isdir(root) and root not in sys.path:
            sys.path.insert(0, root)
