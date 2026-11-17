"""
The workstation: the IDE board is where the seats build together.

WHY: 2026-11-17. Everett: "the IDE board actually needs ... to be more emphasized
because ... I want that IDE board to be a workstation for us."

These tests hold the shape: ASK FOR CODE goes to the meeting from Everett, each seat
writes its part as code one at a time seeing what the others wrote, only one spoken
sentence goes on the board, the code is kept as a proposal outside the repo, nothing
is written to any project file, and the page shows it all with textContent.
"""
import os
import tempfile
import unittest
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
os.environ.setdefault("SEAT_WAKE_HOME", tempfile.mkdtemp(prefix="workstation-test-"))
os.environ.setdefault("SEAT_WAKE_LOG", os.path.join(os.environ["SEAT_WAKE_HOME"], "wake.log"))

import seat_wake as w  # noqa: E402

MAIN = (HERE / "main.py").read_text()
HTML = (HERE / "dashboard.html").read_text()
ANSWER = ("This is the route that serves the brief.\nFILE: routes/brief.py\n"
          "```python\ndef brief():\n    return 'hi'\n```\nThat's it.")


def _main_parser():
    """main.py's _proposal_from_text, run on its own (main.py itself needs the whole house)."""
    src = MAIN.split("def _proposal_from_text")[1].split("\ndef _add_proposal")[0]
    ns = {"Optional": Optional, "HUDDLE_SEATS": {"opus5": "Opus 5"}, "PROPOSAL_MAX_CHARS": 40000}
    exec("def _proposal_from_text" + src, ns)
    return ns["_proposal_from_text"]


class WorkstationBridgeTests(unittest.TestCase):
    def test_routes_exist(self):
        for route in ('@app.post("/workstation/ask")', '@app.post("/workstation/proposal")',
                      '@app.get("/workstation/state")', '@app.get("/workstation/proposal/{proposal_id}")'):
            self.assertIn(route, MAIN, route)

    def test_ask_goes_through_the_meeting_and_needs_a_speaker(self):
        ask = MAIN.split("async def workstation_ask")[1].split('@app.post("/workstation/proposal")')[0]
        self.assertIn('"from is required"', ask)
        self.assertIn("await meeting_broadcast(speaker, _code_line(speaker,", ask)

    def test_mark_matches(self):
        self.assertIn(f'WORK_MARK = "{w.WORK_MARK}"', MAIN)
        self.assertTrue(w.is_code_ask(w.WORK_MARK + " Everett asked for code"))
        self.assertFalse(w.is_huddle(w.WORK_MARK + " Everett asked for code"))
        self.assertFalse(w.is_code_ask("[build huddle] round 1"))

    def test_proposals_live_outside_the_repo(self):
        self.assertIn('Path.home() / ".seat-minds" / "proposals.jsonl"', MAIN)

    def test_no_project_file_is_written(self):
        section = MAIN.split("# ── The workstation")[1].split('@app.post("/channel/send")')[0]
        for forbidden in ("write_text(", "open(p", "Path(p", 'p["file"]).', "shutil"):
            self.assertNotIn(forbidden, section, forbidden)

    def test_main_parser_splits_sentence_file_and_code(self):
        p = _main_parser()("opus5", ANSWER, "test")
        self.assertEqual(p["file"], "routes/brief.py")
        self.assertEqual(p["language"], "python")
        self.assertEqual(p["code"], "def brief():\n    return 'hi'")
        self.assertEqual(p["summary"], "This is the route that serves the brief.")
        self.assertIsNone(_main_parser()("opus5", "no code here", "test"))

    def test_brockston_code_is_noted(self):
        said = MAIN.split("def _brockston_said")[1].split("def _derek_said")[0]
        self.assertIn("_workstation_note_brockston(entry)", said)


class WorkstationPageTests(unittest.TestCase):
    def ws(self):
        return HTML.split('<div class="ide-wrapper">')[1].split("<!-- Apple Music")[0]

    def test_workstation_is_emphasized_and_reachable(self):
        self.assertIn('id="workstation"', HTML)
        self.assertIn('href="#workstation"', HTML)
        self.assertIn("CHRISTMAN WORKSTATION", self.ws())

    def test_crew_and_proposals_are_on_the_workstation(self):
        for el in ('id="ws-crew"', 'id="ws-proposal-grid"', 'id="ws-ask-code"', 'id="ide-build-brief"'):
            self.assertIn(el, self.ws(), el)

    def test_ask_speaks_as_everett(self):
        fn = HTML.split("async function askForCode")[1].split("function wsOpenInEditor")[0]
        self.assertIn("'/workstation/ask'", fn)
        self.assertIn("from: 'everett'", fn)

    def test_seat_words_are_never_html(self):
        part = HTML.split("// ── The workstation: the crew")[1].split("async function pollIde")[0]
        self.assertNotIn("innerHTML", part)
        self.assertNotIn("insertAdjacentHTML", part)


