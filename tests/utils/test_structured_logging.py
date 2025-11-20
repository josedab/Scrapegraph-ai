"""
Comprehensive tests for structured logging with correlation IDs.

Tests cover:
- Correlation ID management
- JSON and Development formatters
- Structured logger functionality
- Performance timing
- Configuration system
"""

import json
import logging
import time
import uuid
from io import StringIO
from unittest.mock import patch

import pytest

from scrapegraphai.utils.logging import (
    LogConfig,
    LogFormat,
    JSONFormatter,
    DevelopmentFormatter,
    StructuredLogger,
    configure_logging,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
    get_structured_logger,
    log_execution_time,
)


class TestCorrelationID:
    """Test correlation ID management."""

    def test_get_correlation_id_creates_new_id(self):
        """Test that get_correlation_id creates a new UUID if none exists."""
        clear_correlation_id()
        cid = get_correlation_id()

        assert cid is not None
        assert len(cid) == 36  # UUID format
        # Verify it's a valid UUID
        uuid.UUID(cid)

    def test_set_correlation_id_persists(self):
        """Test that set_correlation_id persists across function calls."""
        test_id = str(uuid.uuid4())
        set_correlation_id(test_id)

        assert get_correlation_id() == test_id

    def test_clear_correlation_id(self):
        """Test that clear_correlation_id removes the ID."""
        set_correlation_id(str(uuid.uuid4()))
        clear_correlation_id()

        # After clearing, a new ID should be generated
        new_id = get_correlation_id()
        assert new_id is not None

    def test_correlation_id_persists_across_calls(self):
        """Test correlation ID persists across multiple get calls."""
        clear_correlation_id()
        cid1 = get_correlation_id()
        cid2 = get_correlation_id()

        assert cid1 == cid2


class TestJSONFormatter:
    """Test JSON formatter."""

    def test_json_formatter_outputs_valid_json(self):
        """Test that JSON formatter outputs valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Should be valid JSON
        data = json.loads(output)
        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["module"] == "test"
        assert data["line"] == 42
        assert "correlation_id" in data
        assert "timestamp" in data

    def test_json_formatter_includes_correlation_id(self):
        """Test that JSON formatter includes correlation ID."""
        test_id = str(uuid.uuid4())
        set_correlation_id(test_id)

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["correlation_id"] == test_id

    def test_json_formatter_includes_extra_fields(self):
        """Test that JSON formatter includes extra fields."""
        formatter = JSONFormatter(include_extra=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.extra = {"user_id": "123", "graph_id": "abc"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["user_id"] == "123"
        assert data["graph_id"] == "abc"

    def test_json_formatter_handles_exceptions(self):
        """Test that JSON formatter includes exception information."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert "exception" in data
            assert "ValueError: Test error" in data["exception"]


class TestDevelopmentFormatter:
    """Test development formatter."""

    def test_development_formatter_includes_correlation_id(self):
        """Test that development formatter includes shortened correlation ID."""
        test_id = str(uuid.uuid4())
        set_correlation_id(test_id)

        formatter = DevelopmentFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Should include shortened correlation ID
        assert test_id[:8] in output
        assert "Test message" in output

    def test_development_formatter_includes_extra_fields(self):
        """Test that development formatter includes extra fields in message."""
        formatter = DevelopmentFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"user_id": "123"}

        output = formatter.format(record)

        assert "user_id=123" in output


class TestStructuredLogger:
    """Test structured logger."""

    def test_structured_logger_logs_with_context(self):
        """Test that structured logger includes context fields."""
        base_logger = logging.getLogger("test")
        logger = StructuredLogger(base_logger)

        with patch.object(base_logger, 'log') as mock_log:
            logger.info("Test message", user_id="123", graph_id="456")

            # Verify log was called with extra context
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert "extra" in call_kwargs
            assert call_kwargs["extra"]["extra"]["user_id"] == "123"
            assert call_kwargs["extra"]["extra"]["graph_id"] == "456"

    def test_structured_logger_debug_level(self):
        """Test structured logger debug method."""
        base_logger = logging.getLogger("test")
        logger = StructuredLogger(base_logger)

        with patch.object(base_logger, 'log') as mock_log:
            logger.debug("Debug message", key="value")

            mock_log.assert_called_once()
            assert mock_log.call_args[0][0] == logging.DEBUG

    def test_structured_logger_error_with_exc_info(self):
        """Test structured logger error method with exception info."""
        base_logger = logging.getLogger("test")
        logger = StructuredLogger(base_logger)

        with patch.object(base_logger, 'log') as mock_log:
            logger.error("Error message", exc_info=True, error_code="E001")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["exc_info"] is True

    def test_structured_logger_exception_method(self):
        """Test structured logger exception method automatically includes exc_info."""
        base_logger = logging.getLogger("test")
        logger = StructuredLogger(base_logger)

        with patch.object(base_logger, 'log') as mock_log:
            logger.exception("Exception occurred", error_code="E001")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["exc_info"] is True


