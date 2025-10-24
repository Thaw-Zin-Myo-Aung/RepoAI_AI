"""
Centralized Logging Configuration for RepoAI
Logging across all modules with proper formatting.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


# Colors for terminal output (ANSI)
class LogColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors based on log level."""

    LEVEL_COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.GREEN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.RED + LogColors.BOLD,
    }

    def format(self, record: logging.LogRecord) -> str:
        # Apply color based on log level
        levelname = record.levelname
        if record.levelno in self.LEVEL_COLORS:
            levelname_color = self.LEVEL_COLORS[record.levelno] + levelname + LogColors.RESET
            record.levelname = levelname_color

        message = super().format(record)
        record.levelname = levelname  # Reset to original levelname
        return message


def setup_logging(
    level: int = logging.INFO,
    log_file: Path | None = None,
    use_colors: bool = True,
) -> None:
    """
    Set up logging for the entire application.
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        use_colors: Whether to use colored output in terminal
    """
    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if use_colors and sys.stdout.isatty():
        console_format = (
            f"{LogColors.GRAY}%(asctime)s{LogColors.RESET} | "
            f"%(levelname)s | "
            f"{LogColors.BLUE}%(name)s{LogColors.RESET} | "
            f"%(message)s"
        )
        console_formatter: logging.Formatter = ColoredFormatter(
            console_format, datefmt="%Y-%m-%d %H:%M:%S"
        )

    else:
        console_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        console_formatter = logging.Formatter(console_format, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            "%(filename)s:%(lineno)d | %(message)s"
        )
        file_formatter = logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Supress noisy third-party loggers if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("pydantic_ai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    Args:
        name: Name of the logger (usually __name__ of the module)
    Returns:
        Configured logger instance

    Example:
        -------
        logger = get_logger(__name__)
        logger.info("This is an info message")
    """
    return logging.getLogger(name)
