"""Correct the ear's known mishearings of this family's names.

WHY: Vosk on Filament :4850 still hears 'Christman' as 'Crispin'. A green lamp
on 8765 means the HTTP process answered. It does not mean the ear spelled the house.
"""
from __future__ import annotations

import re

# Surname only. Word-boundary. Do not touch Christmas.
_FIXES = (
    (re.compile(r"\bCrispin\b", re.IGNORECASE), "Christman"),
    (re.compile(r"\bCrispen\b", re.IGNORECASE), "Christman"),
    (re.compile(r"\bChrisman\b", re.IGNORECASE), "Christman"),
    (re.compile(r"\bCristman\b", re.IGNORECASE), "Christman"),
    (re.compile(r"\bKristman\b", re.IGNORECASE), "Christman"),
    (re.compile(r"\bKrisman\b", re.IGNORECASE), "Christman"),
    (re.compile(r"\bChris\s+man\b", re.IGNORECASE), "Christman"),
)

FILAMENT_FAMILY_PROMPT = (
    "Everett Christman. The Christman AI Project. "
    "Brockston. Riley. Derek. AlphaVox. Luma Cognify."
)


def correct_family_names(text: str) -> str:
    if not text:
        return text
    out = text
    for pat, repl in _FIXES:
        out = pat.sub(repl, out)
    return out
