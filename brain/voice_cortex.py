"""
© 2025 The Christman AI Project. All rights reserved.

VOICE CORTEX - THE ONE TRUE VOICE CONTROLLER
Single point of control for ALL AlphaVox speech output

This module ensures only ONE voice can speak at a time.
All other modules must route through this cortex.

NO MORE VOICE CHAOS.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional
import uuid
import io
from pydub import AudioSegment
import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet, InvalidToken

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
logger.propagate = False

ENCRYPTION_KEY = os.getenv("ALPHAVOX_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise ValueError("ALPHAVOX_ENCRYPTION_KEY missing")
try:
    cipher = Fernet(ENCRYPTION_KEY.encode("utf-8"))
except Exception:
    raise ValueError("ALPHAVOX_ENCRYPTION_KEY is not a valid Fernet key")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("ALPHAVOX_S3_BUCKET")
KMS_KEY_ID = os.getenv("ALPHAVOX_KMS_KEY_ID")
if not KMS_KEY_ID:
    raise ValueError("ALPHAVOX_KMS_KEY_ID missing")

polly_client = boto3.client("polly", region_name=AWS_REGION)
s3_client = boto3.client("s3", region_name=AWS_REGION)

class VoiceCortex:
    """
    The One True Voice Controller

    Ensures only one voice output at a time.
    All other modules must route through this cortex.
    """

    def __init__(self):
        self._voice_lock = threading.Lock()
        self._current_speaker = None
        self._speaking = False
        self._voice_queue = []
        self._initialized = False
        self._active_providers = {}

        # Load configuration
        self._load_config()

        # Initialize the primary TTS provider
        self._init_primary_provider()

        logger.info("🎯 Voice Cortex initialized - Single voice control active")

    def _load_config(self):
        """Load voice configuration"""
        try:
            config_path = "voice_cortex_config.json"
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "primary_provider": "aws_polly",
                    "fallback_provider": "basic_print",
                    "default_voice": "Matthew",
                    "default_emotion": "neutral",
                    "max_queue_size": 10,
                    "voice_timeout": 30,
                }
                self._save_config()
        except Exception as e:
            logger.error("Config load failed")
            self.config = {"primary_provider": "aws_polly"}

    def _save_config(self):
        """Save voice configuration"""
        try:
            with open("voice_cortex_config.json", "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error("Config save failed")

    def _init_primary_provider(self):
        """Initialize the primary TTS provider"""
        try:
            self._primary_tts = self._aws_polly_speak
            self._provider_name = "aws_polly"
            logger.info("✅ Primary provider: AWS Polly")
        except ImportError:
            self._primary_tts = self._basic_speak
            self._provider_name = "basic_print"
            logger.warning("⚠️ No TTS providers available, using print(fallback)")

        self._initialized = True

    def _aws_polly_speak(self, text: str, voice_id: str, emotion: str) -> str:
        """AWS Polly TTS with normalization and S3 upload"""
        try:
            response = polly_client.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="neural"
            )
            audio_data = response["AudioStream"].read()
            audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            audio = audio.normalize()
            body_bytes = audio.export(format="mp3").read()
            key = f"audio/{uuid.uuid4()}.mp3"
            s3_client.put_object(
                Body=body_bytes,
                Bucket=S3_BUCKET,
                Key=key,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=KMS_KEY_ID,
                ContentType="audio/mpeg"
            )
            return s3_client.generate_presigned_url("get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=300)
        except ClientError as e:
            logger.error("AWS Polly error")
            return ""

    def _basic_speak(self, text: str, **kwargs):
        """Fallback when no TTS is available"""
        print(f"[VOICE CORTEX]: {text}")
        time.sleep(len(text) * 0.05)  # Simulate speaking time
        return ""

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        emotion: str = "neutral",
        priority: int = 1,
    ) -> bool:
        """
        THE ONLY SPEAK FUNCTION THAT SHOULD BE USED

        Args:
            text: Text to speak
            voice: Voice ID (optional)
            emotion: Emotion for voice (optional)
            priority: Priority level (1=highest, 10=lowest)

        Returns:
            bool: True if speech was successful
        """
        if not text or text.strip() == "":
            return False

        # Clean the text
        text = text.strip()

        with self._voice_lock:
            if self._speaking:
                logger.info(f"🔒 Voice busy, queueing: {text[:50]}...")
                self._add_to_queue(text, voice, emotion, priority)
                return False

            self._speaking = True
            self._current_speaker = threading.current_thread().name

            try:
                # Log the speech attempt
                logger.info(f"🗣️ Speaking ({self._provider_name}): {text[:100]}...")

                # Use the configured voice and emotion
                final_voice = voice or self.config.get("default_voice", "Matthew")
                final_emotion = emotion or self.config.get("default_emotion", "neutral")

                # Call the primary TTS provider
                audio_url = self._primary_tts(text, final_voice, final_emotion)

                if audio_url:
                    logger.info(f"✅ Speech completed: {text[:50]}...")
                    return True
                else:
                    return False

            except Exception as e:
                logger.error("Speech failed")
                return False

            finally:
                self._speaking = False
                self._current_speaker = None
                self._process_queue()

    def _add_to_queue(self, text: str, voice: Optional[str], emotion: Optional[str], priority: int):
        """Add speech request to queue"""
        max_queue_size = int(self.config.get("max_queue_size", 10))
        if len(self._voice_queue) >= max_queue_size:
            logger.warning("🚫 Voice queue full, dropping oldest request")
            self._voice_queue.pop(0)

        self._voice_queue.append(
            {
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "priority": priority,
                "timestamp": time.time(),
            }
        )

        # Sort by priority
        self._voice_queue.sort(key=lambda x: x["priority"])

    def _process_queue(self):
        """Process the next item in the voice queue"""
        if not self._voice_queue:
            return

        next_request = self._voice_queue.pop(0)

        # Check if request is too old
        voice_timeout = int(self.config.get("voice_timeout", 30))
        if time.time() - next_request["timestamp"] > voice_timeout:
            logger.warning("🕐 Dropping old voice request")
            self._process_queue()  # Try the next one
            return

        # Speak the queued request
        threading.Thread(
            target=self.speak,
            args=(next_request["text"], next_request["voice"], next_request["emotion"], next_request["priority"]),
            daemon=True,
        ).start()

    def is_speaking(self) -> bool:
        """Check if voice is currently active"""
        return self._speaking

    def stop_current_speech(self):
        """Stop current speech (if possible)"""
        with self._voice_lock:
            if self._speaking:
                logger.info("🛑 Stopping current speech")
                self._speaking = False
                self._current_speaker = None

    def clear_queue(self):
        """Clear all queued speech"""
        with self._voice_lock:
            self._voice_queue.clear()
            logger.info("🗑️ Voice queue cleared")

    def get_status(self) -> Dict[str, Any]:
        """Get current voice status"""
        return {
            "speaking": self._speaking,
            "current_speaker": self._current_speaker,
            "queue_length": len(self._voice_queue),
            "provider": self._provider_name,
            "initialized": self._initialized,
        }


# Create the singleton instance
voice_cortex = VoiceCortex()


def speak(
    text: str,
    voice: Optional[str] = None,
    emotion: Optional[str] = None,
    priority: int = 1,
) -> bool:
    """
    GLOBAL SPEAK FUNCTION - USE THIS EVERYWHERE

    This is the ONLY speak function that should be called.
    All other modules should import and use this function.
    """
    return voice_cortex.speak(text, voice, emotion or "neutral", priority)


def is_speaking() -> bool:
    """Check if voice is currently active"""
    return voice_cortex.is_speaking()


def stop_speech():
    """Stop current speech"""
    voice_cortex.stop_current_speech()


def clear_voice_queue():
    """Clear all queued speech"""
    voice_cortex.clear_queue()


def get_voice_status() -> Dict[str, Any]:
    """Get current voice status"""
    return voice_cortex.get_status()


if __name__ == "__main__":
    # Test the voice cortex
    print("🧪 Testing Voice Cortex...")

    status = get_voice_status()
    print(f"Status: {status}")

    # Test speech
    speak("Voice Cortex test - this should be the only voice you hear")

    # Test multiple rapid calls
    speak("First message", priority=1)
    speak("Second message", priority=2)
    speak("Third message", priority=1)

    time.sleep(5)

    final_status = get_voice_status()
    print(f"Final status: {final_status}")

    print("✅ Voice Cortex test complete")

__all__ = ['speak', 'is_speaking', 'stop_speech', 'clear_voice_queue', 'get_voice_status', 'VoiceCortex']
