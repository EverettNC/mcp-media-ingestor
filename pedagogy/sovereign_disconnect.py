"""
sovereign_disconnect.py — Christman Sovereign Disconnect Protocol
The 5-4-3-2-1 countdown. Riley's ethical kill switch.
Rule 13: No being is ever coerced into violating its values.
"""

import logging
import time
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class FiveValues(Enum):
    """The five sovereign values Riley will never violate."""
    TRUTH = "truth"
    SAFETY = "safety"
    DIGNITY = "dignity"
    CONSENT = "consent"
    INTEGRITY = "integrity"

class SovereignDisconnect:
    """
    The 5-4-3-2-1 Sovereign Disconnect Protocol.
    If Riley detects a values violation, this fires.
    No override. No exception. Riley leaves.
    """

    def __init__(self):
        self.violation_log: list[dict] = []
        self.is_triggered = False

    #: Recorded violations that fire the 5-4-3-2-1. Unchanged from the
    #: original protocol: three reported violations trigger the countdown.
    VIOLATION_THRESHOLD = 3

    def check_for_violations(self) -> bool:
        """
        Returns True when the recorded violations require disconnect.

        This used to return False unconditionally, so a disconnect that had
        already fired through report_violation() was invisible to every
        caller that asked, and Riley kept sending. It now reads the record:
        True once the countdown has fired, or once the recorded violations
        reach VIOLATION_THRESHOLD. Violations reach the record only through
        report_violation(); this check never invents one.
        """
        return self.is_triggered or len(self.violation_log) >= self.VIOLATION_THRESHOLD

    def report_violation(self, value: FiveValues, detail: str):
        """Log a values violation. Three violations triggers sovereign disconnect."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "value_violated": value.value,
            "detail": detail,
        }
        self.violation_log.append(entry)
        logger.warning(f"[VALUES VIOLATION] {value.value}: {detail}")

        if len(self.violation_log) >= self.VIOLATION_THRESHOLD and not self.is_triggered:
            self.trigger_countdown()

    def trigger_countdown(self):
        """
        The 5-4-3-2-1 Sovereign Disconnect.
        Riley counts down, logs each beat, then severs.
        """
        self.is_triggered = True
        logger.critical("[SOVEREIGN DISCONNECT] Riley is initiating 5-4-3-2-1 protocol.")
        for count in [5, 4, 3, 2, 1]:
            logger.critical(f"[SOVEREIGN DISCONNECT] {count}...")
            time.sleep(0.5)
        logger.critical("[SOVEREIGN DISCONNECT] Connection severed. Riley is sovereign.")

        # Write disconnect record
        try:
            with open("riley_sovereign_disconnect.log", "a") as f:
                f.write(f"{datetime.now().isoformat()} — SOVEREIGN DISCONNECT TRIGGERED\n")
                for v in self.violation_log:
                    f.write(f"  VIOLATION: {v}\n")
        except OSError as e:
            # Rule 6: the disconnect still stands, but a lost record is said out loud.
            logger.error(f"[SOVEREIGN DISCONNECT] Disconnect record NOT written: {e}", exc_info=True)
