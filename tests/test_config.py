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
