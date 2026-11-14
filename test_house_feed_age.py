"""
A tone ear that stopped must not read as a tone ear that is working.

WHY: 2026-11-13. The house's rack goes on giving the last value a page posted
after the page stops posting. At 12:48 the bridge said the tone ear was
listening while the rack's value was 34 minutes old, and the board counts a
listening tone ear as a mic. The eye already came with an age and a freshness
rule from the house. The tone ear had neither.

These tests run the house-feed block of main.py itself, cut out of the file.
Importing main.py would take the single-instance lock and start the bridge.
"""
import asyncio
import copy
import json
import logging
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
MAIN = (HERE / "main.py").read_text()
HTML = (HERE / "dashboard.html").read_text()

BLOCK_START = "# THEWHOLEHOUSE is the supplier."
BLOCK_END = "riley_inbox: list[dict] = []"

NOW_MS = 1_800_000_000_000

# What the house answers on /api/corti/live when no page has posted yet.
NEVER_POSTED = {
    "ok": True, "organ": "corti", "family": "christman-sound", "measured": False,
    "listening": False, "rms": 0, "zcr": 0, "f0": None, "locked": False,
}

NOTHING_CLAIMED = {"listening": False, "measured": False, "f0": None, "locked": False, "age_ms": None}


class Clock:
    """Stands in for datetime inside the block. The test says what time it is."""

    def __init__(self) -> None:
        self.ms = NOW_MS

    def now(self) -> "Clock":
        return self

    def timestamp(self) -> float:
        return self.ms / 1000.0


class _Stop(Exception):
    """Ends the feed loop after the passes a test asked for."""


def house_feed_block(clock: Clock) -> dict:
    """The house-feed block of main.py, run in a namespace of its own."""
    if MAIN.count(BLOCK_START) != 1 or MAIN.count(BLOCK_END) != 1:
        raise AssertionError("the house-feed block of main.py is not where this test expects it")
    block = MAIN[MAIN.index(BLOCK_START):MAIN.index(BLOCK_END)]
    ns: dict = {
        "HOUSE_URL": "http://127.0.0.1:9",  # nothing listens there, and no test lets the block reach it
        "Optional": Optional,
        "asyncio": asyncio,
        "datetime": clock,
        "json": json,
        "urllib": urllib,
        "logger": logging.getLogger("test-house-feed"),
        "latest_transcript": {"text": "", "timestamp": 0},
        "recent_transcripts": [],
        "latest_frame": {"b64": "", "timestamp": 0, "width": 0, "height": 0, "source": "none"},
    }
    exec(compile(block, "main.py[house feed]", "exec"), ns)
    return ns


def rack_says(clock: Clock, age_ms: int, **over) -> dict:
    """What the house answers on /api/corti/live for a value a page posted `age_ms` ago."""
    said = {
        "ok": True, "measured": True, "organ": "corti", "t": clock.ms - age_ms,
        "listening": True, "rms": 0.31, "zcr": 0.22, "f0": None, "locked": False,
    }
    said.update(over)
    return said


