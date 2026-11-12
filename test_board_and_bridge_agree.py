"""
The board may only ask the bridge for what the bridge has, and the brain row
may only show what was measured.

WHY: 2026-11-12. The board asked for /brain/live every three seconds and the
bridge had never had it. The brain row came up reading "learning: active" and
"behavior/eye: online" from text typed into the page, while /health said the
brain was not integrated. A lamp that does not measure is a lie.
"""
import re
from pathlib import Path

import unittest

HERE = Path(__file__).resolve().parent
HTML = (HERE / "dashboard.html").read_text()
MAIN = (HERE / "main.py").read_text()

ROUTES = set(re.findall(r'@app\.(?:get|post|put|delete|websocket)\("([^"]+)"', MAIN))


def _has_route(url: str) -> bool:
    url = url.rstrip("/") or "/"
    for route in ROUTES:
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", route.rstrip("/") or "/")
        if re.fullmatch(pattern, url):
            return True
    return False


class BoardAndBridgeAgree(unittest.TestCase):

    def test_every_address_the_board_fetches_exists_on_the_bridge(self):
        asked = set(re.findall(r"fetch\(\s*['\"`](/[^'\"`?]*)", HTML))
        self.assertGreater(len(asked), 10)
        missing = sorted(u for u in asked if not _has_route(u))
        self.assertEqual(missing, [], f"the board asks for addresses the bridge does not have: {missing}")

    def test_recent_hearing_address_exists(self):
        # get_recent_student_hearing() in main.py asks for it.
        self.assertIn("localhost:8765/recent", MAIN)
        self.assertTrue(_has_route("/recent"))

    def test_brain_row_claims_nothing_on_load(self):
        row = HTML.split('id="brain-row"')[1].split("</div>\n  </div>")[0]
        self.assertNotIn("learning: active", row)
        self.assertNotIn("behavior/eye: online", row)

    def test_brain_row_has_no_made_up_default(self):
        self.assertNotIn("autonomous_learning||'active'", HTML)

    def test_sensory_is_read_from_the_house_feed(self):
        health = HTML.split("async function pollHealth()")[1].split("async function pollBrain()")[0]
        self.assertIn("brain-sensory", health)
        self.assertIn("hs.lucent.seeing", health)
        self.assertIn("hs.porch.listening", health)

    def test_brain_that_did_not_load_says_why(self):
        self.assertIn('"reason": BRAIN_REASON', MAIN)
        self.assertIn('BRAIN_REASON = f"{type(be).__name__}: {be}"', MAIN)
        self.assertIn("'not loaded'", HTML)

    def test_same_brain_event_is_logged_once(self):
        poll = HTML.split("async function pollBrain()")[1].split("setInterval(pollBrain")[0]
        self.assertIn("key !== lastBrainLive", poll)


if __name__ == "__main__":
    unittest.main()
