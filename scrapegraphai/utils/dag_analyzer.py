"""
DAG analysis utilities for dependency resolution and parallel execution planning.

This module provides the DAGAnalyzer class for analyzing directed acyclic graph (DAG)
structures to identify parallelization opportunities, detect cycles, and calculate
execution levels for optimal parallel scheduling.
"""

from typing import List, Set, Dict, Tuple
from collections import deque


class DAGAnalyzer:
    """
    Analyzes graph structure to identify parallelization opportunities.

    Features:
    - Topological sorting for execution ordering
    - Dependency level calculation for parallel batching
    - Cycle detection for validation
    - Critical path analysis for optimization

    Args:
        adjacency_list: Dictionary mapping each node to its successors
            {node_name: [successor1, successor2, ...]}
        reverse_adjacency_list: Dictionary mapping each node to its predecessors
            {node_name: [predecessor1, predecessor2, ...]}

    Example:
        >>> adj_list = {'fetch': ['parse'], 'parse': ['validate', 'transform'],
        ...             'validate': ['merge'], 'transform': ['merge'], 'merge': []}
        >>> rev_adj_list = {'fetch': [], 'parse': ['fetch'],
        ...                 'validate': ['parse'], 'transform': ['parse'],
        ...                 'merge': ['validate', 'transform']}
        >>> analyzer = DAGAnalyzer(adj_list, rev_adj_list)
        >>> levels = analyzer.calculate_execution_levels()
        >>> print(f"Execution levels: {levels}")
    """

    def __init__(
        self,
        adjacency_list: Dict[str, List[str]],
        reverse_adjacency_list: Dict[str, List[str]],
    ):
        self.adj_list = adjacency_list
        self.rev_adj_list = reverse_adjacency_list
        self.nodes = set(adjacency_list.keys())

    def detect_cycles(self) -> Tuple[bool, List[str]]:
        """
        Detect cycles in the graph using depth-first search.

        This method performs a DFS traversal and tracks nodes in the current
        recursion stack to detect back edges, which indicate cycles.

        Returns:
            Tuple[bool, List[str]]: A tuple containing:
                - bool: True if cycle detected, False otherwise
                - List[str]: List of node names forming the cycle (empty if no cycle)

        Example:
            >>> has_cycle, cycle = analyzer.detect_cycles()
            >>> if has_cycle:
            ...     print(f"Cycle detected: {' → '.join(cycle)}")
        """
        visited = set()
        rec_stack = set()
        cycle_path = []

        def dfs(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.adj_list.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle - reconstruct the cycle path
                    cycle_start = path.index(neighbor)
                    cycle_path.extend(path[cycle_start:])
                    cycle_path.append(neighbor)  # Close the cycle
                    return True

            rec_stack.remove(node)
            path.pop()
            return False

        for node in self.nodes:
            if node not in visited:
                if dfs(node, []):
                    return True, cycle_path

        return False, []

    def topological_sort(self) -> List[str]:
        """
        Perform topological sort using Kahn's algorithm.

        This algorithm repeatedly removes nodes with no dependencies and adds
        them to the result, reducing the in-degree of their successors.

        Returns:
            List[str]: Nodes in topological order

        Raises:
            ValueError: If graph contains cycles

        Example:
            >>> topo_order = analyzer.topological_sort()
            >>> print(f"Execution order: {' → '.join(topo_order)}")
        """
        has_cycle, cycle = self.detect_cycles()
        if has_cycle:
            raise ValueError(f"Graph contains cycle: {' → '.join(cycle)}")

        # Calculate in-degrees (number of dependencies)
        in_degree = {node: len(self.rev_adj_list[node]) for node in self.nodes}

        # Queue of nodes with no dependencies
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)

            # Reduce in-degree of successors
            for successor in self.adj_list[node]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        if len(result) != len(self.nodes):
            raise ValueError("Failed to produce complete topological ordering")

        return result

    def calculate_execution_levels(self) -> List[List[str]]:
        """
        Group nodes into execution levels where each level can run in parallel.

        Level 0: Nodes with no dependencies
        Level 1: Nodes that depend only on Level 0 nodes
        Level N: Nodes that depend on nodes from levels 0 to N-1

        This grouping enables parallel execution by ensuring all dependencies
        for nodes in a level are satisfied by previous levels.

        Returns:
            List[List[str]]: List of node groups, each group can execute in parallel

        Raises:
            ValueError: If graph contains cycles or cannot be leveled

        Example:
            >>> levels = analyzer.calculate_execution_levels()
            >>> for i, level in enumerate(levels):
            ...     print(f"Level {i} ({len(level)} nodes): {level}")
        """
        # Check for cycles first
        has_cycle, cycle = self.detect_cycles()
        if has_cycle:
            raise ValueError(f"Cannot calculate execution levels: graph contains cycle: {' → '.join(cycle)}")

        levels = []
        remaining = set(self.nodes)

        while remaining:
            # Find all nodes with no remaining dependencies
            current_level = [
                node
                for node in remaining
                if all(dep not in remaining for dep in self.rev_adj_list[node])
            ]

            if not current_level:
                # This should not happen if graph is acyclic
                raise ValueError(
                    "Unable to determine execution levels - possible cycle or implementation error"
                )

            levels.append(current_level)
            remaining -= set(current_level)

        return levels

    def find_independent_nodes(self, completed: Set[str]) -> List[str]:
        """
        Find all nodes that can execute given the set of completed nodes.

        A node is ready to execute if all its dependencies (predecessors)
        have been completed.

        Args:
            completed: Set of node names that have finished execution

        Returns:
            List[str]: Nodes ready to execute (all dependencies satisfied)

        Example:
            >>> completed = {'fetch', 'parse'}
            >>> ready = analyzer.find_independent_nodes(completed)
            >>> print(f"Ready to execute: {ready}")
        """
        ready = []

        for node in self.nodes:
            if node in completed:
                continue

            # Check if all dependencies are satisfied
            dependencies = self.rev_adj_list[node]
            if all(dep in completed for dep in dependencies):
                ready.append(node)

        return ready

    def calculate_critical_path(
        self, node_durations: Dict[str, float]
    ) -> Tuple[List[str], float]:
        """
        Calculate the critical path (longest path) through the graph.

        The critical path represents the sequence of nodes that determines
        the minimum possible execution time, even with perfect parallelization.
        This is useful for identifying bottlenecks and estimating speedup limits.

        Args:
            node_durations: Estimated or measured execution time per node

        Returns:
            Tuple[List[str], float]: A tuple containing:
                - List[str]: Node names in the critical path
                - float: Total duration of the critical path

        Example:
            >>> durations = {'fetch': 2.8, 'parse': 0.9, 'validate': 1.2,
            ...              'transform': 2.1, 'merge': 0.5}
            >>> path, duration = analyzer.calculate_critical_path(durations)
            >>> print(f"Critical path: {' → '.join(path)} ({duration}s)")
        """
        # Calculate earliest start time for each node
        earliest_start = {node: 0.0 for node in self.nodes}
        predecessor = {node: None for node in self.nodes}

        # Process nodes in topological order
        topo_order = self.topological_sort()

        for node in topo_order:
            node_duration = node_durations.get(node, 0.0)
            node_end = earliest_start[node] + node_duration

            # Update successors
            for successor in self.adj_list[node]:
                if node_end > earliest_start[successor]:
                    earliest_start[successor] = node_end
                    predecessor[successor] = node

        # Find terminal node (node with latest end time)
        terminal_node = max(earliest_start, key=earliest_start.get)
        total_duration = earliest_start[terminal_node]

        # Add the duration of the terminal node itself
        total_duration += node_durations.get(terminal_node, 0.0)

        # Reconstruct critical path
        path = []
        current = terminal_node
        while current is not None:
            path.append(current)
            current = predecessor[current]

        path.reverse()
        return path, total_duration

    def get_parallelism_factor(self) -> float:
        """
        Calculate theoretical parallelism factor.

        The parallelism factor is the ratio of total nodes to critical path length
        (number of execution levels). Higher values indicate more parallelism potential.

        Returns:
            float: Ratio of total nodes to critical path length
                   1.0 = no parallelism (sequential)
                   >1.0 = parallelism potential
                   2.0 = 50% of work can be parallelized

        Example:
            >>> factor = analyzer.get_parallelism_factor()
            >>> if factor > 1.5:
            ...     print("Good parallelism potential!")
            >>> elif factor > 1.2:
            ...     print("Moderate parallelism potential")
            >>> else:
            ...     print("Limited parallelism (mostly sequential)")
        """
        levels = self.calculate_execution_levels()
        critical_path_length = len(levels)
        total_nodes = len(self.nodes)

        return total_nodes / critical_path_length if critical_path_length > 0 else 1.0

    def get_max_parallel_width(self) -> int:
        """
        Calculate the maximum number of nodes that can run in parallel.

        This is the size of the largest execution level, representing the
        peak parallelism potential.

        Returns:
            int: Maximum number of nodes that can execute concurrently

        Example:
            >>> max_width = analyzer.get_max_parallel_width()
            >>> print(f"Peak parallelism: {max_width} concurrent nodes")
        """
        levels = self.calculate_execution_levels()
        return max(len(level) for level in levels) if levels else 0
