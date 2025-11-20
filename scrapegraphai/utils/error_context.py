"""
Error context capture module for enhanced debugging of scraping failures.

This module provides rich error context capture including screenshots, HTML snapshots,
browser logs, network activity, and more to dramatically improve debuggability.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime
import json
import base64
from pathlib import Path
import traceback
import asyncio
import time

try:
    from playwright.async_api import Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = Any
    Browser = Any
    BrowserContext = Any


@dataclass
class ErrorContext:
    """
    Rich context information captured when a scraping error occurs.

    This class contains all the debugging information needed to understand
    what went wrong during a scraping operation.
    """

    # Basic error information
    error_type: str
    error_message: str
    stack_trace: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Page information
    url: str = ""
    final_url: str = ""  # After redirects
    page_title: str = ""

    # Visual context
    screenshot_base64: Optional[str] = None
    screenshot_path: Optional[str] = None

    # Content context
    html_content: Optional[str] = None
    html_length: int = 0

    # Browser context
    console_logs: List[Dict[str, Any]] = field(default_factory=list)
    network_logs: List[Dict[str, Any]] = field(default_factory=list)
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)

    # Request/Response context
    status_code: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    request_headers: Dict[str, str] = field(default_factory=dict)

    # Retry context
    attempt_number: int = 1
    total_attempts: int = 1

    # Performance context
    load_time_ms: Optional[float] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
            "url": self.url,
            "final_url": self.final_url,
            "page_title": self.page_title,
            "screenshot_path": self.screenshot_path,
            "html_length": self.html_length,
            "console_logs": self.console_logs,
            "network_logs": self.network_logs[-20:] if self.network_logs else [],  # Last 20 only
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "session_storage": self.session_storage,
            "status_code": self.status_code,
            "response_headers": self.response_headers,
            "request_headers": self.request_headers,
            "attempt_number": self.attempt_number,
            "total_attempts": self.total_attempts,
            "load_time_ms": self.load_time_ms,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_disk(self, output_dir: Path) -> Dict[str, Path]:
        """
        Save error context to disk for debugging.

        Returns:
            Dictionary mapping artifact type to file path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
        base_name = f"error_{timestamp}"

        saved_files = {}

        # Save JSON metadata
        json_path = output_dir / f"{base_name}_context.json"
        with open(json_path, "w") as f:
            f.write(self.to_json())
        saved_files["context"] = json_path

        # Save screenshot
        if self.screenshot_base64:
            screenshot_path = output_dir / f"{base_name}_screenshot.png"
            screenshot_data = base64.b64decode(self.screenshot_base64)
            with open(screenshot_path, "wb") as f:
                f.write(screenshot_data)
            saved_files["screenshot"] = screenshot_path
            self.screenshot_path = str(screenshot_path)

        # Save HTML
        if self.html_content:
            html_path = output_dir / f"{base_name}_page.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.html_content)
            saved_files["html"] = html_path

        # Save console logs
        if self.console_logs:
            console_path = output_dir / f"{base_name}_console.json"
            with open(console_path, "w") as f:
                json.dump(self.console_logs, f, indent=2)
            saved_files["console"] = console_path

        # Save network logs
        if self.network_logs:
            network_path = output_dir / f"{base_name}_network.json"
            with open(network_path, "w") as f:
                json.dump(self.network_logs, f, indent=2)
            saved_files["network"] = network_path

        return saved_files

    def get_summary(self) -> str:
        """Get a human-readable summary of the error context."""
        summary = [
            f"Error: {self.error_type}",
            f"Message: {self.error_message}",
            f"URL: {self.url}",
            f"Attempt: {self.attempt_number}/{self.total_attempts}",
            f"Timestamp: {self.timestamp.isoformat()}",
        ]

        if self.status_code:
            summary.append(f"Status Code: {self.status_code}")

        if self.html_length > 0:
            summary.append(f"HTML Length: {self.html_length} bytes")
        else:
            summary.append("HTML Length: 0 bytes (empty response)")

        if self.console_logs:
            error_logs = [log for log in self.console_logs if log.get("type") == "error"]
            if error_logs:
                summary.append(f"Console Errors: {len(error_logs)}")

        if self.screenshot_path:
            summary.append(f"Screenshot: {self.screenshot_path}")

        return "\n".join(summary)


