"""
Centralized logging configuration for ImageMagick Agent.

This module sets up structured logging for the application including:
- Application-wide logging
- LLM call tracking
- Command execution audit trail
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logging(
    log_dir: Path = Path("logs"),
    app_log_level: str = "INFO",
    enable_llm_logging: bool = True,
    enable_execution_logging: bool = True,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure application-wide logging.

    Args:
        log_dir: Directory to store log files
        app_log_level: Logging level for application logs (DEBUG, INFO, WARNING, ERROR)
        enable_llm_logging: Enable specialized LLM call logging
        enable_execution_logging: Enable command execution logging
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
    """
    # Create log directory if it doesn't exist
    log_dir.mkdir(exist_ok=True, parents=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, handlers will filter

    # Main application logger
    app_logger = logging.getLogger("imagemagick_agent")
    app_logger.setLevel(getattr(logging, app_log_level.upper()))
    app_logger.propagate = False  # Don't propagate to root

    # Create console handler for CLI output (WARNING and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    app_logger.addHandler(console_handler)

    # Create rotating file handler for application logs
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=max_bytes, backupCount=backup_count
    )
    app_handler.setLevel(getattr(logging, app_log_level.upper()))
    app_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    app_handler.setFormatter(app_formatter)
    app_logger.addHandler(app_handler)

    # Set up specialized loggers
    if enable_llm_logging:
        setup_llm_logger(log_dir, max_bytes, backup_count)

    if enable_execution_logging:
        setup_execution_logger(log_dir, max_bytes, backup_count)

    app_logger.info("Logging system initialized")
    app_logger.debug(
        f"Log directory: {log_dir.absolute()}, Level: {app_log_level}, "
        f"LLM logging: {enable_llm_logging}, Execution logging: {enable_execution_logging}"
    )


def setup_llm_logger(
    log_dir: Path, max_bytes: int = 10_000_000, backup_count: int = 5
) -> None:
    """
    Set up specialized logger for LLM API calls.

    Creates a separate log file for tracking LLM requests and responses
    in JSON Lines format for easy parsing.
    """
    llm_logger = logging.getLogger("llm_calls")
    llm_logger.setLevel(logging.DEBUG)
    llm_logger.propagate = False  # Don't propagate to parent

    # JSON Lines format handler - append mode for structured logs
    llm_handler = logging.handlers.RotatingFileHandler(
        log_dir / "llm_calls.jsonl", maxBytes=max_bytes, backupCount=backup_count
    )
    llm_handler.setLevel(logging.DEBUG)

    # Simple formatter - we'll write JSON directly in the logger
    llm_formatter = logging.Formatter("%(message)s")
    llm_handler.setFormatter(llm_formatter)
    llm_logger.addHandler(llm_handler)


def setup_execution_logger(
    log_dir: Path, max_bytes: int = 10_000_000, backup_count: int = 5
) -> None:
    """
    Set up specialized logger for command execution audit trail.

    Creates a separate log file for tracking all ImageMagick command
    executions in JSON Lines format.
    """
    exec_logger = logging.getLogger("executions")
    exec_logger.setLevel(logging.DEBUG)
    exec_logger.propagate = False

    exec_handler = logging.handlers.RotatingFileHandler(
        log_dir / "executions.jsonl", maxBytes=max_bytes, backupCount=backup_count
    )
    exec_handler.setLevel(logging.DEBUG)
    exec_formatter = logging.Formatter("%(message)s")
    exec_handler.setFormatter(exec_formatter)
    exec_logger.addHandler(exec_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"imagemagick_agent.{name}")
