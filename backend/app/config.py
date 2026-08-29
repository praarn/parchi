"""Central configuration.

Everything the service needs from the environment is declared here as a typed
pydantic-settings model, so a missing/misspelled var fails loudly at startup
instead of surfacing as a confusing runtime error later.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",  # tolerate a BOM on Windows-edited .env files
        extra="ignore",
    )

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql://bureaucracy:bureaucracy@localhost:5432/bureaucracy"

    # --- Auth -------------------------------------------------------------
    jwt_secret: str = "dev-only-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    # --- Uploads --------------------------------------------------------
    upload_dir: str = "./uploads"
    max_upload_mb: int = 50

    # --- LLM (Groq) ---------------------------------------------------------
    groq_api_key: str = ""
    groq_text_model: str = "openai/gpt-oss-120b"
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # --- CORS -------------------------------------------------------------
    # Comma-separated list of allowed origins for the browser client.
    cors_origins: str = "http://localhost:3000"

    # --- Worker ---------------------------------------------------------
    worker_poll_interval_seconds: float = 2.0
    worker_stuck_threshold_minutes: int = 15
    job_max_attempts: int = 3

    # The API's Postgres LISTEN task for WebSocket progress. Disabled in the
    # test suite (TestClient spins the lifespan up and down per test).
    enable_progress_listener: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
