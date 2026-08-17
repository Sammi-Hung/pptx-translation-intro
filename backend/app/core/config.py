from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    storage_root: Path = Path("./storage")
    max_upload_mb: int = 50
    retention_minutes: int = 30
    cleanup_interval_seconds: int = 300
    translation_provider: str = "mock"
    translation_api_key: str | None = None
    translation_api_url: str | None = None
    translation_model: str = "gpt-4o-mini"
    translation_ollama_num_gpu: int | None = None
    translation_cloud_provider: str | None = None
    translation_cloud_api_url: str | None = None
    translation_cloud_model: str | None = None
    translation_local_primary_api_url: str | None = None
    translation_local_primary_model: str | None = None
    translation_local_secondary_api_url: str | None = None
    translation_local_secondary_model: str | None = None
    tts_provider: str = "mock"
    tts_api_key: str | None = None
    tts_api_url: str | None = None
    audio_embed_provider: str = "mock"
    allowed_origins: str = Field(default="http://localhost:3000")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @field_validator("translation_ollama_num_gpu", mode="before")
    @classmethod
    def empty_num_gpu_means_default(cls, value: object) -> object:
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
