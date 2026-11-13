"""
Duey's seat exists on both sides of the table, and a chair is not Duey.

WHY: 2026-11-13. Everett gave the chair that was Riley's on the board to Duey.
The board asks the bridge for /duey/status and /duey/latest every two seconds;
these tests hold the bridge, the board and the seat script to the same names.
"""
from pathlib import Path

import unittest

HERE = Path(__file__).resolve().parent
HTML = (HERE / "dashboard.html").read_text()
MAIN = (HERE / "main.py").read_text()
SEAT = (HERE / "duey_seat.py").read_text()


class DueySeatTests(unittest.TestCase):

    def test_bridge_has_every_address_the_board_asks_for(self):
        for route in ('@app.websocket("/ws/duey")', '@app.get("/duey/status")',
                      '@app.get("/duey/latest")', '@app.post("/duey/send")'):
            self.assertIn(route, MAIN)
        self.assertIn('if who == "duey":', MAIN)
        self.assertIn('"duey_connected": active_connections.get("duey", 0) > 0', MAIN)

    def test_board_defines_the_poll_it_calls(self):
        self.assertIn("async function pollDuey()", HTML)
        self.assertIn("setInterval(pollDuey", HTML)

    def test_board_has_every_element_the_poll_looks_up(self):
        for el in ("duey-dot", "duey-session-dot", "duey-session-label",
                   "duey-card-status", "duey-card", "duey-ring", "duey-inbox-display"):
            self.assertIn(f'id="{el}"', HTML, el)

    def test_card_does_not_claim_live_on_load(self):
        self.assertIn('id="duey-card-status">OFFLINE', HTML)

    def test_only_a_socket_named_duey_counts_as_duey(self):
        self.assertIn('kind = "duey" if who in ("duey", "duey-live") else "duey-seat"', MAIN)
        self.assertIn('active_connections["duey"] = len(duey_live_clients)', MAIN)

    def test_a_chair_cannot_put_words_under_dueys_name(self):
        block = MAIN.split('@app.websocket("/ws/duey")')[1].split("@app.post")[0]
        self.assertLess(block.index('if kind != "duey":'), block.index("duey_inbox.append(entry)"))

    def test_no_speaker_is_guessed(self):
        block = MAIN.split('@app.post("/duey/send")')[1].split("@app.get")[0]
        self.assertIn('speaker or "unattributed"', block)

    def test_seat_script_answers_nothing(self):
        listen = SEAT.split("async def listen(ws)")[1].split("async def session")[0]
        self.assertNotIn("ws.send", listen)

    def test_seat_names_itself_only_as_asked(self):
        self.assertIn('LIVE = "duey"', SEAT)
        self.assertIn('CHAIR = "duey-seat"', SEAT)
        self.assertNotIn("live-minutes", SEAT)
        self.assertNotIn("live_until", SEAT)
        self.assertNotIn("async def lease", SEAT)
        self.assertIn("who = CHAIR if args.chair else LIVE", SEAT)

    def test_seat_detaches_so_a_closing_session_cannot_take_it_down(self):
        self.assertIn("os.setsid()", SEAT)
        self.assertLess(SEAT.index("        daemonize()"), SEAT.index("    acquire_lock()\n    who ="))


if __name__ == "__main__":
    unittest.main()
