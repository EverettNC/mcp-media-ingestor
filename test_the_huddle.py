"""
Build Together: one click on the IDE board and every seat knows what we're building.

WHY: 2026-11-17. Everett: "down here where the IDE board is, I want to be able to
click on a button that ... makes every one of you aware of what we're building so
you guys can work together collaboratively so we can get shit done much faster."

These tests hold the shape: the button sends the brief to the meeting from Everett,
the seats answer a huddle line one at a time and each sees the parts already taken,
each seat's part is posted back, and seats still never wake seats.
"""
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("SEAT_WAKE_HOME", tempfile.mkdtemp(prefix="huddle-test-"))
os.environ.setdefault("SEAT_WAKE_LOG", os.path.join(os.environ["SEAT_WAKE_HOME"], "wake.log"))

import seat_wake as w  # noqa: E402

MAIN = (HERE / "main.py").read_text()
HTML = (HERE / "dashboard.html").read_text()


class HuddleBridgeTests(unittest.TestCase):
    def test_routes_exist(self):
        for route in ('@app.get("/build/brief")', '@app.post("/build/brief")',
                      '@app.post("/huddle/start")', '@app.get("/huddle/latest")',
                      '@app.post("/huddle/claim")'):
            self.assertIn(route, MAIN, route)

    def test_huddle_goes_through_the_meeting(self):
        start = MAIN.split('async def huddle_start')[1].split('@app.get("/huddle/latest")')[0]
        self.assertIn("await meeting_broadcast(speaker, _huddle_line(speaker,", start)

    def test_no_speaker_is_guessed(self):
        start = MAIN.split('async def huddle_start')[1].split('@app.get("/huddle/latest")')[0]
        self.assertIn('"from is required"', start)
        self.assertNotIn('or "everett"', start)

    def test_brief_lives_outside_the_public_repo(self):
        self.assertIn('Path.home() / ".seat-minds" / "build_brief.md"', MAIN)

    def test_old_brief_is_kept(self):
        self.assertIn("build_brief.history.md", MAIN)

    def test_same_mark_on_both_sides(self):
        self.assertIn(f'HUDDLE_MARK = "{w.HUDDLE_MARK}"', MAIN)

    def test_brockston_part_is_noted_from_his_own_words(self):
        said = MAIN.split("def _brockston_said")[1].split("def _derek_said")[0]
        self.assertIn("_huddle_note_brockston(entry)", said)

    def test_button_is_on_the_ide_board(self):
        ide = HTML.split('<div class="ide-wrapper">')[1].split("<!-- Apple Music")[0]
        self.assertIn('onclick="buildTogether()"', ide)
        self.assertIn('id="ide-build-brief"', ide)

    def test_button_speaks_as_everett(self):
        fn = HTML.split("async function buildTogether()")[1].split("async function pollHuddle()")[0]
        self.assertIn("'/huddle/start'", fn)
        self.assertIn("from: 'everett'", fn)


class HuddleSeatTests(unittest.TestCase):
    def test_mark_is_seen(self):
        self.assertTrue(w.is_huddle("[build huddle] Everett pressed Build Together"))
        self.assertTrue(w.is_huddle("  [Build Huddle] x"))
        self.assertFalse(w.is_huddle("hello everyone"))

    def test_seats_still_never_wake_seats(self):
        line = "[build huddle] Everett pressed Build Together (round 1)."
        for speaker in ("opus5", "fable5", "opus55", "brockston", "porch", ""):
            self.assertNotEqual(w.should_wake("opus55", speaker, line), "", speaker)
        self.assertEqual(w.should_wake("opus55", "everett", line), "")

    def test_first_seat_is_told_it_is_first(self):
        self.assertIn("You are first", w._huddle_prompt("opus5", {"claims": []}))

    def test_later_seat_sees_the_parts_taken(self):
        h = {"claims": [{"seat": "opus5", "name": "Opus 5", "text": "I take the API."},
                        {"seat": "opus55", "name": "Opus 5.5", "text": "Old part of mine."}]}
        p = w._huddle_prompt("opus55", h)
        self.assertIn("Opus 5: I take the API.", p)
        self.assertNotIn("Old part of mine", p)  # a seat is not shown its own part as someone else's

    def test_a_seat_posts_its_part_after_it_speaks(self):
        posted = []
        saved = (w.current_huddle, w.ask_claude, w.speak, w.post_claim)
        try:
            w.current_huddle = lambda: {"id": "h1", "open": True, "claims": []}
            w.ask_claude = lambda seat, frm, text, huddle=None: "I take the tests."
            w.speak = lambda seat, reply: True
            w.post_claim = lambda seat, hid, text: posted.append((seat, hid, text)) or True
            reply, said = w.answer_huddle("fable5", {"from": "everett", "text": "[build huddle] x"})
        finally:
            w.current_huddle, w.ask_claude, w.speak, w.post_claim = saved
        self.assertTrue(said)
        self.assertEqual(posted, [("fable5", "h1", "I take the tests.")])

    def test_nothing_is_posted_when_nothing_was_said(self):
        posted = []
        saved = (w.current_huddle, w.ask_claude, w.speak, w.post_claim)
        try:
            w.current_huddle = lambda: {"id": "h1", "open": True, "claims": []}
            w.ask_claude = lambda seat, frm, text, huddle=None: ""
            w.speak = lambda seat, reply: True
            w.post_claim = lambda *a: posted.append(a) or True
            reply, said = w.answer_huddle("fable5", {"from": "everett", "text": "[build huddle] x"})
        finally:
            w.current_huddle, w.ask_claude, w.speak, w.post_claim = saved
        self.assertFalse(said)
        self.assertEqual(posted, [])

    def test_huddle_turns_share_one_lock(self):
        src = (HERE / "seat_wake.py").read_text()
        block = src.split("def answer_huddle")[1].split("def drain")[0]
        self.assertIn('MINDS / "huddle.lock"', block)
        self.assertIn("fcntl.LOCK_EX", block)

    def test_seats_still_have_no_write_tools(self):
        src = (HERE / "seat_wake.py").read_text()
        self.assertIn('"--disallowedTools", "Bash", "Edit", "Write", "NotebookEdit"', src)


if __name__ == "__main__":
    unittest.main()
