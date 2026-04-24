from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neonize_service_token: str = ""
    neonize_session_path: str = "/data/session.sqlite"
    neonize_log_level: str = "INFO"
    # DPV-006 — Forward de mensajes entrantes al webhook Django
    django_webhook_url: str = ""
    django_webhook_token: str = ""
    django_webhook_timeout_seconds: int = 15
    django_webhook_max_retries: int = 2

    class Config:
        env_prefix = ""  # Las env vars vienen con nombres completos
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
