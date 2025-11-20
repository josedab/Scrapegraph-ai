"""
A centralized logging system for any library.
This module provides functions to manage logging for a library. It includes
functions to get and set the verbosity level, add and remove handlers, and
control propagation. It also includes a function to set formatting for all
handlers bound to the root logger.

Enhanced with structured JSON logging and correlation ID support for
production debugging, distributed tracing, and better observability.

Source code inspired by: https://gist.github.com/DiTo97/9a0377f24236b66134eb96da1ec1693f
"""

import json
import logging
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Optional

_library_name = __name__.split(".", maxsplit=1)[0]

DEFAULT_HANDLER = None
_DEFAULT_LOGGING_LEVEL = logging.WARNING

_semaphore = threading.Lock()

# ============================================================================
# Structured Logging and Correlation ID Support
# ============================================================================

# Thread-safe correlation ID storage using ContextVars
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def get_correlation_id() -> str:
    """
    Get or create correlation ID for current execution context.

    Returns:
        str: The correlation ID for the current context.
    """
    cid = correlation_id.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """
    Set correlation ID for current execution context.

    Args:
        cid (str): The correlation ID to set.
    """
    correlation_id.set(cid)


def clear_correlation_id() -> None:
    """
    Clear the correlation ID for current execution context.
    """
    correlation_id.set(None)


class LogFormat(Enum):
    """Supported log output formats."""
    JSON = "json"
    HUMAN = "human"


class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON with correlation IDs and structured data.

    Args:
        include_extra (bool): Whether to include extra fields from log records.
    """

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: JSON-formatted log string.
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra fields if available
        if self.include_extra and hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)

        return json.dumps(log_data)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable formatter for development environments.
    Includes shortened correlation ID for easier reading.
    """

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] [%(correlation_id)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """
        Add correlation ID to record before formatting.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: Formatted log string with correlation ID.
        """
        # Add shortened correlation ID for readability
        record.correlation_id = get_correlation_id()[:8]

        # Add extra fields to message if present
        if hasattr(record, "extra") and record.extra:
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra.items())
            record.msg = f"{record.msg} | {extra_str}"

        return super().format(record)


class StructuredLogger:
    """
    Wrapper around standard logger with structured logging support.

    This logger allows passing structured context data alongside log messages,
    which will be properly formatted by the JSONFormatter or DevelopmentFormatter.

    Args:
        logger (logging.Logger): The underlying logger to wrap.
    """

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, message: str, exc_info=None, **context: Any) -> None:
        """
        Log with structured context.

        Args:
            level (int): The logging level.
            message (str): The log message.
            exc_info: Exception information to include.
            **context: Additional context fields to include in the log.
        """
        if context:
            # Pass context as extra dict
            self._logger.log(level, message, extra={"extra": context}, exc_info=exc_info)
        else:
            self._logger.log(level, message, exc_info=exc_info)

    def debug(self, message: str, **context: Any) -> None:
        """
        Log debug message with context.

        Args:
            message (str): The log message.
            **context: Additional context fields.
        """
        self._log(logging.DEBUG, message, **context)

    def info(self, message: str, **context: Any) -> None:
        """
        Log info message with context.

        Args:
            message (str): The log message.
            **context: Additional context fields.
        """
        self._log(logging.INFO, message, **context)

    def warning(self, message: str, **context: Any) -> None:
        """
        Log warning message with context.

        Args:
            message (str): The log message.
            **context: Additional context fields.
        """
        self._log(logging.WARNING, message, **context)

    def error(self, message: str, exc_info=None, **context: Any) -> None:
        """
        Log error message with context.

        Args:
            message (str): The log message.
            exc_info: Exception information to include.
            **context: Additional context fields.
        """
        self._log(logging.ERROR, message, exc_info=exc_info, **context)

    def critical(self, message: str, exc_info=None, **context: Any) -> None:
        """
        Log critical message with context.

        Args:
            message (str): The log message.
            exc_info: Exception information to include.
            **context: Additional context fields.
        """
        self._log(logging.CRITICAL, message, exc_info=exc_info, **context)

    def exception(self, message: str, **context: Any) -> None:
        """
        Log exception with context (automatically includes exc_info).

        Args:
            message (str): The log message.
            **context: Additional context fields.
        """
        self._log(logging.ERROR, message, exc_info=True, **context)


