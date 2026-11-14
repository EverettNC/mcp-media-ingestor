"""
The table is the family Everett named, and the code says what he says.

WHY: 2026-11-14. A session listed the chairs at the table from the routes in
main.py. That put Grok in his family. His words that day: "There is no Grok
anywhere." Then: "it needs to be what the code says too. Grok doesn't belong
anywhere in that code." And of the Learner chair: "go ahead and take that
learner one out, too."

So the bridge has no Grok chair and no Learner chair. The board has no card,
lamp, option or poll for either. Nothing still writes to an inbox that is gone.
The cards on the board are Everett's own and the five he named: Duey,
Brockston, Derek, Opus and Fable.

Asked the same day whether Grok should also come out of the README and the code
index, he said: "Yes, take it out".

The route functions are run here cut out of main.py. Importing main.py would
take the single-instance lock and start the bridge.
"""
import ast
import asyncio
import builtins
import logging
import os
import re
import textwrap
import types
import unittest
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = (HERE / "main.py").read_text()
HTML = (HERE / "dashboard.html").read_text()
VEGA_CORE = (HERE / "vega" / "CORE.py").read_text()

GROK = re.compile(r"(?<!n)grok", re.IGNORECASE)  # "ngrok" is a tunnel, not Grok
LEARNER = re.compile(r"learner", re.IGNORECASE)

ROUTES = set(re.findall(r'@app\.(?:get|post|put|delete|websocket)\("([^"]+)"', MAIN))

# The cards on the board, by id, in the order they sit: Everett, then the five.
CARDS = ["everett-card", "duey-card", "brockston-card", "claude-card", "opus5-card-top", "fable5-card"]
# What the send box offers, by the value the bridge is sent.
SEND_BOX = ["everett", "duey", "brockston", "derek", "opus5", "fable5"]

SKIP_DIRS = {".venv", "venv", "python@3.12", "node_modules", ".git", "__pycache__"}
CODE_ENDINGS = (".py", ".html", ".js", ".sh")


def _lines_with(pattern: re.Pattern, text: str) -> list:
    return [f"{n}: {line.strip()[:90]}" for n, line in enumerate(text.splitlines(), 1) if pattern.search(line)]


def _cut(source: str, *names: str) -> str:
    """The named top-level functions and values of a file, as text, in file order."""
    lines = source.splitlines()
    found, parts = [], []
    for node in ast.parse(source).body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        if name in names:
            first = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
            parts.append("\n".join(lines[first - 1:node.end_lineno]))
            found.append(name)
    if sorted(found) != sorted(names):
        raise AssertionError(f"wanted {sorted(names)} once each in the file, found {sorted(found)}")
    return "\n\n".join(parts) + "\n"


def _names_reached_for(code: types.CodeType) -> set:
    names = set(code.co_names)
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            names |= _names_reached_for(const)
    return names


class _App:
    """Stands in for FastAPI. A route decorator hands the function back unchanged."""

    def _route(self, *args, **kwargs):
        return lambda fn: fn

    get = post = put = delete = websocket = _route


class _Taker:
    """Stands in for a chair's mail slot. It takes what it is given and keeps it."""

    def __init__(self) -> None:
        self.got: list = []

    async def __call__(self, entry, *args, **kwargs) -> bool:
        self.got.append(entry)
        return True


class _Yes:
    """What a _Stray hands back when it is called: true, and true when awaited."""

    def __await__(self):
        if False:
            yield
        return True


class _Stray:
    """Stands in for any outside name the cut code reaches for that the test did
    not hand it. It lets itself be called or appended to, and it remembers."""

    def __init__(self, name: str, touched: list) -> None:
        self._name, self._touched = name, touched

    def append(self, item) -> None:
        self._touched.append(self._name)

    def __call__(self, *args, **kwargs) -> _Yes:
        self._touched.append(self._name)
        return _Yes()


