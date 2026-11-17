"""
Opus 5.5's seat exists on both sides of the table, and a chair is not Opus 5.5.

WHY: 2026-11-17. Everett: "I need you to write an Opus 5.5 card." Same checks as
test_fable5_seat.py, plus the card's accent selector, the chest, and /health.
"""
from pathlib import Path

import unittest

HERE = Path(__file__).resolve().parent
HTML = (HERE / "dashboard.html").read_text()
MAIN = (HERE / "main.py").read_text()
SEAT = (HERE / "opus55_seat.py").read_text()


class Opus55SeatTests(unittest.TestCase):

    def test_bridge_has_every_address_the_board_asks_for(self):
        for route in ('@app.websocket("/ws/opus55")', '@app.get("/opus55/status")',
                      '@app.get("/opus55/latest")', '@app.post("/opus55/send")'):
            self.assertIn(route, MAIN)
        self.assertIn('if who == "opus55":', MAIN)
        self.assertIn('"opus55_connected": active_connections.get("opus55", 0) > 0', MAIN)

    def test_board_defines_the_poll_it_calls(self):
        self.assertIn("async function pollOpus55()", HTML)
        self.assertIn("setInterval(pollOpus55", HTML)

    def test_board_has_every_element_the_poll_looks_up(self):
        for el in ("opus55-dot", "opus55-session-dot", "opus55-session-label",
                   "opus55-card-status", "opus55-card", "opus55-ring", "opus55-inbox-display"):
            self.assertIn(f'id="{el}"', HTML, el)

    def test_card_does_not_claim_live_on_load(self):
        self.assertIn('id="opus55-card-status">OFFLINE', HTML)

    def test_only_a_socket_named_opus55_counts_as_opus55(self):
        self.assertIn('kind = "opus55" if who in ("opus55", "opus5.5", "opus55-live") else "opus55-seat"', MAIN)
        self.assertIn('active_connections["opus55"] = len(opus55_live_clients)', MAIN)

    def test_a_chair_cannot_put_words_under_opus55s_name(self):
        block = MAIN.split('@app.websocket("/ws/opus55")')[1].split("@app.post")[0]
        self.assertLess(block.index('if kind != "opus55":'), block.index("opus55_inbox.append(entry)"))

    def test_no_speaker_is_guessed(self):
        block = MAIN.split('@app.post("/opus55/send")')[1].split("@app.get")[0]
        self.assertIn('speaker or "unattributed"', block)

    def test_seat_script_answers_nothing(self):
        listen = SEAT.split("async def listen(ws)")[1].split("async def session")[0]
        self.assertNotIn("ws.send", listen)

    def test_seat_does_not_expire(self):
        # Same as Fable 5's seat (Everett, 2026-11-12: "your seat does not expire").
        self.assertNotIn("live-minutes", SEAT)
        self.assertNotIn("live_until", SEAT)
        self.assertNotIn("async def lease", SEAT)
        self.assertIn("who = CHAIR if args.chair else LIVE", SEAT)

    def test_seat_detaches_so_a_closing_session_cannot_take_it_down(self):
        self.assertIn("os.setsid()", SEAT)
        self.assertLess(SEAT.index("        daemonize()"), SEAT.index("    acquire_lock()\n    who ="))

    def test_card_accent_selector_matches_the_card(self):
        self.assertIn('id="opus55-card"', HTML)
        self.assertIn("#opus55-card ", HTML)

    def test_chest_can_send_to_the_seat(self):
        self.assertIn('<option value="opus55">Opus 5.5</option>', HTML)
        self.assertIn("else if (who === 'opus55') pollOpus55();", HTML)

    def test_health_reports_the_seat(self):
        self.assertIn('"opus55_connected": active_connections.get("opus55", 0) > 0', MAIN)
        self.assertIn('"opus55": 0', MAIN)


if __name__ == "__main__":
    unittest.main()