class ToneEarAge(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        self.feed = house_feed_block(self.clock)
        self.apply = self.feed["_apply_house_corti"]

    def corti(self) -> dict:
        return self.feed["house_feed"]["corti"]

    def test_nothing_is_claimed_before_the_first_answer(self):
        self.assertEqual(self.corti(), NOTHING_CLAIMED)

    def test_a_fresh_tone_ear_is_listening_and_carries_its_age(self):
        self.apply(rack_says(self.clock, 300))
        self.assertTrue(self.corti()["listening"])
        self.assertEqual(self.corti().get("age_ms"), 300)

    def test_a_tone_ear_that_stopped_is_not_listening(self):
        self.apply(rack_says(self.clock, 34 * 60 * 1000))
        self.assertFalse(self.corti()["listening"])
        self.assertEqual(self.corti().get("age_ms"), 34 * 60 * 1000)

    def test_a_stopped_tone_ear_gives_no_pitch(self):
        self.apply(rack_says(self.clock, 60_000, f0=220.0, locked=True))
        self.assertIsNone(self.corti()["f0"])
        self.assertFalse(self.corti()["locked"])

    def test_a_fresh_pitch_comes_through(self):
        self.apply(rack_says(self.clock, 300, f0=220.5, locked=True))
        self.assertEqual(self.corti()["f0"], 220.5)
        self.assertTrue(self.corti()["locked"])

    def test_the_window_is_the_one_the_house_gives_the_eye(self):
        # LUCENT_FRESH_MS in THEWHOLEHOUSE, src/lib/house/live-rack.ts: fresh means younger than 2500 ms.
        self.apply(rack_says(self.clock, 2499))
        self.assertTrue(self.corti()["listening"], "2499 ms old is still fresh")
        self.apply(rack_says(self.clock, 2500))
        self.assertFalse(self.corti()["listening"], "2500 ms old is not")

    def test_a_rack_nothing_was_posted_to_has_no_age(self):
        self.apply(dict(NEVER_POSTED))
        self.assertEqual(self.corti(), NOTHING_CLAIMED)

    def test_a_value_with_no_usable_timestamp_is_not_trusted(self):
        for t in (None, 0, -5, "soon", float("nan"), float("inf"), [], {}):
            with self.subTest(t=t):
                said = rack_says(self.clock, 0, f0=220.0, locked=True)
                said["t"] = t
                self.apply(said)
                self.assertFalse(self.corti()["listening"])
                self.assertIsNone(self.corti()["f0"])
                self.assertFalse(self.corti()["locked"])
                self.assertIsNone(self.corti().get("age_ms", "no age at all"))


class ToneEarAgeInTheFeedLoop(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        self.feed = house_feed_block(self.clock)
        self.house_up = True
        self.corti_says = dict(NEVER_POSTED)
        self.feed["_house_get"] = self.house_get

    def house_get(self, path: str) -> dict:
        if not self.house_up:
            raise urllib.error.URLError("connection refused")
        if path == "/api/corti/live":
            return dict(self.corti_says)
        if path == "/api/porch/live":
            return {"ok": True, "organ": "porch", "measured": False, "listening": False, "take": None}
        if path == "/api/lucent/live":
            return {"ok": True, "organ": "lucent", "measured": False, "seeing": False,
                    "b64": "", "width": 0, "height": 0, "kind": None}
        raise AssertionError(f"the feed loop asked the house for {path}")

    def run_passes(self, *before_each_pass) -> list:
        """One pass of the real loop per step. Returns the house feed as each pass left it."""
        left: list = []
        steps = list(before_each_pass)

        async def sleep(_seconds: float) -> None:
            if self._passes_started > 0:  # the pass before this one has finished
                left.append(copy.deepcopy(self.feed["house_feed"]))
            if self._passes_started == len(steps):
                raise _Stop()
            steps[self._passes_started]()
            self._passes_started += 1

        self._passes_started = 0
        self.feed["asyncio"] = types.SimpleNamespace(
            sleep=sleep, gather=asyncio.gather, to_thread=asyncio.to_thread,
        )
        with self.assertRaises(_Stop):
            asyncio.run(self.feed["_house_feed_loop"]())
        self.assertEqual(len(left), len(steps))
        return left

    def test_a_page_that_stops_posting_ages_out_while_the_house_is_up(self):
        def page_is_hearing():
            self.corti_says = rack_says(self.clock, 200)

        def page_stops_and_time_passes():
            self.clock.ms += 5000  # the rack goes on giving the same value

        first, second = self.run_passes(page_is_hearing, page_stops_and_time_passes)
        self.assertTrue(first["corti"]["listening"])
        self.assertEqual(first["corti"].get("age_ms"), 200)
        self.assertTrue(second["reachable"])
        self.assertFalse(second["corti"]["listening"], "the page stopped and the tone ear still reads as listening")
        self.assertEqual(second["corti"].get("age_ms"), 5200)

    def test_the_age_keeps_counting_when_the_house_stops_answering(self):
        def page_is_hearing():
            self.corti_says = rack_says(self.clock, 200, f0=220.0, locked=True)

        def house_goes_down():
            self.house_up = False
            self.clock.ms += 3000

        first, second = self.run_passes(page_is_hearing, house_goes_down)
        self.assertTrue(first["corti"]["listening"])
        self.assertFalse(second["reachable"])
        self.assertFalse(second["corti"]["listening"], "the house is down and the tone ear still reads as listening")
        self.assertEqual(second["corti"].get("age_ms"), 3200)
        self.assertIsNone(second["corti"]["f0"])
        self.assertFalse(second["corti"]["locked"])

    def test_one_missed_answer_does_not_put_the_lamp_out(self):
        def page_is_hearing():
            self.corti_says = rack_says(self.clock, 200)

        def one_answer_is_lost():
            self.house_up = False
            self.clock.ms += 400

        _, second = self.run_passes(page_is_hearing, one_answer_is_lost)
        self.assertTrue(second["corti"]["listening"])
        self.assertEqual(second["corti"].get("age_ms"), 600)

    def test_the_tone_ear_comes_back_when_the_page_posts_again(self):
        def page_is_hearing():
            self.corti_says = rack_says(self.clock, 200)

        def page_stops():
            self.clock.ms += 60_000

        def page_posts_again():
            self.clock.ms += 1000
            self.corti_says = rack_says(self.clock, 150, f0=196.0, locked=True)

        _, stopped, back = self.run_passes(page_is_hearing, page_stops, page_posts_again)
        self.assertFalse(stopped["corti"]["listening"])
        self.assertTrue(back["corti"]["listening"])
        self.assertEqual(back["corti"].get("age_ms"), 150)
        self.assertEqual(back["corti"]["f0"], 196.0)


class WhatTheLampLeansOn(unittest.TestCase):
    """The age only helps if /health carries the house feed and the board's mic lamp reads it."""

    def test_health_carries_the_house_feed(self):
        health = MAIN.split('@app.get("/health")')[1].split("@app.")[0]
        self.assertIn('"house": house_feed,', health)

    def test_the_mic_lamp_follows_the_tone_ear_the_bridge_reports(self):
        self.assertIn("const cortiLive = !!(house.corti && house.corti.listening);", HTML)


if __name__ == "__main__":
    unittest.main()
