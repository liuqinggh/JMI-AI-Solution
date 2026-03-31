"""Logging configuration and utilities."""

from __future__ import annotations

import logging
import sys
from typing import Any

# ANSI color codes for terminal output
RESET = "\033[0m"
GRAY = "\033[90m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""

    LEVEL_COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: MAGENTA,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: The log record to format

        Returns:
            Formatted and colored log message
        """
        # Add color to level name
        levelname = record.levelname
        if record.levelno in self.LEVEL_COLORS:
            levelname_color = self.LEVEL_COLORS[record.levelno] + levelname + RESET
            record.levelname = levelname_color

        return super().format(record)


def setup_logging(
    level: str | int = logging.INFO,
    format_string: str | None = None,
    use_colors: bool = True,
) -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (e.g., logging.INFO, "DEBUG")
        format_string: Custom format string. If None, uses default format.
        use_colors: Whether to use colored output (default: True)

    Example:
        setup_logging(level="DEBUG", use_colors=True)
    """
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Set formatter (with or without colors)
    if use_colors and sys.stdout.isatty():
        formatter = ColoredFormatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
    else:
        formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name. If None, returns the root logger.

    Returns:
        Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    return logging.getLogger(name)


def sanitize_log_data(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize sensitive data from logs.

    Masks values for keys that might contain sensitive information.

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        Dictionary with sensitive values masked

    Example:
        sanitize_log_data({"api_key": "secret", "user": "john"})
        # Returns: {"api_key": "***", "user": "john"}
    """
    sensitive_keys = {
        "api_key",
        "apikey",
        "api-key",
        "password",
        "secret",
        "token",
        "authorization",
        "anthropic_api_key",
        "openai_api_key",
    }

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower().replace("_", "").replace("-", "")
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        else:
            sanitized[key] = value

    return sanitized
