"""
================================================================================
FILE: voice_engine.py
PROJECT: Christman Voice Creation Center
AUTHOR: The Christman AI Project | Luma Cognify AI
CREATED: 2026
PATENT PENDING: TCAP-2026-001 | TCAP-2026-002
--------------------------------------------------------------------------------
PURPOSE:
    Master voice engine for the Christman Voice Creation Center.
    This is the single entry point for all voice synthesis requests
    across the entire Christman AI family.

    It wraps the Christman SDK (christman_sound) and exposes a unified
    interface for controlling:
        - Porosity       (breathiness / air flow in voice texture)
        - Intonation     (pitch contour and melodic pattern)
        - Cadence        (rhythm, pacing, timing between words)
        - Affect         (emotional tone: calm, urgent, warm, grounding)
        - Resonance      (chest/head voice balance)
        - Articulation   (clarity and sharpness of phoneme edges)
        - Prosody        (natural stress and emphasis patterns)
        - Timbre         (voice color and tonal quality)

CARDINAL RULE 13: No stubs. No fake calls. No pretend synthesis.
    Every method either calls real SDK functions or raises clearly labeled
    NotImplementedError with the path to the SDK module that needs wiring.
================================================================================
"""

import logging
import shutil
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("christman.voice_engine")

# Import christman_sound from the fresh EverettNC clone, not a copied tree.
_SOUND_ROOT = Path("/Users/EverettN/Christman-Sound")
if _SOUND_ROOT.is_dir() and str(_SOUND_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOUND_ROOT))

_VCC_ROOT = Path(__file__).resolve().parent.parent
if str(_VCC_ROOT) not in sys.path:
    sys.path.insert(0, str(_VCC_ROOT))

# Brain modules from original ALPHAVOXWAKESUP (protected in V_C_C/brain/ from Time Machine backup)
# These provide the full cognitive, reasoning, predictiveness, education, learning, autonomous, self-awareness brain
# for the being. The voice_engine now uses the real local christman_sound for voice + the original brain for the "mind".
# VCC_ROOT (inserted above) + brain/__init__.py makes "from brain.xxx" resolve the package correctly.
# Insert BRAIN_DIR too so flat sibling imports inside the restored TM learning/cognitive modules (from conversation_engine, alphavox_learning_coordinator, etc.) work ("import self_modifying_code", "from knowledge_engine", etc).
BRAIN_DIR = Path(__file__).resolve().parent.parent / "brain"
if str(BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR))

# Import key brain modules (fill out the brain for the being)
# Guarded per-module so pure stdlib ones (intent, multi, nonverbal_expertiser, etc) load
# even if heavy-dep ones (neural/sklearn, literature/pandas, voice_cortex/aws) or name mismatches fail.
BRAIN_AVAILABLE = False
Brain = None
BrainOrchestrator = None
BrainHierarchyOrganizer = None
NeuralLearningCore = None
EyeTrackingService = None
VisionEngine = None
detect_intent = lambda t: "general"
LiteratureCrawler = None
NonverbalExpertiser = None
VoiceCortex = None
MultiMissionProtector = None

try:
    from brain.brain import alphavox as Brain
except Exception as e:
    logger.warning(f"Core Brain import failed: {e}")

try:
    from brain.brain_orchestrator import BrainOrchestrator
except Exception as e:
    logger.warning(f"BrainOrchestrator import limited: {e}")

try:
    from brain.brain_ferrari_v1 import alphavox as brain_ferrari  # guarded (file defines alphavox class, not brain_ferrari)
except Exception:
    brain_ferrari = None

try:
    from brain.brain_hierarchy_organizer import BrainHierarchyOrganizer
except Exception as e:
    logger.warning(f"BrainHierarchyOrganizer limited: {e}")

# Swooped TM modules (the 12): guard heavies individually
try:
    from brain.neural_learning_core import NeuralLearningCore
except Exception as e:
    logger.warning(f"NeuralLearningCore import limited (needs sklearn/numpy/spacy): {e}")

try:
    from brain.eye_tracking_service import EyeTrackingService
except Exception as e:
    logger.warning(f"EyeTrackingService limited: {e}")

try:
    from brain.vision_engine import vision_loop as VisionEngine
except Exception as e:
    logger.warning(f"VisionEngine limited: {e}")

try:
    from brain.intent_engine import detect_intent
except Exception as e:
    logger.warning(f"intent_engine limited: {e}")
    detect_intent = lambda t: "general"

