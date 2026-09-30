"""Check ULTRON microphone, STT and ElevenLabs TTS configuration."""
from __future__ import annotations

import os

from config import CFG  # loads .env


def main() -> int:
    print("ULTRON VOICE CHECK")

    try:
        import sounddevice as sd
        import speech_recognition as sr
        import numpy as np
        from elevenlabs.client import ElevenLabs
    except Exception as exc:
        print(f"IMPORT ERROR: {exc}")
        print("Run: pip install -r requirements-voice.txt")
        return 1

    print("[OK] sounddevice")
    print("[OK] SpeechRecognition")
    print("[OK] elevenlabs")

    print("\nDEFAULT MICROPHONE")
    try:
        print(sd.query_devices(kind="input"))
    except Exception as exc:
        print(f"Could not query microphone: {exc}")

    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ULTRON_VOICE_ID", "Z3fcrqgcBXM6sVM29Z80").strip()
    if not api_key:
        print("\n[WARN] ELEVENLABS_API_KEY is missing from .env")
        print("Add your ElevenLabs API key, then run this check again.")
        return 1

    print(f"\nULTRON VOICE ID: {voice_id}")
    print("[OK] ElevenLabs API key found")

    try:
        client = ElevenLabs(api_key=api_key)
        response = client.text_to_speech.convert(
            voice_id=voice_id,
            text="Ultron voice link test successful.",
            model_id=os.getenv("ULTRON_TTS_MODEL", "eleven_flash_v2_5"),
            output_format="pcm_16000",
        )
        audio = b"".join(chunk for chunk in response if chunk)
        if not audio:
            raise RuntimeError("ElevenLabs returned empty audio.")
        print(f"[OK] ElevenLabs generated {len(audio):,} bytes of audio")
    except Exception as exc:
        print(f"ELEVENLABS ERROR: {exc}")
        return 1

    try:
        sd.check_output_settings(samplerate=16_000, channels=1, dtype="int16")
        pcm = np.frombuffer(audio, dtype=np.int16)
        print(f"[OK] sounddevice output ready (16 kHz PCM, {pcm.size:,} samples)")
    except Exception as exc:
        print(f"AUDIO OUTPUT ERROR: {exc}")
        return 1

    _ = sr.Recognizer()
    print("[OK] STT engine can be created")
    print("\nVOICE CHECK COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
