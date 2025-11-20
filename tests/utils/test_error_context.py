"""
Unit tests for error_context module.
"""

import pytest
import asyncio
import json
import base64
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from scrapegraphai.utils.error_context import (
    ErrorContext,
    ScrapingException,
    ErrorContextCapture,
    ErrorContextManager,
)
from scrapegraphai.utils.retry_policy import RetryPolicy, RetryStrategy


class TestErrorContext:
    """Test ErrorContext dataclass."""

    def test_initialization(self):
        """Test basic initialization."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            stack_trace="Traceback...",
            url="https://example.com",
        )
        assert context.error_type == "ValueError"
        assert context.error_message == "Test error"
        assert context.url == "https://example.com"
        assert context.attempt_number == 1
        assert context.total_attempts == 1

    def test_to_dict(self):
        """Test conversion to dictionary."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            stack_trace="Traceback...",
            url="https://example.com",
        )
        data = context.to_dict()
        assert data["error_type"] == "ValueError"
        assert data["error_message"] == "Test error"
        assert data["url"] == "https://example.com"
        assert "timestamp" in data

    def test_to_json(self):
        """Test conversion to JSON string."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            stack_trace="Traceback...",
        )
        json_str = context.to_json()
        data = json.loads(json_str)
        assert data["error_type"] == "ValueError"
        assert data["error_message"] == "Test error"

    def test_get_summary(self):
        """Test summary generation."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            stack_trace="Traceback...",
            url="https://example.com",
            status_code=404,
            html_length=1024,
        )
        summary = context.get_summary()
        assert "ValueError" in summary
        assert "Test error" in summary
        assert "https://example.com" in summary
        assert "404" in summary
        assert "1024 bytes" in summary

    def test_save_to_disk(self, tmp_path):
        """Test saving error context to disk."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            stack_trace="Traceback...",
            url="https://example.com",
            html_content="<html>Test</html>",
            console_logs=[{"type": "error", "text": "JS error"}],
            network_logs=[{"event": "request", "url": "https://example.com"}],
        )

        # Add a screenshot
        screenshot_data = b"fake_image_data"
        context.screenshot_base64 = base64.b64encode(screenshot_data).decode()

        # Save to temp directory
        saved_files = context.save_to_disk(tmp_path)

        # Verify files were created
        assert "context" in saved_files
        assert "screenshot" in saved_files
        assert "html" in saved_files
        assert "console" in saved_files
        assert "network" in saved_files

        # Verify file contents
        assert saved_files["context"].exists()
        assert saved_files["screenshot"].exists()
        assert saved_files["html"].exists()

        # Check JSON content
        with open(saved_files["context"]) as f:
            data = json.load(f)
            assert data["error_type"] == "ValueError"


class TestScrapingException:
    """Test ScrapingException class."""

    def test_basic_exception(self):
        """Test basic exception without context."""
        exc = ScrapingException("Test error")
        assert str(exc) == "Test error"
        assert exc.context is None

    def test_exception_with_context(self):
        """Test exception with error context."""
        context = ErrorContext(
            error_type="ValueError",
            error_message="Test error",
            stack_trace="Traceback...",
            url="https://example.com",
        )
        exc = ScrapingException("Test error", context=context)
        assert exc.context is not None
        assert exc.context.error_type == "ValueError"

        # String representation should include context summary
        exc_str = str(exc)
        assert "Test error" in exc_str
        assert "Error Context:" in exc_str
        assert "ValueError" in exc_str


class TestErrorContextCapture:
    """Test ErrorContextCapture class."""

    def test_initialization(self):
        """Test initialization with default values."""
        capturer = ErrorContextCapture()
        assert capturer.capture_screenshot is True
        assert capturer.capture_html is True
        assert capturer.capture_console is True
        assert capturer.capture_network is True

    def test_initialization_custom(self):
        """Test initialization with custom values."""
        capturer = ErrorContextCapture(
            capture_screenshot=False,
            capture_html=False,
            save_to_disk=True,
            output_dir="/tmp/errors",
        )
        assert capturer.capture_screenshot is False
        assert capturer.capture_html is False
        assert capturer.save_to_disk is True
        assert capturer.output_dir == Path("/tmp/errors")

    @pytest.mark.asyncio
    async def test_capture_without_page(self):
        """Test capture without a page object."""
        capturer = ErrorContextCapture()
        error = ValueError("Test error")

        context = await capturer.capture(
            error=error,
            page=None,
            url="https://example.com",
            attempt=1,
            max_attempts=3,
        )

        assert context.error_type == "ValueError"
        assert context.error_message == "Test error"
        assert context.url == "https://example.com"
        assert context.attempt_number == 1
        assert context.total_attempts == 3

    @pytest.mark.asyncio
    async def test_capture_with_mock_page(self):
        """Test capture with a mock page object."""
        # Create a mock page
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/final"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot")
        mock_page.content = AsyncMock(return_value="<html>Test Content</html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value={})

        capturer = ErrorContextCapture()
        error = ValueError("Test error")

        context = await capturer.capture(
            error=error,
            page=mock_page,
            url="https://example.com",
            attempt=2,
            max_attempts=3,
        )

        assert context.error_type == "ValueError"
        assert context.final_url == "https://example.com/final"
        assert context.page_title == "Test Page"
        assert context.html_content == "<html>Test Content</html>"
        assert context.html_length == len("<html>Test Content</html>")
        assert context.screenshot_base64 is not None

    @pytest.mark.asyncio
    async def test_capture_with_save_to_disk(self, tmp_path):
        """Test capture with save_to_disk enabled."""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot")
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value={})

        capturer = ErrorContextCapture(
            save_to_disk=True,
            output_dir=str(tmp_path),
        )
        error = ValueError("Test error")

        context = await capturer.capture(
            error=error,
            page=mock_page,
            url="https://example.com",
        )

        # Check that files were saved
        assert "saved_files" in context.metadata
        saved_files = context.metadata["saved_files"]
        assert "context" in saved_files
        assert "screenshot" in saved_files

    def test_attach_listeners(self):
        """Test attaching event listeners to a page."""
        mock_page = Mock()
        mock_page.on = Mock()

        capturer = ErrorContextCapture()
        capturer.attach_listeners(mock_page)

        # Verify listeners were attached
        assert mock_page.on.call_count >= 4  # console, request, response, requestfailed


class TestErrorContextManager:
    """Test ErrorContextManager class."""

    def test_initialization(self):
        """Test initialization."""
        policy = RetryPolicy(max_attempts=3)
        manager = ErrorContextManager(
            retry_policy=policy,
            capture_config={"capture_screenshot": True},
        )
        assert manager.retry_policy == policy
        assert manager.capture_config == {"capture_screenshot": True}

    def test_initialization_with_defaults(self):
        """Test initialization with default retry policy."""
        manager = ErrorContextManager()
        assert manager.retry_policy is not None
        assert manager.retry_policy.max_attempts == 3

    def test_set_page(self):
        """Test setting page and URL."""
        mock_page = Mock()
        mock_page.on = Mock()

        manager = ErrorContextManager()
        manager.set_page(mock_page, "https://example.com")

        assert manager._page == mock_page
        assert manager._url == "https://example.com"

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self):
        """Test successful execution on first attempt."""
        manager = ErrorContextManager()

        async def operation():
            return "success"

        result = await manager.execute_with_retry(operation, "https://example.com")
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retries(self):
        """Test successful execution after retries."""
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.IMMEDIATE,
        )
        manager = ErrorContextManager(retry_policy=policy)

        # Mock page
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.screenshot = AsyncMock(return_value=b"fake")
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value={})

        manager.set_page(mock_page, "https://example.com")

        attempt_count = [0]

        async def operation():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise TimeoutError("timeout")
            return "success"

        result = await manager.execute_with_retry(operation, "https://example.com")
        assert result == "success"
        assert attempt_count[0] == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_failure_exhausted(self):
        """Test failure after exhausting retries."""
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.IMMEDIATE,
        )
        manager = ErrorContextManager(retry_policy=policy)

        # Mock page
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.screenshot = AsyncMock(return_value=b"fake")
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value={})

        manager.set_page(mock_page, "https://example.com")

        async def operation():
            raise TimeoutError("timeout")

        with pytest.raises(ScrapingException) as exc_info:
            await manager.execute_with_retry(operation, "https://example.com")

        assert "timeout" in str(exc_info.value)
        assert exc_info.value.context is not None
        assert exc_info.value.context.error_type == "TimeoutError"

    @pytest.mark.asyncio
    async def test_execute_with_retry_permanent_error(self):
        """Test immediate failure with permanent error."""
        policy = RetryPolicy(max_attempts=5)
        manager = ErrorContextManager(retry_policy=policy)

        # Mock page
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.screenshot = AsyncMock(return_value=b"fake")
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value={})

        manager.set_page(mock_page, "https://example.com")

        async def operation():
            raise ValueError("invalid input")

        with pytest.raises(ScrapingException) as exc_info:
            await manager.execute_with_retry(operation, "https://example.com")

        # Should fail on first attempt (ValueError is non-retryable)
        assert exc_info.value.context.attempt_number == 1

    @pytest.mark.asyncio
    async def test_execute_with_retry_callbacks(self):
        """Test retry and failure callbacks."""
        policy = RetryPolicy(
            max_attempts=3,
            strategy=RetryStrategy.IMMEDIATE,
        )

        retry_calls = []
        failure_calls = []

        def on_retry(attempt, error, context):
            retry_calls.append((attempt, str(error)))

        def on_failure(error, context):
            failure_calls.append(str(error))

        manager = ErrorContextManager(
            retry_policy=policy,
            on_retry=on_retry,
            on_failure=on_failure,
        )

        # Mock page
        mock_page = AsyncMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Test")
        mock_page.screenshot = AsyncMock(return_value=b"fake")
        mock_page.content = AsyncMock(return_value="<html>Test</html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[])
        mock_page.evaluate = AsyncMock(return_value={})

        manager.set_page(mock_page, "https://example.com")

        async def operation():
            raise TimeoutError("timeout")

        with pytest.raises(ScrapingException):
            await manager.execute_with_retry(operation, "https://example.com")

        # Should have 2 retry calls (attempts 1 and 2, then fail on 3)
        assert len(retry_calls) == 2
        assert len(failure_calls) == 1


class TestIntegration:
    """Integration tests for error context capture."""

    @pytest.mark.asyncio
    async def test_full_error_capture_flow(self, tmp_path):
        """Test complete error capture flow with save to disk."""
        # Setup
        policy = RetryPolicy(max_attempts=2, strategy=RetryStrategy.IMMEDIATE)
        capture_config = {
            "capture_screenshot": True,
            "capture_html": True,
            "save_to_disk": True,
            "output_dir": str(tmp_path),
        }

        manager = ErrorContextManager(
            retry_policy=policy,
            capture_config=capture_config,
        )

        # Mock page
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/page"
        mock_page.title = AsyncMock(return_value="Test Page")
        mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot_data")
        mock_page.content = AsyncMock(return_value="<html><body>Test Content</body></html>")
        mock_page.context = Mock()
        mock_page.context.cookies = AsyncMock(return_value=[{"name": "test", "value": "cookie"}])
        mock_page.evaluate = AsyncMock(return_value={"key": "value"})

        manager.set_page(mock_page, "https://example.com")

        # Operation that always fails
        async def failing_operation():
            raise TimeoutError("Timeout after 30s")

        # Execute and expect failure
        with pytest.raises(ScrapingException) as exc_info:
            await manager.execute_with_retry(failing_operation)

        # Verify exception has context
        assert exc_info.value.context is not None
        context = exc_info.value.context

        # Verify context contents
        assert context.error_type == "TimeoutError"
        assert context.error_message == "Timeout after 30s"
        assert context.final_url == "https://example.com/page"
        assert context.page_title == "Test Page"
        assert context.html_content == "<html><body>Test Content</body></html>"
        assert context.screenshot_base64 is not None

        # Verify files were saved
        assert "saved_files" in context.metadata
        saved_files = context.metadata["saved_files"]
        assert Path(saved_files["context"]).exists()
        assert Path(saved_files["screenshot"]).exists()
        assert Path(saved_files["html"]).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
