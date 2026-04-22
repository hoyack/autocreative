"""Environment-driven configuration via pydantic-settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from FLYER_-prefixed environment variables.

    List fields (e.g. ollama_text_model_fallbacks) accept a comma-separated
    string from the environment, e.g.
    ``FLYER_OLLAMA_TEXT_MODEL_FALLBACKS="kimi-k2.6:cloud,qwen3.6:35b"``.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLYER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API keys (SecretStr masks values in logs/repr)
    anthropic_api_key: SecretStr = SecretStr("")
    comfycloud_api_key: SecretStr = SecretStr("")
    comfycloud_base_url: str = "https://cloud.comfy.org"

    # Vision provider selector
    vision_provider: Literal["anthropic", "ollama"] = "anthropic"

    # Vision model (Anthropic)
    vision_model: str = "claude-sonnet-4-5"
    vision_max_tokens: int = 1024  # vision verdicts are compact JSON
    # Text completions (outline, text_gen) benefit from a larger budget — the
    # brochure schema-renderer asks the LLM to produce ~20 structured fields
    # which regularly exceeds 1024 tokens and gets truncated mid-JSON.
    text_max_tokens: int = 8192
    vision_timeout_seconds: int = 60

    # Ollama / OpenAI-compatible provider
    ollama_api_key: SecretStr = SecretStr("")
    ollama_base_url: str = "https://ollama.com"
    ollama_vision_model: str = "llama3.2-vision"
    ollama_text_model: str = "llama3.2"  # future use — not wired to any stage

    # --- Fallback model chains (comma-separated in env, e.g.
    # FLYER_OLLAMA_TEXT_MODEL_FALLBACKS="kimi-k2.6:cloud,qwen3.6:35b").
    # Pydantic-settings parses bare comma-separated strings into list[str].
    ollama_text_model_fallbacks: list[str] = Field(
        default_factory=lambda: ["kimi-k2.6:cloud"]
    )
    ollama_vision_model_fallbacks: list[str] = Field(
        default_factory=lambda: ["kimi-k2.6:cloud"]
    )

    # --- LLM retry policy (applies to both text and vision Ollama calls).
    llm_retry_max_attempts: int = 3
    llm_retry_base_delay: float = 1.0  # seconds
    llm_retry_max_delay: float = 10.0  # seconds

    # ComfyUI workflow (name or path to .json)
    workflow: str = "turbo_portrait"

    # Regen policy
    max_bg_attempts: int = 3
    vision_confidence_threshold: float = 0.6

    # Comfy polling
    poll_initial_wait_seconds: float = 3.0
    poll_interval_seconds: float = 4.0
    poll_max_attempts: int = 20

    # Output
    output_dir: Path = Path("./output")
    # Brand kit storage (Phase 18). Configurable via FLYER_BRAND_KITS_DIR env var.
    brand_kits_dir: Path = Path(".brand-kits")
    # Social campaigns storage (Phase 19). Configurable via FLYER_SOCIAL_CAMPAIGNS_DIR env var.
    social_campaigns_dir: Path = Path(".social-campaigns")
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"