class ScrapingException(Exception):
    """
    Enhanced exception that includes rich error context.
    """

    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.context = context

    def __str__(self) -> str:
        if self.context:
            return f"{super().__str__()}\n\nError Context:\n{self.context.get_summary()}"
        return super().__str__()


class ErrorContextCapture:
    """
    Captures rich debugging context from browser state on errors.
    """

    def __init__(
        self,
        capture_screenshot: bool = True,
        capture_html: bool = True,
        capture_console: bool = True,
        capture_network: bool = True,
        capture_storage: bool = True,
        save_to_disk: bool = False,
        output_dir: str = "./error_artifacts",
    ):
        self.capture_screenshot = capture_screenshot
        self.capture_html = capture_html
        self.capture_console = capture_console
        self.capture_network = capture_network
        self.capture_storage = capture_storage
        self.save_to_disk = save_to_disk
        self.output_dir = Path(output_dir)

        # Runtime state
        self._console_logs: List[Dict] = []
        self._network_logs: List[Dict] = []
        self._page: Optional[Page] = None

    def attach_listeners(self, page: Page) -> None:
        """Attach event listeners to capture runtime information."""
        if not PLAYWRIGHT_AVAILABLE:
            return

        self._page = page

        if self.capture_console:
            page.on("console", self._on_console_message)

        if self.capture_network:
            page.on("request", self._on_request)
            page.on("response", self._on_response)
            page.on("requestfailed", self._on_request_failed)

    def _on_console_message(self, msg) -> None:
        """Capture console messages."""
        try:
            self._console_logs.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location if hasattr(msg, 'location') else None,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            # Don't let listener errors break the scraping
            pass

    def _on_request(self, request) -> None:
        """Capture network requests."""
        try:
            self._network_logs.append({
                "event": "request",
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    def _on_response(self, response) -> None:
        """Capture network responses."""
        try:
            self._network_logs.append({
                "event": "response",
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers) if hasattr(response, 'headers') else {},
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    def _on_request_failed(self, request) -> None:
        """Capture failed requests."""
        try:
            self._network_logs.append({
                "event": "request_failed",
                "url": request.url,
                "failure": request.failure if hasattr(request, 'failure') else None,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    async def capture(
        self,
        error: Exception,
        page: Optional[Page] = None,
        url: str = "",
        attempt: int = 1,
        max_attempts: int = 1,
    ) -> ErrorContext:
        """
        Capture full error context from the current browser state.

        Args:
            error: The exception that occurred
            page: The Playwright page object (if available)
            url: The URL being scraped
            attempt: Current attempt number
            max_attempts: Maximum number of attempts

        Returns:
            ErrorContext object with all captured information
        """
        page = page or self._page

        context = ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            url=url,
            attempt_number=attempt,
            total_attempts=max_attempts,
        )

        if not page or not PLAYWRIGHT_AVAILABLE:
            return context

        try:
            # Capture basic page info
            context.final_url = page.url
            context.page_title = await page.title()

            # Capture screenshot
            if self.capture_screenshot:
                try:
                    screenshot_bytes = await page.screenshot(full_page=True, timeout=5000)
                    context.screenshot_base64 = base64.b64encode(screenshot_bytes).decode()
                except Exception as e:
                    context.metadata["screenshot_error"] = str(e)

            # Capture HTML content
            if self.capture_html:
                try:
                    context.html_content = await page.content()
                    context.html_length = len(context.html_content)
                except Exception as e:
                    context.metadata["html_error"] = str(e)

            # Capture console logs
            if self.capture_console:
                context.console_logs = self._console_logs.copy()

            # Capture network logs
            if self.capture_network:
                context.network_logs = self._network_logs.copy()

            # Capture storage
            if self.capture_storage:
                try:
                    # Cookies
                    browser_context = page.context
                    context.cookies = await browser_context.cookies()

                    # localStorage and sessionStorage
                    try:
                        context.local_storage = await page.evaluate("() => JSON.parse(JSON.stringify(localStorage))")
                    except Exception:
                        context.local_storage = {}

                    try:
                        context.session_storage = await page.evaluate("() => JSON.parse(JSON.stringify(sessionStorage))")
                    except Exception:
                        context.session_storage = {}
                except Exception as e:
                    context.metadata["storage_error"] = str(e)

        except Exception as capture_error:
            # Don't let capture errors mask the original error
            context.metadata["capture_error"] = str(capture_error)

        # Save to disk if configured
        if self.save_to_disk:
            try:
                saved_files = context.save_to_disk(self.output_dir)
                context.metadata["saved_files"] = {k: str(v) for k, v in saved_files.items()}
            except Exception as e:
                context.metadata["save_error"] = str(e)

        return context


class ErrorContextManager:
    """
    Context manager that wraps scraping operations with error context capture and retry logic.

    Usage:
        manager = ErrorContextManager(
            retry_policy=policy,
            capture_config=capture_config,
        )
        manager.set_page(page, url)
        result = await manager.execute_with_retry(operation, url)
    """

    def __init__(
        self,
        retry_policy=None,
        capture_config: Optional[dict] = None,
        on_retry: Optional[Callable[[int, Exception, ErrorContext], None]] = None,
        on_failure: Optional[Callable[[Exception, ErrorContext], None]] = None,
    ):
        # Avoid circular import by importing here
        from .retry_policy import DEFAULT_RETRY_POLICY

        self.retry_policy = retry_policy or DEFAULT_RETRY_POLICY
        self.capture_config = capture_config or {}
        self.on_retry = on_retry
        self.on_failure = on_failure

        self.capturer = ErrorContextCapture(**self.capture_config)

        self._page: Optional[Page] = None
        self._url: str = ""

    def set_page(self, page: Page, url: str = "") -> None:
        """Set the page and URL for context capture."""
        self._page = page
        self._url = url
        self.capturer.attach_listeners(page)

    async def execute_with_retry(
        self,
        operation: Callable,
        url: str = "",
    ) -> Any:
        """
        Execute an operation with retry logic and error context capture.

        Args:
            operation: Async function to execute
            url: URL being scraped (for context)

        Returns:
            Result of the operation

        Raises:
            ScrapingException: If operation fails after all retries
        """
        last_error = None
        last_context = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                # Execute the operation
                result = await operation()
                return result

            except Exception as e:
                last_error = e

                # Capture error context
                context = await self.capturer.capture(
                    error=e,
                    page=self._page,
                    url=url or self._url,
                    attempt=attempt,
                    max_attempts=self.retry_policy.max_attempts,
                )
                last_context = context

                # Check if should retry
                should_retry = self.retry_policy.should_retry(e, attempt)

                if not should_retry or attempt >= self.retry_policy.max_attempts:
                    # Final failure
                    if self.on_failure:
                        self.on_failure(e, context)

                    # Raise with context
                    raise ScrapingException(
                        f"Scraping failed after {attempt} attempt(s): {str(e)}",
                        context=context
                    ) from e

                # Will retry
                if self.on_retry:
                    self.on_retry(attempt, e, context)

                # Calculate and apply delay
                delay = self.retry_policy.get_delay(attempt)
                if delay > 0:
                    await asyncio.sleep(delay)

        # Should not reach here, but just in case
        raise ScrapingException(
            f"Scraping failed after all retries: {str(last_error)}",
            context=last_context
        ) from last_error