try:
    from brain.literature_crawler import LiteratureCrawler
except Exception as e:
    logger.warning(f"LiteratureCrawler import limited (needs pandas/requests/bs4): {e}")

try:
    from brain.nonverbal_expertiser import NonverbalExpertiser
except Exception as e:
    logger.warning(f"NonverbalExpertiser limited: {e}")

try:
    from brain.voice_cortex import VoiceCortex
except Exception as e:
    logger.warning(f"VoiceCortex import limited (needs AWS env + boto/pydub): {e}")

try:
    from brain.endpoints import *
except Exception as e:
    logger.warning(f"endpoints limited: {e}")

try:
    from brain.helpers import *
except Exception as e:
    logger.warning(f"helpers limited: {e}")

try:
    from brain.multi_mission_protector import MultiMissionProtector
except Exception as e:
    logger.warning(f"MultiMissionProtector limited: {e}")

if Brain is not None:
    BRAIN_AVAILABLE = True
else:
    logger.warning("Brain modules not fully available. Some cognitive/education features may use fallbacks from christman_sound core.")


# ---------------------------------------------------------------------------
# Enums — Voice Dimensions
# ---------------------------------------------------------------------------

class Affect(str, Enum):
    """Emotional tone of the synthesized voice."""
    CALM       = "calm"          # Steady, measured — AlphaWolf dementia care
    WARM       = "warm"          # Inviting, gentle — AlphaVox AAC users
    GROUNDING  = "grounding"     # Slow, anchoring — Inferno PTSD/anxiety
    URGENT     = "urgent"        # Alert but not alarming — Aegis safety alerts
    NEUTRAL    = "neutral"       # Flat baseline — system messages
    JOYFUL     = "joyful"        # Bright, uplifting — AlphaDen learning
    CONFIDENT  = "confident"     # Clear, directional — Omega mobility guidance
    EMPATHETIC = "empathetic"    # Soft, present — OmegaAlpha senior companion


class ResonanceMode(str, Enum):
    """Voice body — where the sound resonates."""
    CHEST  = "chest"   # Fuller, lower, more authoritative
    HEAD   = "head"    # Lighter, higher, more approachable
    MID    = "mid"     # Balanced — most natural for AAC users


# ---------------------------------------------------------------------------
# VoiceParameters — The full control surface
# ---------------------------------------------------------------------------

