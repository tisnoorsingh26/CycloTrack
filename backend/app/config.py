from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ml_artifact_dir: Path = PROJECT_ROOT / "ml"
    cors_origins: str = "http://localhost:3000"
    tinyfish_api_key: str = ""
    tinyfish_timeout_seconds: float = 15.0
    ibtracs_cache_dir: Path = BACKEND_DIR / "cache" / "ibtracs"
    imd_api_token: str = ""
    log_level: str = "INFO"

    def artifact_dir(self) -> Path:
        path = self.ml_artifact_dir
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
