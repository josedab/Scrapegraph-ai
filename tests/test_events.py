"""
Unit tests for the event system.
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from scrapegraphai.events import Event, EventType, EventEmitter, EventHandler


class TestEventTypes:
    """Test event types and event data structures."""

    def test_event_creation(self):
        """Test creating an event."""
        event = Event(
            event_type=EventType.GRAPH_STARTED,
            graph_id="test-123",
            graph_name="TestGraph",
            data={"test": "data"}
        )

        assert event.event_type == EventType.GRAPH_STARTED
        assert event.graph_id == "test-123"
        assert event.graph_name == "TestGraph"
        assert event.data == {"test": "data"}
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = Event(
            event_type=EventType.NODE_COMPLETED,
            graph_id="test-123",
            node_name="TestNode",
            data={"progress": 50}
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "node.completed"
        assert event_dict["graph_id"] == "test-123"
        assert event_dict["node_name"] == "TestNode"
        assert event_dict["data"]["progress"] == 50

    def test_event_to_json(self):
        """Test converting event to JSON."""
        event = Event(
            event_type=EventType.GRAPH_COMPLETED,
            graph_id="test-123",
        )

        event_json = event.to_json()
        parsed = json.loads(event_json)

        assert parsed["event_type"] == "graph.completed"
        assert parsed["graph_id"] == "test-123"

    def test_event_with_error(self):
        """Test creating an event with error information."""
        event = Event(
            event_type=EventType.NODE_FAILED,
            node_name="FailedNode",
            error="Test error",
            error_type="ValueError",
            stack_trace="Test stack trace"
        )

        assert event.error == "Test error"
        assert event.error_type == "ValueError"
        assert event.stack_trace == "Test stack trace"


class TestEventEmitter:
    """Test event emitter functionality."""

    def test_emitter_creation(self):
        """Test creating an event emitter."""
        emitter = EventEmitter({"events_enabled": True})

        assert emitter._enabled is True
        assert emitter._handlers == []

    def test_emitter_disabled(self):
        """Test that disabled emitter doesn't emit events."""
        emitter = EventEmitter({"events_enabled": False})

        event_received = []

        class TestHandler(EventHandler):
            def handle(self, event):
                event_received.append(event)

        emitter.add_handler(TestHandler({}))
        emitter.emit(Event(event_type=EventType.GRAPH_STARTED))

        assert len(event_received) == 0

    def test_add_remove_handler(self):
        """Test adding and removing handlers."""
        emitter = EventEmitter({"events_enabled": True})

        class TestHandler(EventHandler):
            def handle(self, event):
                pass

        handler = TestHandler({})
        emitter.add_handler(handler)
        assert len(emitter._handlers) == 1

        emitter.remove_handler(handler)
        assert len(emitter._handlers) == 0

    def test_emit_sync(self):
        """Test synchronous event emission."""
        emitter = EventEmitter({
            "events_enabled": True,
            "async_delivery": False
        })

        events_received = []

        class TestHandler(EventHandler):
            def handle(self, event):
                events_received.append(event)

        emitter.add_handler(TestHandler({}))

        event = Event(event_type=EventType.GRAPH_STARTED)
        emitter.emit(event, blocking=True)

        assert len(events_received) == 1
        assert events_received[0].event_type == EventType.GRAPH_STARTED


class TestEventHandler:
    """Test event handler base class."""

    def test_should_handle_all_events(self):
        """Test handler that should handle all events."""
        handler = EventHandler({})

        assert handler.should_handle(Event(event_type=EventType.GRAPH_STARTED))
        assert handler.should_handle(Event(event_type=EventType.NODE_COMPLETED))

    def test_should_handle_specific_events(self):
        """Test handler that should handle specific events."""
        handler = EventHandler({
            "event_types": ["graph.started", "graph.completed"]
        })

        assert handler.should_handle(Event(event_type=EventType.GRAPH_STARTED))
        assert handler.should_handle(Event(event_type=EventType.GRAPH_COMPLETED))
        assert not handler.should_handle(Event(event_type=EventType.NODE_STARTED))

    def test_handler_not_implemented(self):
        """Test that base handler raises NotImplementedError."""
        handler = EventHandler({})

        with pytest.raises(NotImplementedError):
            handler.handle(Event(event_type=EventType.GRAPH_STARTED))


