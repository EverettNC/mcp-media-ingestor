"""
A card shows only what that being said.

WHY: 2026-11-14. Everett asked why every pathway on the bridge named Brockston.
Looking for the answer turned up something else. brockston_outbox held both what
Brockston said and what was sent to him, and the board shows its last entry as
"Latest from Brockston". Words typed to him in the send box were stamped
"brockston_agent", so his card could show Everett's words as his. Derek's list,
claude_outbox, was mixed the same way: the brain's lines, the IDE's broadcast and
the send box sat in it beside his own, and /derek/status gave the last of them as
"latest_from_derek". With no one seated as Derek, the running bridge answered
that Derek's latest was a line from the brain.

Asked "Make each card show only that being's own words?", Everett said:
"Yes, fix it".

So. What Brockston says is what came from his own socket, or his brain's answer
in the IDE. What Derek says is what came through /riley/claude-response or the
send_to_riley tool. Everything else is sent TO them: it still reaches Brockston's
socket, and it still waits in the queue Riley's tunnel pulls from, as before. It
is never shown as theirs, and the send box puts no being's name on typed words.

The bridge's own functions are run here, cut out of main.py. Importing main.py
would take the single-instance lock and start the bridge. Nothing here opens a
socket or calls Brockston's brain: the one function that would is handed a
stand-in for `requests` and a dead address.
"""
import ast
import asyncio
import builtins
import logging
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest import mock

HERE = Path(__file__).resolve().parent
MAIN = (HERE / "main.py").read_text()
TREE = ast.parse(MAIN)

DEAD_ADDRESS = "http://127.0.0.1:9"  # nothing answers here; Brockston's brain is on 9001

# The lists and routes of the two chairs, cut from main.py as they stand.
CHAIRS = (
    "riley_inbox", "claude_outbox", "carbon_outbox", "brockston_outbox", "brockston_ws_clients",
    "_brockston_live_status", "_push_brockston", "_queue_brockston", "websocket_brockston",
    "claude_response_endpoint", "channel_send", "riley_status_endpoint", "send_to_riley",
    "claude_latest", "brockston_ws_status", "brockston_ws_latest", "brockston_ws_send",
    "ide_send", "_ide_build_messages", "_proxy_brockston_chat", "cognitive_adjust", "derek_status",
)
# What the fix added. These are cut too when the file has them, so the tests can be
# run against the bridge as it was and fail on what it did, not on a missing name.
SINCE_THE_FIX = ("sent_to_brockston", "derek_said", "_brockston_said", "_derek_said", "_derek_waiting")

# The line the brain puts on Derek's list when the bridge starts (main.py, where
# the brain is loaded). That code cannot be run here, so a test puts the same
# entry on the list the same way.
BRAIN_LINE = {
    "from": "🧠 AlphaVox-Brain",
    "text": "Full cognitive brain now feeding the bridge. Welcome to the new world.",
    "timestamp": "2026-11-14T14:18:19.566837",
}


