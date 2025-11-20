# RFC-0014: Parallel Node Execution within Single Graph

**Status:** Draft
**Author:** ScrapeGraphAI Analysis Team
**Created:** 2025-11-20
**Based on Commit:** 32d5636ac3465edd0a8af47c6242f16a0beb35f5

## Summary

This RFC proposes implementing parallel execution of independent nodes within a single graph to reduce total execution time by 40-60%. Currently, ScrapeGraphAI's `BaseGraph._execute_standard()` uses a sequential while loop (line 264) that executes all nodes one after another, even when nodes have no dependencies and could run concurrently. By analyzing the DAG structure in `self.edges` and executing independent nodes in parallel using ThreadPoolExecutor or asyncio, we can significantly improve performance for graphs with parallelizable workflows.

**Key Distinction:** This is fundamentally different from `MultiGraph`, which parallelizes multiple graph instances for multiple URLs. This RFC focuses on parallelizing independent nodes **within a single graph execution**.

## Motivation

### Current Performance Problems

**Problem 1: Sequential Execution of Independent Nodes**

The current execution model in `BaseGraph._execute_standard()` processes nodes strictly sequentially:

```python
# From scrapegraphai/graphs/base_graph.py:264-291
while current_node_name:
    current_node = self._get_node_by_name(current_node_name)

    # ... metadata collection ...

    try:
        result, node_exec_time, cb_data = self._execute_node(
            current_node, state, llm_model, llm_model_name
        )
        total_exec_time += node_exec_time

        # ... result handling ...

        current_node_name = self._get_next_node(current_node, result)
    except Exception as e:
        # ... error handling ...
```

**The Problem:** Even when multiple nodes have no dependencies on each other, they execute sequentially. This is particularly inefficient in several common scenarios:

**Scenario 1: Multi-Source Fetching**
```python
# Current behavior: Sequential fetching
FetchNode(url1)  →  FetchNode(url2)  →  FetchNode(url3)  →  MergeNode
   2.8s               2.8s               2.8s               0.5s
Total: 8.9 seconds

# Potential with parallelism: Concurrent fetching
FetchNode(url1)  ┐
FetchNode(url2)  ├→  MergeNode
FetchNode(url3)  ┘
   2.8s             0.5s
Total: 3.3 seconds (63% faster)
```

**Scenario 2: Independent Processing Branches**
```python
# Current: Sequential processing
ParseNode  →  ValidationNode  →  TransformNode  →  MergeNode
  0.3s          0.5s              0.4s              0.2s
Total: 1.4 seconds

# Potential: Parallel branches
ParseNode  ┐
           ├→  TransformNode  →  MergeNode
           └→  ValidationNode ┘
  0.3s          0.5s              0.2s
Total: 1.0 seconds (29% faster)
```

**Scenario 3: Multi-Model LLM Queries**
```python
# Current: Sequential LLM calls
GPT4Node(extract_prices)  →  ClaudeNode(extract_specs)  →  CombineNode
     1.2s                        1.5s                         0.3s
Total: 3.0 seconds

# Potential: Concurrent LLM calls
GPT4Node(extract_prices)    ┐
ClaudeNode(extract_specs)   ├→  CombineNode
     1.5s                       0.3s
Total: 1.8 seconds (40% faster)
```

**Problem 2: No DAG Analysis Infrastructure**

The current `BaseGraph` stores edges but never analyzes the dependency structure:

```python
# From scrapegraphai/graphs/base_graph.py:67
self.edges = self._create_edges(set(edges))

# self.edges is a simple dictionary: {from_node: to_node}
# Example: {'fetch': 'parse', 'parse': 'generate'}
```

This simple edge mapping is sufficient for sequential execution but provides no information about:
- Which nodes can run in parallel
- Topological ordering for optimal scheduling
- Dependency chains and critical paths
- Resource utilization opportunities

**Problem 3: Performance Impact on Complex Graphs**

Consider a realistic scraping workflow with validation and enrichment:

```python
# A more complex graph with opportunities for parallelism
FetchNode
    ↓
ParseNode
    ├→ ValidationNode  ┐
    ├→ CleanupNode     ├→ MergeNode → GenerateAnswerNode
    └→ EnrichmentNode  ┘
```

**Current execution time:**
```
FetchNode:        2.8s
ParseNode:        0.5s
ValidationNode:   0.8s  ← Could run in parallel
CleanupNode:      0.6s  ← Could run in parallel
EnrichmentNode:   1.2s  ← Could run in parallel
MergeNode:        0.3s
GenerateAnswer:   1.5s
─────────────────────
Total:            7.7s
```

**With parallel execution:**
```
FetchNode:        2.8s
ParseNode:        0.5s
[Validation + Cleanup + Enrichment]:  1.2s  ← Max of 0.8s, 0.6s, 1.2s
MergeNode:        0.3s
GenerateAnswer:   1.5s
─────────────────────
Total:            6.3s (18% faster, saves 1.4s)
```

**For graphs with more parallelism, savings are even greater:**
- 3 parallel branches: 25-35% time reduction
- 5 parallel branches: 35-45% time reduction
- 8+ parallel branches: 45-60% time reduction

**Problem 4: Bottleneck Propagation**

Sequential execution means slow nodes block fast nodes unnecessarily:

```python
# Scenario: Slow fetch followed by fast processing
FetchNode (2.8s)  →  FastParseNode (0.1s)  →  FastTransform (0.1s)

# With another independent branch:
FetchNode (2.8s)  →  FastParseNode (0.1s)  →  FastTransform (0.1s)
                  →  SlowValidation (2.0s)  →

# Sequential total: 5.1 seconds
# Parallel total: 3.0 seconds (FastTransform and SlowValidation overlap)
```

### Why This Matters

**Performance Impact:**
- **Reduced latency:** Users get results 40-60% faster for parallelizable workflows
- **Better resource utilization:** Multi-core CPUs and concurrent API calls fully utilized
- **Improved throughput:** More requests processed per second on same hardware

**Cost Impact:**
- **Lower infrastructure costs:** Same workload on fewer/smaller machines
- **Reduced API wait time:** Concurrent LLM calls reduce time-to-completion
- **Better ROI:** Faster results = happier users = higher conversion

**User Experience:**
- **Responsive applications:** Web scraping APIs respond faster
- **Batch processing:** Large scraping jobs complete in fraction of the time
- **Real-time workflows:** Enables use cases requiring sub-second responses

**Competitive Advantage:**
- Other scraping frameworks (Scrapy, Playwright) already support concurrency
- LangChain has parallel execution via LangGraph
- ScrapeGraphAI should match or exceed industry standards

## Current State

### Architecture Analysis

**File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`**

**Lines 18-82: BaseGraph Structure**

```python
class BaseGraph:
    """
    BaseGraph manages the execution flow of a graph composed of interconnected nodes.

    Attributes:
        nodes (list): A dictionary mapping each node's name to its corresponding node instance.
        edges (list): A dictionary representing the directed edges of the graph where each
                      key-value pair corresponds to the from-node and to-node relationship.
        entry_point (str): The name of the entry point node from which the graph execution begins.
    """

    def __init__(
        self,
        nodes: list,
        edges: list,
        entry_point: str,
        use_burr: bool = False,
        burr_config: dict = None,
        graph_name: str = "Custom",
    ):
        self.nodes = nodes
        self.raw_edges = edges
        self.edges = self._create_edges(set(edges))  # Simple dict: {from: to}
        self.entry_point = entry_point.node_name
        self.graph_name = graph_name
        # ...
```

**Current edge representation:**
```python
# Example edges for: Fetch → Parse → Generate
self.edges = {
    'fetch': 'parse',
    'parse': 'generate',
    'generate': None  # Terminal node
}
```

**Limitation:** This representation only supports linear chains. There's no way to represent:
- Multiple successors (fan-out)
- Multiple predecessors (fan-in)
- Parallel branches

**Lines 236-340: Sequential Execution Engine**

```python
def _execute_standard(self, initial_state: dict) -> Tuple[dict, list]:
    """
    Executes the graph by traversing nodes
    starting from the entry point using the standard method.
    """
    current_node_name = self.entry_point
    state = initial_state

    total_exec_time = 0.0
    exec_info = []

    # Sequential execution loop
    while current_node_name:
        current_node = self._get_node_by_name(current_node_name)

        # Execute node (blocking)
        result, node_exec_time, cb_data = self._execute_node(
            current_node, state, llm_model, llm_model_name
        )

        # Single next node
        current_node_name = self._get_next_node(current_node, result)

    return state, exec_info
```

**Key observations:**
1. **Single-threaded execution:** Only one node runs at a time
2. **Linear traversal:** `current_node_name` is a string, not a list
3. **Blocking operations:** Each node completes before next begins
4. **No concurrency primitives:** No locks, futures, or async coordination

**Lines 83-98: Edge Creation Logic**

```python
def _create_edges(self, edges: list) -> dict:
    """
    Helper method to create a dictionary of edges from the given iterable of tuples.
    """
    edge_dict = {}
    for from_node, to_node in edges:
        if from_node.node_type != "conditional_node":
            edge_dict[from_node.node_name] = to_node.node_name
    return edge_dict
```

**Problem:** This flattens the DAG structure into a simple dictionary, losing information about:
- Nodes with multiple outgoing edges
- Nodes with multiple incoming edges
- Dependency relationships

**Lines 198-220: Node Execution**

```python
def _execute_node(self, current_node, state, llm_model, llm_model_name):
    """Executes a single node and returns execution information."""
    curr_time = time.time()

    with self.callback_manager.exclusive_get_callback(
        llm_model, llm_model_name
    ) as cb:
        result = current_node.execute(state)  # ← Blocking call
        node_exec_time = time.time() - curr_time

        # ... callback data collection ...

    return result, node_exec_time, cb_data
