"""Centralized application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed configuration for the MetaStudio backend."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    backend_host: str = Field(default="127.0.0.1")
    backend_port: int = Field(default=8000)
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )

    # Media / FFmpeg
    ffmpeg_path: str = Field(default="")
    audio_mp3_bitrate: int = Field(default=320, ge=96, le=320)

    # Storage & Concurrency
    temp_storage_dir: str = Field(default="backend/tmp")
    data_storage_dir: str = Field(default="backend/data")
    playlist_download_concurrency: int = Field(default=2, ge=1, le=5)
    max_artwork_upload_mb: int = Field(default=10, ge=1, le=25)
    rate_limit_per_minute: int = Field(default=60, ge=10, le=600)

    # External Metadata Providers (never exposed to frontend)
    musicbrainz_user_agent: str = Field(
        default="MetaStudio/1.0.0 (https://github.com/donivanovich/MetaStudio)"
    )
    discogs_token: str = Field(default="")

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def temp_path(self) -> Path:
        path = Path(self.temp_storage_dir)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data_path(self) -> Path:
        path = Path(self.data_storage_dir)
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_artwork_upload_bytes(self) -> int:
        return self.max_artwork_upload_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
