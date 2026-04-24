from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neonize_service_token: str = ""
    neonize_session_path: str = "/data/session.sqlite"
    neonize_log_level: str = "INFO"

    class Config:
        env_prefix = ""  # Las env vars vienen con nombres completos
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
