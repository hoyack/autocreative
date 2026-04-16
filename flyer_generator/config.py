"""Environment-driven configuration via pydantic-settings."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from FLYER_-prefixed environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="FLYER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API keys (SecretStr masks values in logs/repr)
    anthropic_api_key: SecretStr = SecretStr("")
    comfycloud_api_key: SecretStr = SecretStr("")
    comfycloud_base_url: str = "https://cloud.comfy.org"

    # Vision model
    vision_model: str = "claude-sonnet-4-5"
    vision_max_tokens: int = 1024
    vision_timeout_seconds: int = 60

    # Regen policy
    max_bg_attempts: int = 3
    vision_confidence_threshold: float = 0.6

    # Comfy polling
    poll_initial_wait_seconds: float = 3.0
    poll_interval_seconds: float = 4.0
    poll_max_attempts: int = 20

    # Output
    output_dir: Path = Path("./output")
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
