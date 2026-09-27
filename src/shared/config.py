"""Application settings — loaded from .env via pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for Surge."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Scanner (portfolio-aware — nenhum ticker hardcodado; carteira vive no SQLite)
    drop_threshold: float = Field(default=5.0, alias="SURGE_DROP_THRESHOLD")
    cron_hour: int = Field(default=18, alias="SURGE_CRON_HOUR")
    cron_minute: int = Field(default=0, alias="SURGE_CRON_MINUTE")

    # Storage
    db_path: str = Field(default="./surge.db", alias="SURGE_DB_PATH")

    # Email
    email_enabled: bool = Field(default=False, alias="SURGE_EMAIL_ENABLED")
    smtp_host: str = Field(default="smtp.gmail.com", alias="SURGE_SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SURGE_SMTP_PORT")
    smtp_user: str = Field(default="", alias="SURGE_SMTP_USER")
    smtp_password: str = Field(default="", alias="SURGE_SMTP_PASSWORD")
    email_from: str = Field(default="", alias="SURGE_EMAIL_FROM")
    email_to: str = Field(default="", alias="SURGE_EMAIL_TO")
    imap_enabled: bool = Field(default=False, alias="SURGE_IMAP_ENABLED")
    imap_host: str = Field(default="imap.gmail.com", alias="SURGE_IMAP_HOST")
    imap_port: int = Field(default=993, alias="SURGE_IMAP_PORT")
    imap_user: str = Field(default="", alias="SURGE_IMAP_USER")
    imap_password: str = Field(default="", alias="SURGE_IMAP_PASSWORD")
    imap_mailbox: str = Field(default="INBOX", alias="SURGE_IMAP_MAILBOX")
    investment_email_subject: str = Field(
        default="SURGE: INVESTIMENTO", alias="SURGE_INVESTMENT_EMAIL_SUBJECT"
    )
    email_poll_minutes: int = Field(default=5, alias="SURGE_EMAIL_POLL_MINUTES")

    # Telegram
    telegram_enabled: bool = Field(default=False, alias="SURGE_TELEGRAM_ENABLED")
    telegram_bot_token: str = Field(default="", alias="SURGE_TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="SURGE_TELEGRAM_CHAT_ID")

    # BRAPI
    brapi_token: str = Field(default="", alias="SURGE_BRAPI_TOKEN")
    brapi_base_url: str = Field(default="https://brapi.dev", alias="SURGE_BRAPI_BASE_URL")

    # App
    timezone: str = Field(default="America/Sao_Paulo", alias="SURGE_TIMEZONE")
    log_level: str = Field(default="INFO", alias="SURGE_LOG_LEVEL")

    @property
    def has_notification_channel(self) -> bool:
        return self.email_enabled or self.telegram_enabled


def get_settings() -> Settings:
    """Load settings from environment / .env."""
    return Settings()  # type: ignore[call-arg]
