"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All application settings loaded from .env or environment."""

    # ── App ──
    app_env: str = "development"
    app_secret_key: str = "change-this-to-a-random-secret"
    cors_origins: str = "http://localhost:3000"

    # ── Supabase ──
    supabase_url: str = "http://localhost:54321"
    supabase_key: str = ""
    supabase_service_key: str = ""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM Providers ──
    groq_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # ── Google OAuth2 ──
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Microsoft OAuth2 ──
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""

    # ── Enrichment APIs ──
    hunter_api_key: str = ""
    apollo_api_key: str = ""

    # ── Embeddings ──
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768

    # ── Jitter Engine ──
    max_emails_per_hour: int = 3
    max_emails_per_day: int = 30

    # ── Ingestion — PIPELINE_AFTER_FETCH=true runs LLMs after each fetch ──
    pipeline_after_fetch: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()