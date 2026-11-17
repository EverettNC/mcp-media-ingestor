"""
The board shows a message as words.

WHY: 2026-11-14. The board's channel log built each line as page code, with the
being's words dropped into the middle of it. So words that hold code were not
shown, they were run: a "<style>" in Brockston's answer restyled the whole board,
an "<img onerror=...>" ran script on it, and a plain "<div>" in a sentence was
swallowed. Brockston writes code for a living, and every being at the table
talks about it. The brain's status line was built the same way. Found while
fixing what a card shows (test_a_card_shows_only_its_own_words.py).

A message is words. The board puts it on the page as text, never as page code.

The board's own addLog is run here under node with a stand-in page, cut out of
dashboard.html. Nothing here opens a browser or talks to the bridge.
"""
import json
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOARD = (HERE / "dashboard.html").read_text()

# Ways a page turns a string into page code.
AS_PAGE_CODE = re.compile(r"\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML|document\.write")
# The only use left: setting innerHTML to a fixed string with nothing joined into it.
A_FIXED_STRING = re.compile(r"""\.innerHTML\s*=\s*(?:'[^'`$+]*'|"[^"`$+]*")\s*;\s*$""")

HARD_WORDS = '<style>body{display:none}</style><img src=x onerror="alert(1)">use a <div> here'

# A page that only writes down what is done to it.
STAND_IN_PAGE = r"""
const builtAsPageCode = [];
function element(tag) {
  const el = { tag: tag, className: '', children: [], text: null, scrollTop: 0, scrollHeight: 999 };
  Object.defineProperty(el, 'innerHTML', { set(v) { builtAsPageCode.push(String(v)); } });
  Object.defineProperty(el, 'textContent', { set(v) { el.text = String(v); el.children = []; } });
  Object.defineProperty(el, 'firstChild', { get() { return el.children[0]; } });
  el.appendChild = (child) => { el.children.push(child); return child; };
  el.removeChild = (child) => { el.children.splice(el.children.indexOf(child), 1); return child; };
  return el;
}
const log = element('div');
const document = {
  getElementById: (id) => (id === 'message-log' ? log : null),
  createElement: (tag) => element(tag),
  createTextNode: (text) => ({ tag: '#text', text: String(text) }),
};
"""


class _InlineScripts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text, self._inside = "", False

    def handle_starttag(self, tag, attrs):
        self._inside = tag == "script" and not dict(attrs).get("src")

    def handle_endtag(self, tag):
        if tag == "script":
            self._inside = False

    def handle_data(self, data):
        if self._inside:
            self.text += data


def _board_script() -> str:
    parser = _InlineScripts()
    parser.feed(BOARD)
    return parser.text


def _add_log() -> str:
    """The board's addLog function, as text."""
    lines = _board_script().splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("  function addLog(")]
    if len(starts) != 1:
        raise AssertionError(f"wanted one addLog on the board, found {len(starts)}")
    end = next(i for i in range(starts[0], len(lines)) if lines[i] == "  }")
    return "\n".join(lines[starts[0]:end + 1])


def _run_on_the_stand_in_page(calls: str) -> dict:
    """Run the board's addLog in node against the stand-in page; say what it did."""
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is not on this Mac; the rule test in this file still holds the line")
    script = STAND_IN_PAGE + _add_log() + "\n" + calls + "\nconsole.log(JSON.stringify({ builtAsPageCode, log }));"
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    if done.returncode != 0:
        raise AssertionError(f"node could not run the board's addLog:\n{done.stderr[-600:]}")
    return json.loads(done.stdout)


class TheLogShowsWordsAsWords(unittest.TestCase):

    def test_a_message_is_never_built_into_page_code(self):
        result = _run_on_the_stand_in_page(
            f"addLog('Brockston · Sovereign Stack', {json.dumps(HARD_WORDS)}, 'brockston');"
        )
        self.assertEqual(result["builtAsPageCode"], [])

    def test_the_line_shows_who_and_the_words_as_they_were_said(self):
        result = _run_on_the_stand_in_page(
            f"addLog('Brockston · Sovereign Stack', {json.dumps(HARD_WORDS)}, 'brockston');"
        )
        (line,) = result["log"]["children"]
        self.assertEqual(line["className"], "log-entry brockston")
        self.assertEqual(
            [(part["tag"], part.get("className", ""), part["text"]) for part in line["children"]],
            [("div", "log-who", "Brockston · Sovereign Stack"), ("#text", "", HARD_WORDS)],
        )

    def test_the_log_still_keeps_its_last_eighty_lines(self):
        # Kept as it was.
        result = _run_on_the_stand_in_page("for (let i = 0; i < 85; i++) addLog('Everett', 'line ' + i, 'everett');")
        self.assertEqual(len(result["log"]["children"]), 80)
        self.assertEqual(result["log"]["scrollTop"], 999)

    def test_nothing_on_the_board_joins_words_into_page_code(self):
        joined = [
            line.strip()
            for line in _board_script().splitlines()
            if AS_PAGE_CODE.search(line) and not A_FIXED_STRING.search(line)
        ]
        self.assertEqual(joined, [])


if __name__ == "__main__":
    unittest.main()
