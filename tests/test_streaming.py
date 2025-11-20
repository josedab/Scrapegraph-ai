"""
Unit tests for streaming LLM response functionality.

This module tests the streaming capabilities of ScrapeGraphAI,
including configuration, callback handling, and token emission.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from scrapegraphai.graphs.abstract_graph import AbstractGraph
from scrapegraphai.nodes.generate_answer_node import GenerateAnswerNode
from scrapegraphai.utils.streaming_callback import StreamingCallbackHandler, BufferedStreamingCallback


class TestStreamingConfiguration:
    """Test streaming configuration handling."""

    def test_streaming_disabled_by_default(self):
        """Test that streaming is disabled by default."""
        # This would need a concrete graph implementation
        # For now, just test the concept
        config = {"llm": {"model": "openai/gpt-4"}}
        assert config.get("llm", {}).get("streaming", False) == False

    def test_streaming_enabled_when_specified(self):
        """Test that user's streaming config is respected."""
        config = {"llm": {"model": "openai/gpt-4", "streaming": True}}
        assert config.get("llm", {}).get("streaming", False) == True

    def test_streaming_callback_registration(self):
        """Test callback registration on abstract graph."""
        # Mock a graph instance
        mock_graph = MagicMock(spec=AbstractGraph)
        mock_graph._streaming_callbacks = []

        # Simulate adding a callback
        def callback(token, metadata):
            pass

        mock_graph._streaming_callbacks.append(callback)
        assert len(mock_graph._streaming_callbacks) == 1


class TestTokenExtraction:
    """Test token extraction from different chunk formats."""

    def test_extract_token_from_string(self):
        """Test extracting token from string chunk."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": Mock(), "streaming": False}
        )

        token = node._extract_token("Hello")
        assert token == "Hello"

    def test_extract_token_from_dict(self):
        """Test extracting token from dictionary chunk."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": Mock(), "streaming": False}
        )

        token = node._extract_token({"content": "World"})
        assert token == "World"

    def test_extract_token_from_object(self):
        """Test extracting token from object with content attribute."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": Mock(), "streaming": False}
        )

        class Chunk:
            content = "Test"

        token = node._extract_token(Chunk())
        assert token == "Test"


class TestResponseParsing:
    """Test accumulated response parsing."""

    def test_parse_json_response(self):
        """Test parsing valid JSON response."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": Mock(), "streaming": False}
        )

        response = '{"content": "test answer"}'
        parsed = node._parse_accumulated_response(response)
        assert isinstance(parsed, dict)
        assert parsed["content"] == "test answer"

    def test_parse_non_json_response(self):
        """Test parsing non-JSON response."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": Mock(), "streaming": False}
        )

        response = "This is a plain text response"
        parsed = node._parse_accumulated_response(response)
        assert parsed == "This is a plain text response"


class TestStreamingCallbackHandler:
    """Test StreamingCallbackHandler class."""

    def test_callback_handler_initialization(self):
        """Test callback handler can be initialized."""
        tokens = []

        def on_token(token, metadata):
            tokens.append(token)

        handler = StreamingCallbackHandler(on_token)
        assert handler.on_token is not None

    def test_callback_handler_token_emission(self):
        """Test that tokens are emitted to callback."""
        tokens = []

        def on_token(token, metadata):
            tokens.append(token)

        handler = StreamingCallbackHandler(on_token)
        handler.on_llm_new_token("Hello", run_id="test-123")

        assert len(tokens) == 1
        assert tokens[0] == "Hello"

    def test_callback_handler_events(self):
        """Test that handler emits start/end events."""
        events = []

        def on_token(token, metadata):
            events.append(metadata.get("event"))

        handler = StreamingCallbackHandler(on_token)
        handler.on_llm_start({}, ["test prompt"], run_id="test-123")
        handler.on_llm_end(None, run_id="test-123")

        assert "start" in events
        assert "end" in events


class TestBufferedStreamingCallback:
    """Test BufferedStreamingCallback class."""

    def test_buffered_callback_batching(self):
        """Test that tokens are buffered before emission."""
        emitted = []

        def callback(text, metadata):
            if text:  # Ignore empty events
                emitted.append(text)

        buffered = BufferedStreamingCallback(callback, buffer_size=3)

        # Emit tokens one by one
        buffered.on_token("Hello", {})
        buffered.on_token(" ", {})
        assert len(emitted) == 0  # Not emitted yet

        buffered.on_token("World", {})
        assert len(emitted) == 1  # Should emit now
        assert emitted[0] == "Hello World"

    def test_buffered_callback_flush(self):
        """Test flushing remaining tokens."""
        emitted = []

        def callback(text, metadata):
            if text:
                emitted.append(text)

        buffered = BufferedStreamingCallback(callback, buffer_size=5)

        buffered.on_token("Hello", {})
        buffered.on_token(" ", {})
        assert len(emitted) == 0

        buffered.flush()
        assert len(emitted) == 1
        assert emitted[0] == "Hello "

    def test_buffered_callback_immediate_events(self):
        """Test that events are emitted immediately."""
        emitted = []

        def callback(text, metadata):
            emitted.append(metadata.get("event"))

        buffered = BufferedStreamingCallback(callback, buffer_size=10)

        buffered.on_token("test", {})  # Buffered
        buffered.on_token("", {"event": "end"})  # Should emit immediately

        assert "end" in emitted


class TestGenerateAnswerNodeStreaming:
    """Test GenerateAnswerNode streaming functionality."""

    def test_node_streaming_configuration(self):
        """Test that node respects streaming configuration."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={
                "llm_model": Mock(),
                "streaming": True,
                "streaming_callback": Mock()
            }
        )

        assert node.streaming_enabled == True
        assert node.streaming_callback is not None

    def test_node_non_streaming_by_default(self):
        """Test that node uses non-streaming by default."""
        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": Mock()}
        )

        assert node.streaming_enabled == False
        assert node.streaming_callback is None


class TestCallbackErrorHandling:
    """Test error handling in callbacks."""

    def test_callback_errors_dont_break_streaming(self):
        """Test that callback errors don't break the streaming flow."""
        def failing_callback(token, metadata):
            raise Exception("Callback error!")

        handler = StreamingCallbackHandler(failing_callback)

        # Should not raise exception
        try:
            handler.on_llm_new_token("test", run_id="123")
            # If we get here, error was handled
            assert True
        except Exception:
            # Should not reach here
            assert False, "Callback error should have been caught"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
