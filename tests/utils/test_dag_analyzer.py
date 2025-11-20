"""
Tests for DAGAnalyzer utility class.

This module tests the DAG analysis functionality including cycle detection,
topological sorting, execution level calculation, and critical path analysis.
"""

import pytest
from scrapegraphai.utils.dag_analyzer import DAGAnalyzer


class TestDAGAnalyzerBasics:
    """Test basic DAGAnalyzer initialization and simple operations."""

    def test_simple_linear_graph(self):
        """Test a simple linear graph: A → B → C"""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        assert analyzer.nodes == {"A", "B", "C"}
        assert analyzer.adj_list == adj_list
        assert analyzer.rev_adj_list == rev_adj_list

    def test_empty_graph(self):
        """Test empty graph."""
        adj_list = {}
        rev_adj_list = {}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        assert analyzer.nodes == set()
        levels = analyzer.calculate_execution_levels()
        assert levels == []


class TestCycleDetection:
    """Test cycle detection in various graph structures."""

    def test_no_cycle_linear(self):
        """Test that a linear graph has no cycles."""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        has_cycle, cycle = analyzer.detect_cycles()

        assert not has_cycle
        assert cycle == []

    def test_no_cycle_parallel(self):
        """Test that a graph with parallel paths has no cycles."""
        # A → B → D
        #   → C → D
        adj_list = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        has_cycle, cycle = analyzer.detect_cycles()

        assert not has_cycle
        assert cycle == []

    def test_simple_cycle(self):
        """Test detection of a simple cycle: A → B → A"""
        adj_list = {"A": ["B"], "B": ["A"]}
        rev_adj_list = {"A": ["B"], "B": ["A"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        has_cycle, cycle = analyzer.detect_cycles()

        assert has_cycle
        assert len(cycle) >= 2
        assert "A" in cycle and "B" in cycle

    def test_self_loop(self):
        """Test detection of a self-loop: A → A"""
        adj_list = {"A": ["A"]}
        rev_adj_list = {"A": ["A"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        has_cycle, cycle = analyzer.detect_cycles()

        assert has_cycle
        assert "A" in cycle

    def test_complex_cycle(self):
        """Test detection of a cycle in a complex graph."""
        # A → B → C → D → B (cycle)
        adj_list = {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["B"]}
        rev_adj_list = {"A": [], "B": ["A", "D"], "C": ["B"], "D": ["C"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        has_cycle, cycle = analyzer.detect_cycles()

        assert has_cycle
        assert "B" in cycle and "C" in cycle and "D" in cycle


class TestTopologicalSort:
    """Test topological sorting functionality."""

    def test_linear_topological_sort(self):
        """Test topological sort on linear graph."""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        topo_order = analyzer.topological_sort()

        assert topo_order == ["A", "B", "C"]

    def test_parallel_topological_sort(self):
        """Test topological sort with parallel branches."""
        # A → B → D
        #   → C → D
        adj_list = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        topo_order = analyzer.topological_sort()

        # A must come first, D must come last
        # B and C can be in any order between A and D
        assert topo_order[0] == "A"
        assert topo_order[-1] == "D"
        assert set(topo_order[1:3]) == {"B", "C"}

    def test_topological_sort_with_cycle_raises_error(self):
        """Test that topological sort raises error on cycle."""
        adj_list = {"A": ["B"], "B": ["A"]}
        rev_adj_list = {"A": ["B"], "B": ["A"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        with pytest.raises(ValueError, match="Graph contains cycle"):
            analyzer.topological_sort()


class TestExecutionLevels:
    """Test calculation of execution levels for parallel execution."""

    def test_linear_execution_levels(self):
        """Test execution levels for linear graph."""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        levels = analyzer.calculate_execution_levels()

        assert levels == [["A"], ["B"], ["C"]]

    def test_parallel_execution_levels(self):
        """Test execution levels with parallel branches."""
        # A → B → D
        #   → C → D
        adj_list = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        levels = analyzer.calculate_execution_levels()

        assert len(levels) == 3
        assert levels[0] == ["A"]
        assert set(levels[1]) == {"B", "C"}  # B and C can run in parallel
        assert levels[2] == ["D"]

    def test_complex_execution_levels(self):
        """Test execution levels for complex graph with multiple parallel branches."""
        # Fetch → Parse → Validate → Merge → Generate
        #              → Transform →
        adj_list = {
            "fetch": ["parse"],
            "parse": ["validate", "transform"],
            "validate": ["merge"],
            "transform": ["merge"],
            "merge": ["generate"],
            "generate": [],
        }
        rev_adj_list = {
            "fetch": [],
            "parse": ["fetch"],
            "validate": ["parse"],
            "transform": ["parse"],
            "merge": ["validate", "transform"],
            "generate": ["merge"],
        }

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        levels = analyzer.calculate_execution_levels()

        assert len(levels) == 5
        assert levels[0] == ["fetch"]
        assert levels[1] == ["parse"]
        assert set(levels[2]) == {"validate", "transform"}
        assert levels[3] == ["merge"]
        assert levels[4] == ["generate"]

    def test_execution_levels_with_cycle_raises_error(self):
        """Test that execution levels raises error on cycle."""
        adj_list = {"A": ["B"], "B": ["A"]}
        rev_adj_list = {"A": ["B"], "B": ["A"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        with pytest.raises(ValueError, match="graph contains cycle"):
            analyzer.calculate_execution_levels()


class TestIndependentNodes:
    """Test finding independent nodes that can execute."""

    def test_find_initial_nodes(self):
        """Test finding nodes with no dependencies."""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        ready = analyzer.find_independent_nodes(completed=set())

        assert ready == ["A"]

    def test_find_nodes_after_completion(self):
        """Test finding ready nodes after some have completed."""
        # A → B → D
        #   → C → D
        adj_list = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        # After A completes, B and C should be ready
        ready = analyzer.find_independent_nodes(completed={"A"})
        assert set(ready) == {"B", "C"}

        # After A, B complete, only C is ready (not D yet)
        ready = analyzer.find_independent_nodes(completed={"A", "B"})
        assert ready == ["C"]

        # After A, B, C complete, D is ready
        ready = analyzer.find_independent_nodes(completed={"A", "B", "C"})
        assert ready == ["D"]


class TestCriticalPath:
    """Test critical path calculation."""

    def test_linear_critical_path(self):
        """Test critical path for linear graph."""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}
        durations = {"A": 1.0, "B": 2.0, "C": 1.5}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        path, duration = analyzer.calculate_critical_path(durations)

        assert path == ["A", "B", "C"]
        assert duration == 4.5  # 1.0 + 2.0 + 1.5

    def test_parallel_critical_path(self):
        """Test critical path with parallel branches."""
        # A → B (2.0) → D
        #   → C (5.0) → D
        # Critical path should go through C (longer duration)
        adj_list = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}
        durations = {"A": 1.0, "B": 2.0, "C": 5.0, "D": 1.0}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        path, duration = analyzer.calculate_critical_path(durations)

        # Critical path should be A → C → D
        assert "A" in path and "C" in path and "D" in path
        assert duration == 7.0  # 1.0 + 5.0 + 1.0


class TestParallelismMetrics:
    """Test parallelism factor and related metrics."""

    def test_linear_parallelism_factor(self):
        """Test parallelism factor for linear graph (should be 1.0)."""
        adj_list = {"A": ["B"], "B": ["C"], "C": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["B"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        factor = analyzer.get_parallelism_factor()

        assert factor == 1.0  # 3 nodes / 3 levels

    def test_parallel_parallelism_factor(self):
        """Test parallelism factor for graph with parallelism."""
        # A → B → D
        #   → C → D
        adj_list = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
        rev_adj_list = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        factor = analyzer.get_parallelism_factor()

        # 4 nodes / 3 levels = 1.33
        assert abs(factor - 4.0 / 3.0) < 0.01

    def test_max_parallel_width(self):
        """Test maximum parallel width calculation."""
        # A → B → E
        #   → C →
        #   → D →
        adj_list = {
            "A": ["B", "C", "D"],
            "B": ["E"],
            "C": ["E"],
            "D": ["E"],
            "E": [],
        }
        rev_adj_list = {
            "A": [],
            "B": ["A"],
            "C": ["A"],
            "D": ["A"],
            "E": ["B", "C", "D"],
        }

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        max_width = analyzer.get_max_parallel_width()

        assert max_width == 3  # B, C, D can all run in parallel


class TestRealWorldGraphs:
    """Test with realistic graph structures from actual use cases."""

    def test_web_scraping_graph(self):
        """Test a typical web scraping graph structure."""
        # Fetch → Parse → Validate → Merge → Generate
        #              → Transform →
        adj_list = {
            "fetch": ["parse"],
            "parse": ["validate", "transform"],
            "validate": ["merge"],
            "transform": ["merge"],
            "merge": ["generate"],
            "generate": [],
        }
        rev_adj_list = {
            "fetch": [],
            "parse": ["fetch"],
            "validate": ["parse"],
            "transform": ["parse"],
            "merge": ["validate", "transform"],
            "generate": ["merge"],
        }

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        # Test cycle detection
        has_cycle, _ = analyzer.detect_cycles()
        assert not has_cycle

        # Test execution levels
        levels = analyzer.calculate_execution_levels()
        assert len(levels) == 5
        assert set(levels[2]) == {"validate", "transform"}

        # Test parallelism factor
        factor = analyzer.get_parallelism_factor()
        assert factor > 1.0  # Should have some parallelism

    def test_multi_source_fetching(self):
        """Test a multi-source fetching scenario."""
        # Fetch1 → Parse1 → Merge → Generate
        # Fetch2 → Parse2 →
        # Fetch3 → Parse3 →
        adj_list = {
            "fetch1": ["parse1"],
            "fetch2": ["parse2"],
            "fetch3": ["parse3"],
            "parse1": ["merge"],
            "parse2": ["merge"],
            "parse3": ["merge"],
            "merge": ["generate"],
            "generate": [],
        }
        rev_adj_list = {
            "fetch1": [],
            "fetch2": [],
            "fetch3": [],
            "parse1": ["fetch1"],
            "parse2": ["fetch2"],
            "parse3": ["fetch3"],
            "merge": ["parse1", "parse2", "parse3"],
            "generate": ["merge"],
        }

        analyzer = DAGAnalyzer(adj_list, rev_adj_list)

        # Test execution levels
        levels = analyzer.calculate_execution_levels()
        assert len(levels) == 4
        assert set(levels[0]) == {"fetch1", "fetch2", "fetch3"}
        assert set(levels[1]) == {"parse1", "parse2", "parse3"}
        assert levels[2] == ["merge"]
        assert levels[3] == ["generate"]

        # Test max parallel width
        max_width = analyzer.get_max_parallel_width()
        assert max_width == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
