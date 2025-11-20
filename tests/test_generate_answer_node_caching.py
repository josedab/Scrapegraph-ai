"""
Integration tests for GenerateAnswerNode caching functionality
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch
from scrapegraphai.nodes.generate_answer_node import GenerateAnswerNode


class DummyLLMWithCaching:
    """Dummy LLM for testing caching."""

    def __init__(self):
        self.call_count = 0
        self.temperature = 0.0
        self.model_name = "test-model"

    def __or__(self, other):
        """Support pipe operator for chain composition."""
        return self

    def invoke(self, inputs):
        """Simulate LLM invocation."""
        self.call_count += 1
        return {"answer": f"Response {self.call_count}"}


class DummyLogger:
    """Dummy logger for testing."""

    def info(self, msg):
        pass

    def error(self, msg):
        pass

    def debug(self, msg):
        pass


@pytest.fixture
def cached_node_memory():
    """Create a GenerateAnswerNode with memory cache enabled."""
    llm = DummyLLMWithCaching()
    node_config = {
        "llm_model": llm,
        "verbose": False,
        "timeout": 480,
        "llm_cache": {
            "enabled": True,
            "backend": "memory",
            "ttl": 3600
        }
    }
    node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)
    node.logger = DummyLogger()
    node.get_input_keys = lambda state: ["user_prompt", "doc"]
    return node, llm


@pytest.fixture
def cached_node_sqlite():
    """Create a GenerateAnswerNode with SQLite cache enabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_cache.db")
        llm = DummyLLMWithCaching()
        node_config = {
            "llm_model": llm,
            "verbose": False,
            "timeout": 480,
            "llm_cache": {
                "enabled": True,
                "backend": "sqlite",
                "backend_config": {"db_path": db_path},
                "ttl": 3600
            }
        }
        node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)
        node.logger = DummyLogger()
        node.get_input_keys = lambda state: ["user_prompt", "doc"]
        yield node, llm, db_path


def test_cache_initialization():
    """Test that cache is initialized correctly."""
    node_config = {
        "llm_model": DummyLLMWithCaching(),
        "llm_cache": {
            "enabled": True,
            "backend": "memory"
        }
    }
    node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)

    assert node.llm_cache is not None
    assert node.llm_cache.enabled is True


def test_cache_disabled_by_default():
    """Test that cache is disabled by default."""
    node_config = {
        "llm_model": DummyLLMWithCaching()
    }
    node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)

    assert node.llm_cache is not None
    assert node.llm_cache.enabled is False


def test_cache_hit_on_second_call(cached_node_memory):
    """Test that second call with same inputs hits cache."""
    node, llm = cached_node_memory

    state = {
        "user_prompt": "What is this?",
        "doc": ["Test content"]
    }

    # First call - cache miss
    result1 = node.execute(state.copy())
    first_call_count = llm.call_count

    # Second call - cache hit
    result2 = node.execute(state.copy())
    second_call_count = llm.call_count

    # LLM should only be called once
    assert first_call_count == 1
    assert second_call_count == 1  # No additional calls

    # Results should be the same
    assert result1["output"] == result2["output"]

    # Cache metrics
    assert node.llm_cache.hits == 1
    assert node.llm_cache.misses == 1


def test_cache_miss_with_different_prompt(cached_node_memory):
    """Test that different prompts result in cache miss."""
    node, llm = cached_node_memory

    state1 = {
        "user_prompt": "What is this?",
        "doc": ["Test content"]
    }

    state2 = {
        "user_prompt": "What is that?",
        "doc": ["Test content"]
    }

    # First call
    node.execute(state1.copy())
    first_call_count = llm.call_count

    # Second call with different prompt
    node.execute(state2.copy())
    second_call_count = llm.call_count

    # LLM should be called twice
    assert first_call_count == 1
    assert second_call_count == 2

    # Cache metrics
    assert node.llm_cache.hits == 0
    assert node.llm_cache.misses == 2


def test_cache_miss_with_different_content(cached_node_memory):
    """Test that different content results in cache miss."""
    node, llm = cached_node_memory

    state1 = {
        "user_prompt": "What is this?",
        "doc": ["Test content 1"]
    }

    state2 = {
        "user_prompt": "What is this?",
        "doc": ["Test content 2"]
    }

    # First call
    node.execute(state1.copy())
    first_call_count = llm.call_count

    # Second call with different content
    node.execute(state2.copy())
    second_call_count = llm.call_count

    # LLM should be called twice
    assert first_call_count == 1
    assert second_call_count == 2

    # Cache metrics
    assert node.llm_cache.hits == 0
    assert node.llm_cache.misses == 2


