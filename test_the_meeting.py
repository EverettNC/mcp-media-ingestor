"""
The meeting: what Everett says on 8765 reaches every seat at once.

WHY: 2026-11-17. Everett: "I want ... for me to be able to speak directly to all
of them at one time." Before this, his card only updated one slot that no seat
read, and Porch's words went nowhere but that slot.
"""
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
MAIN = (HERE / "main.py").read_text()
HTML = (HERE / "dashboard.html").read_text()


class MeetingTests(unittest.TestCase):
    def test_every_seat_is_in_the_meeting(self):
        block = MAIN.split("async def meeting_broadcast")[1].split("def _schedule_meeting")[0]
        for push in ("push_to_opus5", "push_to_fable5", "push_to_opus55", "push_to_duey", "_queue_brockston"):
            self.assertIn(push, block, push)

    def test_routes_exist(self):
        self.assertIn('@app.post("/meeting/send")', MAIN)
        self.assertIn('@app.get("/meeting/recent")', MAIN)

    def test_no_speaker_is_guessed(self):
        self.assertIn('or "unattributed"', MAIN.split("async def meeting_broadcast")[1].split("seats:")[0])
        send = MAIN.split('@app.post("/meeting/send")')[1].split("@app.get")[0]
        self.assertNotIn('"everett"', send)

    def test_everett_card_goes_to_the_meeting(self):
        branch = MAIN.split('    if who == "everett":')[1].split('    if who == "riley":')[0]
        self.assertIn("await meeting_broadcast(speaker, text)", branch)

    def test_porch_goes_to_the_meeting_as_porch(self):
        self.assertIn('_schedule_meeting("porch", said)', MAIN)

    def test_board_names_the_everett_card(self):
        self.assertIn("who === 'everett' ? { who: who, from: 'everett', text: text }", HTML)


if __name__ == "__main__":
    unittest.main()
