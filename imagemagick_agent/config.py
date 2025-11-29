"""Configuration management for ImageMagick Agent."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Configuration
    llm_provider: LLMProvider = Field(
        default=LLMProvider.ANTHROPIC,
        description="LLM provider to use (anthropic, openai, or google)",
    )
    llm_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Specific model to use",
    )

    # API Keys (loaded from environment variables)
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    google_api_key: Optional[str] = Field(default=None, description="Google API key")

    # Agent Behavior
    auto_execute: bool = Field(
        default=False,
        description="Auto-execute commands without confirmation",
    )
    max_history: int = Field(
        default=10,
        description="Maximum number of conversation turns to keep in history",
    )

    # Logging Configuration
    enable_logging: bool = Field(
        default=True,
        description="Enable structured logging",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    log_dir: Path = Field(
        default=Path("logs"),
        description="Directory for log files",
    )
    enable_llm_logging: bool = Field(
        default=True,
        description="Enable detailed LLM call logging",
    )
    enable_execution_logging: bool = Field(
        default=True,
        description="Enable command execution audit logging",
    )
    log_retention_days: int = Field(
        default=7,
        description="Number of days to retain logs",
    )
    log_max_bytes: int = Field(
        default=10_000_000,
        description="Maximum size of each log file before rotation (bytes)",
    )
    log_backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep",
    )

    def validate_api_keys(self) -> None:
        """Validate that required API keys are set."""
        if self.llm_provider == LLMProvider.ANTHROPIC and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set when using anthropic provider")
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when using openai provider")
        if self.llm_provider == LLMProvider.GOOGLE and not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY must be set when using google provider")


def load_settings() -> Settings:
    """Load and validate settings."""
    settings = Settings()
    settings.validate_api_keys()
    return settings
