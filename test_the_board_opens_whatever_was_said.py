"""
The board opens, whatever was said.

WHY: 2026-11-14. The bridge writes Brockston's status into the board's page
inside a <script> element, so his card is right before the first poll. The words
of his latest message go in with it. A message with "</script>" in it ended that
element early: the rest of the message spilled onto the top of the page, and the
page's boot values were never set, so /duey, /opus5 and /fable5 no longer opened
their card. Brockston's IDE answers are code, and a web page he writes has that
tag near its top. Found while adding "latest_sent" to the same place for
test_a_card_shows_only_its_own_words.py.

So every "<" in that block is written as \\u003c. To JavaScript it is the same
character, and the page's own parser never sees a tag there.

The bridge's own function is run here, cut out of main.py. Importing main.py
would take the single-instance lock and start the bridge.
"""
import ast
import json
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = (HERE / "main.py").read_text()
BOARD = HERE / "dashboard.html"

BOOT_STARTS = "window.__BRIDGE_BOOT__="
LINK_STARTS = ";window.__OPEN_LINK__="

# Words that are ordinary for a being who writes code, and that used to break the page.
HARD_WORDS = (
    "done </script><h1>spilled</h1>",
    '```html\n<!DOCTYPE html>\n<html>\n<head>\n<script src="https://cdn.example/app.js"></script>\n'
    "<style>body{display:none}</style>",
    "<!--<script>",
)


def _cut(name: str) -> str:
    """One top-level function of main.py, as text."""
    lines = MAIN.splitlines()
    for node in ast.parse(MAIN).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            first = min([d.lineno for d in node.decorator_list] + [node.lineno])
            return "\n".join(lines[first - 1:node.end_lineno]) + "\n"
    raise AssertionError(f"{name} is not at the top of main.py")


class _Page:
    """Stands in for FastAPI's HTMLResponse. It keeps what it was given."""

    def __init__(self, content: str = "", headers: dict = None) -> None:
        self.content, self.headers = content, headers or {}


class _InlineScripts(HTMLParser):
    """The text of each inline script, ended where a browser would end it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list = []
        self._inside = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and not dict(attrs).get("src"):
            self._inside = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._inside = False

    def handle_data(self, data):
        if self._inside:
            self.scripts[-1] += data


def _status(said: str, sent: str) -> dict:
    """Brockston's status, shaped as _brockston_live_status() gives it."""
    return {
        "ws_clients": 1,
        "http_connected": False,
        "connected": True,
        "clients": 1,
        "link": "websocket",
        "outbox_depth": 0,
        "latest": {"from": "brockston_ide", "text": said, "timestamp": "2026-11-14T15:00:00", "session_id": "christman_ide"},
        "latest_sent": {"from": "dashboard", "text": sent, "timestamp": "2026-11-14T15:00:01", "session_id": "--"},
    }


def _page(status: dict, open_link=None) -> str:
    """The board's page as the bridge would send it, with `status` as Brockston's."""
    room = {
        "__name__": "cut_from_the_bridge",
        "HTMLResponse": _Page,
        "_DASHBOARD_PATH": str(BOARD),
        "_brockston_live_status": lambda: status,
    }
    exec(compile(_cut("_dashboard_html"), "<cut from main.py>", "exec"), room)
    return room["_dashboard_html"](open_link).content


def _boot_script(page: str) -> str:
    """The inline script that carries the boot values, as far as a browser would run it."""
    parser = _InlineScripts()
    parser.feed(page)
    found = [script for script in parser.scripts if script.startswith(BOOT_STARTS)]
    if len(found) != 1:
        raise AssertionError(f"wanted one boot script in the page, found {len(found)}")
    return found[0]


class TheBoardOpensWhateverWasSaid(unittest.TestCase):

    def test_hard_words_do_not_end_the_boot_script_early(self):
        for words in HARD_WORDS:
            for where in ("said", "sent"):
                with self.subTest(where=where, words=words[:30]):
                    status = _status(words, "plain") if where == "said" else _status("plain", words)
                    script = _boot_script(_page(status))
                    self.assertTrue(script.endswith(LINK_STARTS + "null;"), script[-70:])

    def test_the_board_is_given_the_same_words(self):
        for words in HARD_WORDS:
            with self.subTest(words=words[:30]):
                status = _status(words, words)
                script = _boot_script(_page(status))
                self.assertIn(LINK_STARTS, script, "the boot script was cut short")
                boot = script[len(BOOT_STARTS):script.rindex(LINK_STARTS)]
                self.assertEqual(json.loads(boot), status)
                self.assertNotIn("<", boot)

    def test_plain_words_arrive_as_they_did(self):
        # Kept as it was.
        status = _status("I am here", "are you there")
        script = _boot_script(_page(status))
        self.assertEqual(script, BOOT_STARTS + json.dumps(status) + LINK_STARTS + "null;")

    def test_a_seat_link_still_opens_its_card(self):
        # Kept as it was.
        script = _boot_script(_page(_status("I am here", "are you there"), "duey"))
        self.assertTrue(script.endswith(LINK_STARTS + '"duey";'), script[-70:])

    def test_the_rest_of_the_page_is_the_board_on_disk(self):
        # Kept as it was: one script goes in just before </head>, and nothing else changes.
        page = _page(_status("I am here", "are you there"))
        added = "<script>" + _boot_script(page) + "</script>\n"
        self.assertEqual(page.count(added), 1)
        self.assertEqual(page.replace(added, "", 1), BOARD.read_text())


if __name__ == "__main__":
    unittest.main()