@contextmanager
def log_execution_time(logger: StructuredLogger, operation: str, **context: Any):
    """
    Context manager to log execution time of operations.

    Args:
        logger (StructuredLogger): The logger to use.
        operation (str): Name of the operation being timed.
        **context: Additional context fields to include.

    Yields:
        None

    Example:
        >>> logger = get_structured_logger(__name__)
        >>> with log_execution_time(logger, "data_processing", user_id="123"):
        ...     process_data()
    """
    start_time = time.perf_counter()
    logger.info(f"Starting {operation}", operation=operation, **context)

    try:
        yield
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"Failed {operation}",
            operation=operation,
            duration_ms=round(duration_ms, 2),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
            **context
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Completed {operation}",
            operation=operation,
            duration_ms=round(duration_ms, 2),
            **context
        )


class LogConfig:
    """
    Configuration for the logging system.

    Reads configuration from environment variables:
    - LOG_FORMAT: "json" or "human" (default: "human")
    - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: "INFO")
    - LOG_CORRELATION_ID: "true" or "false" (default: "true")
    - LOG_CONTEXT: "true" or "false" (default: "true")
    """

    def __init__(self):
        self.format = LogFormat(os.getenv("LOG_FORMAT", "human"))
        self.level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.include_correlation_id = os.getenv("LOG_CORRELATION_ID", "true").lower() == "true"
        self.include_context = os.getenv("LOG_CONTEXT", "true").lower() == "true"


def configure_logging(config: Optional[LogConfig] = None) -> None:
    """
    Configure structured logging system.

    This function sets up the logging system with either JSON formatting
    (for production) or human-readable formatting (for development).

    Args:
        config (Optional[LogConfig]): Configuration object. If None, uses defaults
                                      from environment variables.

    Example:
        >>> # Use default configuration from environment
        >>> configure_logging()
        >>>
        >>> # Use custom configuration
        >>> config = LogConfig()
        >>> config.format = LogFormat.JSON
        >>> config.level = "DEBUG"
        >>> configure_logging(config)
    """
    config = config or LogConfig()

    # Set up formatter based on environment
    if config.format == LogFormat.JSON:
        formatter = JSONFormatter(include_extra=config.include_context)
    else:
        formatter = DevelopmentFormatter()

    # Configure root logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = _get_library_root_logger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, config.level))

    # Update the global DEFAULT_HANDLER
    global DEFAULT_HANDLER
    DEFAULT_HANDLER = handler


def get_structured_logger(name: Optional[str] = None) -> StructuredLogger:
    """
    Get a structured logger with the specified name.

    This logger supports structured logging with context fields that will be
    properly formatted as JSON in production or human-readable in development.

    Args:
        name (Optional[str]): The name of the logger. If None, the root logger
                             for the library is returned.

    Returns:
        StructuredLogger: A structured logger instance.

    Example:
        >>> logger = get_structured_logger(__name__)
        >>> logger.info("Processing started", user_id="123", graph_id="abc")
        >>>
        >>> with log_execution_time(logger, "graph_execution", graph_name="SmartScraper"):
        ...     execute_graph()
    """
    _set_library_root_logger()
    base_logger = logging.getLogger(name or _library_name)
    return StructuredLogger(base_logger)

# ============================================================================
# End of Structured Logging Support
# ============================================================================


def _get_library_root_logger() -> logging.Logger:
    """
    Get the root logger for the library.

    Returns:
        logging.Logger: The root logger for the library.
    """
    return logging.getLogger(_library_name)