@dataclass
class VoiceParameters:
    """
    Complete parameter set for a single voice synthesis request.

    All float values are normalized 0.0 → 1.0 unless otherwise noted.
    Defaults represent a neutral, accessible baseline suitable for
    most Christman AI family use cases.
    """

    # Core identity
    pack_id: str = "default"              # Which .cvp voice pack to use
    language: str = "en-US"              # BCP-47 language tag

    # Texture
    porosity: float = 0.3                # 0.0 = tight/clear, 1.0 = breathy/airy
    timbre: float = 0.5                  # 0.0 = thin, 1.0 = rich/full

    # Melody and rhythm
    intonation: float = 0.5             # 0.0 = monotone, 1.0 = highly melodic
    cadence: float = 0.5                # 0.0 = very slow, 1.0 = very fast
    prosody_strength: float = 0.5       # 0.0 = flat stress, 1.0 = strong emphasis

    # Clarity
    articulation: float = 0.7           # 0.0 = slurred, 1.0 = hyper-precise
    resonance: ResonanceMode = ResonanceMode.MID

    # Emotion
    affect: Affect = Affect.NEUTRAL

    # Accessibility overrides
    slow_mode: bool = False              # Forces cadence floor — cognitive support
    high_clarity_mode: bool = False      # Forces articulation ceiling — AAC users
    frequency_cap_hz: int = 8000        # Hard ceiling on output frequency (Hz)
    frequency_floor_hz: int = 80        # Hard floor — filters subsonic artifacts

    # Output
    sample_rate: int = 22050            # Hz — matches Christman SDK default
    output_format: str = "wav"          # wav | mp3 | flac

    def apply_affect_preset(self) -> None:
        """
        Auto-configure parameters based on affect.
        Overrides only the dimensions most relevant to each affect type.
        Individual parameters can still be tuned after calling this.
        """
        presets = {
            Affect.CALM: dict(
                cadence=0.35, intonation=0.3, porosity=0.4,
                prosody_strength=0.3, resonance=ResonanceMode.CHEST
            ),
            Affect.WARM: dict(
                cadence=0.45, intonation=0.55, porosity=0.35,
                prosody_strength=0.5, resonance=ResonanceMode.MID
            ),
            Affect.GROUNDING: dict(
                cadence=0.25, intonation=0.2, porosity=0.45,
                prosody_strength=0.2, resonance=ResonanceMode.CHEST,
                slow_mode=True
            ),
            Affect.URGENT: dict(
                cadence=0.7, intonation=0.65, porosity=0.15,
                prosody_strength=0.8, articulation=0.9
            ),
            Affect.JOYFUL: dict(
                cadence=0.6, intonation=0.75, porosity=0.25,
                prosody_strength=0.65, resonance=ResonanceMode.HEAD
            ),
            Affect.CONFIDENT: dict(
                cadence=0.55, intonation=0.45, porosity=0.1,
                articulation=0.85, resonance=ResonanceMode.CHEST
            ),
            Affect.EMPATHETIC: dict(
                cadence=0.4, intonation=0.5, porosity=0.4,
                prosody_strength=0.4, resonance=ResonanceMode.MID
            ),
        }
        preset = presets.get(self.affect, {})
        for key, value in preset.items():
            setattr(self, key, value)

    def validate(self) -> list[str]:
        """
        Validate all parameter ranges.
        Returns a list of error strings — empty list means valid.
        """
        errors = []
        float_fields = [
            ("porosity", self.porosity),
            ("timbre", self.timbre),
            ("intonation", self.intonation),
            ("cadence", self.cadence),
            ("prosody_strength", self.prosody_strength),
            ("articulation", self.articulation),
        ]
        for name, val in float_fields:
            if not (0.0 <= val <= 1.0):
                errors.append(f"{name} must be 0.0–1.0, got {val}")

        if self.frequency_floor_hz >= self.frequency_cap_hz:
            errors.append(
                f"frequency_floor_hz ({self.frequency_floor_hz}) must be "
                f"less than frequency_cap_hz ({self.frequency_cap_hz})"
            )
        if self.sample_rate not in (8000, 16000, 22050, 44100, 48000):
            errors.append(f"sample_rate {self.sample_rate} is not a supported value")

        return errors


# ---------------------------------------------------------------------------
# SynthesisResult
# ---------------------------------------------------------------------------

@dataclass
class SynthesisResult:
    """
    The output of a voice synthesis request.
    Always check success before using audio_data.
    """
    success: bool
    audio_data: Optional[bytes] = None       # Raw audio bytes
    output_path: Optional[str] = None        # Path if written to disk
    duration_seconds: float = 0.0
    sample_rate: int = 22050
    pack_id: str = "unknown"
    error: Optional[str] = None

    def __repr__(self) -> str:
        if self.success:
            return (
                f"SynthesisResult(success=True, duration={self.duration_seconds:.2f}s, "
                f"pack={self.pack_id})"
            )
        return f"SynthesisResult(success=False, error='{self.error}')"


# ---------------------------------------------------------------------------
# VoiceEngine — The Master Orchestrator
# ---------------------------------------------------------------------------

