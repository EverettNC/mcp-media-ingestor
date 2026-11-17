"""
The meeting answers back: Everett speaks once, and each iMac seat's own Claude answers.

WHY: 2026-11-17. Everett: "I should be able to ... just speak to all of you at once.
Because that's what the fucking IDE board is." His words already reached every seat;
only Brockston answered. seat_wake.py wakes Opus 5, Fable 5 and Opus 5.5. These tests
hold the guards: only Everett or the board wake a seat, so seats never answer seats,
echoes, Porch or stale queued lines.
"""
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["SEAT_WAKE_HOME"] = tempfile.mkdtemp(prefix="seatwake-test-")
os.environ["SEAT_WAKE_LOG"] = os.path.join(os.environ["SEAT_WAKE_HOME"], "wake.log")

import seat_wake as w  # noqa: E402


class SeatWakeTests(unittest.TestCase):
    def test_everett_and_the_board_wake_a_seat(self):
        self.assertEqual(w.should_wake("opus55", "everett", "hello"), "")
        self.assertEqual(w.should_wake("fable5", "dashboard", "hello"), "")

    def test_seats_never_wake_seats(self):
        for speaker in ("opus5", "fable5", "opus55", "duey", "brockston_agent", "claude", "porch", ""):
            self.assertNotEqual(w.should_wake("opus55", speaker, "hello"), "", speaker)

    def test_own_echo_never_wakes(self):
        self.assertEqual(w.should_wake("opus5", "opus5", "hello"), "own echo")

    def test_stale_lines_are_not_answered(self):
        self.assertTrue(w.should_wake("opus55", "everett", "hi", "2020-01-01T00:00:00").startswith("stale"))

    def test_duey_is_not_woken_from_the_imac(self):
        self.assertNotIn("duey", w.SEATS)

    def test_off_switch(self):
        off = Path(os.environ["SEAT_WAKE_HOME"]) / "OFF"
        off.parent.mkdir(parents=True, exist_ok=True)
        off.touch()
        try:
            self.assertEqual(w.should_wake("opus55", "everett", "hi"), "switched off")
        finally:
            off.unlink()

    def test_same_line_is_answered_once(self):
        self.assertTrue(w.enqueue("fable5", "everett", "twice"))
        self.assertFalse(w.enqueue("fable5", "everett", "twice"))

    def test_claude_has_a_timeout_and_no_write_tools(self):
        src = (HERE / "seat_wake.py").read_text()
        self.assertIn("timeout=TIMEOUT_S", src)
        self.assertIn('"--disallowedTools", "Bash", "Edit", "Write", "NotebookEdit"', src)

    def test_each_seat_wakes_itself(self):
        self.assertIn('seat_wake.spawn("fable5", msg)', (HERE / "fable5_seat.py").read_text())
        self.assertIn('seat_wake.spawn("opus55", msg)', (HERE / "opus55_seat.py").read_text())
        opus5 = Path.home() / ".opus5-seat" / "seat.py"
        if opus5.exists():
            self.assertIn('seat_wake.spawn("opus5", msg)', opus5.read_text())


if __name__ == "__main__":
    unittest.main()