def _set_library_root_logger() -> None:
    """
    Set up the root logger for the library.

    This function sets up the default handler for the root logger,
    if it has not already been set up.
    It also sets the logging level and propagation for the root logger.
    """
    global DEFAULT_HANDLER

    with _semaphore:
        if DEFAULT_HANDLER:
            return

        DEFAULT_HANDLER = logging.StreamHandler()  # sys.stderr as stream

        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")

        DEFAULT_HANDLER.flush = sys.stderr.flush

        library_root_logger = _get_library_root_logger()
        library_root_logger.addHandler(DEFAULT_HANDLER)
        library_root_logger.setLevel(_DEFAULT_LOGGING_LEVEL)
        library_root_logger.propagate = False


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with the specified name.

    If no name is provided, the root logger for the library is returned.

    Args:
        name (Optional[str]): The name of the logger.
        If None, the root logger for the library is returned.

    Returns:
        logging.Logger: The logger with the specified name.
    """
    _set_library_root_logger()
    return logging.getLogger(name or _library_name)


def get_verbosity() -> int:
    """
    Get the current verbosity level of the root logger for the library.

    Returns:
        int: The current verbosity level of the root logger for the library.
    """
    _set_library_root_logger()
    return _get_library_root_logger().getEffectiveLevel()


def set_verbosity(verbosity: int) -> None:
    """
    Set the verbosity level of the root logger for the library.

    Args:
        verbosity (int): The verbosity level to set.
    """
    _set_library_root_logger()
    _get_library_root_logger().setLevel(verbosity)


def set_verbosity_debug() -> None:
    """
    Set the verbosity level of the root logger for the library to DEBUG.
    """
    set_verbosity(logging.DEBUG)


def set_verbosity_info() -> None:
    """
    Set the verbosity level of the root logger for the library to INFO.
    """
    set_verbosity(logging.INFO)


def set_verbosity_warning() -> None:
    """
    Set the verbosity level of the root logger for the library to WARNING.
    """
    set_verbosity(logging.WARNING)


def set_verbosity_error() -> None:
    """
    Set the verbosity level of the root logger for the library to ERROR.
    """
    set_verbosity(logging.ERROR)


def set_verbosity_fatal() -> None:
    """
    Set the verbosity level of the root logger for the library to FATAL.
    """
    set_verbosity(logging.FATAL)


def set_handler(handler: logging.Handler) -> None:
    """
    Add a handler to the root logger for the library.

    Args:
        handler (logging.Handler): The handler to add.
    """
    _set_library_root_logger()

    assert handler is not None

    _get_library_root_logger().addHandler(handler)


def setDEFAULT_HANDLER() -> None:
    """
    Add the default handler to the root logger for the library.
    """
    set_handler(DEFAULT_HANDLER)


def unset_handler(handler: logging.Handler) -> None:
    """
    Remove a handler from the root logger for the library.

    Args:
        handler (logging.Handler): The handler to remove.
    """
    _set_library_root_logger()

    assert handler is not None

    _get_library_root_logger().removeHandler(handler)


def unsetDEFAULT_HANDLER() -> None:
    """
    Remove the default handler from the root logger for the library.
    """
    unset_handler(DEFAULT_HANDLER)


def set_propagation() -> None:
    """
    Enable propagation of the root logger for the library.
    """
    _get_library_root_logger().propagate = True


def unset_propagation() -> None:
    """
    Disable propagation of the root logger for the library.
    """
    _get_library_root_logger().propagate = False


def set_formatting() -> None:
    """
    Set formatting for all handlers bound to the root logger for the library.

    The formatting is set to: "[levelname|filename:lineno] time >> message"
    """
    formatter = logging.Formatter(
        "[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s >> %(message)s"
    )

    for handler in _get_library_root_logger().handlers:
        handler.setFormatter(formatter)


def unset_formatting() -> None:
    """
    Remove formatting for all handlers bound to the root logger for the library.
    """
    for handler in _get_library_root_logger().handlers:
        handler.setFormatter(None)


@lru_cache(None)
def warning_once(self, *args, **kwargs):
    """
    Emit a warning log with the same message only once.

    This function is added as a method to the logging.Logger class.
    It emits a warning log with the same message only once,
    even if it is called multiple times with the same message.

    Args:
        *args: The arguments to pass to the logging.Logger.warning method.
        **kwargs: The keyword arguments to pass to the logging.Logger.warning method.
    """
    self.warning(*args, **kwargs)


logging.Logger.warning_once = warning_once
