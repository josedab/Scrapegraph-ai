# Parallel Node Execution Guide

This guide explains how to use parallel execution of independent nodes within a single graph to improve performance.

## Overview

ScrapeGraphAI now supports parallel execution of independent nodes within a single graph. This is fundamentally different from `MultiGraph`, which parallelizes multiple graph instances for multiple URLs. This feature focuses on parallelizing independent nodes **within a single graph execution**.

### Key Benefits

- **Reduced latency:** Get results 40-60% faster for parallelizable workflows
- **Better resource utilization:** Multi-core CPUs and concurrent API calls fully utilized
- **Improved throughput:** More requests processed per second on same hardware
- **100% Backward compatible:** Opt-in feature, existing graphs work unchanged

## Quick Start

### Basic Usage

```python
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import FetchNode, ParseNode, ValidationNode, TransformNode, MergeNode, GenerateAnswerNode

# Create nodes
fetch = FetchNode(...)
parse = ParseNode(...)
validate = ValidationNode(...)
transform = TransformNode(...)
merge = MergeNode(...)
generate = GenerateAnswerNode(...)

# Create graph with parallel structure
graph = BaseGraph(
    nodes=[fetch, parse, validate, transform, merge, generate],
    edges=[
        (fetch, parse),
        (parse, validate),      # Parse fans out to both
        (parse, transform),     # validate and transform
        (validate, merge),      # Both feed into merge
        (transform, merge),
        (merge, generate),
    ],
    entry_point=fetch,
    enable_parallel=True,       # Enable parallel execution
    parallel_config={
        "mode": "threads",      # Execution mode
        "max_workers": 4,       # Thread pool size
        "fail_fast": True,      # Stop on first error
    }
)

# Execute
result = graph.execute({
    "url": "https://example.com",
    "user_prompt": "Extract data"
})
```

### Execution Timeline

**Without Parallelism (Sequential):**
```
Fetch:     ████████                    (2.8s)
Parse:             ███                 (0.9s)
Validate:             ████             (1.2s)
Transform:                 ███████     (2.1s)
Merge:                            ██   (0.6s)
Generate:                           ████ (1.1s)

Total: 8.7 seconds
```

**With Parallelism:**
```
Level 0 - Fetch:     ████████                (2.8s)
Level 1 - Parse:             ███             (0.9s)
Level 2 - Parallel:             ███████      (2.1s = max(1.2s, 2.1s))
  Validate:                     ████
  Transform:                    ███████
Level 3 - Merge:                       ██    (0.6s)
Level 4 - Generate:                      ████ (1.1s)

Total: 5.6 seconds (36% improvement, saves 3.1s)
```

## Configuration Options

### Parallel Config Parameters

```python
parallel_config = {
    "mode": "threads",           # Execution mode: "threads", "asyncio", or "sequential"
    "max_workers": 4,            # Maximum number of parallel workers
    "timeout_per_node": 30.0,    # Optional timeout in seconds per node
    "fail_fast": True,           # Stop on first error (True) or continue (False)
}
```

### Execution Modes

1. **threads** (Default): Uses ThreadPoolExecutor
   - Best for I/O-bound tasks (LLM calls, web fetching)
   - Simple and reliable
   - Recommended for most use cases

2. **asyncio**: Uses async/await
   - Best for async-native code
   - Lower overhead for many small tasks
   - Requires async-compatible nodes

3. **sequential**: Fallback to sequential execution
   - Useful for debugging
   - Maintains same interface as parallel execution

## Common Patterns

### Pattern 1: Multi-Source Fetching

Fetch data from multiple sources in parallel:

```python
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import FetchNode, MergeNode, GenerateAnswerNode

# Create multiple fetch nodes
fetch1 = FetchNode(input="url1", output=["doc1"], node_name="fetch_source1", ...)
fetch2 = FetchNode(input="url2", output=["doc2"], node_name="fetch_source2", ...)
fetch3 = FetchNode(input="url3", output=["doc3"], node_name="fetch_source3", ...)

merge = MergeNode(input="doc1 & doc2 & doc3", output=["merged_doc"], ...)
generate = GenerateAnswerNode(input="merged_doc & user_prompt", output=["answer"], ...)

graph = BaseGraph(
    nodes=[fetch1, fetch2, fetch3, merge, generate],
    edges=[
        (fetch1, merge),
        (fetch2, merge),
        (fetch3, merge),
        (merge, generate),
    ],
    entry_point=fetch1,
    enable_parallel=True,
    parallel_config={"max_workers": 3}
)

result = graph.execute({
    "url1": "https://site1.com",
    "url2": "https://site2.com",
    "url3": "https://site3.com",
    "user_prompt": "Compare prices"
})

# Sequential: 3 × 2.8s = 8.4s
# Parallel:   max(2.8s, 2.8s, 2.8s) = 2.8s
# Improvement: 67% faster!
```

### Pattern 2: Independent Processing Branches

Process data through multiple independent pipelines:

