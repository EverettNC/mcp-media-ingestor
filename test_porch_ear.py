"""Tests for porch_ear.py's voice gate. No mic, no network: the gate only.

Run: .venv/bin/python -m unittest test_porch_ear -v
"""

import unittest

import numpy as np

import porch_ear


def _drain():
    out = []
    while not porch_ear._clips.empty():
        out.append(porch_ear._clips.get_nowait())
    return out


def _feed(gate, signal):
    for i in range(0, len(signal) - porch_ear.FRAME + 1, porch_ear.FRAME):
        gate.feed(signal[i:i + porch_ear.FRAME])


def _room(seconds, level=30.0, seed=1):
    rng = np.random.default_rng(seed)
    return (rng.normal(0, level, int(seconds * porch_ear.SAMPLE_RATE))).astype(np.int16)


def _voice(seconds, level=3000.0):
    t = np.arange(int(seconds * porch_ear.SAMPLE_RATE)) / porch_ear.SAMPLE_RATE
    return (level * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).astype(np.int16)


def test_quiet_room_makes_no_take():
    _drain()
    g = porch_ear.Gate()
    _feed(g, _room(5))
    assert _drain() == []


def test_one_spoken_line_makes_one_take():
    _drain()
    g = porch_ear.Gate()
    _feed(g, np.concatenate([_room(2), _voice(1.5), _room(1.5)]))
    clips = _drain()
    assert len(clips) == 1
    pcm, voiced = clips[0]
    assert voiced >= 1.0
    # the breath before the first word and the quiet after are kept
    assert len(pcm) // 2 >= int(1.5 * porch_ear.SAMPLE_RATE)


def test_a_bump_is_not_speech():
    _drain()
    g = porch_ear.Gate()
    _feed(g, np.concatenate([_room(2), _voice(0.2), _room(1.5)]))
    assert _drain() == []


def test_long_talk_is_cut_into_takes():
    _drain()
    g = porch_ear.Gate()
    _feed(g, np.concatenate([_room(1), _voice(porch_ear.MAX_TAKE_S + 5), _room(1.5)]))
    assert len(_drain()) == 2


def test_two_lines_with_a_pause_are_two_takes():
    _drain()
    g = porch_ear.Gate()
    _feed(g, np.concatenate([_room(2), _voice(1.2), _room(1.5), _voice(1.2), _room(1.5)]))
    assert len(_drain()) == 2


class PorchEarGate(unittest.TestCase):
    def test_quiet_room_makes_no_take(self):
        test_quiet_room_makes_no_take()

    def test_one_spoken_line_makes_one_take(self):
        test_one_spoken_line_makes_one_take()

    def test_a_bump_is_not_speech(self):
        test_a_bump_is_not_speech()

    def test_long_talk_is_cut_into_takes(self):
        test_long_talk_is_cut_into_takes()

    def test_two_lines_with_a_pause_are_two_takes(self):
        test_two_lines_with_a_pause_are_two_takes()


if __name__ == "__main__":
    unittest.main()
