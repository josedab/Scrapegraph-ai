"""
Integration tests for correlation ID flow through graph execution.

Tests verify that correlation IDs are properly propagated through:
- Graph initialization
- Graph execution
- Node execution
- Error handling
"""

import json
import logging
import uuid
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from scrapegraphai.graphs.base_graph import BaseGraph
from scrapegraphai.nodes.base_node import BaseNode
from scrapegraphai.utils.logging import (
    LogConfig,
    LogFormat,
    JSONFormatter,
    configure_logging,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
)


class MockNode(BaseNode):
    """Mock node for testing."""

    def __init__(self, node_name: str, output_value: dict = None):
        super().__init__(
            node_name=node_name,
            node_type="node",
            input="state",
            output=["result"],
        )
        self.output_value = output_value or {}

    def execute(self, state: dict) -> dict:
        """Execute the mock node."""
        self.structured_logger.info(
            "Mock node executing",
            node_name=self.node_name,
            state_keys=list(state.keys()),
        )
        state.update(self.output_value)
        return state


class MockFailingNode(BaseNode):
    """Mock node that always fails for testing error handling."""

    def __init__(self, node_name: str):
        super().__init__(
            node_name=node_name,
            node_type="node",
            input="state",
            output=["result"],
        )

    def execute(self, state: dict) -> dict:
        """Execute and fail."""
        self.structured_logger.error("Mock node failing", node_name=self.node_name)
        raise ValueError("Intentional test failure")


class TestCorrelationIDPropagation:
    """Test correlation ID propagation through graph execution."""

    def setup_method(self):
        """Set up test method."""
        clear_correlation_id()
        # Configure JSON logging for testing
        config = LogConfig()
        config.format = LogFormat.JSON
        configure_logging(config)

    def test_correlation_id_set_on_graph_execute(self):
        """Test that correlation ID is set when graph executes."""
        clear_correlation_id()

        # Create a simple graph
        node1 = MockNode("node1", {"step1": "done"})
        node2 = MockNode("node2", {"step2": "done"})

        graph = BaseGraph(
            nodes=[node1, node2],
            edges=[(node1, node2)],
            entry_point=node1,
            graph_name="TestGraph",
        )

        # Execute the graph
        with patch('builtins.print'):  # Suppress print output
            state, _ = graph.execute({"state": "initial"})

        # Verify correlation ID was set
        cid = get_correlation_id()
        assert cid is not None
        assert len(cid) == 36  # UUID format

    def test_correlation_id_persists_across_nodes(self):
        """Test that the same correlation ID is used across all nodes."""
        clear_correlation_id()

        # Capture logs
        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create a graph with multiple nodes
        node1 = MockNode("node1", {"step1": "done"})
        node2 = MockNode("node2", {"step2": "done"})
        node3 = MockNode("node3", {"step3": "done"})

        graph = BaseGraph(
            nodes=[node1, node2, node3],
            edges=[(node1, node2), (node2, node3)],
            entry_point=node1,
            graph_name="MultiNodeGraph",
        )

        # Execute the graph
        with patch('builtins.print'):
            state, _ = graph.execute({"state": "initial"})

        # Parse all log entries
        output = stream.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split('\n') if line]

        # Extract all correlation IDs from logs
        correlation_ids = {entry["correlation_id"] for entry in log_entries}

        # All logs should have the same correlation ID
        assert len(correlation_ids) == 1, f"Expected 1 unique correlation ID, got {len(correlation_ids)}"

        # Clean up
        logger.removeHandler(handler)

    def test_custom_correlation_id_preserved(self):
        """Test that a pre-set correlation ID is preserved."""
        # Set a custom correlation ID before execution
        custom_id = str(uuid.uuid4())
        set_correlation_id(custom_id)

        # Capture logs
        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create and execute graph
        node1 = MockNode("node1", {"result": "done"})
        graph = BaseGraph(
            nodes=[node1],
            edges=[],
            entry_point=node1,
            graph_name="SingleNodeGraph",
        )

        with patch('builtins.print'):
            state, _ = graph.execute({"state": "initial"})

        # Parse log entries
        output = stream.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split('\n') if line]

        # All logs should have the custom correlation ID
        for entry in log_entries:
            assert entry["correlation_id"] == custom_id

        # Clean up
        logger.removeHandler(handler)

    def test_correlation_id_in_error_logs(self):
        """Test that correlation ID is included in error logs."""
        clear_correlation_id()

        # Capture logs
        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create a graph with a failing node
        node1 = MockNode("node1", {"step1": "done"})
        failing_node = MockFailingNode("failing_node")

        graph = BaseGraph(
            nodes=[node1, failing_node],
            edges=[(node1, failing_node)],
            entry_point=node1,
            graph_name="FailingGraph",
        )

        # Execute the graph and expect failure
        with pytest.raises(ValueError), patch('builtins.print'):
            graph.execute({"state": "initial"})

        # Parse log entries
        output = stream.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split('\n') if line]

        # Find error logs
        error_logs = [entry for entry in log_entries if entry["level"] == "ERROR"]

        # Should have at least one error log
        assert len(error_logs) > 0

        # All error logs should have correlation ID
        for error_log in error_logs:
            assert "correlation_id" in error_log
            assert error_log["correlation_id"] is not None

        # All logs should have the same correlation ID
        correlation_ids = {entry["correlation_id"] for entry in log_entries}
        assert len(correlation_ids) == 1

        # Clean up
        logger.removeHandler(handler)

    def test_node_execution_logging(self):
        """Test that node execution is properly logged with context."""
        clear_correlation_id()

        # Capture logs
        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create and execute graph
        node1 = MockNode("test_node", {"result": "success"})
        graph = BaseGraph(
            nodes=[node1],
            edges=[],
            entry_point=node1,
            graph_name="LoggingTestGraph",
        )

        with patch('builtins.print'):
            state, _ = graph.execute({"state": "initial"})

        # Parse log entries
        output = stream.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split('\n') if line]

        # Find logs related to node execution
        node_execution_logs = [
            entry for entry in log_entries
            if "node" in entry.get("message", "").lower() and "executing" in entry.get("message", "").lower()
        ]

        # Should have node execution logs
        assert len(node_execution_logs) > 0

        # Node logs should include node name
        for log in node_execution_logs:
            if "node_name" in log:
                assert log["node_name"] in ["test_node", "node1"]

        # Clean up
        logger.removeHandler(handler)

    def test_graph_execution_timing_logged(self):
        """Test that graph execution timing is logged."""
        clear_correlation_id()

        # Capture logs
        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create and execute graph
        node1 = MockNode("node1", {"result": "done"})
        graph = BaseGraph(
            nodes=[node1],
            edges=[],
            entry_point=node1,
            graph_name="TimingTestGraph",
        )

        with patch('builtins.print'):
            state, _ = graph.execute({"state": "initial"})

        # Parse log entries
        output = stream.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split('\n') if line]

        # Find completion logs with timing
        timing_logs = [
            entry for entry in log_entries
            if "duration_ms" in entry
        ]

        # Should have timing logs
        assert len(timing_logs) > 0

        # Timing should be positive
        for log in timing_logs:
            assert log["duration_ms"] >= 0

        # Clean up
        logger.removeHandler(handler)


