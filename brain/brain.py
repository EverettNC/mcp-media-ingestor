"""
AlphaVox Brain - Ferrari Engine V2
Nonverbal Autistic Support AI with Behavioral Capture at Core

Mission: Communication accessibility for nonverbal neurodivergent autistic individuals
Core Technology: Behavioral capture, gesture recognition, eye tracking, vocalization analysis

© 2025 The Christman AI Project
"""

import datetime
import logging
import os
import sys

from conversation_engine import ConversationEngine
from memory_engine import MemoryEngine

# CORE: Behavioral Capture System
try:
    from behavior_capture import BehaviorCapture
except ImportError:
    BehaviorCapture = None
    logging.warning("BehaviorCapture not available - CORE FEATURE")

try:
    from nonverbal_engine import NonverbalEngine
except ImportError:
    NonverbalEngine = None
    logging.warning("NonverbalEngine not available - CORE FEATURE")

try:
    from behavioral_interpreter import BehavioralInterpreter
except ImportError:
    BehavioralInterpreter = None
    logging.warning("BehavioralInterpreter not available")

try:
    from temporal_nonverbal_engine import TemporalNonverbalEngine
except ImportError:
    TemporalNonverbalEngine = None
    logging.warning("TemporalNonverbalEngine not available")

# Ferrari Engine Components
try:
    from local_reasoning_engine import LocalReasoningEngine
except ImportError:
    LocalReasoningEngine = None

try:
    from alphavox_knowledge_engine import KnowledgeEngine
except ImportError:
    KnowledgeEngine = None

try:
    from tone_manager import ToneManager
except ImportError:
    ToneManager = None

try:
    from perplexity_service import PerplexityService
except ImportError:
    PerplexityService = None

# Legacy imports
try:
    from intent_engine import detect_intent
except ImportError:
    def detect_intent(text):
        return "general"

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


