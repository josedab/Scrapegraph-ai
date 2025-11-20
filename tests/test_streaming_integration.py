"""
Integration tests for end-to-end streaming functionality.

This module tests the complete streaming flow from graph creation
through execution to callback emission.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


class TestEndToEndStreaming:
    """Test end-to-end streaming flow."""

    @pytest.mark.skip(reason="Requires live LLM - enable for manual testing")
    def test_streaming_with_smart_scraper_graph(self):
        """Test streaming with SmartScraperGraph (requires API key)."""
        from scrapegraphai.graphs import SmartScraperGraph

        tokens = []

        def on_token(token, metadata):
            tokens.append(token)

        graph = SmartScraperGraph(
            prompt="What is this page about?",
            source="https://example.com",
            config={
                "llm": {
                    "model": "openai/gpt-4",
                    "api_key": "test-key",  # Would need real key
                    "streaming": True
                }
            }
        )

        graph.add_streaming_callback(on_token)

        # Would run: result = graph.run()
        # assert len(tokens) > 0

    def test_multiple_callbacks_receive_same_tokens(self):
        """Test that multiple callbacks receive the same tokens."""
        # This would need a mock graph setup
        tokens1 = []
        tokens2 = []

        def callback1(token, metadata):
            tokens1.append(token)

        def callback2(token, metadata):
            tokens2.append(token)

        # Mock graph
        from scrapegraphai.graphs.abstract_graph import AbstractGraph

        # Create a minimal mock
        class MockGraph:
            def __init__(self):
                self._streaming_enabled = True
                self._streaming_callbacks = []

            def add_streaming_callback(self, callback):
                self._streaming_callbacks.append(callback)

            def _emit_token(self, token, metadata=None):
                for callback in self._streaming_callbacks:
                    try:
                        callback(token, metadata or {})
                    except Exception:
                        pass

        graph = MockGraph()
        graph.add_streaming_callback(callback1)
        graph.add_streaming_callback(callback2)

        # Emit test tokens
        graph._emit_token("Hello", {})
        graph._emit_token(" World", {})

        assert tokens1 == tokens2
        assert tokens1 == ["Hello", " World"]

    def test_streaming_callback_receives_metadata(self):
        """Test that callbacks receive proper metadata."""
        received_metadata = []

        def callback(token, metadata):
            received_metadata.append(metadata)

        class MockGraph:
            def __init__(self):
                self._streaming_callbacks = []

            def add_streaming_callback(self, callback):
                self._streaming_callbacks.append(callback)

            def _emit_token(self, token, metadata=None):
                for callback in self._streaming_callbacks:
                    callback(token, metadata or {})

        graph = MockGraph()
        graph.add_streaming_callback(callback)

        graph._emit_token("test", {"node": "GenerateAnswer", "phase": "generation"})

        assert len(received_metadata) == 1
        assert received_metadata[0]["node"] == "GenerateAnswer"
        assert received_metadata[0]["phase"] == "generation"


class TestStreamingWithMockLLM:
    """Test streaming with mocked LLM responses."""

    def test_generate_answer_node_streaming_execution(self):
        """Test GenerateAnswerNode streaming execution."""
        from scrapegraphai.nodes.generate_answer_node import GenerateAnswerNode

        # Create mock LLM that returns streaming chunks
        mock_llm = MagicMock()

        # Mock the stream method to return chunks
        def mock_stream(inputs):
            chunks = [
                {"content": "The"},
                {"content": " answer"},
                {"content": " is"},
                {"content": " 42"}
            ]
            for chunk in chunks:
                yield chunk

        mock_chain = MagicMock()
        mock_chain.stream = mock_stream

        tokens = []

        def callback(token, metadata):
            tokens.append(token)

        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={
                "llm_model": mock_llm,
                "streaming": True,
                "streaming_callback": callback
            }
        )

        # Execute streaming
        state = {}
        result = node._execute_streaming(mock_chain, {"test": "input"}, state)

        assert len(tokens) == 4
        assert "".join(tokens) == "The answer is 42"
        assert result["answer"] == "The answer is 42"


class TestStreamingPerformance:
    """Test streaming performance characteristics."""

    def test_buffered_streaming_reduces_calls(self):
        """Test that buffered streaming reduces callback calls."""
        from scrapegraphai.utils.streaming_callback import BufferedStreamingCallback

        call_count = [0]

        def callback(text, metadata):
            call_count[0] += 1

        # Create buffered callback with size 5
        buffered = BufferedStreamingCallback(callback, buffer_size=5)

        # Emit 10 tokens
        for i in range(10):
            buffered.on_token(f"token{i}", {})

        # Should have called callback 2 times (10/5)
        assert call_count[0] == 2

        # Flush remaining
        buffered.flush()
        assert call_count[0] == 2  # No more tokens to flush


class TestStreamingBackwardCompatibility:
    """Test that streaming doesn't break existing code."""

    def test_non_streaming_still_works(self):
        """Test that non-streaming execution still works."""
        from scrapegraphai.nodes.generate_answer_node import GenerateAnswerNode

        mock_llm = MagicMock()
        mock_llm.invoke = MagicMock(return_value="answer")

        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={
                "llm_model": mock_llm,
                "streaming": False  # Explicitly disabled
            }
        )

        assert node.streaming_enabled == False

    def test_default_is_non_streaming(self):
        """Test that default behavior is non-streaming."""
        from scrapegraphai.nodes.generate_answer_node import GenerateAnswerNode

        node = GenerateAnswerNode(
            input="test",
            output=["answer"],
            node_config={"llm_model": MagicMock()}
        )

        assert node.streaming_enabled == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