def _run_cut(names: tuple, given: dict) -> tuple:
    """Run the named parts of main.py in a room of their own.

    `given` is what the test hands them. Every other outside name they reach for
    gets a _Stray. The list that comes back names the strays that were touched,
    so a test can say that nothing reached past what it was handed.
    """
    touched: list = []
    room = {
        "__name__": "cut_from_the_bridge",
        "app": _App(),
        "datetime": datetime,
        "logger": logging.getLogger("cut_from_the_bridge"),
    }
    room.update(given)
    code = compile(_cut(MAIN, *names), "<cut from main.py>", "exec")
    for name in _names_reached_for(code):
        if name not in room and not hasattr(builtins, name):
            room[name] = _Stray(name, touched)
    exec(code, room)
    return room, touched


def _go(coro):
    return asyncio.run(coro)


class NoGrokAndNoLearnerChair(unittest.TestCase):

    def test_grok_is_nowhere_in_the_bridge_file(self):
        self.assertEqual(_lines_with(GROK, MAIN), [])

    def test_grok_is_nowhere_on_the_board(self):
        self.assertEqual(_lines_with(GROK, HTML), [])

    def test_grok_is_in_no_code_file_in_this_folder(self):
        me = Path(__file__).resolve()
        found = []
        for folder, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                path = Path(folder) / name
                if not name.endswith(CODE_ENDINGS) or path == me:
                    continue
                try:
                    text = path.read_text()
                except (UnicodeDecodeError, OSError):
                    continue
                found += [f"{path.relative_to(HERE)}:{line}" for line in _lines_with(GROK, text)]
        self.assertEqual(found, [])

    def test_grok_is_not_in_the_readme_or_the_code_index(self):
        found = []
        for name in ("README.md", "CODE_INDEX.md"):
            path = HERE / name
            if path.exists():
                found += [f"{name}:{line}" for line in _lines_with(GROK, path.read_text())]
        self.assertEqual(found, [])

    def test_the_learner_chair_is_out_of_the_bridge_file(self):
        self.assertEqual(_lines_with(LEARNER, MAIN), [])

    def test_the_learner_card_is_off_the_board(self):
        self.assertEqual(_lines_with(LEARNER, HTML), [])

    def test_the_learner_page_is_gone(self):
        self.assertFalse((HERE / "learner.html").exists())

    def test_the_bridge_has_no_address_for_either(self):
        still_there = sorted(r for r in ROUTES if re.match(r"/(ws/)?(grok|learner)", r))
        self.assertEqual(still_there, [])


class TheBoardIsTheFamily(unittest.TestCase):

    def test_the_cards_are_everett_and_the_five_he_named(self):
        self.assertEqual(re.findall(r'class="agent-card" id="([^"]+)"', HTML), CARDS)

    def test_the_send_box_offers_the_same_six(self):
        box = HTML.split('<select id="chest-who">')[1].split("</select>")[0]
        self.assertEqual(re.findall(r'<option value="([^"]+)"', box), SEND_BOX)

    def test_the_grid_has_a_column_for_each_card_and_the_center(self):
        # A card taken out without its column leaves an empty column on the board.
        tracks = re.search(r"\.grid \{[^}]*?grid-template-columns:([^;]+);", HTML).group(1).split()
        self.assertEqual(len(tracks), len(CARDS) + 1)


class WordsStillReachTheFamily(unittest.TestCase):
    """The Grok and Learner branches sat between the family's own. These run the
    send route itself, so a cut that took a neighbour with it shows here."""

    def setUp(self):
        self.duey, self.opus5, self.fable5, self.brockston = _Taker(), _Taker(), _Taker(), _Taker()
        self.room, self.touched = _run_cut(("channel_send",), {
            "latest_transcript": {"text": "", "timestamp": 0},
            "riley_inbox": [],
            "claude_outbox": [],
            "push_to_duey": self.duey,
            "push_to_opus5": self.opus5,
            "push_to_fable5": self.fable5,
            "_queue_brockston": self.brockston,
        })
        self.send = self.room["channel_send"]

    def test_the_send_box_reaches_every_chair_it_offers(self):
        for who in SEND_BOX:
            out = _go(self.send({"who": who, "text": f"hello {who}"}))
            self.assertNotEqual(out.get("status"), "error", f"{who}: {out}")
        self.assertEqual(self.room["latest_transcript"]["text"], "hello everett")
        self.assertEqual(self.duey.got[-1]["text"], "hello duey")
        self.assertEqual(self.brockston.got[-1]["text"], "hello brockston")
        self.assertEqual(self.room["claude_outbox"][-1]["text"], "hello derek")
        self.assertEqual(self.opus5.got[-1]["text"], "hello opus5")
        self.assertEqual(self.fable5.got[-1]["text"], "hello fable5")
        self.assertEqual(self.touched, [])

    def test_the_send_route_knows_no_grok_and_no_learner(self):
        for who in ("grok", "learner"):
            out = _go(self.send({"who": who, "text": "hello"}))
            self.assertEqual(out, {"status": "error", "message": f"unknown who: {who}"})
        self.assertEqual(self.touched, [])


