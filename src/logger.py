"""Logging infrastructure for Obsidian-Claude Agent."""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class Logger:
    """Centralized logging manager with rotating file handler."""

    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        """Singleton pattern to ensure single logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize logger (only once due to singleton)."""
        if self._logger is not None:
            return  # Already initialized

        self._logger = logging.getLogger("obsidian_claude_agent")
        self._logger.setLevel(logging.DEBUG)  # Capture all levels
        self._logger.propagate = False

        # Clear any existing handlers
        self._logger.handlers.clear()

    def setup(
        self,
        log_file: str = "logs/agent.log",
        level: str = "DEBUG",
        max_size: int = 10485760,  # 10MB
        backup_count: int = 5,
        console: bool = True
    ) -> None:
        """
        Configure logging with file and optional console output.

        Args:
            log_file: Path to log file
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
            max_size: Maximum size of log file before rotation (bytes)
            backup_count: Number of backup log files to keep
            console: Whether to also log to console
        """
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert string level to logging constant
        numeric_level = getattr(logging, level.upper(), logging.DEBUG)
        self._logger.setLevel(numeric_level)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

        # Console handler (optional)
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        """Get the logger instance."""
        if self._logger is None:
            raise RuntimeError("Logger not initialized. Call setup() first.")
        return self._logger

    @classmethod
    def debug(cls, message: str, **kwargs) -> None:
        """Log debug message."""
        logger = cls()._logger
        if logger:
            logger.debug(message, **kwargs)

    @classmethod
    def info(cls, message: str, **kwargs) -> None:
        """Log info message."""
        logger = cls()._logger
        if logger:
            logger.info(message, **kwargs)

    @classmethod
    def warning(cls, message: str, **kwargs) -> None:
        """Log warning message."""
        logger = cls()._logger
        if logger:
            logger.warning(message, **kwargs)

    @classmethod
    def error(cls, message: str, **kwargs) -> None:
        """Log error message."""
        logger = cls()._logger
        if logger:
            logger.error(message, **kwargs)

    @classmethod
    def critical(cls, message: str, **kwargs) -> None:
        """Log critical message."""
        logger = cls()._logger
        if logger:
            logger.critical(message, **kwargs)

    @classmethod
    def exception(cls, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        logger = cls()._logger
        if logger:
            logger.exception(message, **kwargs)


# Convenience function for easy access
def get_logger() -> logging.Logger:
    """
    Get the configured logger instance.

    Returns:
        Logger instance

    Raises:
        RuntimeError: If logger not yet initialized
    """
    return Logger().get_logger()


# Convenience function to setup logger
def setup_logging(
    log_file: str = "logs/agent.log",
    level: str = "DEBUG",
    max_size: int = 10485760,
    backup_count: int = 5,
    console: bool = True
) -> logging.Logger:
    """
    Setup and configure logging.

    Args:
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        max_size: Maximum size of log file before rotation (bytes)
        backup_count: Number of backup log files to keep
        console: Whether to also log to console

    Returns:
        Configured logger instance
    """
    logger_instance = Logger()
    logger_instance.setup(
        log_file=log_file,
        level=level,
        max_size=max_size,
        backup_count=backup_count,
        console=console
    )
    return logger_instance.get_logger()
