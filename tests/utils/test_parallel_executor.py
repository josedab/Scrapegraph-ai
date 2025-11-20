"""
Tests for ParallelExecutor utility class.

This module tests the parallel execution functionality including thread-based
and sequential execution, error handling, and result aggregation.
"""

import time
import pytest
from unittest.mock import Mock, MagicMock
from scrapegraphai.utils.parallel_executor import (
    ParallelExecutor,
    ExecutorConfig,
    ExecutionMode,
    NodeExecutionResult,
)


class TestExecutorConfig:
    """Test ExecutorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExecutorConfig()

        assert config.mode == ExecutionMode.THREADS
        assert config.max_workers == 4
        assert config.timeout_per_node is None
        assert config.fail_fast is True
        assert config.max_retries == 0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ExecutorConfig(
            mode=ExecutionMode.SEQUENTIAL,
            max_workers=8,
            timeout_per_node=30.0,
            fail_fast=False,
            max_retries=3,
        )

        assert config.mode == ExecutionMode.SEQUENTIAL
        assert config.max_workers == 8
        assert config.timeout_per_node == 30.0
        assert config.fail_fast is False
        assert config.max_retries == 3


class TestNodeExecutionResult:
    """Test NodeExecutionResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = NodeExecutionResult(
            node_name="test_node",
            state={"key": "value"},
            exec_time=1.5,
            cb_data={"tokens": 100},
            success=True,
        )

        assert result.node_name == "test_node"
        assert result.state == {"key": "value"}
        assert result.exec_time == 1.5
        assert result.cb_data == {"tokens": 100}
        assert result.success is True
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed result."""
        error = ValueError("Test error")
        result = NodeExecutionResult(
            node_name="test_node",
            state={},
            exec_time=0.5,
            error=error,
            success=False,
        )

        assert result.node_name == "test_node"
        assert result.exec_time == 0.5
        assert result.error == error
        assert result.success is False


class TestParallelExecutorBasics:
    """Test basic ParallelExecutor initialization and context management."""

    def test_initialization_with_default_config(self):
        """Test executor initialization with default config."""
        executor = ParallelExecutor()

        assert executor.config.mode == ExecutionMode.THREADS
        assert executor.config.max_workers == 4
        assert executor._executor is None

    def test_initialization_with_custom_config(self):
        """Test executor initialization with custom config."""
        config = ExecutorConfig(max_workers=8, mode=ExecutionMode.SEQUENTIAL)
        executor = ParallelExecutor(config)

        assert executor.config.max_workers == 8
        assert executor.config.mode == ExecutionMode.SEQUENTIAL

    def test_context_manager(self):
        """Test executor as context manager."""
        config = ExecutorConfig(mode=ExecutionMode.THREADS)

        with ParallelExecutor(config) as executor:
            # Executor should be initialized inside context
            assert executor._executor is not None

        # Executor should be shut down after context
        # Note: We can't directly test if it's shut down,
        # but we can verify it doesn't raise errors


class TestSequentialExecution:
    """Test sequential execution mode."""

    def test_sequential_execution_success(self):
        """Test successful sequential execution of multiple nodes."""
        # Create mock nodes
        node1 = Mock()
        node1.node_name = "node1"
        node2 = Mock()
        node2.node_name = "node2"
        node3 = Mock()
        node3.node_name = "node3"

        # Create mock execute function
        def mock_execute(node, state, llm_model, llm_model_name):
            new_state = state.copy()
            new_state[node.node_name] = f"result_{node.node_name}"
            return new_state, 0.1, {"tokens": 10}

        config = ExecutorConfig(mode=ExecutionMode.SEQUENTIAL)

        with ParallelExecutor(config) as executor:
            results = executor.execute_batch(
                nodes=[node1, node2, node3],
                execute_fn=mock_execute,
                state={"initial": "state"},
                llm_model=Mock(),
                llm_model_name="test-model",
            )

        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].node_name == "node1"
        assert results[1].node_name == "node2"
        assert results[2].node_name == "node3"

    def test_sequential_execution_with_failure(self):
        """Test sequential execution stops on first failure when fail_fast=True."""
        node1 = Mock()
        node1.node_name = "node1"
        node2 = Mock()
        node2.node_name = "node2"
        node3 = Mock()
        node3.node_name = "node3"

        def mock_execute(node, state, llm_model, llm_model_name):
            if node.node_name == "node2":
                raise ValueError("Node 2 failed")
            new_state = state.copy()
            new_state[node.node_name] = "result"
            return new_state, 0.1, {}

        config = ExecutorConfig(mode=ExecutionMode.SEQUENTIAL, fail_fast=True)

        with ParallelExecutor(config) as executor:
            results = executor.execute_batch(
                nodes=[node1, node2, node3],
                execute_fn=mock_execute,
                state={},
                llm_model=Mock(),
                llm_model_name="test-model",
            )

        # Should have 2 results: node1 success, node2 failure
        # node3 should not execute due to fail_fast
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error is not None


class TestThreadedExecution:
    """Test threaded execution mode."""

    def test_threaded_execution_success(self):
        """Test successful threaded execution of multiple nodes."""
        node1 = Mock()
        node1.node_name = "node1"
        node2 = Mock()
        node2.node_name = "node2"
        node3 = Mock()
        node3.node_name = "node3"

        def mock_execute(node, state, llm_model, llm_model_name):
            # Simulate some work
            time.sleep(0.1)
            new_state = state.copy()
            new_state[node.node_name] = f"result_{node.node_name}"
            return new_state, 0.1, {"tokens": 10}

        config = ExecutorConfig(mode=ExecutionMode.THREADS, max_workers=3)

        with ParallelExecutor(config) as executor:
            start_time = time.time()
            results = executor.execute_batch(
                nodes=[node1, node2, node3],
                execute_fn=mock_execute,
                state={"initial": "state"},
                llm_model=Mock(),
                llm_model_name="test-model",
            )
            elapsed = time.time() - start_time

        assert len(results) == 3
        assert all(r.success for r in results)

        # With 3 workers and 3 nodes taking 0.1s each,
        # parallel execution should take ~0.1s, not 0.3s
        # Allow some overhead
        assert elapsed < 0.25

    def test_threaded_execution_with_failure_fail_fast(self):
        """Test threaded execution with fail_fast=True."""
        node1 = Mock()
        node1.node_name = "node1"
        node2 = Mock()
        node2.node_name = "node2"
        node3 = Mock()
        node3.node_name = "node3"

        def mock_execute(node, state, llm_model, llm_model_name):
            if node.node_name == "node2":
                raise ValueError("Node 2 failed")
            time.sleep(0.1)
            new_state = state.copy()
            new_state[node.node_name] = "result"
            return new_state, 0.1, {}

        config = ExecutorConfig(mode=ExecutionMode.THREADS, fail_fast=True)

        with ParallelExecutor(config) as executor:
            results = executor.execute_batch(
                nodes=[node1, node2, node3],
                execute_fn=mock_execute,
                state={},
                llm_model=Mock(),
                llm_model_name="test-model",
            )

        # Should have results, but one should have failed
        assert any(not r.success for r in results)


class TestStateHandling:
    """Test state isolation in parallel execution."""

    def test_state_isolation_between_nodes(self):
        """Test that each node gets its own state copy."""
        node1 = Mock()
        node1.node_name = "node1"
        node2 = Mock()
        node2.node_name = "node2"

        executed_states = []

        def mock_execute(node, state, llm_model, llm_model_name):
            # Record the initial state each node sees
            executed_states.append(state.copy())

            # Modify state
            new_state = state.copy()
            new_state[node.node_name] = f"result_{node.node_name}"
            return new_state, 0.1, {}

        config = ExecutorConfig(mode=ExecutionMode.SEQUENTIAL)
        initial_state = {"initial": "value"}

        with ParallelExecutor(config) as executor:
            results = executor.execute_batch(
                nodes=[node1, node2],
                execute_fn=mock_execute,
                state=initial_state,
                llm_model=Mock(),
                llm_model_name="test-model",
            )

        # Both nodes should see the initial state
        assert len(executed_states) == 2
        assert all(s == {"initial": "value"} for s in executed_states)

        # Results should have their own state modifications
        assert results[0].state["node1"] == "result_node1"
        assert results[1].state["node2"] == "result_node2"


class TestExecuteNodeWrapper:
    """Test the _execute_node_wrapper method."""

    def test_wrapper_success(self):
        """Test wrapper with successful execution."""
        node = Mock()
        node.node_name = "test_node"

        def mock_execute(node, state, llm_model, llm_model_name):
            new_state = state.copy()
            new_state["result"] = "success"
            return new_state, 0.5, {"tokens": 100}

        executor = ParallelExecutor()
        result = executor._execute_node_wrapper(
            node=node,
            execute_fn=mock_execute,
            state={"initial": "state"},
            llm_model=Mock(),
            llm_model_name="test-model",
        )

        assert result.success is True
        assert result.node_name == "test_node"
        assert result.state["result"] == "success"
        assert result.exec_time == 0.5
        assert result.cb_data == {"tokens": 100}
        assert result.error is None

    def test_wrapper_with_exception(self):
        """Test wrapper handles exceptions properly."""
        node = Mock()
        node.node_name = "test_node"

        def mock_execute(node, state, llm_model, llm_model_name):
            raise ValueError("Test error")

        executor = ParallelExecutor()
        result = executor._execute_node_wrapper(
            node=node,
            execute_fn=mock_execute,
            state={"initial": "state"},
            llm_model=Mock(),
            llm_model_name="test-model",
        )

        assert result.success is False
        assert result.node_name == "test_node"
        assert isinstance(result.error, ValueError)
        assert str(result.error) == "Test error"


class TestRealWorldScenarios:
    """Test realistic execution scenarios."""

    def test_parallel_fetch_nodes(self):
        """Simulate parallel fetching of multiple URLs."""
        # Create mock fetch nodes
        nodes = []
        for i in range(3):
            node = Mock()
            node.node_name = f"fetch_{i}"
            nodes.append(node)

        def mock_fetch(node, state, llm_model, llm_model_name):
            # Simulate network delay
            time.sleep(0.1)
            new_state = state.copy()
            new_state[f"doc_{node.node_name}"] = f"content from {node.node_name}"
            return new_state, 0.1, {"tokens": 50}

        config = ExecutorConfig(mode=ExecutionMode.THREADS, max_workers=3)

        with ParallelExecutor(config) as executor:
            start_time = time.time()
            results = executor.execute_batch(
                nodes=nodes,
                execute_fn=mock_fetch,
                state={"urls": ["url1", "url2", "url3"]},
                llm_model=Mock(),
                llm_model_name="test-model",
            )
            elapsed = time.time() - start_time

        # All should succeed
        assert all(r.success for r in results)
        assert len(results) == 3

        # Parallel execution should be faster than sequential
        # 3 nodes * 0.1s each = 0.3s sequential
        # With parallelism, should take ~0.1s (allow overhead)
        assert elapsed < 0.25

    def test_validation_and_transform_branches(self):
        """Simulate parallel validation and transformation."""
        validate_node = Mock()
        validate_node.node_name = "validate"
        transform_node = Mock()
        transform_node.node_name = "transform"

        def mock_execute(node, state, llm_model, llm_model_name):
            time.sleep(0.1)  # Simulate work
            new_state = state.copy()
            if node.node_name == "validate":
                new_state["is_valid"] = True
            else:
                new_state["transformed_data"] = "cleaned_data"
            return new_state, 0.1, {"tokens": 30}

        config = ExecutorConfig(mode=ExecutionMode.THREADS)

        with ParallelExecutor(config) as executor:
            results = executor.execute_batch(
                nodes=[validate_node, transform_node],
                execute_fn=mock_execute,
                state={"parsed_doc": "raw_data"},
                llm_model=Mock(),
                llm_model_name="test-model",
            )

        assert len(results) == 2
        assert all(r.success for r in results)

        # Find results by node name
        validate_result = next(r for r in results if r.node_name == "validate")
        transform_result = next(r for r in results if r.node_name == "transform")

        assert validate_result.state.get("is_valid") is True
        assert transform_result.state.get("transformed_data") == "cleaned_data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
