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

    def test_ide_shows_chat_error_instead_of_empty_ok(self):
        self.assertIn("d.error", HTML)
        self.assertIn("liftCommentToEditor", HTML)
        self.assertIn('option value="grok"', HTML.split("ide-instance")[1][:800])

    def test_ide_output_does_not_break_every_character(self):
        self.assertNotIn("word-break: break-all;", HTML)

    def test_ide_comment_mail_slot_exists(self):
        self.assertIn('/ide/comment', MAIN)
        self.assertIn('/ide/latest', MAIN)

    def test_ide_prompt_has_enter(self):
        self.assertIn("ideEnter()", HTML)
        self.assertIn("↵ ENTER", HTML)
        self.assertIn("e.target.id === 'ide-prompt'", HTML)

    def test_transcript_lamp_is_measured(self):
        self.assertIn('id="ear-dot"', HTML)
        self.assertNotIn("LIVE TRANSCRIPT · PORCH WORD-EAR · 9785", HTML)
        self.assertNotIn(
            '<div class="dot alive"></div>\n          LIVE TRANSCRIPT',
            HTML,
        )

    def test_health_fail_kills_bridge_lamp(self):
        self.assertIn("BRIDGE DOWN", HTML)
        catch = HTML.split("async function pollHealth()")[1].split("async function pollBrain()")[0]
        self.assertIn("bridge-dot", catch.split("catch(e)")[1])
        self.assertIn("grok-dot", catch.split("catch(e)")[1])

    def test_filament_is_the_word_ear(self):
        self.assertIn("127.0.0.1:4850", MAIN)
        self.assertIn("filament", MAIN.lower())
        self.assertIn("correct_family_names", MAIN)
        self.assertNotIn("whisper-cli", MAIN)
        self.assertNotIn("WHISPER_BIN", MAIN)
        self.assertNotIn("ggml-small.en.bin", MAIN)
        self.assertNotIn("--prompt", MAIN)

    def test_mcp_transcribe_uses_filament(self):
        server = (HERE / "server.py").read_text()
        self.assertIn("127.0.0.1:4850", server)
        self.assertIn("/stt", server)
        self.assertNotIn("whisper.cpp", server)
        self.assertNotIn("ggml-small.en.bin", server)


if __name__ == "__main__":
    unittest.main()