class SeatPickerTests(unittest.TestCase):
    """Everett, 2026-11-17: keep the picker "in case I'm just working independently",
    with everyone listed, and "All of you" as the default. The comment row names no seat."""

    def picker(self):
        return HTML.split('<select id="ide-instance"')[1].split("</select>")[0]

    def test_everyone_is_listed_and_all_is_the_default(self):
        p = self.picker()
        self.assertIn('<option value="all" selected>', p)
        for seat in ("opus5", "fable5", "opus55", "duey", "brockston"):
            self.assertIn(f'<option value="{seat}">', p, seat)
        self.assertEqual(p.count("selected"), 1)

    def test_comment_row_names_no_seat(self):
        bar = HTML.split('id="ide-prompt"')[1].split("/>")[0]
        self.assertIn("Type a comment, then ENTER", bar)
        for name in ("Fable", "Opus", "Brockston", "Duey"):
            self.assertNotIn(name, bar)

    def test_enter_follows_the_picker(self):
        fn = HTML.split("async function ideEnter")[1].split("function liftCommentToEditor")[0]
        self.assertNotIn("who: 'fable5'", fn)
        self.assertIn("who: seat.value === 'all' ? 'everett' : seat.value", fn)
        self.assertIn("liftCommentToEditor('everett', text)", fn)

    def _chat(self, instance):
        import test_the_table_is_the_family as t
        sent = {k: t._Taker() for k in ("opus5", "opus55", "duey")}
        meeting = []

        async def broadcast(speaker, text):
            meeting.append((speaker, text))
            return {"status": "sent", "seats": {}}
        room, touched = t._run_cut(("api_chat",), {
            "_IDE_DEFAULT_LANE": "test-lane", "meeting_broadcast": broadcast,
            "push_to_opus5": sent["opus5"], "push_to_opus55": sent["opus55"], "push_to_duey": sent["duey"],
        })
        out = t._go(room["api_chat"]({"message": "hello", "instance": instance, "from": "everett"}))
        self.assertEqual(touched, [])
        return out, sent, meeting

    def test_all_goes_to_the_meeting_once(self):
        out, sent, meeting = self._chat("all")
        self.assertTrue(out["ok"])
        self.assertEqual(meeting, [("everett", "hello")])
        self.assertEqual([len(s.got) for s in sent.values()], [0, 0, 0])

    def test_one_seat_gets_it_alone(self):
        for seat in ("opus5", "opus55", "duey"):
            out, sent, meeting = self._chat(seat)
            self.assertEqual(meeting, [])
            self.assertEqual({k: len(s.got) for k, s in sent.items()},
                             {k: int(k == seat) for k in sent}, seat)
            self.assertEqual(sent[seat].got[-1]["from"], "everett")


class WorkstationSeatTests(unittest.TestCase):
    def setUp(self):
        self.saved = {k: getattr(w, k) for k in ("ask_claude", "current_code_ask", "post_proposal", "speak")}
        self.spoken, self.posted, self.prompts = [], [], []
        w.speak = lambda seat, line: self.spoken.append(line) or True
        w.post_proposal = lambda seat, ask, part: self.posted.append((seat, ask, part)) or True
        w.current_code_ask = lambda: {"ask": {"id": "code-1", "open": True}, "proposals": [
            {"seat": "fable5", "name": "Fable 5", "file": "t.py", "summary": "tests", "language": "python",
             "code": "assert True"}]}

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(w, k, v)

    def test_split_code(self):
        part = w.split_code(ANSWER)
        self.assertEqual(part["file"], "routes/brief.py")
        self.assertEqual(part["code"], "def brief():\n    return 'hi'")
        self.assertEqual(w.split_code("just words"), {})

    def test_only_the_sentence_is_spoken_and_the_code_is_posted(self):
        def fake(seat, speaker, text, huddle=None, extra="", timeout=0, max_chars=0):
            self.prompts.append(extra)
            return ANSWER
        w.ask_claude = fake
        line, said = w.answer_code("opus5", {"from": "everett", "text": w.WORK_MARK + " go"})
        self.assertTrue(said)
        self.assertEqual(self.spoken, ["This is the route that serves the brief."])
        self.assertEqual(self.posted[0][1], "code-1")
        self.assertNotIn("```", self.spoken[0])
        self.assertIn("Fable 5", self.prompts[0])      # sees the code already proposed
        self.assertIn("assert True", self.prompts[0])

    def test_no_code_means_the_words_are_spoken(self):
        w.ask_claude = lambda *a, **k: "I need the brief first."
        line, said = w.answer_code("opus5", {"from": "everett", "text": w.WORK_MARK + " go"})
        self.assertEqual(self.spoken, ["I need the brief first."])
        self.assertEqual(self.posted, [])

    def test_seats_still_cannot_write(self):
        src = (HERE / "seat_wake.py").read_text()
        self.assertIn('"--disallowedTools", "Bash", "Edit", "Write", "NotebookEdit"', src)

    def test_code_asks_share_the_turn_lock(self):
        src = (HERE / "seat_wake.py").read_text().split("def answer_code")[1].split("def drain")[0]
        self.assertIn('MINDS / "huddle.lock"', src)


if __name__ == "__main__":
    unittest.main()
