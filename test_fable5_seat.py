"""
Fable 5's seat exists on both sides of the table, and a chair is not Fable.

WHY: 2026-11-12. The board had the Fable5 card and asked the bridge for
/fable5/status and /fable5/latest every two seconds. The bridge had neither,
the board called a function (pollFable5) that was not defined, and the card
could only ever say "Not seated."
"""
from pathlib import Path

import unittest

HERE = Path(__file__).resolve().parent
HTML = (HERE / "dashboard.html").read_text()
MAIN = (HERE / "main.py").read_text()
SEAT = (HERE / "fable5_seat.py").read_text()


class Fable5SeatTests(unittest.TestCase):

    def test_bridge_has_every_address_the_board_asks_for(self):
        for route in ('@app.websocket("/ws/fable5")', '@app.get("/fable5/status")',
                      '@app.get("/fable5/latest")', '@app.post("/fable5/send")'):
            self.assertIn(route, MAIN)
        self.assertIn('if who == "fable5":', MAIN)
        self.assertIn('"fable5_connected": active_connections.get("fable5", 0) > 0', MAIN)

    def test_board_defines_the_poll_it_calls(self):
        self.assertIn("async function pollFable5()", HTML)
        self.assertIn("setInterval(pollFable5", HTML)

    def test_board_has_every_element_the_poll_looks_up(self):
        for el in ("fable5-dot", "fable5-session-dot", "fable5-session-label",
                   "fable5-card-status", "fable5-card", "fable5-ring", "fable5-inbox-display"):
            self.assertIn(f'id="{el}"', HTML, el)

    def test_card_does_not_claim_live_on_load(self):
        self.assertIn('id="fable5-card-status">OFFLINE', HTML)

    def test_only_a_socket_named_fable_counts_as_fable(self):
        self.assertIn('kind = "fable5" if who in ("fable5", "fable", "fable-live") else "fable5-seat"', MAIN)
        self.assertIn('active_connections["fable5"] = len(fable5_live_clients)', MAIN)

    def test_a_chair_cannot_put_words_under_fables_name(self):
        block = MAIN.split('@app.websocket("/ws/fable5")')[1].split("@app.post")[0]
        self.assertLess(block.index('if kind != "fable5":'), block.index("fable5_inbox.append(entry)"))

    def test_no_speaker_is_guessed(self):
        block = MAIN.split('@app.post("/fable5/send")')[1].split("@app.get")[0]
        self.assertIn('speaker or "unattributed"', block)

    def test_seat_script_answers_nothing_and_gives_up_live_when_its_time_ends(self):
        listen = SEAT.split("async def listen(ws)")[1].split("async def session")[0]
        self.assertNotIn("ws.send", listen)
        self.assertIn('{"type": "identify", "who": CHAIR}', SEAT)


if __name__ == "__main__":
    unittest.main()
