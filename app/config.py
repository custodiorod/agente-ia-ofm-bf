from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API & App
    app_name: str = "agente-ia-ofm"
    app_env: str = "production"
    debug: bool = False
    log_level: str = "INFO"
    api_port: int = 8000
    api_host: str = "0.0.0.0"

    # Database - Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM - OpenRouter
    openrouter_api_key: str
    openrouter_model: str = "anthropic/claude-3-haiku"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Langfuse
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Uazapi
    uazapi_instance_id: str
    uazapi_api_token: str
    uazapi_webhook_verify_token: str
    uazapi_webhook_url: str

    # PixBank
    pixbank_api_key: str
    pixbank_secret_key: str
    pixbank_webhook_secret: str
    pixbank_webhook_url: str

    # Kestra
    kestra_url: str = "http://localhost:8080"
    kestra_api_key: Optional[str] = None

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_worker_concurrency: int = 4
    celery_task_time_limit: int = 300

    # Security
    secret_key: str
    webhook_secret_whatsapp: str
    webhook_secret_pixbank: str

    # Follow-up
    followup_initial_delay_minutes: int = 20
    followup_retry_hours: int = 2
    followup_max_attempts: int = 5
    inactive_days_threshold: int = 30

    # RAG
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
