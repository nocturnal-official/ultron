"""Loads settings from the .env file next to this script."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv missing -> fall back to real environment variables
    def load_dotenv(*_a, **_k):
        return False

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    def __init__(self):
        self.reload()

    def reload(self):
        load_dotenv(BASE_DIR / ".env", override=True)

        # ---- AI brain ----
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-5").strip()

        # ---- Local model (Ollama / LM Studio) ----
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").strip().rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2").strip()
        self.ollama_vision_model = os.getenv("OLLAMA_VISION_MODEL", "").strip()

        provider = os.getenv("AI_PROVIDER", "").strip().lower()
        if provider in ("claude", "anthropic"):
            provider = "anthropic"
        elif provider in ("openai", "chatgpt", "gpt"):
            provider = "openai"
        elif provider in ("ollama", "local", "lmstudio"):
            provider = "ollama"
        else:  # auto-detect from whichever key is present
            provider = ("anthropic" if self.anthropic_api_key
                        else "openai" if self.openai_api_key else "")
        self.provider = provider

        # ---- Email (Gmail by default) ----
        self.email_address = os.getenv("EMAIL_ADDRESS", "").strip()
        self.email_password = os.getenv("EMAIL_APP_PASSWORD", "").strip().replace(" ", "")
        self.email_display_name = os.getenv("EMAIL_DISPLAY_NAME", "").strip()
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "465") or 465)
        self.imap_host = os.getenv("IMAP_HOST", "imap.gmail.com").strip()

        # ---- Messaging ----
        self.discord_bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        self.whatsapp_mode = os.getenv("WHATSAPP_MODE", "desktop").strip().lower()
        self.whatsapp_wait = _float("WHATSAPP_WAIT_SECONDS", 7)
        self.whatsapp_web_wait = _float("WHATSAPP_WEB_WAIT_SECONDS", 20)
        self.default_country_code = os.getenv("DEFAULT_COUNTRY_CODE", "91").strip().lstrip("+")

        # ---- Android phone (ADB) ----
        self.adb_path = os.getenv("ADB_PATH", "adb").strip() or "adb"
        self.phone_serial = os.getenv("PHONE_SERIAL", "").strip()
        self.phone_pin = os.getenv("PHONE_PIN", "").strip()

        # ---- Extra features (JARVIS-ported tools) ----
        self.default_city = os.getenv("DEFAULT_CITY", "").strip()
        self.dashboard_enabled = _bool("DASHBOARD_ENABLED", False)
        self.dashboard_port = int(os.getenv("DASHBOARD_PORT", "8000") or 8000)
        self.tts_engine = os.getenv("TTS_ENGINE", "system").strip().lower()
        self.stt_engine = os.getenv("STT_ENGINE", "google").strip().lower()

        # ---- Behaviour ----
        self.confirm_actions = _bool("CONFIRM_ACTIONS", True)
        self.user_name = os.getenv("USER_NAME", "").strip()


CFG = Config()