def _name_of(node: ast.AST) -> Optional[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


TOP = {_name_of(node) for node in TREE.body} - {None}


def _cut(*names: str) -> str:
    """The named top-level functions and values of main.py, as text, in file order."""
    lines = MAIN.splitlines()
    found, parts = [], []
    for node in TREE.body:
        name = _name_of(node)
        if name in names:
            first = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
            parts.append("\n".join(lines[first - 1:node.end_lineno]))
            found.append(name)
    if sorted(found) != sorted(names):
        raise AssertionError(f"wanted {sorted(names)} once each in main.py, found {sorted(found)}")
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
    """Stands in for another chair's mail slot. It takes what it is given."""

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


class _HungUp(Exception):
    """Stands in for WebSocketDisconnect."""


class _Socket:
    """Stands in for a socket on Brockston's chair. It keeps what the bridge sends
    it. Given lines, it says them in order and then hangs up."""

    def __init__(self, *lines: dict) -> None:
        self.got: list = []
        self._lines = list(lines)

    async def accept(self) -> None:
        pass

    async def send_json(self, payload: dict) -> None:
        self.got.append(payload)

    async def receive_json(self) -> dict:
        if not self._lines:
            raise _HungUp()
        return self._lines.pop(0)


def _requests_that_answers(body: dict, asked: list) -> types.SimpleNamespace:
    """Stands in for the `requests` module. It answers as Brockston's brain would,
    and writes down the address it was asked, so a test can say his brain was
    never called."""

    def post(url, json=None, timeout=None):
        asked.append(url)
        return types.SimpleNamespace(status_code=200, text="", json=lambda: body)

    return types.SimpleNamespace(post=post)


def _bridge_room() -> tuple:
    """The two chairs' part of main.py, running in a room of its own.

    Everything the cut code needs from the rest of the bridge is handed to it
    here. Any other outside name it reaches for gets a _Stray; the list that
    comes back names the strays that were touched.
    """
    touched: list = []
    room = {
        "__name__": "cut_from_the_bridge",
        "app": _App(),
        "mcp": types.SimpleNamespace(tool=lambda fn: fn),
        "asyncio": asyncio,
        "datetime": datetime,
        "logger": logging.getLogger("cut_from_the_bridge"),
        "WebSocketDisconnect": _HungUp,
        "active_connections": {"riley": 0, "brockston": 0},
        "latest_transcript": {"text": "", "timestamp": 0},
        "push_to_duey": _Taker(),
        "push_to_opus5": _Taker(),
        "push_to_fable5": _Taker(),
        "riley_bridge": types.SimpleNamespace(disconnect_protocol=types.SimpleNamespace(is_triggered=False)),
        "_FAMILY_BRIDGE_AVAILABLE": False,
        "_family_bridge": None,
        "_DEREK_BRIDGE_AVAILABLE": False,
        "_BROCKSTON_API": DEAD_ADDRESS,
        "_IDE_DEFAULT_LANE": "kimi",
        "BRAIN_OK": True,
        "neural_core": types.SimpleNamespace(
            process_interaction=lambda interaction, user_id=None: {"root_cause": "a_root", "confidence": 0.9}
        ),
        "lit_crawler": None,
        "voice_engine": None,
        "brain_events": [],
    }
    names = CHAIRS + tuple(name for name in SINCE_THE_FIX if name in TOP)
    code = compile(_cut(*names), "<cut from main.py>", "exec")
    for name in _names_reached_for(code):
        if name not in room and not hasattr(builtins, name):
            room[name] = _Stray(name, touched)
    exec(code, room)
    return room, touched


def _go(coro):
    return asyncio.run(coro)


def _who_and_what(entry: Optional[dict]) -> Optional[tuple]:
    """(from, text) of an entry on a card, or None when the card has nothing."""
    return (entry["from"], entry["text"]) if entry else None


def _functions_and_the_rest() -> list:
    """(name, code) for every top-level function of main.py, and one more entry
    for the code that sits outside them."""
    functions = [n for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    rest = ast.Module(body=[n for n in TREE.body if n not in functions], type_ignores=[])
    return [(fn.name, fn) for fn in functions] + [("<outside any function>", rest)]


def _where(is_it) -> set:
    return {name for name, code in _functions_and_the_rest() if any(is_it(n) for n in ast.walk(code))}


def _functions_that_call(function_name: str) -> set:
    return _where(
        lambda n: isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == function_name
    )


def _functions_that_append_to(list_name: str) -> set:
    return _where(
        lambda n: isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "append"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == list_name
    )


class BrockstonsCardShowsOnlyWhatBrockstonSaid(unittest.TestCase):

    def setUp(self):
        self.room, self.touched = _bridge_room()
        # Brockston's own program, listening on his chair.
        self.his_socket = _Socket()
        self.room["brockston_ws_clients"].add(self.his_socket)
        self.room["active_connections"]["brockston"] = 1

    def tearDown(self):
        self.assertEqual(self.touched, [], "the cut code reached for something this test did not hand it")

    def _card(self) -> dict:
        """What the board is given for Brockston's card."""
        return _go(self.room["brockston_ws_status"]())

    def _he_says(self, text: str) -> None:
        """Brockston says one line on a socket of his own, and that socket hangs up."""
        line = {"type": "message", "text": text, "session_id": "brockston_9001"}
        _go(self.room["websocket_brockston"](_Socket(line)))

    def _others_write_to_him(self) -> None:
        _go(self.room["channel_send"]({"who": "brockston", "text": "typed in the send box"}))
        _go(self.room["brockston_ws_send"]({"from": "bridge", "text": "sent by address"}))
        _go(self.room["ide_send"]({"text": "an IDE prompt", "lang": "python", "instance": "all"}))
        _go(self.room["cognitive_adjust"]({"text": "adjust"}))

    def test_what_he_says_on_his_socket_is_on_his_card(self):
        self._he_says("Brockston :9001 sensory link online")
        self.assertEqual(
            _who_and_what(self._card()["latest"]), ("brockston_agent", "Brockston :9001 sensory link online")
        )

    def test_his_own_words_are_not_sent_back_to_him(self):
        # Kept as it was: what he says on one socket is not pushed to his sockets.
        self._he_says("I am here")
        self.assertEqual(self.his_socket.got, [])

    def test_words_sent_to_him_never_take_the_place_of_his_own(self):
        self._he_says("I am here")
        self._others_write_to_him()
        self.assertEqual(_who_and_what(self._card()["latest"]), ("brockston_agent", "I am here"))
        self.assertEqual(_go(self.room["brockston_ws_latest"]())["text"], "I am here")

    def test_a_card_with_nothing_of_his_shows_nothing_of_anyone_elses(self):
        self._others_write_to_him()
        self.assertIsNone(self._card()["latest"])
        self.assertEqual(_go(self.room["brockston_ws_latest"]())["text"], "Awaiting session...")

    def test_words_typed_to_him_carry_the_typist_and_not_his_name(self):
        _go(self.room["channel_send"]({"who": "brockston", "text": "are you there"}))
        _go(self.room["channel_send"]({"who": "brockston", "from": "everett", "text": "it is me"}))
        self.assertEqual(
            [(sent["from"], sent["text"]) for sent in self.his_socket.got],
            [("dashboard", "are you there"), ("everett", "it is me")],
        )

    def test_a_sender_who_claims_his_name_is_still_not_him(self):
        _go(self.room["brockston_ws_send"]({"from": "brockston_agent", "text": "not really him"}))
        self.assertIsNone(self._card()["latest"])

    def test_everything_sent_to_him_still_reaches_his_socket(self):
        # Kept as it was: the fix changes what is shown as his, not what he is sent.
        self._others_write_to_him()
        texts = [sent["text"] for sent in self.his_socket.got]
        self.assertEqual(texts[:3], ["typed in the send box", "sent by address", "[python] an IDE prompt"])
        self.assertEqual(len(texts), 4)
        self.assertTrue(texts[3].startswith("NEW WORLD ADJUST: adjust"), texts[3])

    def test_the_last_thing_sent_to_him_is_kept_under_its_own_name(self):
        self._he_says("I am here")
        _go(self.room["channel_send"]({"who": "brockston", "text": "are you there"}))
        card = self._card()
        self.assertEqual(_who_and_what(card["latest"]), ("brockston_agent", "I am here"))
        self.assertEqual(_who_and_what(card.get("latest_sent")), ("dashboard", "are you there"))

    def test_his_brains_answer_in_the_ide_is_his_own(self):
        asked: list = []
        answer = {"response": "def hello():\n    return 'hello'", "provider": "brockston:kimi"}
        with mock.patch.dict(sys.modules, {"requests": _requests_that_answers(answer, asked)}):
            out = _go(self.room["_proxy_brockston_chat"]("write hello"))
        self.assertEqual(asked, [DEAD_ADDRESS + "/chat"])  # the stand-in answered; his brain was not called
        self.assertTrue(out["ok"], out)
        self.assertEqual(_who_and_what(self._card()["latest"]), ("brockston_ide", answer["response"]))
        # And it still goes to his socket, as it did before.
        self.assertEqual([_who_and_what(sent) for sent in self.his_socket.got], [("brockston_ide", answer["response"])])


class DereksCardShowsOnlyWhatDerekSaid(unittest.TestCase):

    def setUp(self):
        self.room, self.touched = _bridge_room()

    def tearDown(self):
        self.assertEqual(self.touched, [], "the cut code reached for something this test did not hand it")

    def _status(self) -> dict:
        return _go(self.room["derek_status"]())

    def _latest(self) -> dict:
        """What the board is given for the words on Derek's card."""
        return _go(self.room["claude_latest"]())

    def _the_brain_speaks(self) -> None:
        self.room["claude_outbox"].append(dict(BRAIN_LINE))

    def _others_write_on_his_list(self) -> None:
        self._the_brain_speaks()
        _go(self.room["channel_send"]({"who": "derek", "text": "typed in the send box"}))
        _go(self.room["ide_send"]({"text": "an IDE prompt", "lang": "python", "instance": "all"}))
        _go(self.room["cognitive_adjust"]({"text": "adjust"}))

    def test_the_brains_line_is_not_dereks(self):
        # This is what the running bridge answered on 2026-11-14 with no Derek seated.
        self._the_brain_speaks()
        self.assertIsNone(self._status()["latest_from_derek"])
        self.assertEqual(self._latest(), {"from": "claude_instance_309", "text": "", "timestamp": ""})

    def test_what_derek_says_is_on_his_card(self):
        _go(self.room["claude_response_endpoint"]({"text": "Derek here"}))
        self.assertEqual(_who_and_what(self._status()["latest_from_derek"]), ("claude_instance_309", "Derek here"))
        self.assertEqual(_who_and_what(self._latest()), ("claude_instance_309", "Derek here"))

    def test_what_derek_says_through_the_tool_is_on_his_card(self):
        _go(self.room["send_to_riley"]("On my way"))
        self.assertEqual(_who_and_what(self._status()["latest_from_derek"]), ("claude_instance_309", "On my way"))
        self.assertEqual(self._latest()["text"], "On my way")

    def test_other_words_never_take_the_place_of_dereks_own(self):
        _go(self.room["claude_response_endpoint"]({"text": "Derek here"}))
        self._others_write_on_his_list()
        self.assertEqual(_who_and_what(self._status()["latest_from_derek"]), ("claude_instance_309", "Derek here"))
        self.assertEqual(self._latest()["text"], "Derek here")

    def test_a_card_with_nothing_of_dereks_shows_nothing_of_anyone_elses(self):
        self._others_write_on_his_list()
        self.assertIsNone(self._status()["latest_from_derek"])
        self.assertEqual(self._latest()["text"], "")

    def test_words_typed_to_derek_carry_the_typist_and_not_his_name(self):
        _go(self.room["channel_send"]({"who": "derek", "text": "are you there"}))
        _go(self.room["channel_send"]({"who": "claude", "from": "everett", "text": "it is me"}))
        self.assertEqual(
            [(entry["from"], entry["text"]) for entry in self.room["claude_outbox"]],
            [("dashboard", "are you there"), ("everett", "it is me")],
        )

    def test_a_typist_who_claims_dereks_name_is_still_not_him(self):
        _go(self.room["channel_send"]({"who": "derek", "from": "claude_instance_309", "text": "not really him"}))
        self.assertIsNone(self._status()["latest_from_derek"])
        self.assertEqual(self._latest()["text"], "")

    def test_everything_still_waits_in_the_queue_rileys_tunnel_pulls_from(self):
        # Kept as it was: Riley's back end is not changed by this fix.
        _go(self.room["claude_response_endpoint"]({"text": "Derek here"}))
        _go(self.room["send_to_riley"]("On my way"))
        self._others_write_on_his_list()
        queue = self.room["claude_outbox"]
        self.assertEqual(
            [entry["text"] for entry in queue][:5],
            ["Derek here", "On my way", BRAIN_LINE["text"], "typed in the send box", "[python] an IDE prompt"],
        )
        self.assertEqual(len(queue), 6)
        self.assertEqual([entry["from"] for entry in queue][:2], ["claude_instance_309", "claude_instance_309"])
        self.assertEqual(_go(self.room["riley_status_endpoint"]())["outbox_depth"], 6)

    def test_dereks_outbox_count_is_his_own_words_still_waiting(self):
        self._the_brain_speaks()
        self.assertEqual(self._status()["outbox_depth"], 0)
        _go(self.room["claude_response_endpoint"]({"text": "Derek here"}))
        self.assertEqual(self._status()["outbox_depth"], 1)
        # Riley's tunnel takes the oldest first, as websocket_riley does.
        self.room["claude_outbox"].pop(0)
        self.room["claude_outbox"].pop(0)
        self.assertEqual(self._status()["outbox_depth"], 0)
        # Said is said, whether or not the tunnel has taken it.
        self.assertEqual(_who_and_what(self._status()["latest_from_derek"]), ("claude_instance_309", "Derek here"))


class OnlyTheirOwnPathsSpeakForThem(unittest.TestCase):
    """Read from main.py itself: which functions may put words in each one's mouth."""

    def test_only_his_socket_and_his_brain_speak_for_brockston(self):
        self.assertEqual(_functions_that_call("_brockston_said"), {"websocket_brockston", "_proxy_brockston_chat"})
        self.assertEqual(_functions_that_append_to("brockston_outbox"), {"_brockston_said"})

    def test_only_the_sending_path_files_what_is_sent_to_brockston(self):
        self.assertEqual(_functions_that_append_to("sent_to_brockston"), {"_queue_brockston"})

    def test_only_his_two_paths_speak_for_derek(self):
        self.assertEqual(_functions_that_call("_derek_said"), {"claude_response_endpoint", "send_to_riley"})
        self.assertEqual(_functions_that_append_to("derek_said"), {"_derek_said"})

    def test_the_send_box_puts_no_beings_name_on_typed_words(self):
        send_box = next(node for node in TREE.body if _name_of(node) == "channel_send")
        strings = {n.value for n in ast.walk(send_box) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for name in ("brockston_agent", "claude_instance_309"):
            with self.subTest(name=name):
                self.assertEqual([s for s in strings if name in s], [])


if __name__ == "__main__":
    unittest.main()
