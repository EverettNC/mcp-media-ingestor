"""
© 2025 The Christman AI Project. All rights reserved.

This code is released as part of a trauma-informed, dignity-first AI ecosystem designed to protect, empower, and elevate vulnerable populations.

By using, modifying, or distributing this software, you agree to uphold the following core principles:

1. Truth — No deception, no manipulation. Use this code honestly.
2. Dignity — Respect the autonomy, privacy, and humanity of all users.
3. Protection — This software must never be used to harm, exploit, or surveil vulnerable individuals.
4. Transparency — You must disclose modifications and contributions clearly.
5. No Erasure — Do not remove the origins, mission, or ethical foundation of this work.

This is not just code. It is redemption in code.

For questions or licensing requests, contact:
Everett N. Christman
📧 lumacognify@thechristmanaiproject.com
🌐 https://thechristmanaiproject.com

AlphaVox Brain - Core AI Logic
"""

import datetime
import logging
import os
import sys

import requests
from bs4 import BeautifulSoup

from conversation_engine import ConversationEngine
from memory_engine import MemoryEngine  # Updated

# Try to import web_crawler, fall back gracefully if newspaper isn't available
try:
    from web_crawler import extract_from_urls

    WEB_CRAWLER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"web_crawler not available: {e}")
    WEB_CRAWLER_AVAILABLE = False

    def extract_from_urls(urls):
        """Fallback when newspaper library isn't available"""
        return [
            {
                "title": "Web Crawler Unavailable",
                "text": "Please install newspaper3k library",
            }
        ]


# brain.py (or equivalent bootstrap)
from boot_guardian import BootGuardian
from json_guardian import JSONGuardian



def boot():
    # Sovereign self-check before anything else happens
    guardian = BootGuardian(memory_dir="memory", schema_dir="schemas")
    guardian.run_full_validation()

    # Continue normal boot if everything passed
    print("🚀 alphavox boot sequence continuing...")
    # load models, services, memory embeddings, etc.


def boot():
    guardian = JSONGuardian()
    guardian.validate_all()
    print("✅ All JSON memory files validated successfully.")
    # then continue with loading memory, models, etc.


# Set up logging
logger = logging.getLogger(__name__)

# Try to import optional modules with fallbacks
try:
    from intent_engine import detect_intent
except ImportError:
    logger.warning("intent_engine not found, using basic intent detection")

    def detect_intent(text):
        return "general"


try:
    from executor import execute_task
except ImportError:
    logger.warning("executor not found, using basic task execution")

    def execute_task(text, intent, context):
        return f"I received your message: {text}"


try:
    from tts_bridge import speak_response
except ImportError:
    logger.warning("tts_bridge not found, speech output disabled")

    def speak_response(text):
        print(f"[SPEECH]: {text}")


# Create a simple learning coordinator fallback
try:
    from alphavox_learning_coordinator import (
        alphavox_coordinator,
        start_alphavox_learning,
    )
except ImportError:
    logger.warning("alphavox_learning_coordinator not found, using fallback")

    class DummyCoordinator:
        def start(self):
            logger.info("Learning coordinator fallback active")

    alphavox_coordinator = DummyCoordinator()

    def start_alphavox_learning():
        alphavox_coordinator.start()


logger = logging.getLogger(__name__)

# ensure the project root is in Python's import path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# try:
#   from ai_learning_engine import learn_from_text

#  logger.info("✅ ai_learning_engine imported successfully")
# except Exception as e:
#   logger.warning(f"⚠️ Failed to import ai_learning_engine: {e}")

#  def learn_from_text(text):
#     logger.info("Learning module unavailable, skipping text ingestion")