class TestStructuredLoggingInNodes:
    """Test structured logging usage within nodes."""

    def setup_method(self):
        """Set up test method."""
        clear_correlation_id()
        config = LogConfig()
        config.format = LogFormat.JSON
        configure_logging(config)

    def test_node_has_structured_logger(self):
        """Test that BaseNode instances have structured logger."""
        node = MockNode("test_node")

        assert hasattr(node, 'structured_logger')
        assert node.structured_logger is not None

    def test_node_can_log_with_context(self):
        """Test that nodes can log with context fields."""
        from scrapegraphai.utils.logging import _get_library_root_logger
        logger = _get_library_root_logger()

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Create node and log with context
        node = MockNode("context_test_node")
        node.structured_logger.info(
            "Processing data",
            record_count=42,
            user_id="user123",
        )

        # Parse log output
        output = stream.getvalue()
        log_entry = json.loads(output.strip().split('\n')[-1])

        # Should include context fields
        assert log_entry["record_count"] == 42
        assert log_entry["user_id"] == "user123"
        assert "correlation_id" in log_entry

        # Clean up
        logger.removeHandler(handler)


class TestBackwardCompatibility:
    """Test backward compatibility with existing logging."""

    def test_standard_logger_still_works(self):
        """Test that standard logger (self.logger) still works."""
        node = MockNode("compat_test_node")

        # Standard logger should work
        assert hasattr(node, 'logger')
        assert node.logger is not None

        # Should be able to log without errors
        node.logger.info("Standard logging still works")

    def test_both_loggers_available(self):
        """Test that both standard and structured loggers are available."""
        node = MockNode("dual_logger_node")

        assert hasattr(node, 'logger')
        assert hasattr(node, 'structured_logger')
        assert node.logger is not None
        assert node.structured_logger is not None
