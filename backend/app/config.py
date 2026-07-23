from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to this file's location (backend/app/../.env)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str

    # AI extraction — provider is auto-selected: Anthropic if ANTHROPIC_API_KEY is
    # set, otherwise the free Google Gemini path if GEMINI_API_KEY is set. Set
    # EXTRACTOR_PROVIDER=anthropic|gemini to force one regardless of which keys exist.
    extractor_provider: str | None = None

    # Claude (paid, best-in-class multimodal extraction)
    anthropic_api_key: str | None = None
    extractor_model: str = "claude-sonnet-5"          # accuracy tier for messy input
    extractor_model_cheap: str = "claude-haiku-4-5-20251001"  # optional cheaper tier

    # Google Gemini (free tier via https://aistudio.google.com/apikey) — native
    # image + PDF understanding and JSON-schema-constrained output, so it preserves
    # the multimodal, structured extraction the Claude path provides.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"  # stable alias → current free flash model

    # Gmail ingestion (OAuth desktop/installed-app credentials)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_refresh_token: str | None = None
    # Comma-separated sender allowlist; empty = accept any sender
    wo_sender_allowlist: str = ""
    # Poll interval in seconds
    gmail_poll_seconds: int = 120

    # Notifications
    slack_webhook_url: str | None = None
    dashboard_url: str = "http://localhost:3000"

    # AppFolio (Phase 4 browser automation)
    appfolio_login_url: str | None = None
    appfolio_username: str | None = None
    appfolio_password: str | None = None
    # If true, automation stops one step before final Submit and waits for a human click
    appfolio_stop_before_submit: bool = True

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")


settings = Settings()