class alphavox:
    """
    AlphaVox Ferrari Engine V2 - Nonverbal Autistic Support AI
    
    Core Mission: Enable communication for nonverbal neurodivergent autistic individuals
    
    Primary Systems:
    1. BehaviorCapture - Webcam-based micro-expressions, movements, gestures
    2. NonverbalEngine - Gesture, eye movement, vocalization classification
    3. BehavioralInterpreter - Pattern recognition and intent mapping
    4. Ferrari Reasoning - Full cascade with behavioral context
    
    Capabilities:
    - Real-time behavioral pattern analysis
    - Gesture recognition and mapping
    - Eye tracking for AAC (Augmentative & Alternative Communication)
    - Micro-expression detection
    - Repetitive movement tracking (stimming detection)
    - Vocalization analysis
    - Symbol system integration (PCS, ARASAAC)
    - Self-learning adaptive responses
    """

    def __init__(self, file_path: str = "./memory/memory_store.json"):
        self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        # Core engines
        self.memory_engine = MemoryEngine(file_path=file_path)
        self.conversation_engine = ConversationEngine()
        self.avatar_engine = None
        self.learning_coordinator = alphavox_coordinator

        # BEHAVIORAL CAPTURE - CORE SYSTEM
        if BehaviorCapture:
            self.behavior_capture = BehaviorCapture()
            logger.info("✅ BehaviorCapture initialized - CORE SYSTEM ACTIVE")
        else:
            self.behavior_capture = None
            logger.error("❌ BehaviorCapture unavailable - CORE SYSTEM MISSING")

        if NonverbalEngine:
            self.nonverbal_engine = NonverbalEngine()
            logger.info("✅ NonverbalEngine initialized - CORE SYSTEM ACTIVE")
        else:
            self.nonverbal_engine = None
            logger.error("❌ NonverbalEngine unavailable - CORE SYSTEM MISSING")

        if BehavioralInterpreter:
            self.behavioral_interpreter = BehavioralInterpreter()
            logger.info("✅ BehavioralInterpreter initialized")
        else:
            self.behavioral_interpreter = None

        if TemporalNonverbalEngine:
            self.temporal_nonverbal = TemporalNonverbalEngine()
            logger.info("✅ TemporalNonverbalEngine initialized")
        else:
            self.temporal_nonverbal = None

        # Ferrari Engine Components
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

        # Statistics - Behavioral Focus
        self.stats = {
            "total_interactions": 0,
            "behavioral_captures": 0,
            "gestures_recognized": 0,
            "eye_movements_tracked": 0,
            "vocalizations_analyzed": 0,
            "patterns_learned": 0,
            "local_reasoning_used": 0,
            "knowledge_hits": 0,
        }

        logger.info(f"🏎️🎤 AlphaVox Ferrari Engine V2 - Behavioral Capture Core")
        logger.info("🎯 Mission: Nonverbal Autistic Communication Support")

    def generate_greeting(self) -> str:
        return "Hello! I'm AlphaVox, ready to understand your unique way of communicating."

    def think(self, input_text: str = "", behavioral_data: dict = None, multimodal_input: dict = None):
        """
        Ferrari Engine V2 - Behavioral Capture Priority Cascade
        
        Flow:
        1. BEHAVIORAL ANALYSIS (Core - Primary Input)
           - Gesture recognition
           - Eye tracking
           - Micro-expressions
           - Vocalization patterns
        2. Context Gathering (Memory + Emotion)
        3. Pattern Recognition (Temporal analysis)
        4. Local Reasoning with Behavioral Context
        5. Knowledge Check
        6. Response Generation (AAC-friendly)
        """
        self.stats["total_interactions"] += 1
        
        # Step 1: BEHAVIORAL ANALYSIS - PRIMARY INPUT
        behavioral_intent = None
        behavioral_confidence = 0.0
        
        if behavioral_data or multimodal_input:
            self.stats["behavioral_captures"] += 1
            
            # Process behavioral data
            if self.behavior_capture and behavioral_data:
                try:
                    # Analyze gestures, movements, expressions
                    behavior_analysis = self.behavior_capture.analyze_frame(behavioral_data)
                    behavioral_intent = behavior_analysis.get("intent")
                    behavioral_confidence = behavior_analysis.get("confidence", 0.0)
                    logger.info(f"👁️ Behavioral Analysis: {behavioral_intent} ({behavioral_confidence:.2f})")
                except Exception as e:
                    logger.error(f"Behavior capture failed: {e}")
            
            # Process nonverbal inputs
            if self.nonverbal_engine and multimodal_input:
                try:
                    gesture = multimodal_input.get("gesture")
                    eye_position = multimodal_input.get("eye_position")
                    vocalization = multimodal_input.get("vocalization")
                    
                    if gesture:
                        self.stats["gestures_recognized"] += 1
                        gesture_intent = self.nonverbal_engine.classify_gesture(gesture)
                        logger.info(f"👋 Gesture: {gesture_intent}")
                    
                    if eye_position:
                        self.stats["eye_movements_tracked"] += 1
                        eye_intent = self.nonverbal_engine.classify_eye_movement(eye_position)
                        logger.info(f"👁️ Eye: {eye_intent}")
                    
                    if vocalization:
                        self.stats["vocalizations_analyzed"] += 1
                        vocal_intent = self.nonverbal_engine.classify_vocalization(vocalization)
                        logger.info(f"🔊 Vocalization: {vocal_intent}")
                except Exception as e:
                    logger.error(f"Nonverbal processing failed: {e}")
        
        # Step 2: Context Gathering
        memory_context = self.memory_engine.query(input_text or str(behavioral_intent), "general")
        emotion_context = ""
        if self.tone_manager and input_text:
            emotion_context = str(self.tone_manager.analyze_user_input(input_text))
        
        # Step 3: Pattern Recognition (Temporal)
        if self.temporal_nonverbal:
            try:
                pattern = self.temporal_nonverbal.detect_pattern(behavioral_data)
                if pattern:
                    self.stats["patterns_learned"] += 1
                    logger.info(f"🔄 Pattern detected: {pattern}")
            except Exception as e:
                logger.debug(f"Pattern recognition skipped: {e}")
        
        # Step 4: Local Reasoning with Behavioral Context
        local_analysis = ""
        if self.local_reasoning:
            try:
                behavioral_context = f"Behavioral intent: {behavioral_intent}, confidence: {behavioral_confidence}"
                local_analysis = self.local_reasoning.analyze(
                    user_input=input_text or str(behavioral_intent),
                    memory=str(memory_context.get("context", "")) if isinstance(memory_context, dict) else str(memory_context),
                    emotion=emotion_context,
                    vision=behavioral_context
                )
                self.stats["local_reasoning_used"] += 1
            except Exception as e:
                logger.error(f"Local reasoning failed: {e}")
        
        # Step 5: Knowledge Check
        knowledge_confidence = 0.0
        if self.knowledge_engine:
            try:
                knowledge_result = self.knowledge_engine.reason(
                    question=input_text or str(behavioral_intent),
                    context={"memory": memory_context, "behavioral": behavioral_intent}
                )
                
                if isinstance(knowledge_result, dict):
                    knowledge_confidence = knowledge_result.get("confidence", 0.0)
                else:
                    knowledge_confidence = min(0.9, len(str(knowledge_result)) / 500)
                
                if knowledge_confidence >= 0.7:
                    self.stats["knowledge_hits"] += 1
            except Exception as e:
                logger.error(f"Knowledge engine failed: {e}")
        
        # Step 6: Response Generation
        # Priority: Behavioral intent > Text input > Fallback
        if behavioral_confidence >= 0.7:
            response = f"I understand your {behavioral_intent}. {local_analysis if local_analysis else ''}"
            source = "Behavioral Recognition"
        elif knowledge_confidence >= 0.7:
            if isinstance(knowledge_result, dict):
                response = knowledge_result.get("response", str(knowledge_result))
            else:
                response = str(knowledge_result)
            source = "Knowledge Engine"
        elif input_text:
            if self.perplexity:
                try:
                    response = self.perplexity.generate_content(input_text)
                    source = "Perplexity API"
                except:
                    response = local_analysis or "I'm listening and learning your communication style."
                    source = "Local Reasoning"
            else:
                response = local_analysis or "I'm here to support your communication."
                source = "Local Reasoning"
        else:
            response = "I'm observing and ready to help you communicate."
            source = "Behavioral Observation"
        
        # Step 7: Save with Behavioral Context
        self.memory_engine.save({
            "input": input_text or "behavioral_input",
            "output": response,
            "source": source,
            "behavioral_intent": behavioral_intent,
            "behavioral_confidence": behavioral_confidence,
            "knowledge_confidence": knowledge_confidence
        })
        
        # Step 8: Output (AAC-friendly)
        speak_response(response)
        if self.avatar_engine:
            self.avatar_engine.speak(response)
        
        return {
            "response": response,
            "source": source,
            "behavioral_intent": behavioral_intent,
            "behavioral_confidence": behavioral_confidence,
            "knowledge_confidence": knowledge_confidence,
            "stats": self.stats.copy()
        }

    def start_learning(self):
        try:
            start_alphavox_learning()
        except Exception as exc:
            logger.error("Failed to start learning: %s", exc)
        else:
            logger.info("AlphaVox learning autonomously")

    def get_stats(self):
        return self.stats.copy()


# Global instance
alphavox_instance = alphavox(file_path="./memory/memory_store.json")
alphavox = alphavox_instance

__all__ = ['alphavox', 'alphavox_instance']
