# ULTRON — Futuristic Voice HUD

ULTRON is a personal AI desktop agent with a holographic, face-free energy orb in the center of the GUI. The orb reacts to the three important voice states:

- **LISTENING** — microphone active; the orb and spectrum wake up.
- **THINKING** — Ultron is waiting for the AI provider to answer.
- **SPEAKING** — the orb, filaments, particles, rings, and spectrum pulse with the TTS speech envelope.

The current central visual is deliberately an **energy orb/core**, not an Ultron face.

## Windows quick start

1. Install Python 3.10+ and make sure `python` works in PowerShell.
2. Extract this folder.
3. Double-click **`start_ultron_gui.bat`**.
4. On first run, the launcher creates `.venv`, installs the dependencies, and creates `.env` from `.env.example`.
5. Add at least one AI provider key in `.env` (or use Ollama), save it, and run the launcher again.

The launcher installs the voice stack automatically.

## Voice

The GUI uses:

- `sounddevice` for microphone capture
- `SpeechRecognition` + Google's speech recognizer for speech-to-text
- `pyttsx3` for Windows system text-to-speech (SAPI)
- `comtypes` on Windows for the SAPI bridge

**No separate text-to-speech app is required.** Windows supplies the speech engine used by `pyttsx3`.

Speech recognition via Google requires an internet connection. The microphone must also be available to Windows and the app must be allowed to use it in Windows Privacy settings.

### Voice controls

- Click **LISTEN [CTRL+SPACE]** to speak one command.
- Press **Ctrl+Space** to listen.
- Press **Esc** to stop current speech/listening.
- The orange/cyan spectrum sits immediately above the state label.

The center status line below the spectrum is updated to **LISTENING**, **THINKING**, or **SPEAKING**.

## Optional local AI

Install Ollama separately if you want a local brain:

1. Install Ollama for Windows.
2. Run `ollama pull llama3.2`.
3. Set `AI_PROVIDER=ollama` in `.env`.

Voice STT is still provided by Google unless you later replace it with an offline STT engine.

## Current project files

- `gui.py` — futuristic Tkinter HUD and GUI/voice state integration
- `voice.py` — microphone STT and Windows TTS
- `main.py` — terminal mode / terminal voice mode
- `brain.py` — AI provider and tool routing
- `config.py` — `.env` configuration
- `tools.py` and `actions/` — computer/automation tools

## Testing the voice stack

After installation, you can run:

```powershell
.venv\Scripts\activate
python -c "import sounddevice, speech_recognition, pyttsx3; print('VOICE IMPORTS OK')"
```

For a microphone/device listing:

```powershell
python -c "import sounddevice as sd; print(sd.query_devices())"
```

## Important

Keep `.env` private. It can contain API keys, email credentials, and phone credentials.

## Voice modes

The GUI has two microphone modes:

- **MIC · ON** (default): continuous listening. Any recognized utterance is sent to the active AI brain.
- **STANDBY · ON**: microphone remains active, but ordinary speech is ignored until a wake phrase is heard: **"wake up"**, **"wake up Ultron"**, or **"Ultron"**. If the wake phrase is followed by a command, the command is processed immediately. If it is only a wake phrase, Ultron says "I'm listening." and waits for the next command.
- **STOP SPEECH** / **Esc**: interrupts current speech/listening and then returns to the current microphone mode; it does not turn the microphone off.

The controls are placed directly below the command-entry box. The central orb rotates calmly when there is no audio and reacts to live microphone audio while you speak or to the TTS speech envelope while Ultron speaks.

## Voice reliability fix

The TTS engine is now created and owned by the dedicated TTS worker thread. This is important on Windows because pyttsx3 uses SAPI/COM, which is thread-sensitive. STT and TTS also use separate stop events, so stopping speech cannot accidentally cancel the microphone listener.

Normal mode is continuous listening by default. After every completed response, ULTRON returns to listening automatically. Standby mode is wake-word-only.

## ULTRON Neural Voice

ULTRON uses ElevenLabs for speech output. Add `ELEVENLABS_API_KEY` and the selected `ULTRON_VOICE_ID` to `.env`. The default voice ID is `Z3fcrqgcBXM6sVM29Z80`. Voice output uses `eleven_flash_v2_5` for lower latency.

Run `voice_check.py` to verify the microphone, ElevenLabs connection and local audio output.