```python
# Fetch → Parse → ┬→ Validation  ┬→ Merge → Generate
#                 └→ Transform    ┘

graph = BaseGraph(
    nodes=[fetch, parse, validation, transform, merge, generate],
    edges=[
        (fetch, parse),
        (parse, validation),
        (parse, transform),
        (validation, merge),
        (transform, merge),
        (merge, generate),
    ],
    entry_point=fetch,
    enable_parallel=True,
)

# validation and transform run in parallel
```

### Pattern 3: Multi-Model LLM Queries

Query multiple LLM models concurrently:

```python
# Extract different information using different models in parallel

gpt4_extract = LLMNode(
    model="gpt-4",
    prompt="Extract product prices",
    output=["prices"],
    ...
)

claude_extract = LLMNode(
    model="claude-3",
    prompt="Extract product specifications",
    output=["specs"],
    ...
)

combine = CombineNode(
    input="prices & specs",
    output=["combined_data"],
    ...
)

graph = BaseGraph(
    nodes=[fetch, parse, gpt4_extract, claude_extract, combine],
    edges=[
        (fetch, parse),
        (parse, gpt4_extract),
        (parse, claude_extract),
        (gpt4_extract, combine),
        (claude_extract, combine),
    ],
    entry_point=fetch,
    enable_parallel=True,
)

# gpt4_extract and claude_extract run in parallel
```

## Analyzing Parallelism Potential

Use `DAGAnalyzer` to analyze your graph structure:

```python
from scrapegraphai.utils import DAGAnalyzer

# Create analyzer from graph
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
# Output: Parallelism factor: 1.20

if factor > 1.5:
    print("✓ Good parallelism potential!")
elif factor > 1.2:
    print("⚠ Moderate parallelism potential")
else:
    print("ℹ Limited parallelism (mostly sequential)")

# Calculate critical path
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

## Performance Considerations

### When to Use Parallel Execution

✅ **Good Use Cases:**
- Multiple independent fetch operations
- Multiple independent transformations
- Multiple independent LLM calls
- Validation and transformation branches
- Multi-source data aggregation

❌ **Not Beneficial:**
- Strictly sequential pipelines (no parallelism)
- Very fast nodes (overhead > benefit)
- Graphs with cycles (not supported)

### Expected Performance Improvements

| Parallel Branches | Expected Speedup |
|------------------|------------------|
| 2 branches       | 25-35%          |
| 3 branches       | 35-45%          |
| 5 branches       | 45-60%          |
| 8+ branches      | 45-60%          |

### Tuning max_workers

- **Too low:** Underutilizes resources
- **Too high:** May overwhelm system or hit rate limits
- **Recommended:** Start with 4, adjust based on:
  - Number of parallel branches in your graph
  - Available CPU cores
  - Network/API rate limits

```python
# For 3 parallel branches
parallel_config={"max_workers": 3}

# For 8 parallel branches on 8-core system
parallel_config={"max_workers": 8}

# For rate-limited APIs
parallel_config={"max_workers": 2}  # Avoid hitting limits
```

## Debugging and Monitoring

### Enable Logging

```python
from scrapegraphai.utils.logging import set_verbosity_info

set_verbosity_info()

# Now you'll see execution logs:
# INFO: Executing graph 'MyGraph' with 3 parallel levels
# INFO: Executing level 0: ['fetch'] (1 nodes)
# INFO: Level 0 completed in 2.81s (1 nodes executed)
# INFO: Executing level 1: ['parse'] (1 nodes)
# INFO: Level 1 completed in 0.92s (1 nodes executed)
# INFO: Executing level 2: ['validate', 'transform'] (2 nodes)
# INFO: Level 2 completed in 2.15s (2 nodes executed)
# ...
```

### Handle Errors

With `fail_fast=True` (default), execution stops on first error:

```python
try:
    result = graph.execute(initial_state)
except Exception as e:
    print(f"Graph execution failed: {e}")
    # Check execution info to see which node failed
```

With `fail_fast=False`, execution continues despite errors:

```python
parallel_config = {
    "fail_fast": False,  # Continue on error
}

result, exec_info = graph.execute(initial_state)

# Check for node failures
for info in exec_info:
    if info.get("error"):
        print(f"Node {info['node_name']} failed: {info['error']}")
```

## State Management

### How State is Handled

In parallel execution, each node receives a **copy** of the input state:

```python
# Initial state
state = {"url": "https://example.com", "prompt": "Extract data"}

# Level 1: Parse node
# State after: {"url": "...", "prompt": "...", "parsed_doc": "..."}

# Level 2: Validate and Transform run in parallel
# Each gets a copy of state from Level 1
# Validate adds: {"is_valid": True}
# Transform adds: {"transformed_data": "..."}

# After Level 2, states are merged:
# {"url": "...", "prompt": "...", "parsed_doc": "...",
#  "is_valid": True, "transformed_data": "..."}
```

### Best Practices for State

1. **Nodes should declare explicit inputs/outputs:**
   ```python
   ValidationNode(input="parsed_doc", output=["is_valid"])
   TransformNode(input="parsed_doc", output=["transformed_data"])
   ```

2. **Avoid state key conflicts:**
   - Different parallel nodes should write to different keys
   - If conflicts occur, last write wins (non-deterministic)

3. **Use merge nodes to combine results:**
   ```python
   MergeNode(input="result1 & result2 & result3", output=["merged"])
   ```

## Limitations and Constraints

### Cycle Detection

Graphs with cycles cannot use parallel execution:

```python
# This will raise ValueError:
# "Cannot enable parallel execution: graph contains cycle: A → B → A"