class TestLogHandler:
    """Test log handler functionality."""

    def test_log_handler_creation(self):
        """Test creating a log handler."""
        from scrapegraphai.events.handlers.log import LogHandler

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name

        try:
            handler = LogHandler({
                "log_file": log_file,
                "event_types": ["graph.completed"]
            })

            assert handler.log_file == log_file
            assert handler.log_format == "json"

            handler.cleanup()

        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)

    def test_log_handler_writes_events(self):
        """Test that log handler writes events to file."""
        from scrapegraphai.events.handlers.log import LogHandler

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            log_file = f.name

        try:
            handler = LogHandler({
                "log_file": log_file,
            })

            event = Event(
                event_type=EventType.GRAPH_COMPLETED,
                graph_id="test-123"
            )

            handler.handle(event)
            handler.cleanup()

            # Read the log file
            with open(log_file, 'r') as f:
                content = f.read()

            assert "graph.completed" in content
            assert "test-123" in content

        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)


class TestWebhookHandler:
    """Test webhook handler functionality."""

    def test_webhook_handler_requires_url(self):
        """Test that webhook handler requires URL."""
        from scrapegraphai.events.handlers.webhook import WebhookHandler

        with pytest.raises(ValueError, match="requires 'url'"):
            WebhookHandler({})

    def test_webhook_handler_creation(self):
        """Test creating a webhook handler."""
        from scrapegraphai.events.handlers.webhook import WebhookHandler

        handler = WebhookHandler({
            "url": "https://example.com/webhook",
            "event_types": ["graph.completed"]
        })

        assert handler.url == "https://example.com/webhook"
        assert handler.method == "POST"
        assert handler.timeout == 30
        assert handler.retry_count == 3


class TestZapierWebhookHandler:
    """Test Zapier webhook handler."""

    def test_zapier_payload_preparation(self):
        """Test Zapier-specific payload preparation."""
        from scrapegraphai.events.handlers.webhook import ZapierWebhookHandler

        handler = ZapierWebhookHandler({
            "url": "https://hooks.zapier.com/test"
        })

        event = Event(
            event_type=EventType.GRAPH_COMPLETED,
            data={
                "result": "test result",
                "count": 5
            }
        )

        payload = handler._prepare_payload(event)

        # Check that data fields are flattened with data_ prefix
        assert "data_result" in payload
        assert "data_count" in payload
        assert payload["data_result"] == "test result"
        assert payload["data_count"] == 5


class TestN8nWebhookHandler:
    """Test n8n webhook handler."""

    def test_n8n_payload_preparation(self):
        """Test n8n-specific payload preparation."""
        from scrapegraphai.events.handlers.webhook import N8nWebhookHandler

        handler = N8nWebhookHandler({
            "url": "https://n8n.example.com/webhook/test"
        })

        event = Event(
            event_type=EventType.GRAPH_COMPLETED,
            graph_id="test-123",
            graph_name="TestGraph",
            data={"result": "test"}
        )

        payload = handler._prepare_payload(event)

        # Check n8n structure
        assert payload["event"] == "graph.completed"
        assert payload["id"] == event.event_id
        assert payload["body"] == {"result": "test"}
        assert payload["metadata"]["graph_id"] == "test-123"
        assert payload["metadata"]["graph_name"] == "TestGraph"


class TestQueueHandler:
    """Test queue handler functionality."""

    def test_queue_handler_requires_type(self):
        """Test that queue handler requires queue_type."""
        from scrapegraphai.events.handlers.queue import QueueHandler

        with pytest.raises(ValueError, match="requires 'queue_type'"):
            QueueHandler({})

    def test_queue_handler_unsupported_type(self):
        """Test that queue handler rejects unsupported types."""
        from scrapegraphai.events.handlers.queue import QueueHandler

        with pytest.raises(ValueError, match="Unsupported queue type"):
            QueueHandler({
                "queue_type": "unsupported",
                "connection_string": "test"
            })


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