def test_sqlite_cache_persistence(cached_node_sqlite):
    """Test that SQLite cache persists across node instances."""
    node1, llm1, db_path = cached_node_sqlite

    state = {
        "user_prompt": "What is this?",
        "doc": ["Test content"]
    }

    # First call with first node
    result1 = node1.execute(state.copy())
    assert llm1.call_count == 1

    # Create second node instance with same cache
    llm2 = DummyLLMWithCaching()
    node_config = {
        "llm_model": llm2,
        "verbose": False,
        "timeout": 480,
        "llm_cache": {
            "enabled": True,
            "backend": "sqlite",
            "backend_config": {"db_path": db_path},
            "ttl": 3600
        }
    }
    node2 = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)
    node2.logger = DummyLogger()
    node2.get_input_keys = lambda state: ["user_prompt", "doc"]

    # Second call with second node - should hit cache
    result2 = node2.execute(state.copy())

    # Second LLM should not be called
    assert llm2.call_count == 0

    # Results should be the same
    assert result1["output"] == result2["output"]


def test_cache_metrics_tracking(cached_node_memory):
    """Test that cache metrics are tracked correctly."""
    node, llm = cached_node_memory

    state = {
        "user_prompt": "What is this?",
        "doc": ["Test content"]
    }

    # First call - cache miss
    node.execute(state.copy())

    # Second call - cache hit
    node.execute(state.copy())

    # Third call - cache hit
    node.execute(state.copy())

    metrics = node.llm_cache.get_metrics()

    assert metrics["enabled"] is True
    assert metrics["hits"] == 2
    assert metrics["misses"] == 1
    assert metrics["errors"] == 0
    assert "hit_rate" in metrics
    assert metrics["backend"] == "memory"


def test_model_identifier_openai():
    """Test model identifier extraction for OpenAI."""
    from langchain_openai import ChatOpenAI

    mock_llm = MagicMock(spec=ChatOpenAI)
    mock_llm.model_name = "gpt-4"

    node_config = {
        "llm_model": mock_llm,
        "llm_cache": {"enabled": False}
    }
    node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)

    identifier = node._get_model_identifier()
    assert identifier == "openai/gpt-4"


def test_model_identifier_bedrock():
    """Test model identifier extraction for Bedrock."""
    from langchain_aws import ChatBedrock

    mock_llm = MagicMock(spec=ChatBedrock)
    mock_llm.model = "anthropic.claude-v2"

    node_config = {
        "llm_model": mock_llm,
        "llm_cache": {"enabled": False}
    }
    node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)

    identifier = node._get_model_identifier()
    assert identifier == "bedrock/anthropic.claude-v2"


def test_model_identifier_ollama():
    """Test model identifier extraction for Ollama."""
    from langchain_community.chat_models import ChatOllama

    mock_llm = MagicMock(spec=ChatOllama)
    mock_llm.model = "llama2"

    node_config = {
        "llm_model": mock_llm,
        "llm_cache": {"enabled": False}
    }
    node = GenerateAnswerNode("user_prompt & doc", ["output"], node_config=node_config)

    identifier = node._get_model_identifier()
    assert identifier == "ollama/llama2"


def test_cache_with_multi_chunk_content(cached_node_memory):
    """Test caching with multiple content chunks."""
    node, llm = cached_node_memory

    state = {
        "user_prompt": "Summarize this",
        "doc": ["Chunk 1", "Chunk 2", "Chunk 3"]
    }

    # First call - cache miss
    result1 = node.execute(state.copy())
    first_call_count = llm.call_count

    # Second call - cache hit
    result2 = node.execute(state.copy())
    second_call_count = llm.call_count

    # For multi-chunk, multiple LLM calls are made on first execution
    assert first_call_count > 1
    # On second execution, no new calls should be made (cache hit)
    assert second_call_count == first_call_count

    # Results should be the same
    assert result1["output"] == result2["output"]


def test_cache_error_handling(cached_node_memory):
    """Test that cache errors don't break execution."""
    node, llm = cached_node_memory

    # Mock cache to raise an error
    with patch.object(node.llm_cache, 'get_cached_response', side_effect=Exception("Cache error")):
        state = {
            "user_prompt": "What is this?",
            "doc": ["Test content"]
        }

        # Should still execute despite cache error
        result = node.execute(state)

        # LLM should still be called
        assert llm.call_count == 1
        assert "output" in result


def test_clear_cache(cached_node_memory):
    """Test clearing the cache."""
    node, llm = cached_node_memory

    state = {
        "user_prompt": "What is this?",
        "doc": ["Test content"]
    }

    # First call
    node.execute(state.copy())
    assert llm.call_count == 1

    # Second call - cache hit
    node.execute(state.copy())
    assert llm.call_count == 1

    # Clear cache
    node.llm_cache.clear_cache()

    # Third call - cache miss after clear
    node.execute(state.copy())
    assert llm.call_count == 2