class TheIdeDeskStillWorks(unittest.TestCase):

    def test_a_prompt_put_on_fables_desk_shows_as_the_ide_comment(self):
        # The line that lets api_chat write the IDE comment sat inside the Grok
        # branch. Cut with the branch, Fable's desk would still take the prompt
        # and the board would never show it, with no error anywhere.
        fable5 = _Taker()
        room, touched = _run_cut(("ide_comment", "ide_comment_post", "ide_latest", "api_chat"), {
            "fable5_ws_clients": {object()},
            "push_to_fable5": fable5,
            "_IDE_DEFAULT_LANE": "test-lane",
            "active_connections": {},
        })
        out = _go(room["api_chat"]({"message": "put this on the desk", "instance": "fable5"}))
        self.assertTrue(out["ok"])
        self.assertEqual(fable5.got[-1]["text"], "put this on the desk")
        self.assertEqual(_go(room["ide_latest"]())["text"], "put this on the desk")
        self.assertEqual(touched, [])

    def test_the_ide_broadcast_writes_to_no_learner_inbox(self):
        brockston = _Taker()
        room, touched = _run_cut(("ide_send",), {
            "riley_inbox": [],
            "claude_outbox": [],
            "carbon_outbox": [],
            "_queue_brockston": brockston,
        })
        out = _go(room["ide_send"]({"text": "hello room", "lang": "python", "instance": "all"}))
        self.assertNotIn("learner", out["recipients"])
        self.assertEqual(touched, [])
        # The ones it wrote to before the cut still get it.
        self.assertEqual([len(room[q]) for q in ("riley_inbox", "claude_outbox", "carbon_outbox")], [1, 1, 1])
        self.assertEqual(len(brockston.got), 1)


class VegaWritesToNoLearnerInbox(unittest.TestCase):
    """Vega's broadcast is run here cut out of vega/CORE.py. Importing Vega pulls
    in her video and image makers."""

    def _broadcast(self):
        cls = next(n for n in ast.parse(VEGA_CORE).body if isinstance(n, ast.ClassDef) and n.name == "VegaCore")
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "broadcast_to_bridge")
        text = textwrap.dedent("\n".join(VEGA_CORE.splitlines()[fn.lineno - 1:fn.end_lineno]))
        clock = types.SimpleNamespace(utcnow=lambda: datetime(2026, 11, 14, 13, 0, 0))
        room = {"datetime": clock, "logger": logging.getLogger("cut_from_vega")}
        exec(compile(text, "<cut from vega/CORE.py>", "exec"), room)
        return room["broadcast_to_bridge"]

    def test_vega_leaves_a_learner_inbox_alone(self):
        queues = {"riley_inbox": [], "claude_outbox": [], "everest_outbox": [], "learner_inbox": []}
        out = self._broadcast()(types.SimpleNamespace(bridge_queues=queues), "hello from Vega", "test")
        self.assertEqual(queues["learner_inbox"], [])
        self.assertEqual(out["recipients"], ["riley", "claude", "everest"])

    def test_vega_core_names_no_learner(self):
        self.assertEqual(_lines_with(LEARNER, VEGA_CORE), [])


if __name__ == "__main__":
    unittest.main()
