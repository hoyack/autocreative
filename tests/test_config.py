"""Tests for flyer_generator.config — Settings loading and validation."""

from pydantic import SecretStr

from flyer_generator.config import Settings


class TestSettings:
    def test_settings_defaults(self):
        s = Settings()
        assert s.comfycloud_base_url == "https://cloud.comfy.org"
        assert s.max_bg_attempts == 3
        assert s.vision_confidence_threshold == 0.6
        assert s.poll_max_attempts == 20
        assert s.log_format == "text"

    def test_settings_env_prefix(self, monkeypatch):
        monkeypatch.setenv("FLYER_MAX_BG_ATTEMPTS", "5")
        s = Settings()
        assert s.max_bg_attempts == 5

    def test_settings_secret_str(self):
        s = Settings()
        assert isinstance(s.anthropic_api_key, SecretStr)
        # SecretStr repr should not leak the value
        assert "**" in repr(s.anthropic_api_key) or s.anthropic_api_key.get_secret_value() == ""


class TestOllamaSettings:
    def test_settings_ollama_defaults(self, monkeypatch):
        # Isolate from .env by unsetting any env vars that override defaults
        for key in ("FLYER_VISION_PROVIDER", "FLYER_OLLAMA_API_KEY", "FLYER_OLLAMA_BASE_URL",
                     "FLYER_OLLAMA_VISION_MODEL", "FLYER_OLLAMA_TEXT_MODEL"):
            monkeypatch.delenv(key, raising=False)
        s = Settings(_env_file=None)
        assert s.vision_provider == "anthropic"
        assert s.ollama_base_url == "https://ollama.com"
        assert s.ollama_vision_model == "llama3.2-vision"
        assert s.ollama_text_model == "llama3.2"
        assert isinstance(s.ollama_api_key, SecretStr)
        assert s.ollama_api_key.get_secret_value() == ""

    def test_settings_vision_provider_ollama(self, monkeypatch):
        monkeypatch.setenv("FLYER_VISION_PROVIDER", "ollama")
        s = Settings()
        assert s.vision_provider == "ollama"

    def test_settings_vision_provider_invalid(self, monkeypatch):
        monkeypatch.setenv("FLYER_VISION_PROVIDER", "openai")
        import pytest
        with pytest.raises(Exception):
            Settings()

    def test_settings_ollama_env_loading(self, monkeypatch):
        monkeypatch.setenv("FLYER_OLLAMA_API_KEY", "my-secret-key")
        monkeypatch.setenv("FLYER_OLLAMA_BASE_URL", "https://custom.ollama.host")
        monkeypatch.setenv("FLYER_OLLAMA_VISION_MODEL", "custom-vision")
        monkeypatch.setenv("FLYER_OLLAMA_TEXT_MODEL", "custom-text")
        s = Settings()
        assert s.ollama_api_key.get_secret_value() == "my-secret-key"
        assert s.ollama_base_url == "https://custom.ollama.host"
        assert s.ollama_vision_model == "custom-vision"
        assert s.ollama_text_model == "custom-text"
