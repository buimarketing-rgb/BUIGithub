"""Application configuration loaded from environment variables (.env supported)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_name: str = "BUI"
    environment: str = "development"  # development | production | test
    debug: bool = False
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Database / cache ---
    database_url: str = "postgresql+psycopg://bui:bui@localhost:5432/bui"
    redis_url: str | None = "redis://localhost:6379/0"

    # --- Security ---
    secret_key: str = "change-me-in-production-please-use-a-long-random-string"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cookie_secure: bool = False
    password_reset_minutes: int = 60
    login_rate_limit_per_minute: int = 10
    chat_rate_limit_per_minute: int = 30

    # --- First super admin (created on startup if no users exist) ---
    initial_admin_email: str = "admin@bui.local"
    initial_admin_password: str | None = None  # if empty, a random password is generated and logged once
    initial_admin_name: str = "BUI Super Admin"

    # --- Uploads ---
    upload_dir: Path = Path("./data/uploads")
    max_upload_mb: int = 25

    # --- Embeddings ---
    embedding_provider: str = "auto"  # auto | sentence-transformers | hash
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    chunk_size: int = 900  # characters
    chunk_overlap: int = 150

    # --- LLM ---
    llm_provider: str = "ollama"  # ollama | openai | extractive
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    openai_base_url: str = "https://api.openai.com/v1"  # any OpenAI-compatible endpoint (Groq, OpenRouter, LM Studio, vLLM...)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 120
    llm_temperature: float = 0.1

    # --- Research ---
    search_provider: str = "searxng"  # searxng | brave | none
    searxng_url: str | None = "http://localhost:8080"
    brave_api_key: str | None = None
    research_user_agent: str = "BUI-ResearchBot/1.0 (+company internal knowledge assistant)"
    research_max_pages: int = 5
    research_timeout_seconds: int = 15
    research_scheduler_enabled: bool = True

    # --- Voice ---
    whisper_enabled: bool = False
    whisper_model: str = "base"

    # --- SMTP (optional, for password reset e-mails) ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "BUI <no-reply@bui.local>"

    # --- Workers ---
    background_workers: int = 2
    run_jobs_inline: bool = False  # tests run ingestion synchronously


@lru_cache
def get_settings() -> Settings:
    return Settings()
