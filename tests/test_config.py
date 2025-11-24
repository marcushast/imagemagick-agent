"""Tests for configuration."""

import pytest
import os

from imagemagick_agent.config import Settings, LLMProvider


class TestSettings:
    """Test settings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.llm_provider == LLMProvider.ANTHROPIC
        assert settings.llm_model == "claude-3-5-sonnet-20241022"
        assert settings.auto_execute is False
        assert settings.max_history == 10

    def test_custom_settings(self):
        """Test custom settings."""
        settings = Settings(
            llm_provider=LLMProvider.OPENAI,
            llm_model="gpt-4",
            auto_execute=True,
        )
        assert settings.llm_provider == LLMProvider.OPENAI
        assert settings.llm_model == "gpt-4"
        assert settings.auto_execute is True

    def test_validate_api_keys_anthropic(self):
        """Test API key validation for Anthropic."""
        settings = Settings(
            llm_provider=LLMProvider.ANTHROPIC,
            anthropic_api_key=None,
        )
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            settings.validate_api_keys()

    def test_validate_api_keys_openai(self):
        """Test API key validation for OpenAI."""
        settings = Settings(
            llm_provider=LLMProvider.OPENAI,
            openai_api_key=None,
        )
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            settings.validate_api_keys()

    def test_validate_api_keys_google(self):
        """Test API key validation for Google."""
        settings = Settings(
            llm_provider=LLMProvider.GOOGLE,
            google_api_key=None,
        )
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            settings.validate_api_keys()

    def test_validate_api_keys_success(self):
        """Test successful API key validation."""
        settings = Settings(
            llm_provider=LLMProvider.ANTHROPIC,
            anthropic_api_key="test-key",
        )
        # Should not raise
        settings.validate_api_keys()