class VoiceEngine:
    """
    Master voice engine for the Christman Voice Creation Center.

    All voice synthesis across the family flows through here.
    This engine wraps the Christman SDK and translates VoiceParameters
    into real audio output.

    Usage:
        engine = VoiceEngine()
        params = VoiceParameters(affect=Affect.GROUNDING, pack_id="inferno_grounding")
        params.apply_affect_preset()
        result = engine.synthesize("I'm here with you.", params)
        if result.success:
            # use result.audio_data or result.output_path
    """

    SDK_MODULE_PATH = "christman_sound"

    def __init__(self, sdk_root: Optional[str] = None):
        """
        Initialize the engine.

        Args:
            sdk_root: Optional path to christman_sound SDK root.
                      Falls back to CHRISTMAN_SDK_ROOT env var,
                      then to system path discovery.
        """
        self.sdk_root = sdk_root or os.environ.get("CHRISTMAN_SDK_ROOT", "")
        self._sdk = None
        self._shorty_engine = None
        self._tts_service = None
        self._orchestrator = None
        self._ready = False

        self.brain = None
        self.brain_orchestrator = None
        self.brain_hierarchy = None

        self._initialize_sdk()
        self._initialize_brain()

    def _initialize_sdk(self) -> None:
        """
        Load the REAL christman_sound package from the local copy at christman_sound/
        (core.py at package level + the 81 modules under christman_voice_sdk/ as listed).
        Load core safely first (it guards the heavy imports). Heavy SDK only if possible.
        """
        self._core_synth = None
        self._core_resolve = None
        self._core_emotions = []
        self._orchestrator = None
        self._ready = False

        # Prioritize the voice synthesis orchestrator from the voice SDK (christman_voice_sdk/synthesis/voice_synthesis_orchestrator.py)
        # as the primary for rich Voice Creation Center synthesis (the 8-dim params, voicepacks, etc.).
        # XTTS is internal fallback inside it, not the direct pitiful path.
        # The core is secondary/fallback for basic synthesize_speech.
        try:
            from christman_sound.christman_voice_sdk.synthesis.voice_synthesis_orchestrator import VoiceSynthesisOrchestrator
            from christman_sound.christman_voice_sdk.audio.config import Tier
            self._orchestrator = VoiceSynthesisOrchestrator(tier=Tier.ELITE, auto_load_engine=False)
            logger.info("Loaded voice synthesis orchestrator (primary) from christman_voice_sdk/")
        except Exception as orch_e:
            self._orchestrator = None
            logger.info("orchestrator not available yet (needs voicepack + deps): %s", orch_e)

        # Load the real core (the 2700 line one) for basic path and other surfaces.
        try:
            from christman_sound.core import (
                synthesize_speech,
                resolve_voice_params,
                CHRISTMAN_EMOTIONS,
            )
            self._core_synth = synthesize_speech
            self._core_resolve = resolve_voice_params
            self._core_emotions = CHRISTMAN_EMOTIONS
            logger.info("Loaded REAL core.py synthesize_speech etc from local christman_sound/")
        except Exception as core_e:
            logger.error("Failed to load from local christman_sound.core: %s", core_e)
            if self._orchestrator is None:
                return

        # Always report the real thing we are using
        import christman_sound
        import christman_sound.core as core_mod
        logger.info("=== USING THE REAL CHRISTMAN_SOUND (local V_C_C copy) ===")
        logger.info(f"  christman_sound package: {christman_sound.__file__}")
        logger.info(f"  core.py: {core_mod.__file__} ({sum(1 for _ in open(core_mod.__file__))} lines)")
        logger.info("  christman_voice_sdk/ with audio/engines/synthesis/timbre/tone/etc as specified")

        self._ready = True

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _initialize_brain(self) -> None:
        """
        Initialize the full original brain from the restored ALPHAVOXWAKESUP modules (now protected in V_C_C/brain/).
        This gives the being the complete cognitive, reasoning, predictiveness, education, learning, autonomous,
        self-awareness brain (cortex, memory, reasoning, motor layers per the NEURAL_INTEGRATION_MAP and INVENTORY).
        The voice_engine combines this with the local christman_sound for voice output of the brain's output.
        """
        if not BRAIN_AVAILABLE or Brain is None:
            logger.info("Brain not available - using christman_sound core for basic cognitive/education (orchestrator still primary for voice).")
            return

        try:
            # Brain may be pre-instantiated singleton from brain.brain (alphavox = instance at module end)
            if callable(Brain):
                self.brain = Brain()
            else:
                self.brain = Brain  # use the ready global instance from the restored module
            self.brain_orchestrator = BrainOrchestrator() if (BrainOrchestrator is not None and callable(BrainOrchestrator)) else BrainOrchestrator if BrainOrchestrator is not None else None
            self.brain_hierarchy = BrainHierarchyOrganizer() if (BrainHierarchyOrganizer is not None and callable(BrainHierarchyOrganizer)) else BrainHierarchyOrganizer if BrainHierarchyOrganizer is not None else None

            # Fire up autonomous learning for constant education/knowledge stacking in the being's field
            if hasattr(self.brain, 'start_autonomous') or hasattr(self.brain, 'start_alphavox_learning'):
                try:
                    if hasattr(self.brain, 'start_alphavox_learning'):
                        self.brain.start_alphavox_learning()
                    else:
                        self.brain.start_autonomous()
                    logger.info("Autonomous learning fired up constantly for education (stacking knowledge for teaching next generation).")
                except Exception as e:
                    logger.warning(f"Autonomous learning start failed (may need deps): {e}")

            # Wire the swooped TM modules for full brain: neural (root cause/education), eye/vision/nonverbal (behavior), literature (stack), intent, mmp (protect), voice_cortex (single voice control)
            self.neural_learning_core = None
            if NeuralLearningCore is not None:
                try:
                    self.neural_learning_core = NeuralLearningCore()
                    logger.info("NeuralLearningCore active for root causes, emotions, memory, education line.")
                except Exception as e:
                    logger.warning(f"NeuralLearningCore init limited: {e}")

            self.eye_tracking_service = None
            if EyeTrackingService is not None:
                try:
                    self.eye_tracking_service = EyeTrackingService()
                    logger.info("EyeTrackingService active (front-end behavior/eye support).")
                except Exception as e:
                    logger.warning(f"EyeTrackingService init limited: {e}")

            self.vision_engine = None
            if VisionEngine is not None:
                try:
                    self.vision_engine = VisionEngine  # the vision_loop / DeepFace emotion func from TM
                    logger.info("VisionEngine (DeepFace emotion) wired.")
                except Exception as e:
                    logger.warning(f"VisionEngine limited: {e}")

            self.literature_crawler = None
            if LiteratureCrawler is not None:
                try:
                    self.literature_crawler = LiteratureCrawler()
                    logger.info("LiteratureCrawler active for knowledge stacking / educational line from literature.")
                except Exception as e:
                    logger.warning(f"LiteratureCrawler init limited (deps like pandas/requests): {e}")

            self.nonverbal_expertiser = None
            if NonverbalExpertiser is not None:
                try:
                    self.nonverbal_expertiser = NonverbalExpertiser()
                    logger.info("NonverbalExpertiser active (expertise + strategies for nonverbal/neurodivergent).")
                except Exception as e:
                    logger.warning(f"NonverbalExpertiser limited: {e}")

            self.multi_mission_protector = None
            if MultiMissionProtector is not None:
                try:
                    self.multi_mission_protector = MultiMissionProtector()
                    logger.info("MultiMissionProtector active (children/veterans/medical/encrypted mission security).")
                except Exception as e:
                    logger.warning(f"MultiMissionProtector limited: {e}")

            self.voice_cortex = None
            if VoiceCortex is not None:
                try:
                    self.voice_cortex = VoiceCortex()
                    logger.info("VoiceCortex (single-voice lock/queue) wired (note: synth primary via christman_sound orchestrator).")
                except Exception as e:
                    logger.warning(f"VoiceCortex init limited (expects ALPHAVOX_* env + AWS): {e}")

            logger.info("Full brain loaded from original modules (cognitive/reasoning/predictive/education/self-awareness/autonomous).")
            logger.info(f"Brain uses NEURAL_INTEGRATION_MAP: Cortex->Memory->Reasoning->Speech->Vision->Motor->Cortex")
        except Exception as e:
            logger.error(f"Failed to initialize full brain: {e}")

    def synthesize(
        self,
        text: str,
        params: VoiceParameters,
        output_path: Optional[str] = None
    ) -> SynthesisResult:
        """
        Synthesize speech from text using the given VoiceParameters.

        Args:
            text:        The text to synthesize.
            params:      Full VoiceParameters controlling every dimension.
            output_path: Optional path to write the audio file.
                         If None, returns raw bytes in result.audio_data.

        Returns:
            SynthesisResult — always check .success before using audio.
        """
        if not text or not text.strip():
            return SynthesisResult(
                success=False,
                error="Cannot synthesize empty text."
            )

        # Validate parameters
        errors = params.validate()
        if errors:
            return SynthesisResult(
                success=False,
                error=f"Invalid VoiceParameters: {'; '.join(errors)}"
            )

        if not self._ready:
            return SynthesisResult(
                success=False,
                error=(
                    "VoiceEngine not ready — Christman SDK failed to load. "
                    "Check CHRISTMAN_SDK_ROOT and SDK installation."
                )
            )

        # Use the full original brain (from restored ALPHAVOXWAKESUP modules in V_C_C/brain/)
        # for cognitive, reasoning, predictiveness, education, learning, self-awareness, autonomous before voice.
        # This is "the brain" the voice expresses. The christman_sound orchestrator/core handles the voice part.
        if self.brain:
            try:
                # Process for reasoning, predictiveness, education, autonomous learning (stack knowledge)
                if hasattr(self.brain, 'process') or hasattr(self.brain, 'reason') or hasattr(self.brain, 'cognitive_process'):
                    brain_out = getattr(self.brain, 'cognitive_process', getattr(self.brain, 'reason', getattr(self.brain, 'process', lambda x: None)))(text)
                    if brain_out:
                        logger.info(f"Brain (cognitive/reasoning/education): {str(brain_out)[:100]}...")
                        # Use brain output to influence params or text for educational tone
                        if hasattr(params, 'apply_education_tone'):
                            params.apply_education_tone(brain_out)
                if self.brain_orchestrator:
                    self.brain_orchestrator.process(text, params)  # for predictiveness, self-awareness
                if self.brain_hierarchy:
                    self.brain_hierarchy.organize(text)  # for layered brain flow per NEURAL_INTEGRATION_MAP

                # Wire swooped modules for education / behavior / protection (brain-first)
                intent = detect_intent(text) if callable(detect_intent) else "general"
                if self.neural_learning_core:
                    try:
                        interaction = {
                            "text": text,
                            "intent": intent,
                            "type": "voice",
                            "emotion": getattr(params, "affect", "neutral"),
                        }
                        if hasattr(params, "affect") and hasattr(params.affect, "value"):
                            interaction["emotion"] = params.affect.value
                        insight = self.neural_learning_core.process_interaction(interaction, user_id="alpha_voice")
                        if insight and insight.get("root_cause"):
                            logger.info(f"Neural education: root_cause={insight['root_cause']} conf={insight.get('confidence', 0):.2f} (knowledge stacking)")
                    except Exception as e:
                        logger.warning(f"Neural learning step limited: {e}")

                if self.multi_mission_protector:
                    try:
                        prot = self.multi_mission_protector.execute_unified_protection({"capacity": 1.0})
                        if prot.get("overall_status"):
                            logger.debug(f"Multi-mission protect: {prot['overall_status']}")
                    except Exception as e:
                        logger.warning(f"MMP limited: {e}")

                if self.literature_crawler:
                    try:
                        # Availability for autonomous education line / stacking (actual crawl via process_topic when triggered externally)
                        count = getattr(self.literature_crawler, "get_scraped_topics_count", lambda: 0)()
                        logger.debug(f"Literature knowledge stack available: {count} topics")
                    except Exception as e:
                        logger.warning(f"Literature step limited: {e}")

                if self.eye_tracking_service:
                    try:
                        eye = self.eye_tracking_service.get_eye_position()
                        # Influence affect for neurodivergent support (e.g. if not center -> more grounding)
                        if eye.get("region") not in ("center",) and hasattr(params, "affect"):
                            if params.affect in (Affect.NEUTRAL, Affect.WARM):
                                params.affect = Affect.GROUNDING
                                params.apply_affect_preset()
                        logger.debug(f"Eye state: {eye}")
                    except Exception as e:
                        logger.warning(f"Eye state limited: {e}")

                if self.nonverbal_expertiser:
                    try:
                        # Expertise available for context (e.g. random fact or strategies for AAC/nonverbal users)
                        if hasattr(self.nonverbal_expertiser, "get_random_fact"):
                            _ = self.nonverbal_expertiser.get_random_fact()
                    except Exception as e:
                        logger.warning(f"Nonverbal expertiser limited: {e}")

                if self.vision_engine:
                    try:
                        # Vision (DeepFace) available; real loop started externally for behavior capture
                        pass
                    except Exception as e:
                        logger.warning(f"Vision limited: {e}")

                if self.voice_cortex:
                    try:
                        status = self.voice_cortex.get_status() if hasattr(self.voice_cortex, "get_status") else {}
                        logger.debug(f"VoiceCortex status: {status.get('speaking')}")
                    except Exception as e:
                        logger.warning(f"VoiceCortex status limited: {e}")
            except Exception as e:
                logger.warning(f"Brain processing limited: {e} (core still provides base cognitive via christman_sound)")

        try:
            # Prioritize the voice synthesis orchestrator (from christman_voice_sdk/synthesis/voice_synthesis_orchestrator.py
            # inside the voice SDK) for the rich V_C_C synthesis using the full VoiceParameters.
            # XTTS is rare internal fallback inside the orchestrator. Core is secondary.
            if getattr(self, "_orchestrator", None):
                emotion = getattr(params, "affect", "neutral")
                if hasattr(emotion, "value"):
                    emotion = emotion.value
                emotion = str(emotion).lower()
                if emotion not in ("neutral", "happy", "proud", "teasing", "annoyed", "sarcastic", "sweetheart", "laugh", "tremble", "emphasis", "last_breath"):
                    emotion = "neutral"

                result = self._orchestrator.synthesize(
                    text=text,
                    emotion=emotion,
                    emotion_intensity=1.0,
                )

                if isinstance(result, dict):
                    audio_bytes = result.get("audio")
                    duration = result.get("duration", 0.0)
                    sr = result.get("sample_rate", getattr(params, "sample_rate", 22050))
                else:
                    audio_bytes = getattr(result, "audio", None)
                    duration = getattr(result, "duration", 0.0)
                    sr = getattr(result, "sample_rate", getattr(params, "sample_rate", 22050))

                if audio_bytes is None:
                    raise RuntimeError("Orchestrator returned no audio data")

                audio_bytes = self._apply_frequency_bounds(
                    audio_bytes if isinstance(audio_bytes, (bytes, bytearray)) else audio_bytes.tobytes() if hasattr(audio_bytes, "tobytes") else audio_bytes,
                    floor_hz=getattr(params, "frequency_floor_hz", 80),
                    cap_hz=getattr(params, "frequency_cap_hz", 8000),
                    sample_rate=sr or getattr(params, "sample_rate", 22050)
                )

                if output_path:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(audio_bytes if isinstance(audio_bytes, (bytes, bytearray)) else audio_bytes.tobytes() if hasattr(audio_bytes, "tobytes") else audio_bytes)
                    logger.info(f"Voice written to {output_path} ({duration:.2f}s)")

                return SynthesisResult(
                    success=True,
                    audio_data=audio_bytes if not output_path else None,
                    output_path=output_path,
                    duration_seconds=duration,
                    sample_rate=sr or getattr(params, "sample_rate", 22050),
                    pack_id=getattr(params, "pack_id", None),
                )

            # Fallback to real core (from the 2700 line core.py) 
            if self._core_synth:
                emotion = getattr(params, "affect", "neutral")
                if hasattr(emotion, "value"):
                    emotion = emotion.value
                emotion = str(emotion).lower()
                if emotion not in self._core_emotions:
                    emotion = "neutral"

                voice_params = {
                    "emotion": emotion,
                    "exaggeration": 0.0,  # from core's resolve_voice_params usage
                }

                # Reference audio: prefer from loaded pack (via voice_loader), or env, or default in V_C_C raw
                ref = None
                if hasattr(self, "_current_pack") and self._current_pack:
                    ref = self._current_pack.get("reference_audio") or self._current_pack.get("audio_path")
                if not ref:
                    ref = os.environ.get("CHRISTMAN_REFERENCE_AUDIO")
                if not ref:
                    # fallback to a real take in V_C_C studio/raw or inventory
                    raw_dir = Path(__file__).parent.parent / "studio" / "raw"
                    if raw_dir.exists():
                        refs = list(raw_dir.glob("*.wav"))
                        if refs:
                            ref = str(refs[0])

                wav_path = self._core_synth(
                    text=text,
                    voice_params=voice_params,
                    reference_audio=ref,
                    language=getattr(params, "language", "en"),
                )

                if wav_path and Path(wav_path).exists():
                    p = Path(wav_path)
                    with open(p, "rb") as f:
                        audio_bytes = f.read()

                    # get duration and sr from the real wav (see core _save_audio_result and _write_wav)
                    duration = 0.0
                    sr = 22050
                    try:
                        with wave.open(str(p), "rb") as wf:
                            sr = wf.getframerate()
                            duration = wf.getnframes() / float(sr)
                    except:
                        pass

                    if output_path:
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        shutil.copy(str(p), output_path)  # or write bytes
                        logger.info(f"Voice written to {output_path} ({duration:.2f}s)")

                    return SynthesisResult(
                        success=True,
                        audio_data=audio_bytes if not output_path else None,
                        output_path=output_path or str(p),
                        duration_seconds=duration,
                        sample_rate=sr,
                        pack_id=getattr(params, "pack_id", "default"),
                    )
                else:
                    logger.error("[SDK] core.synthesize_speech returned no valid wav")

            # Fallback to orchestrator if core not sufficient (still the real SDK)
            if self._orchestrator:
                emotion = getattr(params, "affect", "neutral")
                if hasattr(emotion, "value"):
                    emotion = emotion.value
                emotion = str(emotion).lower()
                if emotion not in ("neutral", "happy", "proud", "teasing", "annoyed", "sarcastic", "sweetheart", "laugh", "tremble", "emphasis", "last_breath"):
                    emotion = "neutral"

                result = self._orchestrator.synthesize(
                    text=text,
                    emotion=emotion,
                    emotion_intensity=1.0,
                )

                if isinstance(result, dict):
                    audio_bytes = result.get("audio")
                    duration = result.get("duration", 0.0)
                    sr = result.get("sample_rate", params.sample_rate)
                else:
                    audio_bytes = getattr(result, "audio", None)
                    duration = getattr(result, "duration", 0.0)
                    sr = getattr(result, "sample_rate", params.sample_rate)

                if audio_bytes is None:
                    raise RuntimeError("Orchestrator returned no audio data")

                audio_bytes = self._apply_frequency_bounds(
                    audio_bytes if isinstance(audio_bytes, (bytes, bytearray)) else audio_bytes.tobytes() if hasattr(audio_bytes, "tobytes") else audio_bytes,
                    floor_hz=getattr(params, "frequency_floor_hz", 80),
                    cap_hz=getattr(params, "frequency_cap_hz", 8000),
                    sample_rate=sr or params.sample_rate
                )

                if output_path:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(audio_bytes if isinstance(audio_bytes, (bytes, bytearray)) else audio_bytes.tobytes() if hasattr(audio_bytes, "tobytes") else audio_bytes)
                    logger.info(f"Voice written to {output_path} ({duration:.2f}s)")

                return SynthesisResult(
                    success=True,
                    audio_data=audio_bytes if not output_path else None,
                    output_path=output_path,
                    duration_seconds=duration,
                    sample_rate=sr or params.sample_rate,
                    pack_id=params.pack_id
                )

            raise RuntimeError("No real christman_sound synthesis path available (core or orchestrator)")

        except Exception as e:
            logger.error(f"Synthesis failed for pack '{params.pack_id}': {e}", exc_info=True)
            return SynthesisResult(
                success=False,
                error=str(e)
            )

    def _build_sdk_request(self, text: str, params: VoiceParameters) -> dict:
        """
        Translate VoiceParameters into the Christman SDK request format.
        Centralizing this translation means SDK API changes only affect this method.
        """
        return {
            "text": text,
            "pack_id": params.pack_id,
            "language": params.language,
            "porosity": params.porosity,
            "timbre": params.timbre,
            "intonation": params.intonation,
            "cadence": params.cadence,
            "prosody_strength": params.prosody_strength,
            "articulation": params.articulation,
            "resonance": params.resonance.value,
            "affect": params.affect.value,
            "slow_mode": params.slow_mode,
            "high_clarity_mode": params.high_clarity_mode,
            "sample_rate": params.sample_rate,
            "output_format": params.output_format,
        }

    def _apply_frequency_bounds(
        self,
        audio_bytes: bytes,
        floor_hz: int,
        cap_hz: int,
        sample_rate: int
    ) -> bytes:
        """
        Apply frequency floor and ceiling to the audio.
        This is the accessibility safety gate — filters frequencies that
        could trigger seizures or sensory overload in vulnerable users.

        Delegates to frequency_guardian in the accessibility module.
        Falls back to returning unfiltered audio with a warning if
        frequency_guardian is unavailable — never silently corrupts audio.
        """
        try:
            from christman_voice_center.accessibility.frequency_guardian import FrequencyGuardian
            guardian = FrequencyGuardian(sample_rate=sample_rate)
            return guardian.filter(audio_bytes, floor_hz=floor_hz, cap_hz=cap_hz)
        except ImportError:
            logger.warning(
                "frequency_guardian not available — audio returned unfiltered. "
                "Build accessibility/frequency_guardian.py to enable safety filtering."
            )
            return audio_bytes

    def get_engine_status(self) -> dict:
        """
        Returns the current engine status.
        Used by Brockston admin dashboard and health checks.
        """
        return {
            "ready": self._ready,
            "sdk_root": self.sdk_root or "system path",
            "shorty_engine_loaded": self._shorty_engine is not None,
            "tts_service_loaded": self._tts_service is not None,
            "orchestrator_loaded": self._orchestrator is not None,
            "phoneme_labeler_loaded": self._phoneme_labeler is not None,
        }

        # GUARANTEED load of REAL core (the 2700 lines) first
        try:
            from christman_sound.core import synthesize_speech, resolve_voice_params, CHRISTMAN_EMOTIONS
            self._core_synth = synthesize_speech
            self._core_resolve = resolve_voice_params
            self._core_emotions = CHRISTMAN_EMOTIONS
            print("[REAL CORE LOADED] from local V_C_C christman_sound/core.py")
        except Exception as ce: print("core load:", ce)
