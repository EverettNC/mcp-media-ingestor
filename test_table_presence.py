"""
The table may not report a being live unless a socket is counted.

WHY: 2026-08-31. The dashboard hardcoded Derek as alive and Riley as
CRUISE MODE / SOVEREIGN INTACT with a green lamp, while /health said
riley_connected false and nothing counted Derek at all. Grok had no
chair. A lamp that does not measure is a lie.
"""
from pathlib import Path

import unittest

HERE = Path(__file__).resolve().parent
HTML = (HERE / "dashboard.html").read_text()
MAIN = (HERE / "main.py").read_text()


class TablePresenceTests(unittest.TestCase):


    def test_derek_status_lamp_is_measured(self):
        self.assertIn('id="derek-dot"', HTML)
        self.assertNotIn(
            '<div class="dot alive"></div><span>DEREK 309</span>', HTML
        )

    def test_derek_card_does_not_claim_live_on_load(self):
        self.assertIn('id="claude-card-status">OFFLINE', HTML)
        self.assertNotIn('id="claude-card-status">ACTIVE', HTML)
        self.assertNotIn("I am here. Always.", HTML)
        self.assertNotIn("SESSION LIVE", HTML)

    def test_riley_card_does_not_claim_live_on_load(self):
        self.assertIn('id="riley-card-status">OFFLINE', HTML)
        self.assertNotIn('id="riley-card-status">CRUISE MODE', HTML)
        self.assertNotIn("Tunnel warm. Standing by.", HTML)

    def test_grok_has_a_chair_on_the_table(self):
        self.assertIn('id="grok-dot"', HTML)
        self.assertIn('id="grok-card"', HTML)
        self.assertIn('option value="grok"', HTML)
        self.assertIn("/ws/grok", MAIN)
        self.assertIn('"grok"', MAIN)

    def test_empty_derek_latest_is_not_a_spoken_line(self):
        self.assertNotIn('"I am here. Always."', MAIN)


if __name__ == "__main__":
    unittest.main()