```

**Key issue:** The `current_node.execute(state)` call is synchronous and blocks until completion. There's no mechanism for:
- Launching multiple executions concurrently
- Waiting for multiple results
- Coordinating parallel execution

### Current Graph Examples

**Example 1: SmartScraperGraph (Linear)**

```python
# From scrapegraphai/graphs/smart_scraper_graph.py
fetch_node = FetchNode(...)
parse_node = ParseNode(...)
generate_answer_node = GenerateAnswerNode(...)

return BaseGraph(
    nodes=[fetch_node, parse_node, generate_answer_node],
    edges=[
        (fetch_node, parse_node),
        (parse_node, generate_answer_node),
    ],
    entry_point=fetch_node,
)
```

**DAG structure:**
```
fetch → parse → generate
```

**Parallelism potential:** None (strict dependency chain)

**Example 2: SmartScraperGraph with Reasoning (Branch Potential)**

```python
# Variation with reasoning node
fetch_node = FetchNode(...)
parse_node = ParseNode(...)
reasoning_node = ReasoningNode(...)
generate_answer_node = GenerateAnswerNode(...)

# Current edges (sequential)
edges = [
    (fetch_node, parse_node),
    (parse_node, reasoning_node),
    (reasoning_node, generate_answer_node),
]
```

**Potential parallelism if we refactored:**
```
fetch → parse → ┬→ reasoning    ┬→ merge → generate
                └→ validation   ┘
```

### MultiGraph vs Single-Graph Parallelism

**What MultiGraph Does:**
```python
# scrapegraphai/graphs/smart_scraper_multi_graph.py
graph_iterator_node = GraphIteratorNode(
    node_config={
        "graph_instance": SmartScraperGraph,  # Runs multiple instances
    },
)

# Parallelizes: Multiple URLs → Multiple graph instances
URL1 → SmartScraperGraph instance 1  ┐
URL2 → SmartScraperGraph instance 2  ├→  MergeAnswersNode
URL3 → SmartScraperGraph instance 3  ┘
```

**Scope:** Parallelizes **multiple executions of the same graph**

**What This RFC Proposes:**
```python
# Within a single graph execution:
FetchNode     ┐
ParseNode1    ├→  MergeNode  →  GenerateNode
ParseNode2    ┘
```

**Scope:** Parallelizes **independent nodes within one graph execution**

**Both are complementary:**
- MultiGraph: Horizontal scaling (more URLs)
- This RFC: Vertical optimization (faster per-graph execution)

### Test Coverage

Current test suite (`tests/graphs/`) tests sequential execution only:
- No tests for concurrent node execution
- No tests for dependency resolution
- No tests for parallel error handling
- No stress tests for race conditions

## Detailed Design

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      BaseGraph (Enhanced)                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Sequential Execution (default, backward compatible)       │  │
│  │  - _execute_standard()                                     │  │
│  │  - Simple while loop                                       │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Parallel Execution (new, opt-in)                          │  │
│  │  - _execute_parallel()                                     │  │
│  │  - DAG analysis → Topological sort → Parallel execution   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                       DAGAnalyzer                                 │
│  - analyze_dependencies()                                         │
│  - find_independent_nodes()                                       │
│  - topological_sort()                                             │
│  - detect_cycles()                                                │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│                    ParallelExecutor                               │
│  - execute_batch() - Run independent nodes concurrently           │
│  - Uses ThreadPoolExecutor or asyncio                             │
│  - Handles errors, timeouts, resource limits                      │
└──────────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. Enhanced Edge Representation

**Location:** `scrapegraphai/graphs/base_graph.py`

**Problem:** Current `self.edges` is a simple dict that can't represent DAG structure.

**Solution:** Add `self.adjacency_list` to properly represent the DAG:

```python
class BaseGraph:
    def __init__(self, nodes, edges, entry_point, ...):
        # Existing attributes
        self.nodes = nodes
        self.raw_edges = edges
        self.edges = self._create_edges(set(edges))  # Keep for backward compatibility

        # NEW: Full DAG representation
        self.adjacency_list = self._create_adjacency_list(edges)
        self.reverse_adjacency_list = self._create_reverse_adjacency_list(edges)

    def _create_adjacency_list(self, edges: list) -> dict:
        """
        Create adjacency list representation for DAG analysis.

        Returns:
            dict: {node_name: [successor1, successor2, ...]}
        """
        adj_list = {node.node_name: [] for node in self.nodes}

        for from_node, to_node in edges:
            if to_node is not None:  # Handle terminal nodes
                adj_list[from_node.node_name].append(to_node.node_name)

        return adj_list

    def _create_reverse_adjacency_list(self, edges: list) -> dict:
        """
        Create reverse adjacency list for dependency tracking.

        Returns:
            dict: {node_name: [predecessor1, predecessor2, ...]}
        """
        rev_adj_list = {node.node_name: [] for node in self.nodes}

        for from_node, to_node in edges:
            if to_node is not None:
                rev_adj_list[to_node.node_name].append(from_node.node_name)

        return rev_adj_list
```

**Example:**
```python
# Given edges:
edges = [
    (fetch, parse),
    (parse, validate),
    (parse, transform),
    (validate, merge),
    (transform, merge),
]

# adjacency_list:
{
    'fetch': ['parse'],
    'parse': ['validate', 'transform'],  # Multiple successors!
    'validate': ['merge'],
    'transform': ['merge'],
    'merge': []
}

# reverse_adjacency_list:
{
    'fetch': [],
    'parse': ['fetch'],
    'validate': ['parse'],
    'transform': ['parse'],
    'merge': ['validate', 'transform']  # Multiple predecessors!
}
```

#### 2. DAGAnalyzer Component

**Location:** `scrapegraphai/utils/dag_analyzer.py`

```python
"""
DAG analysis utilities for dependency resolution and parallel execution planning.
"""

from typing import List, Set, Dict, Tuple
from collections import deque, defaultdict


class DAGAnalyzer:
    """
    Analyzes graph structure to identify parallelization opportunities.

    Features:
    - Topological sorting for execution ordering
    - Dependency level calculation for parallel batching
    - Cycle detection for validation
    - Critical path analysis for optimization
    """

    def __init__(self, adjacency_list: Dict[str, List[str]],
                 reverse_adjacency_list: Dict[str, List[str]]):
        self.adj_list = adjacency_list
        self.rev_adj_list = reverse_adjacency_list
        self.nodes = set(adjacency_list.keys())

    def detect_cycles(self) -> Tuple[bool, List[str]]:
        """
        Detect cycles in the graph using DFS.

        Returns:
            Tuple[bool, List[str]]: (has_cycle, cycle_path)
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
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle_path.extend(path[cycle_start:])
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

        Returns:
            List[str]: Nodes in topological order

        Raises:
            ValueError: If graph contains cycles
        """
        has_cycle, cycle = self.detect_cycles()
        if has_cycle:
            raise ValueError(f"Graph contains cycle: {' → '.join(cycle)}")

        # Calculate in-degrees
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

        Returns:
            List[List[str]]: List of node groups, each group can execute in parallel
        """
        # Calculate in-degrees (number of dependencies)
        in_degree = {node: len(self.rev_adj_list[node]) for node in self.nodes}

        levels = []
        remaining = set(self.nodes)

        while remaining:
            # Find all nodes with no remaining dependencies
            current_level = [
                node for node in remaining
                if all(dep not in remaining for dep in self.rev_adj_list[node])
            ]

            if not current_level:
                # This should not happen if graph is acyclic
                raise ValueError("Unable to determine execution levels - possible cycle")

            levels.append(current_level)
            remaining -= set(current_level)

        return levels

    def find_independent_nodes(self, completed: Set[str]) -> List[str]:
        """
        Find all nodes that can execute given the set of completed nodes.

        Args:
            completed: Set of node names that have finished execution

        Returns:
            List[str]: Nodes ready to execute (all dependencies satisfied)
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

    def calculate_critical_path(self, node_durations: Dict[str, float]) -> Tuple[List[str], float]:
        """
        Calculate the critical path (longest path) through the graph.

        This identifies the sequence of nodes that determines minimum execution time.
        Useful for identifying bottlenecks.

        Args:
            node_durations: Estimated or measured execution time per node

        Returns:
            Tuple[List[str], float]: (critical_path_nodes, total_duration)
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

        Returns:
            float: Ratio of total nodes to critical path length
                   Higher values = more parallelism potential
        """
        levels = self.calculate_execution_levels()
        critical_path_length = len(levels)
        total_nodes = len(self.nodes)

        return total_nodes / critical_path_length if critical_path_length > 0 else 1.0