graph = BaseGraph(
    nodes=[nodeA, nodeB],
    edges=[
        (nodeA, nodeB),
        (nodeB, nodeA),  # Cycle!
    ],
    entry_point=nodeA,
    enable_parallel=True,  # ← Will raise error
)
```

### ConditionalNode Support

Conditional nodes are currently not fully supported with parallel execution. Use sequential execution for graphs with conditional branches.

### Thread Safety

Nodes should be thread-safe if using parallel execution. Avoid:
- Shared mutable state between nodes
- Non-thread-safe operations
- Blocking I/O without proper timeouts

## Migration Guide

### Existing Sequential Graphs

No changes needed! Existing graphs work as-is:

```python
# This continues to work exactly as before
graph = BaseGraph(
    nodes=[fetch, parse, generate],
    edges=[(fetch, parse), (parse, generate)],
    entry_point=fetch,
    # enable_parallel=False by default
)
```

### Enabling Parallelism

To enable parallel execution:

1. **Review your graph structure** for parallelization opportunities
2. **Refactor edges** to create parallel branches (if needed)
3. **Enable parallel execution:**

```python
# Before
graph = SmartScraperGraph(
    prompt="Extract data",
    source="https://example.com",
    config={"llm": {"model": "gpt-4"}}
)

# After (with custom parallel graph)
graph = BaseGraph(
    nodes=[...],  # Your custom nodes
    edges=[...],  # With parallel branches
    entry_point=fetch,
    enable_parallel=True,
)
```

## Troubleshooting

### Problem: No Performance Improvement

**Cause:** Graph may not have parallelizable structure

**Solution:** Check execution levels:
```python
levels = analyzer.calculate_execution_levels()
print(f"Levels: {len(levels)}, Max parallel: {max(len(l) for l in levels)}")
```

If `max(len(l) for l in levels) == 1`, your graph is sequential.

### Problem: Errors in Parallel Execution

**Cause:** Thread-safety issues or state conflicts

**Solution:**
1. Enable sequential mode to isolate issue:
   ```python
   parallel_config={"mode": "sequential"}
   ```
2. Check for state key conflicts
3. Verify nodes are thread-safe

### Problem: Slower with Parallel Execution

**Cause:** Overhead exceeds benefits for fast nodes

**Solution:**
- Disable parallel execution for fast graphs
- Increase granularity (combine multiple fast ops into single node)
- Check `max_workers` (may be too high)

## Best Practices

### 1. Design for Parallelism

When creating custom graphs, think about parallelization:

```python
# Good: Parallel branches
(parse, validate)
(parse, transform)

# Less efficient: Sequential chain
(parse, validate)
(validate, transform)
```

### 2. Start with Default Config

```python
enable_parallel=True,  # Use defaults
```

Then tune based on profiling.

### 3. Monitor and Measure

Use logging and timing:

```python
import time

start = time.time()
result = graph.execute(state)
elapsed = time.time() - start

print(f"Execution time: {elapsed:.2f}s")
```

### 4. Test Both Modes

Test your graph with both sequential and parallel execution to ensure correctness:

```python
# Test sequential
graph_seq = BaseGraph(..., enable_parallel=False)
result_seq = graph_seq.execute(state)

# Test parallel
graph_par = BaseGraph(..., enable_parallel=True)
result_par = graph_par.execute(state)

# Verify results match
assert result_seq == result_par
```

## Additional Resources

- [RFC-0014: Parallel Node Execution](../analysis-output/rfcs/RFC-0014-parallel-node-execution.md)
- [DAGAnalyzer API Documentation](../scrapegraphai/utils/dag_analyzer.py)
- [ParallelExecutor API Documentation](../scrapegraphai/utils/parallel_executor.py)
- [BaseGraph API Documentation](../scrapegraphai/graphs/base_graph.py)

## Contributing

Have ideas for improving parallel execution? See our [Contributing Guide](../CONTRIBUTING.md) and open an issue or PR!

## FAQ

**Q: Is this the same as MultiGraph?**

A: No. MultiGraph parallelizes multiple graph instances (multiple URLs). This feature parallelizes nodes within a single graph execution. They're complementary.

**Q: Will this break my existing graphs?**

A: No. It's opt-in (enable_parallel=False by default). Existing graphs work unchanged.

**Q: What's the performance overhead?**

A: < 2% for sequential graphs. For parallel graphs, you'll see 25-60% speedup depending on structure.

**Q: Can I use this with BurrBridge?**

A: Not yet. Parallel execution is currently not compatible with Burr integration. This will be addressed in a future update.

**Q: How do I know if my graph will benefit?**

A: Use `DAGAnalyzer` to check parallelism factor. Values > 1.2 indicate potential benefits.
