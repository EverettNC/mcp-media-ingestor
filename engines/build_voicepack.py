#!/usr/bin/env python3
"""
Build a .voicepack from a reference audio sample using the REAL local christman_sound
(core.py + the 81 modules under christman_voice_sdk/ as you listed: timbre/voicepack + timbre_modeler,
audio processor, etc.).

This is how we start making the "thousands" of voicepacks.
Drop clean long references (like your AlphaVox2.mp3 converted to WAV), run this, get a pack.

Usage (after installing heavy deps in the python/venv):
  python engines/build_voicepack.py /path/to/ref.wav alphavox2 "My description"

Requires in the env running it:
  torch, torchaudio, speechbrain (for x-vector), numpy, soundfile/pydub (for processor).
The V_C_C venv may need: pip install torch torchaudio speechbrain

The resulting pack goes to inventory/packs/<pack_id>/<pack_id>.voicepack
Then voice_loader + orchestrator in the engine can use it for real synthesis (not pitiful TTS).
"""
import sys
import os
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone

# Make sure we use the LOCAL christman_sound in this V_C_C (the one with the exact tree you listed)
VCC_ROOT = Path(__file__).resolve().parent.parent
if str(VCC_ROOT) not in sys.path:
    sys.path.insert(0, str(VCC_ROOT))

import christman_sound  # the local copy
print(f"Using REAL local christman_sound: {christman_sound.__file__}")

from christman_sound.christman_voice_sdk.timbre.timbre_modeler import TimbreModeler
from christman_sound.christman_voice_sdk.timbre.voicepack import VoicepackBuilder, VoicepackMetadata
from christman_sound.christman_voice_sdk.timbre.audio_processor import AudioProcessor  # the one in timbre or main
from christman_sound.christman_voice_sdk.audio.config import Tier

def main():
    parser = argparse.ArgumentParser(description="Build voicepack from reference using real christman_sound SDK")
    parser.add_argument("reference_wav", help="Path to clean reference WAV (long sample best for averaging embeddings)")
    parser.add_argument("pack_id", help="Short id e.g. alphavox2")
    parser.add_argument("description", nargs="?", default="Built from user-provided reference", help="Short desc for metadata")
    args = parser.parse_args()

    ref = Path(args.reference_wav).resolve()
    if not ref.exists():
        print(f"ERROR: reference not found: {ref}")
        sys.exit(1)

    pack_dir = VCC_ROOT / "inventory" / "packs" / args.pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_path = pack_dir / f"{args.pack_id}.voicepack"

    print(f"Building voicepack for {args.pack_id} from {ref}")
    print(f"Using local SDK under christman_sound/christman_voice_sdk/ (timbre, audio, etc.)")

    # Process the reference (chunks it, normalizes)
    # Use PREMIUM tier for better processing
    try:
        processor = AudioProcessor(tier=Tier.PREMIUM)
        segments = processor.process_file(str(ref))
        print(f"Processed into {len(segments)} segments")
    except Exception as e:
        print(f"Processor failed (may need more deps): {e}")
        segments = []  # fallback stub for when no torch

    if not segments:
        print("No segments (likely missing torch/speechbrain). Creating minimal pack with the raw ref as reference_audio only.")
        # Still build a stub pack so the pipeline works; real embedding needs the model.
        profile = None
    else:
        modeler = TimbreModeler(device="auto")
        profile = modeler.build_voice_profile(segments)
        print("Voice profile (x-vector etc.) built from segments.")

    metadata = VoicepackMetadata(
        name=args.pack_id,
        tier="elite",
        gender="unknown",  # fill from your knowledge of the sample
        age_range="unknown",
        training_hours=ref.stat().st_size / (352000 / 8 / 3600) if ref.suffix == '.wav' else 0.1,  # rough
        sample_count=len(segments) or 1,
        emotions=["neutral", "happy", "proud", "teasing", "annoyed", "sarcastic", "sweetheart", "laugh", "tremble", "emphasis", "last_breath"],
        created_at=datetime.now(timezone.utc).isoformat(),
        description=args.description,
        source_file=str(ref),
    )

    builder = VoicepackBuilder(output_dir=pack_dir)
    created = builder.build(
        name=args.pack_id,
        voice_profile=profile,
        reference_audio=[ref],
        metadata=metadata,
        compress=True,
        extras={"built_by": "voice_creation_center_from_mp3", "original_mp3": "/Users/EverettN/Downloads/AlphaVox2.mp3"}
    )

    print(f"\n✅ Voicepack created: {created}")
    print(f"   Size: {created.stat().st_size} bytes")
    print(f"   Load it in the engine with voice_loader.load_pack('{args.pack_id}') then orchestrator.load_voicepack(...)")
    print(f"   Then synthesize with the rich VoiceParameters (porosity, timbre, affect etc).")
    print(f"\nWhy not thousands yet? Each one needs clean consented source audio (like this long sample),")
    print(f"the ML deps for embeddings (torch + speechbrain), the validation/approval flow in live_studio,")
    print(f"and the full pipeline (ingestor -> registrar -> this builder) wired to the real orchestrator.")
    print(f"We just got the imports, paths, orchestrator priority, and sound_package + player integration working.")
    print(f"Now drop more samples and run this for each.")

if __name__ == "__main__":
    main()
