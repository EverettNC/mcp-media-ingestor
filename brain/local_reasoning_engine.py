# © 2025 The Christman AI Project. All rights reserved.
#
# This code is released as part of a trauma-informed, dignity-first AI ecosystem
# designed to protect, empower, and elevate vulnerable populations.
#
# By using, modifying, or distributing this software, you agree to uphold the following:
# 1. Truth — No deception, no manipulation.
# 2. Dignity — Respect the autonomy and humanity of all users.
# 3. Protection — Never use this to exploit or harm vulnerable individuals.
# 4. Transparency — Disclose all modifications and contributions clearly.
# 5. No Erasure — Preserve the mission and ethical origin of this work.
#
# This is not just code. This is redemption in code.
# Contact: lumacognify@thechristmanaiproject.com
# https://thechristmanaiproject.com

"""
Local Reasoning Engine
----------------------
alphavoxC's internal thought kernel.
Builds short conclusions from user input, memory, tone, and vision.
No external AI calls — purely local synthesis.
"""

import math
from datetime import datetime


class LocalReasoningEngine:
    def __init__(self):
        self.last_reflection = ""
        self.reasoning_log = []

    # ----------------------------------------------------------
    def analyze(
        self, user_input: str, memory: str = "", emotion: str = "", vision: str = ""
    ) -> str:
        """
        Primary reasoning function.
        Combines alphavox's sensory and contextual inputs into a unified interpretation.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reflection = []

        # 1️⃣  Gather sensory context
        if emotion:
            reflection.append(f"My emotional tone reads as {emotion}.")
        if vision:
            reflection.append(f"My visual impression is {vision}.")
        if memory:
            reflection.append(f"I remember that {memory.strip()}.")

        # 2️⃣  Process new input
        reflection.append(f"The new input is: '{user_input.strip()}'.")

        # 3️⃣  Internal reasoning — weighted synthesis
        weight = self._calculate_context_weight(memory, emotion, vision)
        core_thought = self._generate_summary(user_input, memory, weight)

        # 4️⃣  Build final reflection
        reflection.append(core_thought)
        final = " | ".join(reflection)
        self.last_reflection = final
        self.reasoning_log.append({"time": timestamp, "reflection": final})
        return final

    def _calculate_context_weight(self, memory: str, emotion: str, vision: str) -> float:
        w = 1.0
        if memory:
            w += 0.3
        if emotion:
            w += 0.2
        if vision:
            w += 0.25
        return min(w, 2.0)

    def _generate_summary(self, user_input: str, memory: str, weight: float) -> str:
        base = "Synthesizing: "
        if "need" in user_input.lower() or "want" in user_input.lower():
            base += "User is expressing a need or desire. "
        else:
            base += "Input received and being integrated. "
        if memory:
            base += "Drawing on prior memory. "
        if weight > 1.5:
            base += "High context confidence."
        return base

    def get_last_reflection(self) -> str:
        return self.last_reflection or "No reflection yet."

__all__ = ['LocalReasoningEngine']
