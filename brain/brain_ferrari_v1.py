"""
© 2025 The Christman AI Project. All rights reserved.

AlphaVox Brain - Ferrari Engine (100% Module Utilization)
"""

import datetime
import logging
import os
import sys

from conversation_engine import ConversationEngine
from memory_engine import MemoryEngine

# Ferrari Engine Components
try:
    from local_reasoning_engine import LocalReasoningEngine
except ImportError:
    LocalReasoningEngine = None
    logging.warning("LocalReasoningEngine not available")

try:
    from alphavox_knowledge_engine import KnowledgeEngine
except ImportError:
    try:
        from knowledge_engine import KnowledgeEngine
    except ImportError:
        KnowledgeEngine = None
        logging.warning("KnowledgeEngine not available")

try:
    from tone_manager import ToneManager
except ImportError:
    ToneManager = None
    logging.warning("ToneManager not available")

try:
    from perplexity_service import PerplexityService
except ImportError:
    PerplexityService = None
    logging.warning("PerplexityService not available")

# Legacy imports
try:
    from intent_engine import detect_intent
except ImportError:
    logging.warning("intent_engine not found")
    def detect_intent(text):
        return "general"

try:
    from executor import execute_task
except ImportError:
    logging.warning("executor not found")
    def execute_task(text, intent, context):
        return f"I received: {text}"

try:
    from tts_bridge import speak_response
except ImportError:
    def speak_response(text):
        print(f"[SPEECH]: {text}")

try:
    from alphavox_learning_coordinator import alphavox_coordinator, start_alphavox_learning
except ImportError:
    class DummyCoordinator:
        def start(self):
            logging.info("Learning coordinator fallback")
    alphavox_coordinator = DummyCoordinator()
    def start_alphavox_learning():
        alphavox_coordinator.start()

logger = logging.getLogger(__name__)
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)


class alphavox:
    def __init__(self, file_path: str = "./memory/memory_store.json"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        # Core engines
        self.memory_engine = MemoryEngine(file_path=file_path)
        self.conversation_engine = ConversationEngine()
        self.avatar_engine = None
        self.learning_coordinator = alphavox_coordinator

        # Ferrari Engine - Full Module Integration
        if LocalReasoningEngine:
            self.local_reasoning = LocalReasoningEngine()
            logger.info("✅ LocalReasoningEngine initialized")
        else:
            self.local_reasoning = None

        if KnowledgeEngine:
            self.knowledge_engine = KnowledgeEngine(
                knowledge_dir="./alphavox_knowledge",
                memory_mesh=self.memory_engine,
                local_reasoning=self.local_reasoning
            )
            logger.info("✅ KnowledgeEngine initialized")
        else:
            self.knowledge_engine = None

        if ToneManager:
            self.tone_manager = ToneManager()
            logger.info("✅ ToneManager initialized")
        else:
            self.tone_manager = None

        if PerplexityService:
            self.perplexity = PerplexityService()
            logger.info("✅ PerplexityService initialized")
        else:
            self.perplexity = None

        # Statistics
        self.stats = {
            "total_interactions": 0,
            "local_reasoning_used": 0,
            "knowledge_hits": 0,
            "external_api_calls": 0,
        }

        logger.info(f"🏎️ AlphaVox Ferrari Engine initialized")

    def generate_greeting(self) -> str:
        return "Hello, I'm AlphaVox — ready with full reasoning capabilities."

    def connect_conversation_engine(self, conversation_engine):
        self.conversation_engine = conversation_engine

    def attach_avatar_engine(self, avatar_engine):
        self.avatar_engine = avatar_engine

    def get_current_mood(self):
        if self.conversation_engine and hasattr(self.conversation_engine, "emotional_state"):
            return self.conversation_engine.emotional_state
        return {}

    def start_learning(self):
        try:
            start_alphavox_learning()
        except Exception as exc:
            logger.error("Failed to start learning: %s", exc)
        else:
            logger.info("AlphaVox learning autonomously")

    def think(self, input_text: str):
        """Ferrari Engine - Full Reasoning Cascade"""
        self.stats["total_interactions"] += 1
        
        # Step 1: Context Gathering
        memory_context = self.memory_engine.query(input_text, "general")
        emotion_context = ""
        if self.tone_manager:
            emotion_context = str(self.tone_manager.analyze_user_input(input_text))
        
        # Step 2: Local Reasoning
        local_analysis = ""
        if self.local_reasoning:
            try:
                local_analysis = self.local_reasoning.analyze(
                    user_input=input_text,
                    memory=str(memory_context.get("context", "")) if isinstance(memory_context, dict) else str(memory_context),
                    emotion=emotion_context
                )
                self.stats["local_reasoning_used"] += 1
            except Exception as e:
                logger.error(f"Local reasoning failed: {e}")
        
        # Step 3: Knowledge Check
        knowledge_confidence = 0.0
        if self.knowledge_engine:
            try:
                knowledge_result = self.knowledge_engine.reason(
                    question=input_text,
                    context={"memory": memory_context, "emotion": emotion_context}
                )
                
                if isinstance(knowledge_result, dict):
                    knowledge_confidence = knowledge_result.get("confidence", 0.0)
                else:
                    knowledge_confidence = min(0.9, len(str(knowledge_result)) / 500)
                
                if knowledge_confidence >= 0.7:
                    self.stats["knowledge_hits"] += 1
            except Exception as e:
                logger.error(f"Knowledge engine failed: {e}")
                knowledge_result = None
        
        # Step 4: Decision - Knowledge vs External
        if knowledge_confidence >= 0.7:
            if isinstance(knowledge_result, dict):
                response = knowledge_result.get("response", str(knowledge_result))
            else:
                response = str(knowledge_result)
            source = "Knowledge Engine"
        elif self.perplexity and knowledge_confidence < 0.4:
            try:
                response = self.perplexity.generate_content(input_text)
                self.stats["external_api_calls"] += 1
                source = "Perplexity API"
            except Exception as e:
                intent = detect_intent(input_text)
                response = execute_task(input_text, intent, memory_context)
                source = "Fallback"
        else:
            intent = detect_intent(input_text)
            response = execute_task(input_text, intent, memory_context)
            source = "Local Execution"
        
        # Step 5: Output
        speak_response(response)
        if self.avatar_engine:
            self.avatar_engine.speak(response)
        
        # Step 6: Save
        self.memory_engine.save({
            "input": input_text,
            "output": response,
            "source": source,
            "confidence": knowledge_confidence
        })
        
        return {
            "intent": detect_intent(input_text),
            "context": source,
            "response": response,
            "confidence": knowledge_confidence,
            "mood": self.get_current_mood(),
            "stats": self.stats.copy()
        }

    def get_stats(self):
        return self.stats.copy()


# Global instance
alphavox_instance = alphavox(file_path="./memory/memory_store.json")
alphavox = alphavox_instance

__all__ = ['alphavox', 'alphavox_instance']
