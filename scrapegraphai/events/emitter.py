"""
Core event emission system for ScrapeGraphAI.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from .event_types import Event, EventType

logger = logging.getLogger(__name__)


class EventHandler:
    """Base class for event handlers."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the handler.

        Args:
            config: Handler-specific configuration
        """
        self.config = config
        self.event_types = config.get("event_types", [])  # Empty = all events

    def should_handle(self, event: Event) -> bool:
        """
        Determine if this handler should handle the event.

        Args:
            event: The event to check

        Returns:
            True if handler should process this event
        """
        # If no event types specified, handle all events
        if not self.event_types:
            return True

        # Check if event type is in handler's list
        return event.event_type.value in self.event_types or event.event_type in self.event_types

    def handle(self, event: Event):
        """
        Handle the event.

        Args:
            event: The event to handle
        """
        raise NotImplementedError("Handlers must implement handle()")

    def cleanup(self):
        """Cleanup handler resources."""
        pass


class EventEmitter:
    """
    Core event emission system for ScrapeGraphAI.

    Manages event handlers and dispatches events to configured destinations.
    Supports both synchronous and asynchronous handlers.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the event emitter.

        Args:
            config: Configuration dictionary with handler settings
        """
        self.config = config or {}
        self._handlers: List[EventHandler] = []
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._async_mode = self.config.get("async_delivery", True)
        self._enabled = self.config.get("events_enabled", True)

        # Initialize handlers from config
        self._initialize_handlers()

    def _initialize_handlers(self):
        """Initialize event handlers from configuration."""
        handlers_config = self.config.get("event_handlers", [])

        for handler_config in handlers_config:
            handler_type = handler_config.get("type")

            try:
                if handler_type == "webhook":
                    from .handlers.webhook import WebhookHandler
                    self._handlers.append(WebhookHandler(handler_config))

                elif handler_type == "queue":
                    from .handlers.queue import QueueHandler
                    self._handlers.append(QueueHandler(handler_config))

                elif handler_type == "log":
                    from .handlers.log import LogHandler
                    self._handlers.append(LogHandler(handler_config))

                elif handler_type == "custom":
                    # Load custom handler from module path
                    handler_class = self._load_custom_handler(handler_config.get("class"))
                    self._handlers.append(handler_class(handler_config))

            except Exception as e:
                logger.error(f"Failed to initialize {handler_type} handler: {e}")

    def add_handler(self, handler: EventHandler):
        """Add an event handler."""
        self._handlers.append(handler)

    def remove_handler(self, handler: EventHandler):
        """Remove an event handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def emit(self, event: Event, blocking: bool = False):
        """
        Emit an event to all registered handlers.

        Args:
            event: The event to emit
            blocking: If True, wait for all handlers to complete (default: False)
        """
        if not self._enabled:
            return

        logger.debug(f"Emitting event: {event.event_type} (id: {event.event_id})")

        if self._async_mode and not blocking:
            # Async delivery - don't block caller
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._emit_async(event))
                else:
                    self._executor.submit(self._emit_sync, event)
            except RuntimeError:
                # No event loop running, use thread pool
                self._executor.submit(self._emit_sync, event)
        else:
            # Synchronous delivery
            self._emit_sync(event)

    def _emit_sync(self, event: Event):
        """Emit event to all handlers synchronously."""
        for handler in self._handlers:
            # Check if handler wants this event type
            if handler.should_handle(event):
                try:
                    handler.handle(event)
                except Exception as e:
                    logger.error(f"Handler {handler.__class__.__name__} failed: {e}")

    async def _emit_async(self, event: Event):
        """Emit event to all handlers asynchronously."""
        tasks = []

        for handler in self._handlers:
            if handler.should_handle(event):
                if asyncio.iscoroutinefunction(handler.handle):
                    tasks.append(handler.handle(event))
                else:
                    # Run sync handler in executor
                    tasks.append(
                        asyncio.get_event_loop().run_in_executor(
                            self._executor,
                            handler.handle,
                            event
                        )
                    )

        # Wait for all handlers to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Handler failed: {result}")

    def shutdown(self):
        """Shutdown the event emitter and cleanup resources."""
        self._executor.shutdown(wait=True)

        for handler in self._handlers:
            if hasattr(handler, 'cleanup'):
                try:
                    handler.cleanup()
                except Exception as e:
                    logger.error(f"Handler cleanup failed: {e}")

    def _load_custom_handler(self, class_path: str):
        """Dynamically load a custom handler class."""
        import importlib

        module_path, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