class alphavox:
    def __init__(self, file_path: str = "./memory/memory_store.json"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        self.memory_engine = MemoryEngine(file_path=file_path)
        self.conversation_engine = ConversationEngine()
        self.avatar_engine = None
        self.learning_coordinator = alphavox_coordinator

        logger.info(f"alphavox initialized successfully with memory file: {file_path}")

    def generate_greeting(self) -> str:
        """
        Returns a startup greeting when alphavox Dashboard launches.
        Can be made dynamic later, but static is fine to unblock startup.
        """
        return "Hello, I’m alphavox — ready to assist you."

    def connect_conversation_engine(self, conversation_engine):
        self.conversation_engine = conversation_engine

    def attach_avatar_engine(self, avatar_engine):
        self.avatar_engine = avatar_engine

    def get_current_mood(self):
        if self.conversation_engine and hasattr(self.conversation_engine, "emotional_state"):
            return self.conversation_engine.emotional_state
        return {}

    def start_learning(self):
        """Activate alphavox's coordinated learning systems."""
        try:
            start_alphavox_learning()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to start learning systems: %s", exc)
        else:
            logger.info("alphavox is now learning autonomously")

    def _search_web(self, query: str) -> str:
        """Performs a web search and returns a summary of the top result."""
        logger.info(f"Performing web search for: {query}")
        try:
            # Prepare the search URL
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            }

            # Get the search results page
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()

            # --- Parse links from the HTML ---
            soup = BeautifulSoup(response.text, "html.parser")
            link_tags = soup.find_all("a", href=lambda href: href and href.startswith("/url?q="))
            urls = [tag["href"].split("/url?q=")[1].split("&sa=U")[0] for tag in link_tags[:3]]

            # Extract content from top 3 links
            article_data = extract_from_urls(urls)

            summaries = []
            for i, item in enumerate(article_data):
                title = item.get("title", "No Title")
                text = item.get("text", "")
                summary = f"{i + 1}. {title}: {text[:200]}..."
                summaries.append(summary)

                # Auto-ingest what alphavox reads
                learn_from_text(text)

            summary_output = "\n\n".join(summaries)

            # Save original search HTML for debugging
            with open("google_search_results.html", "w", encoding="utf-8") as file:
                file.write(response.text)

            return summary_output

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            print(f"Web search failed with error: {e}")
            return "I had trouble searching the web. Please check my connection and logs."

    def think(self, input_text: str):
        # Step 1: Detect Intent
        intent = detect_intent(input_text)

        # --- Smarter question detection ---
        question_keywords = [
            "who is",
            "what is",
            "what's",
            "when did",
            "where is",
            "why is",
            "how is",
            "weather in",
        ]
        is_question = any(kw in input_text.lower() for kw in question_keywords)

        if is_question:
            logger.info("Question detected, performing web search.")
            repaired_result = self._search_web(input_text)
        else:
            # Non-search tasks use local context
            memory_context = self.memory_engine.query(input_text, intent)
            raw_result = execute_task(input_text, intent, memory_context)
            repaired_result = self.run_self_repair(input_text, raw_result)

        # Step 5: Speak the Output
        speak_response(repaired_result)
        if self.avatar_engine:
            self.avatar_engine.speak(repaired_result)

        # Step 6: Save to Memory and Log
        self.memory_engine.save({"input": input_text, "output": repaired_result, "intent": intent})
        self.log_interaction(input_text, repaired_result)

        return {
            "intent": intent,
            "context": "Web Search" if is_question else "Memory",
            "response": repaired_result,
            "mood": self.get_current_mood(),
        }

    def run_self_repair(self, user_input, alphavox_output):
        """Detect canned or low-depth responses and trigger auto-improvement."""
        canned_indicators = [
            "you got it",
            "happy to help",
            "sounds good",
            "let me know",
            "here’s how",
            "you’re doing great",
            "as an ai language model",
            "i'm here to assist",
        ]

        if any(phrase in alphavox_output.lower() for phrase in canned_indicators):
            return (
                f"⚠️ [Self-Repair Triggered]\n"
                f"Your last response lacked depth and originality.\n\n"
                f"🧠 USER INPUT:\n{user_input.strip()}\n\n"
                f"🛠️ alphavox'S IMPROVED RESPONSE:\n"
                f"[Insert real, contextual, emotionally intelligent response here]"
            )
        return alphavox_output

    def log_interaction(self, user_input, alphavox_output):
        """Logs every conversation exchange to a markdown file."""
        timestamp = datetime.datetime.now().isoformat()
        log_entry = (
            f"## {timestamp}\n"
            f"**Input:** {user_input}\n"
            f"**Output:** {alphavox_output[:150]}...\n\n"
        )

        os.makedirs("logs", exist_ok=True)
        with open("logs/study_log.md", "a") as f:
            f.write(log_entry)


# -------------------------------------------------------------
# Global alphavox instance
# -------------------------------------------------------------
# Create the global instance - this is what other modules import
alphavox_instance = alphavox(file_path="./memory/memory_store.json")

# For backward compatibility, also export as 'alphavox'
# But we use alphavox_instance internally to avoid confusion
alphavox = alphavox_instance

# ==============================================================================
# © 2025 The Christman AI Project
# Created by Everett Christman and Derek C. Junior
# All rights reserved. Unauthorized use, replication, or derivative training
# of this material is prohibited.
# Core Directive: "How can I help you love yourself more?"
# Autonomy & Alignment Protocol v3.0
# ==============================================================================

__all__ = ['boot', 'boot', 'alphavox']
