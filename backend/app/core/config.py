"""Application configuration loaded from environment variables / .env file."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path: check current dir first, then walk up to project root
_env_file = ".env"
_here = Path(__file__).resolve()
for _candidate in [
    Path.cwd() / ".env",
    _here.parent.parent.parent / ".env",   # backend/app/core -> backend -> project root
    _here.parent.parent.parent.parent / ".env",  # extra level if needed
]:
    if _candidate.is_file():
        _env_file = str(_candidate)
        break


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AI / Qwen
    DASHSCOPE_API_KEY: str = ""
    QWEN_MODEL: str = "qwen2.5-vl-72b-instruct"
    MOCK_AI_ENGINE: bool = True  # Use mock AI engine for local/dev testing

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@host:5432/dawaecheck"

    # Supabase (image storage)
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # Clone detection
    CLONE_DETECTION_WINDOW_HOURS: int = 24
    CLONE_DETECTION_LOCATION_THRESHOLD: int = 3


settings = Settings()