class TestLogExecutionTime:
    """Test log execution time context manager."""

    def test_log_execution_time_success(self):
        """Test that log_execution_time logs start and completion."""
        base_logger = logging.getLogger("test")
        logger = StructuredLogger(base_logger)

        with patch.object(logger, 'info') as mock_info:
            with log_execution_time(logger, "test_operation", user_id="123"):
                time.sleep(0.01)  # Small delay

            # Should have been called twice: start and completion
            assert mock_info.call_count == 2

            # Check start log
            start_call = mock_info.call_args_list[0]
            assert "Starting test_operation" in start_call[0][0]
            assert start_call[1]["operation"] == "test_operation"
            assert start_call[1]["user_id"] == "123"

            # Check completion log
            complete_call = mock_info.call_args_list[1]
            assert "Completed test_operation" in complete_call[0][0]
            assert complete_call[1]["operation"] == "test_operation"
            assert "duration_ms" in complete_call[1]
            assert complete_call[1]["duration_ms"] >= 10  # At least 10ms

    def test_log_execution_time_failure(self):
        """Test that log_execution_time logs errors on exception."""
        base_logger = logging.getLogger("test")
        logger = StructuredLogger(base_logger)

        with patch.object(logger, 'info') as mock_info, \
             patch.object(logger, 'error') as mock_error:
            with pytest.raises(ValueError):
                with log_execution_time(logger, "test_operation"):
                    raise ValueError("Test error")

            # Should have start log
            assert mock_info.call_count == 1

            # Should have error log
            assert mock_error.call_count == 1
            error_call = mock_error.call_args
            assert "Failed test_operation" in error_call[0][0]
            assert error_call[1]["error"] == "Test error"
            assert error_call[1]["error_type"] == "ValueError"
            assert "duration_ms" in error_call[1]


class TestLogConfig:
    """Test log configuration."""

    def test_log_config_defaults(self):
        """Test that LogConfig uses default values."""
        config = LogConfig()

        assert config.format == LogFormat.HUMAN
        assert config.level == "INFO"
        assert config.include_correlation_id is True
        assert config.include_context is True

    def test_log_config_from_environment(self, monkeypatch):
        """Test that LogConfig reads from environment variables."""
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LOG_CORRELATION_ID", "false")
        monkeypatch.setenv("LOG_CONTEXT", "false")

        config = LogConfig()

        assert config.format == LogFormat.JSON
        assert config.level == "DEBUG"
        assert config.include_correlation_id is False
        assert config.include_context is False


class TestConfigureLogging:
    """Test logging configuration."""

    def test_configure_logging_json_format(self):
        """Test configure_logging sets up JSON formatter."""
        config = LogConfig()
        config.format = LogFormat.JSON

        configure_logging(config)

        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_configure_logging_human_format(self):
        """Test configure_logging sets up development formatter."""
        config = LogConfig()
        config.format = LogFormat.HUMAN

        configure_logging(config)

        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, DevelopmentFormatter)

    def test_configure_logging_sets_level(self):
        """Test configure_logging sets the log level."""
        config = LogConfig()
        config.level = "DEBUG"

        configure_logging(config)

        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        assert logger.level == logging.DEBUG


class TestGetStructuredLogger:
    """Test get_structured_logger function."""

    def test_get_structured_logger_returns_structured_logger(self):
        """Test that get_structured_logger returns a StructuredLogger instance."""
        logger = get_structured_logger("test")

        assert isinstance(logger, StructuredLogger)

    def test_get_structured_logger_with_name(self):
        """Test that get_structured_logger creates logger with correct name."""
        logger = get_structured_logger("test.module")

        assert logger._logger.name == "test.module"


class TestIntegration:
    """Integration tests for structured logging."""

    def test_end_to_end_json_logging(self):
        """Test complete JSON logging flow."""
        # Configure for JSON logging
        config = LogConfig()
        config.format = LogFormat.JSON
        configure_logging(config)

        # Set a correlation ID
        test_id = str(uuid.uuid4())
        set_correlation_id(test_id)

        # Create a logger and log a message with context
        logger = get_structured_logger("test.integration")

        # Capture the log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger._logger.addHandler(handler)
        logger._logger.setLevel(logging.INFO)

        logger.info("Integration test", user_id="123", operation="test")

        # Verify the output
        output = stream.getvalue()
        data = json.loads(output)

        assert data["message"] == "Integration test"
        assert data["correlation_id"] == test_id
        assert data["user_id"] == "123"
        assert data["operation"] == "test"
        assert data["level"] == "INFO"

    def test_end_to_end_performance_logging(self):
        """Test performance logging with timing."""
        config = LogConfig()
        config.format = LogFormat.JSON
        configure_logging(config)

        logger = get_structured_logger("test.performance")

        # Capture the log output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger._logger.addHandler(handler)
        logger._logger.setLevel(logging.INFO)

        with log_execution_time(logger, "test_task", task_id="T001"):
            time.sleep(0.01)

        # Verify the output
        output = stream.getvalue()
        lines = output.strip().split('\n')

        # Should have 2 log lines (start and complete)
        assert len(lines) == 2

        start_log = json.loads(lines[0])
        complete_log = json.loads(lines[1])

        assert "Starting test_task" in start_log["message"]
        assert "Completed test_task" in complete_log["message"]
        assert complete_log["duration_ms"] >= 10
        assert complete_log["task_id"] == "T001"
