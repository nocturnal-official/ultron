"""ULTRON voice I/O.

STT: sounddevice + SpeechRecognition/Google Web Speech API.
TTS: ElevenLabs neural TTS using the user's selected ULTRON voice.

The TTS worker downloads generated audio, plays it locally with pygame and
keeps ownership of the playback state on one thread. The GUI receives only
small callbacks, so Tkinter is never touched from the audio thread.
"""
from __future__ import annotations

import io
import os
import queue
import re
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class Voice:
    SAMPLE_RATE = 16_000
    CHANNELS = 1
    BLOCK_MS = 80
    END_SILENCE_SECONDS = 3.0
    MAX_PHRASE_SECONDS = 30.0

    DEFAULT_VOICE_ID = "Z3fcrqgcBXM6sVM29Z80"
    DEFAULT_MODEL = "eleven_flash_v2_5"
    DEFAULT_OUTPUT_FORMAT = "pcm_16000"

    def __init__(
        self,
        on_listening: Optional[Callable[[], None]] = None,
        on_speaking: Optional[Callable[[], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
    ):
        import speech_recognition as sr

        self.sr = sr
        self.rec = sr.Recognizer()
        self.on_listening = on_listening
        self.on_speaking = on_speaking
        self.on_finished = on_finished
        self.on_level = on_level

        self._listen_stop = threading.Event()
        self._speech_stop = threading.Event()
        self._closed = threading.Event()
        self._listening = False
        self._speaking = False

        self.voice_id = os.getenv("ULTRON_VOICE_ID", self.DEFAULT_VOICE_ID).strip() or self.DEFAULT_VOICE_ID
        self.model_id = os.getenv("ULTRON_TTS_MODEL", self.DEFAULT_MODEL).strip() or self.DEFAULT_MODEL
        # Playback is intentionally raw PCM through sounddevice; compressed MP3
        # output would require a separate decoder and is not needed here.
        self.output_format = "pcm_16000"
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()

        self._tts_queue: queue.Queue = queue.Queue()
        self._tts_ready = threading.Event()
        self._tts_error: Optional[str] = None
        self._audio_ready = False
        self._client = None

        self._tts_thread = threading.Thread(
            target=self._tts_worker,
            name="ultron-elevenlabs-tts",
            daemon=True,
        )
        self._tts_thread.start()
        self._tts_ready.wait(timeout=8.0)
        if not self._tts_ready.is_set():
            raise RuntimeError("ElevenLabs TTS initialisation timed out.")
        if self._tts_error:
            raise RuntimeError(self._tts_error)

    @property
    def is_listening(self):
        return self._listening

    @property
    def is_speaking(self):
        return self._speaking

    @property
    def tts_error(self):
        return self._tts_error

    def _safe(self, callback, *args):
        if not callback:
            return
        try:
            callback(*args)
        except Exception:
            pass

    def _tts_worker(self):
        """Own the ElevenLabs client and sounddevice playback on one thread."""
        try:
            if not self.api_key:
                raise RuntimeError(
                    "ELEVENLABS_API_KEY is missing from .env. "
                    "Create an ElevenLabs API key and add it to the project .env."
                )

            from elevenlabs import VoiceSettings
            from elevenlabs.client import ElevenLabs

            self._client = ElevenLabs(api_key=self.api_key)
            # TTS playback uses sounddevice, so pygame is NOT required.
            self._voice_settings_cls = VoiceSettings
            self._audio_ready = True
            self._tts_ready.set()
        except Exception as exc:
            self._tts_error = str(exc)
            self._tts_ready.set()
            return

        while not self._closed.is_set():
            try:
                item = self._tts_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                break

            text, done = item
            if self._closed.is_set():
                done.set()
                continue

            self._speech_stop.clear()
            self._speaking = True
            self._safe(self.on_speaking)

            try:
                response = self._client.text_to_speech.convert(
                    voice_id=self.voice_id,
                    text=text,
                    model_id=self.model_id,
                    output_format=self.output_format,
                    voice_settings=self._voice_settings_cls(
                        stability=0.55,
                        similarity_boost=0.88,
                        style=0.22,
                        use_speaker_boost=True,
                        speed=0.94,
                    ),
                )

                audio = b"".join(chunk for chunk in response if chunk)
                if not audio:
                    raise RuntimeError("ElevenLabs returned empty audio.")

                if self._speech_stop.is_set() or self._closed.is_set():
                    continue

                # ElevenLabs pcm_16000 is raw signed 16-bit PCM. Play it
                # directly with sounddevice; this avoids pygame entirely and
                # works cleanly on modern Python versions including 3.14.
                pcm = np.frombuffer(audio, dtype=np.int16)
                if pcm.size == 0:
                    raise RuntimeError("ElevenLabs returned empty PCM audio.")

                sd.play(pcm, samplerate=16_000, blocking=False)

                # Animate the orb while the real generated audio is playing.
                # The visual envelope follows the current playback position.
                phase = 0.0
                while sd.get_stream() is not None and sd.get_stream().active:
                    if self._speech_stop.is_set() or self._closed.is_set():
                        sd.stop()
                        break
                    phase += 0.18
                    # Use a small moving envelope so the core remains alive
                    # even during quieter syllables.
                    level = 0.30 + 0.25 * abs(np.sin(phase * 1.7)) + 0.18 * abs(np.sin(phase * 4.3))
                    self._safe(self.on_level, min(1.0, level))
                    time.sleep(0.045)

            except Exception as exc:
                self._tts_error = str(exc)
                self._safe(self.on_level, 0.0)
            finally:
                try:
                    sd.stop()
                except Exception:
                    pass
                self._speaking = False
                self._safe(self.on_level, 0.0)
                self._safe(self.on_finished)
                done.set()

        try:
            sd.stop()
        except Exception:
            pass

    def listen(self, timeout: float = 4.0, phrase_time_limit: float = 30.0) -> Optional[str]:
        """Capture speech and wait for 3 seconds of silence before recognition."""
        self._listen_stop.clear()
        self._listening = True
        self._safe(self.on_listening)

        block_frames = int(self.SAMPLE_RATE * self.BLOCK_MS / 1000)
        calibration_blocks = max(1, int(0.7 * self.SAMPLE_RATE / block_frames))
        noise_rms = []
        chunks = []
        speech_started = False
        silence_blocks = 0
        end_silence_blocks = max(1, int(self.END_SILENCE_SECONDS * 1000 / self.BLOCK_MS))
        max_wait_blocks = max(1, int(timeout * 1000 / self.BLOCK_MS))
        max_speech_seconds = min(float(phrase_time_limit), self.MAX_PHRASE_SECONDS)
        max_speech_blocks = max(1, int(max_speech_seconds * 1000 / self.BLOCK_MS))
        wait_blocks = 0
        speech_blocks = 0
        threshold = 0.015

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="int16",
                blocksize=block_frames,
            ) as stream:
                for _ in range(max_wait_blocks + max_speech_blocks):
                    if self._listen_stop.is_set() or self._closed.is_set():
                        return None

                    data, _overflowed = stream.read(block_frames)
                    block = np.asarray(data[:, 0], dtype=np.int16).copy()
                    rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2) + 1e-9) / 32768.0)
                    self._safe(self.on_level, min(1.0, rms * 20.0))

                    if not speech_started:
                        noise_rms.append(rms)
                        if len(noise_rms) >= calibration_blocks:
                            baseline = float(np.median(noise_rms))
                            threshold = max(0.008, min(0.12, baseline * 3.0 + 0.004))
                        else:
                            threshold = 0.015

                        wait_blocks += 1
                        if rms > threshold:
                            speech_started = True
                            chunks.append(block)
                            speech_blocks = 1
                        elif wait_blocks >= max_wait_blocks:
                            break
                        continue

                    chunks.append(block)
                    speech_blocks += 1
                    silence_blocks = silence_blocks + 1 if rms < max(0.007, threshold * 0.70) else 0

                    # IMPORTANT: the brain does not receive the command until
                    # the full 3-second pause has elapsed.
                    if silence_blocks >= end_silence_blocks or speech_blocks >= max_speech_blocks:
                        break
        finally:
            self._listening = False
            self._safe(self.on_level, 0.0)

        if self._listen_stop.is_set() or not chunks:
            return None

        raw = np.concatenate(chunks).astype(np.int16).tobytes()
        try:
            audio = self.sr.AudioData(raw, self.SAMPLE_RATE, 2)
            text = self.rec.recognize_google(audio)
        except self.sr.UnknownValueError:
            return None
        except self.sr.RequestError as exc:
            raise RuntimeError("Speech recognition could not reach Google. Check your internet connection.") from exc
        return text.strip() or None

    def stop_listening(self):
        self._listen_stop.set()

    def speak(self, text: str):
        """Generate and play one ElevenLabs utterance, then return when finished."""
        if not text or self._closed.is_set():
            return
        if not self._tts_ready.wait(timeout=8.0):
            raise RuntimeError("ElevenLabs TTS did not initialise in time.")
        if self._client is None or not self._audio_ready:
            raise RuntimeError(self._tts_error or "ElevenLabs TTS could not initialise.")

        clean = re.sub(r"https?://\S+", "link", str(text))
        clean = re.sub(r"[*_#`>\[\]]", "", clean)[:1800].strip()
        if not clean:
            return

        self._tts_error = None
        done = threading.Event()
        self._tts_queue.put((clean, done))
        done.wait()

        if self._tts_error and not self._closed.is_set():
            # The GUI will log this; don't crash the voice loop.
            raise RuntimeError(self._tts_error)

    def stop_speaking(self):
        self._speech_stop.set()
        try:
            sd.stop()
        except Exception:
            pass

    def close(self):
        self._closed.set()
        self._listen_stop.set()
        self._speech_stop.set()
        try:
            sd.stop()
        except Exception:
            pass
        try:
            self._tts_queue.put_nowait(None)
        except Exception:
            pass