```

#### 3. ParallelExecutor Component

**Location:** `scrapegraphai/utils/parallel_executor.py`

```python
"""
Parallel execution engine for running independent graph nodes concurrently.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from typing import List, Dict, Callable, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ExecutionMode(Enum):
    """Execution mode for parallel execution."""
    THREADS = "threads"      # ThreadPoolExecutor (I/O bound tasks)
    ASYNCIO = "asyncio"      # asyncio (async/await tasks)
    SEQUENTIAL = "sequential"  # Fallback to sequential


@dataclass
class NodeExecutionResult:
    """Result of executing a single node."""
    node_name: str
    state: dict
    exec_time: float
    cb_data: Optional[dict] = None
    error: Optional[Exception] = None
    success: bool = True


@dataclass
class ExecutorConfig:
    """Configuration for parallel executor."""
    mode: ExecutionMode = ExecutionMode.THREADS
    max_workers: int = 4
    timeout_per_node: Optional[float] = None
    fail_fast: bool = True  # Stop on first error
    max_retries: int = 0


class ParallelExecutor:
    """
    Executes multiple independent nodes in parallel.

    Supports both thread-based and async-based execution.
    Handles errors, timeouts, and result aggregation.
    """

    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()
        self._executor = None

    def __enter__(self):
        if self.config.mode == ExecutionMode.THREADS:
            self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._executor:
            self._executor.shutdown(wait=True)

    def execute_batch(
        self,
        nodes: List[Any],
        execute_fn: Callable[[Any, dict], Tuple[dict, float, Optional[dict]]],
        state: dict,
        llm_model: Any,
        llm_model_name: str
    ) -> List[NodeExecutionResult]:
        """
        Execute a batch of independent nodes in parallel.

        Args:
            nodes: List of node instances to execute
            execute_fn: Function to execute each node (e.g., _execute_node)
            state: Current graph state (shared read-only)
            llm_model: LLM model instance
            llm_model_name: LLM model name

        Returns:
            List[NodeExecutionResult]: Results for each node
        """
        if self.config.mode == ExecutionMode.THREADS:
            return self._execute_batch_threads(
                nodes, execute_fn, state, llm_model, llm_model_name
            )
        elif self.config.mode == ExecutionMode.ASYNCIO:
            return asyncio.run(
                self._execute_batch_async(
                    nodes, execute_fn, state, llm_model, llm_model_name
                )
            )
        else:
            # Fallback to sequential
            return self._execute_batch_sequential(
                nodes, execute_fn, state, llm_model, llm_model_name
            )

    def _execute_batch_threads(
        self,
        nodes: List[Any],
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str
    ) -> List[NodeExecutionResult]:
        """Execute nodes using ThreadPoolExecutor."""
        futures_to_nodes = {}
        results = []

        # Submit all tasks
        for node in nodes:
            future = self._executor.submit(
                self._execute_node_wrapper,
                node,
                execute_fn,
                state,
                llm_model,
                llm_model_name
            )
            futures_to_nodes[future] = node

        # Collect results as they complete
        for future in as_completed(futures_to_nodes, timeout=self.config.timeout_per_node):
            node = futures_to_nodes[future]

            try:
                result = future.result()
                results.append(result)

                if not result.success and self.config.fail_fast:
                    # Cancel remaining tasks
                    for f in futures_to_nodes:
                        if not f.done():
                            f.cancel()
                    break

            except Exception as e:
                result = NodeExecutionResult(
                    node_name=node.node_name,
                    state=state,
                    exec_time=0.0,
                    error=e,
                    success=False
                )
                results.append(result)

                if self.config.fail_fast:
                    break

        return results

    async def _execute_batch_async(
        self,
        nodes: List[Any],
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str
    ) -> List[NodeExecutionResult]:
        """Execute nodes using asyncio."""
        tasks = [
            asyncio.create_task(
                self._execute_node_async(
                    node, execute_fn, state, llm_model, llm_model_name
                )
            )
            for node in nodes
        ]

        results = []

        if self.config.fail_fast:
            # Stop on first error
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                if not result.success:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    break
        else:
            # Wait for all, even if some fail
            results = await asyncio.gather(*tasks, return_exceptions=True)
            results = [
                r if isinstance(r, NodeExecutionResult) else
                NodeExecutionResult(
                    node_name="unknown",
                    state=state,
                    exec_time=0.0,
                    error=r if isinstance(r, Exception) else None,
                    success=False
                )
                for r in results
            ]

        return results

    def _execute_batch_sequential(
        self,
        nodes: List[Any],
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str
    ) -> List[NodeExecutionResult]:
        """Fallback: Execute nodes sequentially."""
        results = []

        for node in nodes:
            result = self._execute_node_wrapper(
                node, execute_fn, state, llm_model, llm_model_name
            )
            results.append(result)

            if not result.success and self.config.fail_fast:
                break

        return results

    def _execute_node_wrapper(
        self,
        node: Any,
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str
    ) -> NodeExecutionResult:
        """
        Wrapper to execute a single node and capture result/errors.

        Note: State mutations need careful handling in parallel execution.
        """
        start_time = time.time()

        try:
            # Execute node
            result_state, exec_time, cb_data = execute_fn(
                node, state, llm_model, llm_model_name
            )

            return NodeExecutionResult(
                node_name=node.node_name,
                state=result_state,
                exec_time=exec_time,
                cb_data=cb_data,
                success=True
            )

        except Exception as e:
            return NodeExecutionResult(
                node_name=node.node_name,
                state=state,
                exec_time=time.time() - start_time,
                error=e,
                success=False
            )

    async def _execute_node_async(
        self,
        node: Any,
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str
    ) -> NodeExecutionResult:
        """Async wrapper for node execution."""
        # If execute_fn is not async, run it in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._execute_node_wrapper,
            node,
            execute_fn,
            state,
            llm_model,
            llm_model_name
        )
```

#### 4. Enhanced BaseGraph with Parallel Execution

**Location:** `scrapegraphai/graphs/base_graph.py`

```python
class BaseGraph:
    """Enhanced BaseGraph with optional parallel execution."""

    def __init__(
        self,
        nodes: list,
        edges: list,
        entry_point: str,
        use_burr: bool = False,
        burr_config: dict = None,
        graph_name: str = "Custom",
        enable_parallel: bool = False,  # NEW
        parallel_config: dict = None,   # NEW
    ):
        # Existing initialization
        self.nodes = nodes
        self.raw_edges = edges
        self.edges = self._create_edges(set(edges))
        self.entry_point = entry_point.node_name
        self.graph_name = graph_name

        # NEW: Enhanced DAG representation
        self.adjacency_list = self._create_adjacency_list(edges)
        self.reverse_adjacency_list = self._create_reverse_adjacency_list(edges)

        # NEW: Parallel execution configuration
        self.enable_parallel = enable_parallel
        self.parallel_config = parallel_config or {}

        # Initialize DAG analyzer if parallel execution enabled
        if self.enable_parallel:
            from ..utils.dag_analyzer import DAGAnalyzer
            self.dag_analyzer = DAGAnalyzer(
                self.adjacency_list,
                self.reverse_adjacency_list
            )

            # Validate graph (detect cycles)
            has_cycle, cycle = self.dag_analyzer.detect_cycles()
            if has_cycle:
                raise ValueError(
                    f"Cannot enable parallel execution: graph contains cycle: "
                    f"{' → '.join(cycle)}"
                )

        # ... rest of initialization

    def execute(self, initial_state: dict):
        """
        Execute the graph using either sequential or parallel mode.
        """
        if self.use_burr:
            return self._execute_with_burr(initial_state)
        elif self.enable_parallel:
            return self._execute_parallel(initial_state)
        else:
            return self._execute_standard(initial_state)

    def _execute_parallel(self, initial_state: dict) -> Tuple[dict, list]:
        """
        Execute graph with parallel execution of independent nodes.

        Algorithm:
        1. Calculate execution levels using DAG analysis
        2. For each level, execute all nodes in parallel
        3. Wait for level completion before proceeding
        4. Aggregate results and update state
        """
        from ..utils.parallel_executor import ParallelExecutor, ExecutorConfig, ExecutionMode

        # Setup
        state = initial_state
        total_exec_time = 0.0
        exec_info = []
        cb_total = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "successful_requests": 0,
            "total_cost_USD": 0.0,
        }

        # Get execution levels
        execution_levels = self.dag_analyzer.calculate_execution_levels()

        # Get metadata (same as sequential)
        source_type = None
        llm_model = None
        llm_model_name = None
        embedder_model = None
        source = []
        prompt = None
        schema = None

        logger.info(f"Executing graph with {len(execution_levels)} parallel levels")

        # Create parallel executor
        executor_config = ExecutorConfig(
            mode=ExecutionMode(self.parallel_config.get("mode", "threads")),
            max_workers=self.parallel_config.get("max_workers", 4),
            timeout_per_node=self.parallel_config.get("timeout_per_node"),
            fail_fast=self.parallel_config.get("fail_fast", True),
        )

        start_time = time.time()
        error_node = None

        try:
            with ParallelExecutor(executor_config) as executor:
                # Execute each level
                for level_idx, level_nodes in enumerate(execution_levels):
                    logger.info(f"Executing level {level_idx}: {level_nodes}")

                    # Get node instances
                    nodes_to_execute = [
                        self._get_node_by_name(node_name)
                        for node_name in level_nodes
                    ]

                    # Extract metadata from first node in level if needed
                    if len(nodes_to_execute) > 0:
                        first_node = nodes_to_execute[0]

                        if source_type is None:
                            source_type, source, prompt = self._update_source_info(
                                first_node, state
                            )

                        if llm_model is None:
                            llm_model, llm_model_name, embedder_model = self._get_model_info(
                                first_node
                            )

                        if schema is None:
                            schema = self._get_schema(first_node)

                    # Execute all nodes in this level in parallel
                    level_start = time.time()
                    results = executor.execute_batch(
                        nodes_to_execute,
                        self._execute_node,
                        state,
                        llm_model,
                        llm_model_name
                    )
                    level_time = time.time() - level_start

                    logger.info(f"Level {level_idx} completed in {level_time:.2f}s")

                    # Process results
                    for result in results:
                        if not result.success:
                            error_node = result.node_name
                            raise result.error

                        # Update state with node results
                        state.update(result.state)

                        # Accumulate execution info
                        total_exec_time += result.exec_time
                        if result.cb_data:
                            exec_info.append(result.cb_data)
                            for key in cb_total:
                                cb_total[key] += result.cb_data[key]

        except Exception as e:
            graph_execution_time = time.time() - start_time
            log_graph_execution(
                graph_name=self.graph_name,
                source=source,
                prompt=prompt,
                schema=schema,
                llm_model=llm_model_name,
                embedder_model=embedder_model,
                source_type=source_type,
                execution_time=graph_execution_time,
                error_node=error_node,
                exception=str(e),
            )
            raise e

        # Success logging
        graph_execution_time = time.time() - start_time
        log_graph_execution(
            graph_name=self.graph_name,
            source=source,
            prompt=prompt,
            schema=schema,
            llm_model=llm_model_name,
            embedder_model=embedder_model,
            source_type=source_type,
            execution_time=graph_execution_time,
            total_tokens=cb_total.get("total_tokens"),
        )

        return state, exec_info
```

### State Management in Parallel Execution

**Critical Challenge:** Node state mutations must be coordinated carefully.

**Current Approach:** State is a mutable dict passed between nodes:
```python
state = {"url": "...", "user_prompt": "..."}
node1.execute(state)  # Adds state["doc"]
node2.execute(state)  # Reads state["doc"], adds state["parsed_doc"]
```

**Parallel Execution Considerations:**

**Option 1: Independent State Branches (Safer)**
```python
# Each parallel node gets a copy of input state
for node in parallel_nodes:
    node_state = state.copy()  # Shallow copy
    result = node.execute(node_state)
    # Merge results back to main state
```

**Option 2: Merge Strategy (More Flexible)**
```python
# Nodes declare their output keys
# Merge node combines outputs from parallel branches

ParseNode → state["parsed_doc"]  ┐
ValidateNode → state["valid"]    ├→ MergeNode combines all
TransformNode → state["cleaned"] ┘
```

**Option 3: Copy-on-Write (Most Efficient)**
```python
# Use immutable state or COW wrappers
# Only copy when modifications occur
```

**Recommended Approach:** Option 2 with explicit merge nodes

**Example:**
```python
# Graph structure
FetchNode → ParseNode → ┬→ ValidationNode  ┬→ MergeValidationTransform → Generate
                        └→ TransformNode   ┘

# Execution:
# Level 0: FetchNode
# Level 1: ParseNode
# Level 2: [ValidationNode, TransformNode] ← Run in parallel
# Level 3: MergeValidationTransform ← Combines results
# Level 4: Generate
```

### Configuration Management

**Graph-Level Configuration:**
```python
graph = BaseGraph(
    nodes=[...],
    edges=[...],
    entry_point=fetch_node,
    enable_parallel=True,
    parallel_config={
        "mode": "threads",        # "threads" or "asyncio"
        "max_workers": 4,         # Thread/process pool size
        "timeout_per_node": 30,   # Timeout in seconds
        "fail_fast": True,        # Stop on first error
    }
)
```

**Environment Variables:**
```bash
SCRAPEGRAPH_PARALLEL_ENABLED=true
SCRAPEGRAPH_PARALLEL_MODE=threads
SCRAPEGRAPH_PARALLEL_MAX_WORKERS=4
```

**Precedence:**
1. Explicit `parallel_config` parameter
2. Environment variables
3. Default values

## Example Usage

### Before (Current Sequential Implementation)

```python
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import FetchNode, ParseNode, GenerateAnswerNode

# Create graph
fetch = FetchNode(...)
parse = ParseNode(...)
validate = ValidationNode(...)
transform = TransformNode(...)
merge = MergeNode(...)
generate = GenerateAnswerNode(...)

graph = BaseGraph(
    nodes=[fetch, parse, validate, transform, merge, generate],
    edges=[
        (fetch, parse),
        (parse, validate),
        (validate, transform),  # Sequential: validate → transform
        (transform, merge),
        (merge, generate),
    ],
    entry_point=fetch
)

# Execute
import time
start = time.time()
result = graph.execute({"url": "https://example.com", "user_prompt": "Extract data"})
print(f"Execution time: {time.time() - start:.2f}s")
# Output: Execution time: 8.7s
```

**Execution timeline:**
```
Fetch: ████████                    (2.8s)
Parse:         ███                 (0.9s)
Validate:         ████             (1.2s)
Transform:            ███████      (2.1s)
Merge:                       ██    (0.6s)
Generate:                      ████ (1.1s)

Total: 8.7 seconds
```

### After (With Parallel Execution - Refactored Graph)

```python
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import (
    FetchNode, ParseNode, ValidationNode, TransformNode,
    MergeNode, GenerateAnswerNode
)

# Create graph with parallel structure
fetch = FetchNode(...)
parse = ParseNode(...)
validate = ValidationNode(...)  # Can run in parallel with transform
transform = TransformNode(...)  # Can run in parallel with validate
merge = MergeNode(...)
generate = GenerateAnswerNode(...)

graph = BaseGraph(
    nodes=[fetch, parse, validate, transform, merge, generate],
    edges=[
        (fetch, parse),
        (parse, validate),      # Parse fans out to both validate and transform
        (parse, transform),     # ← Multiple edges from parse
        (validate, merge),      # Both validate and transform feed into merge
        (transform, merge),
        (merge, generate),
    ],
    entry_point=fetch,
    enable_parallel=True,       # ← Enable parallel execution
    parallel_config={
        "mode": "threads",
        "max_workers": 4,
    }
)

# Execute
import time
start = time.time()
result = graph.execute({"url": "https://example.com", "user_prompt": "Extract data"})
print(f"Execution time: {time.time() - start:.2f}s")
# Output: Execution time: 5.6s (36% faster!)
```

**Execution timeline with parallelism:**
```
Level 0 - Fetch:     ████████                (2.8s)
Level 1 - Parse:             ███             (0.9s)
Level 2 - Parallel:             ███████      (2.1s = max(validate:1.2s, transform:2.1s))
  Validate:                     ████
  Transform:                    ███████
Level 3 - Merge:                       ██    (0.6s)
Level 4 - Generate:                      ████ (1.1s)

Total: 5.6 seconds (36% improvement)
Saved: 3.1 seconds
```

### Advanced Example: Multi-Source Scraping with Parallel Fetching

```python
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import FetchNode, MergeNode, GenerateAnswerNode

# Create multiple fetch nodes for different sources
fetch_source1 = FetchNode(
    input="url1",
    output=["doc1"],
    node_config={"llm_model": llm_model},
    node_name="fetch_source1"
)

fetch_source2 = FetchNode(
    input="url2",
    output=["doc2"],
    node_config={"llm_model": llm_model},
    node_name="fetch_source2"
)

fetch_source3 = FetchNode(
    input="url3",
    output=["doc3"],
    node_config={"llm_model": llm_model},
    node_name="fetch_source3"
)

merge_docs = MergeNode(
    input="doc1 & doc2 & doc3",
    output=["merged_doc"],
    node_name="merge_docs"
)

generate = GenerateAnswerNode(
    input="merged_doc & user_prompt",
    output=["answer"],
    node_config={"llm_model": llm_model}
)

# Graph structure: All fetches in parallel, then merge, then generate
graph = BaseGraph(
    nodes=[fetch_source1, fetch_source2, fetch_source3, merge_docs, generate],
    edges=[
        (fetch_source1, merge_docs),
        (fetch_source2, merge_docs),
        (fetch_source3, merge_docs),
        (merge_docs, generate),
    ],
    entry_point=fetch_source1,  # Any of the fetch nodes can be entry
    enable_parallel=True,
    parallel_config={"max_workers": 3}
)

# Execute
result = graph.execute({
    "url1": "https://site1.com",
    "url2": "https://site2.com",
    "url3": "https://site3.com",
    "user_prompt": "Compare product prices"
})

# Sequential: 3 × 2.8s + 0.5s + 1.5s = 10.9s
# Parallel:   max(2.8s, 2.8s, 2.8s) + 0.5s + 1.5s = 4.8s
# Improvement: 56% faster!
```

### Example: Analyzing Parallelism Potential

```python
from scrapegraphai.utils.dag_analyzer import DAGAnalyzer

# After creating graph
analyzer = DAGAnalyzer(graph.adjacency_list, graph.reverse_adjacency_list)

# Check execution levels
levels = analyzer.calculate_execution_levels()
print(f"Execution levels: {len(levels)}")
for i, level in enumerate(levels):
    print(f"Level {i}: {level} ({len(level)} nodes)")

# Output:
# Execution levels: 5
# Level 0: ['fetch'] (1 node)
# Level 1: ['parse'] (1 node)
# Level 2: ['validate', 'transform'] (2 nodes) ← Parallelism!
# Level 3: ['merge'] (1 node)
# Level 4: ['generate'] (1 node)

# Calculate parallelism factor
factor = analyzer.get_parallelism_factor()
print(f"Parallelism factor: {factor:.2f}")
# Output: Parallelism factor: 1.20 (20% more nodes than critical path)

# Estimate time savings
node_durations = {
    'fetch': 2.8,
    'parse': 0.9,
    'validate': 1.2,
    'transform': 2.1,
    'merge': 0.6,
    'generate': 1.1
}

critical_path, duration = analyzer.calculate_critical_path(node_durations)
print(f"Critical path: {' → '.join(critical_path)}")
print(f"Minimum possible time: {duration:.2f}s")

# Output:
# Critical path: fetch → parse → transform → merge → generate
# Minimum possible time: 7.5s
```

## Implementation Plan

### Phase 1: Foundation (Week 1-2)
**Goal:** Core infrastructure without breaking changes

**Tasks:**
1. **Create DAGAnalyzer component**
   - Implement `scrapegraphai/utils/dag_analyzer.py`
   - Topological sort, cycle detection, level calculation
   - Unit tests with 95%+ coverage
   - Test edge cases: cycles, disconnected components, complex DAGs

2. **Create ParallelExecutor component**
   - Implement `scrapegraphai/utils/parallel_executor.py`
   - ThreadPoolExecutor-based execution
   - Error handling and timeout support
   - Unit tests for concurrent execution

3. **Enhance BaseGraph edge representation**
   - Add `adjacency_list` and `reverse_adjacency_list`
   - Keep backward compatibility with `self.edges`
   - Add tests to verify DAG structure correctness

**Success Criteria:**
- [ ] 95% test coverage for new components
- [ ] All existing tests still pass
- [ ] Documentation for new utilities complete

### Phase 2: Integration (Week 3-4)
**Goal:** Integrate parallel execution into BaseGraph (opt-in)

**Tasks:**
1. **Add parallel execution to BaseGraph**
   - Implement `_execute_parallel()` method
   - Add `enable_parallel` and `parallel_config` parameters
   - Default to `enable_parallel=False` for backward compatibility

2. **Create comprehensive integration tests**
   - Test sequential vs parallel execution equivalence
   - Test state management in parallel scenarios
   - Test error propagation and recovery
   - Test with various graph structures

3. **Add example graphs demonstrating parallelism**
   - Multi-source fetch example
   - Validation + transform parallel branches
   - Complex DAG with multiple levels

4. **Documentation**
   - API documentation for new parameters
   - Tutorial: "Optimizing Graphs with Parallel Execution"
   - Migration guide for existing graphs

**Success Criteria:**
- [ ] Parallel execution works for common graph patterns
- [ ] Zero breaking changes to existing API
- [ ] Documentation complete with examples

### Phase 3: Optimization & Advanced Features (Week 5-6)
**Goal:** Performance tuning and advanced capabilities

**Tasks:**
1. **Add asyncio support**
   - Implement async execution mode in ParallelExecutor
   - Support async nodes (for async LLM calls)
   - Benchmark threads vs asyncio performance

2. **State management improvements**
   - Implement copy-on-write state wrapper
   - Add state conflict detection
   - Optimize state copying overhead

3. **Performance benchmarking**
   - Create benchmark suite for various graph patterns
   - Measure actual speedup vs theoretical maximum
   - Identify bottlenecks and optimize

4. **Advanced DAG analysis**
   - Critical path analysis
   - Resource utilization metrics
   - Parallelism factor calculation

**Success Criteria:**
- [ ] 40-60% speedup demonstrated on parallelizable graphs
- [ ] Async mode performs better for I/O-bound tasks
- [ ] Comprehensive benchmark results documented

### Phase 4: Production Readiness (Week 7-8)
**Goal:** Polish, monitoring, and deployment

**Tasks:**
1. **Add monitoring and metrics**
   - Execution time per level
   - Parallelism utilization
   - Bottleneck identification
   - Integration with existing telemetry

2. **Error handling hardening**
   - Graceful degradation on parallel execution failure
   - Retry logic for transient errors
   - Detailed error context preservation

3. **Performance optimization**
   - Thread pool tuning based on workload
   - Smart scheduling (prioritize critical path)
   - Resource limit enforcement

4. **Documentation completion**
   - Best practices guide
   - Troubleshooting guide
   - Performance tuning guide
   - FAQ

5. **Community engagement**
   - Blog post announcing feature
   - Example notebooks
   - Discord/GitHub discussions

**Success Criteria:**
- [ ] Production-grade error handling
- [ ] Comprehensive documentation
- [ ] Community awareness and feedback

### Milestones

| Milestone | Completion Date | Deliverables |
|-----------|----------------|--------------|
| M1: Core Infrastructure | Week 2 | DAGAnalyzer, ParallelExecutor, tests |
| M2: Integration Complete | Week 4 | Parallel execution in BaseGraph, docs |
| M3: Optimization Complete | Week 6 | Async support, benchmarks, tuning |
| M4: Production Ready | Week 8 | Monitoring, hardening, documentation |

### Rollback Plan

If critical issues arise:
1. Default `enable_parallel=False` in next release
2. Keep parallel execution available but opt-in only
3. Fix issues in dedicated hotfix branch
4. Re-enable by default after thorough validation

## Backwards Compatibility

### Breaking Changes

**None.** This RFC is designed to be 100% backward compatible.

### Compatibility Strategy

**1. Opt-in by Default:**
```python
# Existing code works unchanged
graph = BaseGraph(
    nodes=[...],
    edges=[...],
    entry_point=fetch_node
)
# Uses sequential execution (default behavior)
```

**2. Explicit Opt-in for Parallel Execution:**
```python
# New code can enable parallelism
graph = BaseGraph(
    nodes=[...],
    edges=[...],
    entry_point=fetch_node,
    enable_parallel=True  # Opt-in
)
```

**3. Future Default Change (Phase 4+):**
After validation and community feedback, we may change the default to `enable_parallel=True` with:
- Clear migration guide
- Automatic detection of incompatible graphs
- Warning messages for users
- Easy opt-out mechanism

### API Stability Guarantees

**Guaranteed Stable:**
- All existing `BaseGraph` parameters
- All existing method signatures
- `_execute_standard()` behavior unchanged
- Return types and data structures

**New Optional Parameters:**
- `enable_parallel: bool = False`
- `parallel_config: dict = None`

These are keyword-only and have safe defaults.

### Migration Guide

**For Most Users:**

No action required. Existing graphs continue to work.

**To Enable Parallelism:**

1. Review your graph structure for parallelization opportunities
2. Refactor edges to create parallel branches (if needed)
3. Enable parallel execution:

```python
# Before
graph = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config={"llm": {"model": "gpt-4"}}
)

# After (with custom graph that has parallel structure)
graph = BaseGraph(
    nodes=[fetch, parse, validate, transform, merge, generate],
    edges=[
        (fetch, parse),
        (parse, validate),
        (parse, transform),  # Parallel fan-out
        (validate, merge),
        (transform, merge),  # Parallel fan-in
        (merge, generate),
    ],
    entry_point=fetch,
    enable_parallel=True  # Enable parallelism
)
```

## Performance Impact

### Expected Improvements

**Metric: Graph Execution Time (Parallelizable Workload)**

**Scenario 1: Multi-Source Fetching (3 URLs)**
- Current: 3 × 2.8s = 8.4 seconds
- With Parallelism: max(2.8s, 2.8s, 2.8s) = 2.8 seconds
- **Improvement: 67% faster** (saves 5.6s)

**Scenario 2: Validation + Transform Branches**
- Current: 0.8s + 2.1s = 2.9 seconds
- With Parallelism: max(0.8s, 2.1s) = 2.1 seconds
- **Improvement: 28% faster** (saves 0.8s)

**Scenario 3: Complex Graph (5 parallel branches)**
- Current: 1.2s + 0.8s + 2.3s + 0.9s + 1.5s = 6.7 seconds
- With Parallelism: max(1.2s, 0.8s, 2.3s, 0.9s, 1.5s) = 2.3 seconds
- **Improvement: 66% faster** (saves 4.4s)

**Metric: Resource Utilization**
- Current: CPU utilization ~25% (single-threaded execution)
- With Parallelism: CPU utilization ~70-90% (multi-threaded execution)
- **Better hardware utilization**

**Metric: Total Cost (for 1000 graph executions)**
- Current: 1000 × 8.7s = 2.4 hours of compute time
- With Parallelism: 1000 × 5.6s = 1.6 hours of compute time
- **33% reduction in compute time = 33% cost savings**

### Benchmarking Methodology

**Test Setup:**
```python
import time
from scrapegraphai.graphs import BaseGraph

def benchmark_graph(graph, iterations=100):
    """Benchmark graph execution time."""
    times = []

    for i in range(iterations):
        start = time.time()
        graph.execute(initial_state)
        elapsed = time.time() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    return {
        "avg": avg_time,
        "min": min_time,
        "max": max_time,
        "total": sum(times)
    }

# Test sequential
sequential_graph = create_test_graph(enable_parallel=False)
sequential_results = benchmark_graph(sequential_graph)

# Test parallel
parallel_graph = create_test_graph(enable_parallel=True)
parallel_results = benchmark_graph(parallel_graph)

# Calculate improvement
improvement = (
    (sequential_results["avg"] - parallel_results["avg"])
    / sequential_results["avg"]
    * 100
)

print(f"Sequential: {sequential_results['avg']:.2f}s")
print(f"Parallel:   {parallel_results['avg']:.2f}s")
print(f"Improvement: {improvement:.1f}%")
```

**Expected Results:**
```
Graph Type              Sequential    Parallel    Improvement
─────────────────────────────────────────────────────────────
Linear (no parallelism)    5.2s        5.3s         -2% (overhead)
2 parallel branches        6.8s        4.9s        +28%
3 parallel branches        8.4s        4.5s        +46%
5 parallel branches       12.1s        5.2s        +57%
Multi-source (3 URLs)      8.9s        3.3s        +63%
```

### Performance Monitoring

**Metrics to Track:**

1. **Execution Time per Level:**
   ```python
   # Log output:
   Level 0 (1 nodes):  2.8s
   Level 1 (1 nodes):  0.9s
   Level 2 (2 nodes):  2.1s  ← Parallel execution
   Level 3 (1 nodes):  0.6s
   Total: 6.4s
   ```

2. **Parallelism Utilization:**
   ```python
   Total nodes: 6
   Critical path length: 5
   Parallelism factor: 1.20
   Nodes executed in parallel: 2
   ```

3. **Resource Usage:**
   - CPU utilization (should increase with parallelism)
   - Memory usage (should remain stable)
   - Thread pool saturation
   - Wait times for thread availability

### Regression Prevention

**Before Merging:**
1. Run benchmark suite on 5 different graph types
2. Verify no regression in sequential mode
3. Validate memory usage under load
4. Check for thread leaks over extended runs

**Continuous Monitoring:**
1. Add benchmarks to CI/CD pipeline
2. Alert on >5% performance regression
3. Weekly performance reports
4. Monthly review of optimization opportunities

## Alternatives Considered

### Alternative 1: Always-On Parallel Execution

**Description:** Enable parallel execution by default for all graphs, with automatic fallback to sequential for incompatible graphs.

**Pros:**
- Users get benefits automatically
- No configuration needed
- Simpler API

**Cons:**
- Risky for production rollout
- Hard to debug issues
- May break existing workflows with side effects
- Overhead for graphs with no parallelism

**Why Not Chosen:** Too risky for initial release. Opt-in is safer and gives users control.

---

### Alternative 2: New ParallelGraph Class

**Description:** Create a separate `ParallelGraph` class instead of modifying `BaseGraph`.

**Pros:**
- Complete isolation from existing code
- Easier to implement initially
- Clear opt-in for users

**Cons:**
- Code duplication
- Two parallel implementations to maintain
- Confusing for users (which to use?)
- Doesn't solve the general problem

**Why Not Chosen:** Creates unnecessary code duplication. Better to enhance `BaseGraph` with backward compatibility.

---

### Alternative 3: Async/Await Rewrite

**Description:** Rewrite the entire execution engine to use async/await from the ground up.

**Pros:**
- Modern Python concurrency model
- Better for I/O-bound tasks
- Cleaner code for concurrent operations

**Cons:**
- Breaking change (all nodes need async methods)
- Massive refactoring required
- Breaks all existing custom nodes
- Users must understand async/await

**Why Not Chosen:** Too disruptive. We can add async support later as an execution mode within the parallel executor.

---

### Alternative 4: External Task Queue (Celery)

**Description:** Use Celery or similar task queue for distributed execution of nodes.

**Pros:**
- Handles complex scheduling
- Can scale across multiple machines
- Battle-tested infrastructure

**Cons:**
- Requires external dependencies (Redis/RabbitMQ)
- Adds operational complexity
- Overkill for single-machine parallelism
- Higher latency for task dispatch

**Why Not Chosen:** Over-engineered for the common case. Most users want faster single-machine execution, not distributed computing.

---

### Alternative 5: Ray Framework Integration

**Description:** Integrate with Ray for distributed execution.

**Pros:**
- Sophisticated distributed computing
- Handles both parallelism and distribution
- Good for large-scale deployments

**Cons:**
- Heavy dependency (~100MB)
- Steep learning curve
- Unnecessary for most use cases
- Adds maintenance burden

**Why Not Chosen:** Too heavyweight for the problem we're solving. ThreadPoolExecutor is sufficient for most use cases.

---

### Decision Matrix

| Alternative | Simplicity | Performance | Compatibility | Maintenance | Score |
|------------|-----------|-------------|---------------|-------------|-------|
| **Opt-in Parallel (Chosen)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **22/25** |
| Always-On Parallel | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | 17/25 |
| New ParallelGraph Class | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 17/25 |
| Async/Await Rewrite | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | 14/25 |
| External Task Queue | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | 13/25 |
| Ray Framework | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | 13/25 |

## Security Considerations

### Threat Model

**Threat 1: Resource Exhaustion via Unbounded Parallelism**

**Description:** Malicious or buggy code could create graphs with excessive parallelism, exhausting system resources (CPU, memory, threads).

**Mitigation:**
- Enforce `max_workers` limit in ParallelExecutor (default: 4)
- Add global thread pool size limit via environment variable
- Monitor thread pool saturation
- Implement circuit breaker for repeated failures

**Implementation:**
```python
# In ExecutorConfig
max_workers: int = 4  # Hard limit on concurrent nodes
max_threads_global: int = 20  # System-wide limit

# In ParallelExecutor
if self.config.max_workers > self.config.max_threads_global:
    logger.warning(f"Limiting max_workers to global limit: {self.config.max_threads_global}")
    self.config.max_workers = self.config.max_threads_global
```

---

**Threat 2: State Race Conditions**

**Description:** Concurrent nodes modifying shared state could cause race conditions, data corruption, or inconsistent results.

**Mitigation:**
- Document state management best practices
- Encourage immutable state patterns
- Detect state conflicts (warn if multiple nodes write same key)
- Provide state locking utilities for advanced users

**Implementation:**
```python
class StateConflictDetector:
    """Detects conflicting state modifications."""

    def __init__(self):
        self.writes = defaultdict(list)  # {key: [node_names]}

    def record_write(self, key: str, node_name: str):
        self.writes[key].append(node_name)

    def check_conflicts(self):
        conflicts = {
            key: nodes
            for key, nodes in self.writes.items()
            if len(nodes) > 1
        }
        if conflicts:
            logger.warning(f"State conflicts detected: {conflicts}")
        return conflicts
```

---

**Threat 3: Deadlock in Cyclic Dependencies**

**Description:** Incorrectly constructed graphs with cycles could cause deadlock in parallel execution.

**Mitigation:**
- Detect cycles before enabling parallel execution
- Raise clear error if cycle detected
- Refuse to enable parallelism for cyclic graphs
- Provide cycle visualization for debugging

**Implementation:**
```python
# In BaseGraph.__init__ when enable_parallel=True
has_cycle, cycle = self.dag_analyzer.detect_cycles()
if has_cycle:
    raise ValueError(
        f"Cannot enable parallel execution: graph contains cycle: "
        f"{' → '.join(cycle)}\n"
        f"Remove the cycle or use sequential execution."
    )
```

---

**Threat 4: Sensitive Data Leakage Between Nodes**

**Description:** State shared between parallel nodes might contain sensitive data (passwords, API keys) that shouldn't be exposed to all nodes.

**Mitigation:**
- Document state isolation best practices
- Encourage minimal state sharing
- Provide state filtering utilities
- Add warnings for large state objects

**Best Practices Documentation:**
```python
# GOOD: Nodes declare explicit inputs/outputs
ValidationNode(input="parsed_doc", output=["is_valid"])
TransformNode(input="parsed_doc", output=["cleaned_doc"])

# BAD: Nodes access entire state indiscriminately
def execute(self, state):
    api_key = state.get("api_key")  # ← Should not be accessible
```

---

**Threat 5: Timeout Bypass**

**Description:** Long-running nodes in parallel execution might not respect timeouts properly.

**Mitigation:**
- Enforce per-node timeouts in ParallelExecutor
- Cancel slow tasks after timeout
- Log timeout events for monitoring
- Graceful degradation on timeout

**Implementation:**
```python
# In ParallelExecutor
for future in as_completed(futures_to_nodes, timeout=self.config.timeout_per_node):
    try:
        result = future.result(timeout=self.config.timeout_per_node)
    except TimeoutError:
        logger.error(f"Node {node.node_name} exceeded timeout")
        # Cancel future and mark as failed
```

### Security Best Practices

1. **Principle of Least Privilege:**
   - Nodes only access state keys they explicitly declare
   - Parallel executor only has execution permissions
   - No global mutable state

2. **Defense in Depth:**
   - Multiple layers: cycle detection, timeouts, resource limits
   - Graceful degradation on failure
   - Comprehensive logging for audit trail

3. **Secure Defaults:**
   - `max_workers=4` (reasonable default)
   - `fail_fast=True` (stop on first error)
   - `timeout_per_node=None` (can be set by user)

4. **Audit Trail:**
   - Log all parallel execution starts/completions
   - Log resource usage (threads, time)
   - Log errors and timeouts
   - Include node names and timestamps

## Open Questions

### Question 1: Default Max Workers

**Context:** What should the default `max_workers` be?

**Options:**
- **4 workers:** Conservative, works on most systems
- **8 workers:** Aggressive, better for high-core systems
- **CPU count:** Dynamic based on available cores
- **Auto-detect:** Based on graph structure and system resources

**Trade-offs:**
- Low value: Underutilizes resources on powerful machines
- High value: May overwhelm systems with limited resources
- Dynamic: Complex but optimal

**Request for Input:** What default provides the best balance for typical use cases?

---

### Question 2: Async/Await Priority

**Context:** Should we prioritize thread-based or async-based parallel execution?

**Current Plan:** Start with threads, add async later.

**Alternative:** Implement async first, add threads as fallback.

**Considerations:**
- Most nodes are currently synchronous
- Async requires node refactoring
- Threads are simpler for CPU-bound tasks
- Async is better for I/O-bound tasks (LLM calls, fetching)

**Request for Input:** Is async support a high priority for users? Should we implement it in Phase 3 or defer to later?

---

### Question 3: State Immutability

**Context:** Should we enforce immutable state in parallel execution?

**Options:**
1. **Copy-on-write:** State is immutable, copies made on modification
2. **Explicit merge:** Nodes return new state, merged by executor
3. **Mutable with warnings:** Current approach, add conflict detection

**Trade-offs:**
- Immutable: Safer but higher memory overhead
- Explicit merge: Clear but requires node changes
- Mutable: Backward compatible but riskier

**Request for Input:** What approach fits best with ScrapeGraphAI's philosophy?

---

### Question 4: Parallelism Visualization

**Context:** Should we provide tools to visualize execution and parallelism?

**Potential Features:**
- Gantt chart of node execution timelines
- DAG visualization with parallelism highlighted
- Critical path visualization
- Real-time execution monitoring

**Request for Input:** Would visualization tools add significant value? Should they be built-in or separate package?

---

### Question 5: Integration with Burr

**Context:** How should parallel execution interact with Burr integration?

**Current State:** Burr has its own execution model.

**Questions:**
- Can Burr handle parallel execution?
- Should we disable parallel execution when `use_burr=True`?
- Can we bridge the two execution models?

**Request for Input:** Input from Burr users on integration requirements.

---

### Question 6: Backward Compatibility for Edge Cases

**Context:** Are there edge cases where parallel execution might break existing graphs?

**Potential Issues:**
- Graphs relying on state mutation order
- Graphs with side effects (file writes, API calls)
- Custom nodes with thread-unsafe operations

**Request for Input:** Identify potential breaking scenarios from community testing.

---

### Question 7: Performance Target

**Context:** What performance improvement should we target?

**Current Proposal:** 40-60% for highly parallel graphs.

**Questions:**
- Is this realistic?
- Should we target higher speedup?
- What's the minimum improvement to be worthwhile?

**Request for Input:** What performance improvement would make this feature valuable for users?

---

### How to Provide Input

**For Community Members:**
- Comment on the RFC GitHub issue
- Join the discussion on Discord (#performance-optimization)
- Submit feedback via GitHub Discussions

**For Core Team:**
- Review during weekly architecture meeting
- Async feedback via RFC document comments
- Vote on contentious decisions

**Timeline:**
- RFC open for feedback: 2 weeks
- Decisions finalized: Week 3
- Implementation begins: Week 4

## Success Metrics

### Primary Metrics

**Metric 1: Execution Time Reduction (Parallelizable Graphs)**

**Definition:** Percentage reduction in total execution time for graphs with parallelizable structure.

**Target:** 40-60% reduction for graphs with 3+ parallel branches

**Measurement:**
```python
def measure_speedup():
    # Sequential
    seq_graph = create_graph(enable_parallel=False)
    seq_time = benchmark(seq_graph, iterations=100)

    # Parallel
    par_graph = create_graph(enable_parallel=True)
    par_time = benchmark(par_graph, iterations=100)

    speedup = (seq_time - par_time) / seq_time * 100
    assert speedup >= 40  # 40% minimum

    return speedup

# Expected results:
# 2 parallel branches:  25-35% speedup
# 3 parallel branches:  35-45% speedup
# 5+ parallel branches: 45-60% speedup
```

**Reporting:** Weekly benchmark dashboard

---

**Metric 2: Resource Utilization**

**Definition:** CPU and thread utilization during parallel execution.

**Target:**
- CPU utilization: 60-90% (vs 20-30% sequential)
- Thread pool saturation: < 10% (avoid bottlenecks)

**Measurement:**
```python
import psutil

def measure_resource_utilization():
    process = psutil.Process()

    # Measure during execution
    cpu_percentages = []
    thread_counts = []

    # Execute graph
    for _ in range(100):
        cpu_percentages.append(process.cpu_percent(interval=0.1))
        thread_counts.append(process.num_threads())

    avg_cpu = sum(cpu_percentages) / len(cpu_percentages)
    avg_threads = sum(thread_counts) / len(thread_counts)

    return avg_cpu, avg_threads
```

**Reporting:** Resource monitoring dashboard

---

**Metric 3: No Regression for Sequential Graphs**

**Definition:** Sequential execution time should not increase by more than 2%.

**Target:** < 2% overhead

**Measurement:**
```python
def measure_overhead():
    # Baseline (current implementation)
    baseline_time = benchmark_current_implementation()

    # New implementation with enable_parallel=False
    new_time = benchmark_new_implementation(enable_parallel=False)

    overhead = (new_time - baseline_time) / baseline_time * 100
    assert overhead < 2  # Less than 2% overhead

    return overhead
```

**Reporting:** CI/CD regression tests

### Secondary Metrics

**Metric 4: Adoption Rate**

**Definition:** Percentage of graphs using parallel execution.

**Target:** 30% of production graphs within 6 months

**Measurement:**
```python
# Telemetry
log_graph_execution(
    graph_name=self.graph_name,
    parallel_enabled=self.enable_parallel,
    parallel_levels=len(execution_levels) if parallel else None
)
```

**Reporting:** Monthly adoption report

---

**Metric 5: Error Rate**

**Definition:** Percentage of graph executions that fail.

**Target:** No increase from baseline (< 1%)

**Measurement:**
```python
def measure_error_rate():
    total = 1000
    failures = 0

    for _ in range(total):
        try:
            graph.execute(initial_state)
        except Exception:
            failures += 1

    error_rate = failures / total * 100
    assert error_rate < 1  # Less than 1%
```

**Reporting:** Production error monitoring

---

**Metric 6: Parallelism Efficiency**

**Definition:** How close actual speedup is to theoretical maximum.

**Target:** 80% efficiency

**Measurement:**
```python
def measure_efficiency():
    # Theoretical speedup (Amdahl's Law)
    parallel_fraction = 0.6  # 60% of work is parallelizable
    num_workers = 4
    theoretical_speedup = 1 / ((1 - parallel_fraction) + parallel_fraction / num_workers)

    # Actual speedup
    actual_speedup = sequential_time / parallel_time

    # Efficiency
    efficiency = (actual_speedup / theoretical_speedup) * 100
    assert efficiency >= 80  # 80% minimum
```

**Reporting:** Performance analytics

---

### Monitoring Dashboard

**Proposed Metrics Dashboard:**

```
┌─────────────────────────────────────────────────────────────────┐
│  ScrapeGraphAI Parallel Execution Metrics                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Speedup (Parallel Graphs):   [████████░░] 52% avg             │
│  CPU Utilization:             [███████░░░] 78%                  │
│  Sequential Overhead:         [██████████] 0.8% (<2% target)    │
│  Adoption Rate:               [█████░░░░░] 18%                  │
│  Error Rate:                  [██████████] 0.4% (<1% target)    │
│  Parallelism Efficiency:      [████████░░] 85%                  │
│                                                                  │
│  Graphs Executed Today:       1,247                             │
│  ├─ Sequential:               1,023 (82%)                       │
│  └─ Parallel:                 224 (18%)                         │
│                                                                  │
│  Parallel Execution Stats:                                      │
│  ├─ Avg Levels:               3.2                               │
│  ├─ Avg Nodes per Level:      2.4                               │
│  ├─ Avg Speedup:              52%                               │
│  └─ Total Time Saved:         4.2 hours                         │
│                                                                  │
│  Recent Events:                                                 │
│  ✓ 14:32:11 - Parallel graph executed (3 levels, 45% speedup)  │
│  ✓ 14:31:45 - Sequential graph executed (no parallelism)       │
│  ⚠ 14:28:15 - Thread pool saturation detected (consider tuning)│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Success Criteria Summary

**Phase 1 (Foundation) Success:**
- [ ] All 6 primary + secondary metrics defined
- [ ] Baseline measurements captured
- [ ] Monitoring infrastructure in place

**Phase 2 (Integration) Success:**
- [ ] Metric 3: < 2% overhead for sequential graphs
- [ ] Metric 5: Error rate unchanged from baseline

**Phase 3 (Optimization) Success:**
- [ ] Metric 1: 40-60% speedup for parallel graphs
- [ ] Metric 2: 60-90% CPU utilization
- [ ] Metric 6: 80% parallelism efficiency

**Phase 4 (Production) Success:**
- [ ] All metrics meeting targets for 2 consecutive weeks
- [ ] Metric 4: 30% adoption rate (or growing trend)
- [ ] Zero critical incidents related to parallel execution
- [ ] Positive community feedback

**Long-term Success (6 months):**
- [ ] All targets maintained
- [ ] No rollbacks or hotfixes required
- [ ] Feature used by 50%+ of production workloads
- [ ] Documentation and best practices established

## References

### Code References

1. **BaseGraph Sequential Execution**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`
   - Lines: 236-340 (`_execute_standard` method)
   - Key issue: Sequential while loop at line 264

2. **Edge Creation**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`
   - Lines: 83-98 (`_create_edges` method)
   - Gap: Simple dict representation doesn't capture DAG structure

3. **Node Execution**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/base_graph.py`
   - Lines: 198-220 (`_execute_node` method)
   - Key issue: Blocking synchronous execution

4. **MultiGraph Implementation**
   - File: `/home/user/Scrapegraph-ai/scrapegraphai/graphs/smart_scraper_multi_graph.py`
   - Shows parallelization of **graph instances**, not nodes
   - Uses `GraphIteratorNode` for parallel execution

5. **Performance Analysis**
   - File: `/home/user/Scrapegraph-ai/analysis-output/blog-series/05-performance-analysis.md`
   - Lines: 82-150
   - Data: Playwright overhead, LLM latency, sequential bottlenecks

6. **Execution Engine Deep Dive**
   - File: `/home/user/Scrapegraph-ai/analysis-output/blog-series/02-deep-dive-execution-engine.md`
   - Lines: 31-150
   - Context: How current execution loop works

### External References

7. **DAG Scheduling Algorithms**
   - Topological Sort (Kahn's Algorithm)
   - Critical Path Method (CPM)
   - Parallel Task Scheduling

8. **Python Concurrency Patterns**
   - ThreadPoolExecutor: https://docs.python.org/3/library/concurrent.futures.html
   - asyncio: https://docs.python.org/3/library/asyncio.html
   - Amdahl's Law for parallel speedup

9. **Similar Implementations**
   - LangChain/LangGraph parallel execution
   - Apache Airflow DAG execution
   - Prefect parallel tasks

10. **Graph Theory Resources**
    - Directed Acyclic Graph (DAG) properties
    - Dependency resolution algorithms
    - Cycle detection algorithms

### Related RFCs

11. **RFC-0001: Browser Connection Pooling**
    - File: `/home/user/Scrapegraph-ai/analysis-output/rfcs/RFC-0001-browser-connection-pooling.md`
    - Related: Reduces Playwright overhead (complements parallelism)

12. **RFC-0008: Graph Template System**
    - File: `/home/user/Scrapegraph-ai/analysis-output/rfcs/RFC-0008-graph-template-system.md`
    - Related: Makes creating parallel graph structures easier

### Academic References

13. **Task Scheduling in Distributed Systems**
    - Concepts: Load balancing, work stealing, task graphs
    - Application: Parallel node scheduling

14. **Parallel Computing Patterns**
    - Fork-join pattern
    - Map-reduce pattern
    - Pipeline parallelism

---

## Appendix: Code Examples

### A1: Complete Example - Multi-Source Scraping

```python
"""
Complete example: Parallel fetching of multiple sources with validation.
"""

from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import (
    FetchNode, ParseNode, ValidationNode,
    MergeNode, GenerateAnswerNode
)

# Create nodes for 3 different sources
fetch1 = FetchNode(
    input="url1",
    output=["doc1"],
    node_config={"llm_model": llm_model},
    node_name="fetch_source_1"
)

fetch2 = FetchNode(
    input="url2",
    output=["doc2"],
    node_config={"llm_model": llm_model},
    node_name="fetch_source_2"
)

fetch3 = FetchNode(
    input="url3",
    output=["doc3"],
    node_config={"llm_model": llm_model},
    node_name="fetch_source_3"
)

# Parse nodes (also run in parallel)
parse1 = ParseNode(input="doc1", output=["parsed1"], node_name="parse_1")
parse2 = ParseNode(input="doc2", output=["parsed2"], node_name="parse_2")
parse3 = ParseNode(input="doc3", output=["parsed3"], node_name="parse_3")

# Validation (parallel)
validate1 = ValidationNode(input="parsed1", output=["valid1"], node_name="validate_1")
validate2 = ValidationNode(input="parsed2", output=["valid2"], node_name="validate_2")
validate3 = ValidationNode(input="parsed3", output=["valid3"], node_name="validate_3")

# Merge and generate
merge = MergeNode(
    input="valid1 & valid2 & valid3",
    output=["merged_data"],
    node_name="merge"
)

generate = GenerateAnswerNode(
    input="merged_data & user_prompt",
    output=["answer"],
    node_config={"llm_model": llm_model},
    node_name="generate"
)

# Create graph with parallel structure
graph = BaseGraph(
    nodes=[
        fetch1, fetch2, fetch3,
        parse1, parse2, parse3,
        validate1, validate2, validate3,
        merge, generate
    ],
    edges=[
        # Fetch → Parse (parallel)
        (fetch1, parse1),
        (fetch2, parse2),
        (fetch3, parse3),
        # Parse → Validate (parallel)
        (parse1, validate1),
        (parse2, validate2),
        (parse3, validate3),
        # Validate → Merge (fan-in)
        (validate1, merge),
        (validate2, merge),
        (validate3, merge),
        # Merge → Generate
        (merge, generate),
    ],
    entry_point=fetch1,
    enable_parallel=True,
    parallel_config={
        "mode": "threads",
        "max_workers": 6,  # Can handle 3 fetches + 3 parses
    }
)

# Execute
result = graph.execute({
    "url1": "https://source1.com",
    "url2": "https://source2.com",
    "url3": "https://source3.com",
    "user_prompt": "Compare information from all sources"
})

# Execution levels:
# Level 0: [fetch1, fetch2, fetch3]        - 2.8s (parallel)
# Level 1: [parse1, parse2, parse3]        - 0.9s (parallel)
# Level 2: [validate1, validate2, validate3] - 1.2s (parallel)
# Level 3: [merge]                         - 0.5s
# Level 4: [generate]                      - 1.5s
# Total: 6.9s
#
# Sequential would be: 3×(2.8+0.9+1.2) + 0.5 + 1.5 = 16.7s
# Speedup: 59%
```

### A2: DAG Analysis Utilities

```python
"""
Utility script to analyze graph structure and parallelism potential.
"""

from scrapegraphai.utils.dag_analyzer import DAGAnalyzer

def analyze_graph(graph):
    """Analyze and report graph parallelization potential."""

    # Create analyzer
    analyzer = DAGAnalyzer(
        graph.adjacency_list,
        graph.reverse_adjacency_list
    )

    # Check for cycles
    has_cycle, cycle = analyzer.detect_cycles()
    if has_cycle:
        print(f"❌ Graph contains cycle: {' → '.join(cycle)}")
        print("   Parallel execution not possible.")
        return

    print("✓ Graph is acyclic (DAG)")

    # Calculate execution levels
    levels = analyzer.calculate_execution_levels()
    print(f"\nExecution Levels: {len(levels)}")
    for i, level in enumerate(levels):
        print(f"  Level {i}: {len(level)} nodes - {level}")

    # Calculate parallelism factor
    factor = analyzer.get_parallelism_factor()
    print(f"\nParallelism Factor: {factor:.2f}")
    if factor > 1.5:
        print("  ✓ Good parallelism potential!")
    elif factor > 1.2:
        print("  ⚠ Moderate parallelism potential")
    else:
        print("  ℹ Limited parallelism (mostly sequential)")

    # Calculate critical path (with estimated durations)
    node_durations = {
        node.node_name: estimate_duration(node)
        for node in graph.nodes
    }

    critical_path, duration = analyzer.calculate_critical_path(node_durations)
    print(f"\nCritical Path: {' → '.join(critical_path)}")
    print(f"Minimum Execution Time: {duration:.2f}s")

    # Calculate potential speedup
    total_sequential = sum(node_durations.values())
    max_speedup = total_sequential / duration
    print(f"\nTheoretical Maximum Speedup: {max_speedup:.1f}x")
    print(f"  (from {total_sequential:.2f}s to {duration:.2f}s)")

def estimate_duration(node):
    """Estimate node execution duration based on type."""
    node_type = node.__class__.__name__
    estimates = {
        "FetchNode": 2.8,
        "ParseNode": 0.9,
        "ValidationNode": 1.2,
        "TransformNode": 2.1,
        "MergeNode": 0.5,
        "GenerateAnswerNode": 1.5,
    }
    return estimates.get(node_type, 1.0)

# Example usage
if __name__ == "__main__":
    from my_graphs import create_my_graph

    graph = create_my_graph()
    analyze_graph(graph)
```

### A3: Performance Comparison Tool

```python
"""
Tool to benchmark sequential vs parallel execution.
"""

import time
import statistics
from typing import List, Dict

def benchmark_comparison(
    graph_factory,
    initial_state: dict,
    iterations: int = 50
) -> Dict:
    """
    Compare sequential vs parallel execution performance.

    Args:
        graph_factory: Function that creates graph with enable_parallel param
        initial_state: Initial state for graph execution
        iterations: Number of benchmark iterations

    Returns:
        Dict with benchmark results
    """
    print("Benchmarking Sequential Execution...")
    seq_graph = graph_factory(enable_parallel=False)
    seq_times = []

    for i in range(iterations):
        start = time.time()
        seq_graph.execute(initial_state)
        elapsed = time.time() - start
        seq_times.append(elapsed)
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{iterations} iterations")

    print("\nBenchmarking Parallel Execution...")
    par_graph = graph_factory(enable_parallel=True)
    par_times = []

    for i in range(iterations):
        start = time.time()
        par_graph.execute(initial_state)
        elapsed = time.time() - start
        par_times.append(elapsed)
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{iterations} iterations")

    # Calculate statistics
    seq_mean = statistics.mean(seq_times)
    seq_stdev = statistics.stdev(seq_times)
    par_mean = statistics.mean(par_times)
    par_stdev = statistics.stdev(par_times)

    speedup = (seq_mean - par_mean) / seq_mean * 100
    time_saved = seq_mean - par_mean

    # Print results
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    print(f"Sequential Execution:")
    print(f"  Mean:   {seq_mean:.3f}s ± {seq_stdev:.3f}s")
    print(f"  Min:    {min(seq_times):.3f}s")
    print(f"  Max:    {max(seq_times):.3f}s")
    print()
    print(f"Parallel Execution:")
    print(f"  Mean:   {par_mean:.3f}s ± {par_stdev:.3f}s")
    print(f"  Min:    {min(par_times):.3f}s")
    print(f"  Max:    {max(par_times):.3f}s")
    print()
    print(f"Improvement:")
    print(f"  Speedup:     {speedup:+.1f}%")
    print(f"  Time Saved:  {time_saved:.3f}s per execution")
    print(f"  Total Saved: {time_saved * iterations:.1f}s over {iterations} runs")
    print("="*60)

    return {
        "sequential": {
            "mean": seq_mean,
            "stdev": seq_stdev,
            "times": seq_times
        },
        "parallel": {
            "mean": par_mean,
            "stdev": par_stdev,
            "times": par_times
        },
        "speedup_percent": speedup,
        "time_saved": time_saved
    }

# Example usage
if __name__ == "__main__":
    def my_graph_factory(enable_parallel=False):
        # Create and return your graph
        pass

    initial_state = {
        "url1": "https://example.com",
        "url2": "https://example.org",
        "url3": "https://example.net",
        "user_prompt": "Extract data"
    }

    results = benchmark_comparison(
        my_graph_factory,
        initial_state,
        iterations=100
    )
```

---

**End of RFC-0014**

---

**Feedback and questions welcome!**
Please direct comments to the RFC discussion thread or reach out to the ScrapeGraphAI team on Discord.
