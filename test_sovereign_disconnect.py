"""
test_sovereign_disconnect.py — real runs of the 5-4-3-2-1 Sovereign Disconnect.

No mocks of the protocol. The countdown runs for real (about 2.5 seconds).
Cardinal Rules 1, 6, 8, 13.
"""

import logging
import os
import stat

from pedagogy.sovereign_disconnect import FiveValues, SovereignDisconnect
from RILEY import RileyBridge


def test_clean_protocol_reports_no_violation():
    sd = SovereignDisconnect()
    assert sd.check_for_violations() is False
    assert sd.is_triggered is False


def test_below_threshold_does_not_disconnect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sd = SovereignDisconnect()
    sd.report_violation(FiveValues.TRUTH, "asked to state something false")
    sd.report_violation(FiveValues.CONSENT, "acted without consent")
    assert len(sd.violation_log) == 2
    assert sd.check_for_violations() is False
    assert sd.is_triggered is False


def test_threshold_fires_countdown_and_check_sees_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sd = SovereignDisconnect()
    for v in (FiveValues.TRUTH, FiveValues.DIGNITY, FiveValues.INTEGRITY):
        sd.report_violation(v, f"violation of {v.value}")
    assert sd.is_triggered is True
    assert sd.check_for_violations() is True
    record = (tmp_path / "riley_sovereign_disconnect.log").read_text()
    assert "SOVEREIGN DISCONNECT TRIGGERED" in record
    assert record.count("VIOLATION:") == 3


def test_countdown_fires_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sd = SovereignDisconnect()
    for v in (FiveValues.TRUTH, FiveValues.SAFETY, FiveValues.DIGNITY, FiveValues.CONSENT):
        sd.report_violation(v, "x")
    record = (tmp_path / "riley_sovereign_disconnect.log").read_text()
    assert record.count("SOVEREIGN DISCONNECT TRIGGERED") == 1
    assert sd.check_for_violations() is True


def test_lost_record_is_said_out_loud(tmp_path, monkeypatch, caplog):
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, stat.S_IRUSR | stat.S_IXUSR)
    monkeypatch.chdir(locked)
    try:
        sd = SovereignDisconnect()
        with caplog.at_level(logging.ERROR):
            sd.trigger_countdown()
        assert sd.is_triggered is True
        assert sd.check_for_violations() is True
        assert any("Disconnect record NOT written" in r.getMessage() for r in caplog.records)
    finally:
        os.chmod(locked, stat.S_IRWXU)


def test_riley_tunnel_closes_after_disconnect(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    riley = RileyBridge()
    assert riley.send_to_architect({"note": "hello"}, integrity_hash="unused") is True
    for v in (FiveValues.TRUTH, FiveValues.SAFETY, FiveValues.INTEGRITY):
        riley.disconnect_protocol.report_violation(v, "x")
    assert riley.send_to_architect({"note": "after"}, integrity_hash="unused") is False
    assert riley.is_connected is False
