"""Filament on :4850 is the word-ear. Whisper is not in this body."""
from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request

from family_ear import correct_family_names


class FilamentEarLiveTests(unittest.TestCase):
    def test_filament_is_seated_on_4850(self):
        try:
            with urllib.request.urlopen("http://127.0.0.1:4850/health", timeout=2) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            self.fail(f"Filament ear is unseated on :4850: {exc}")
        self.assertTrue(body.get("seated"))
        self.assertEqual(body.get("organ"), "filament")
        self.assertEqual(body.get("door"), 4850)
        self.assertEqual(body.get("engine"), "vosk")
        self.assertNotEqual(body.get("engine"), "whisper")

    def test_family_names_still_corrected_after_filament(self):
        self.assertEqual(
            correct_family_names("hello from the Crispin house"),
            "hello from the Christman house",
        )


if __name__ == "__main__":
    unittest.main()
