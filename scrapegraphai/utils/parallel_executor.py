"""
Parallel execution engine for running independent graph nodes concurrently.

This module provides the ParallelExecutor class for executing multiple independent
nodes in parallel using ThreadPoolExecutor or asyncio, with support for error
handling, timeouts, and result aggregation.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ExecutionMode(Enum):
    """Execution mode for parallel execution."""

    THREADS = "threads"  # ThreadPoolExecutor (I/O bound tasks)
    ASYNCIO = "asyncio"  # asyncio (async/await tasks)
    SEQUENTIAL = "sequential"  # Fallback to sequential


@dataclass
class NodeExecutionResult:
    """
    Result of executing a single node.

    Attributes:
        node_name: Name of the node that was executed
        state: The state dict after node execution
        exec_time: Execution time in seconds
        cb_data: Optional callback data (tokens, cost, etc.)
        error: Optional exception if node failed
        success: Whether execution succeeded
    """

    node_name: str
    state: dict
    exec_time: float
    cb_data: Optional[dict] = None
    error: Optional[Exception] = None
    success: bool = True


@dataclass
class ExecutorConfig:
    """
    Configuration for parallel executor.

    Attributes:
        mode: Execution mode (threads, asyncio, or sequential)
        max_workers: Maximum number of parallel workers
        timeout_per_node: Optional timeout in seconds for each node
        fail_fast: If True, stop on first error; if False, continue execution
        max_retries: Number of retries for failed nodes (not yet implemented)
    """

    mode: ExecutionMode = ExecutionMode.THREADS
    max_workers: int = 4
    timeout_per_node: Optional[float] = None
    fail_fast: bool = True
    max_retries: int = 0


class ParallelExecutor:
    """
    Executes multiple independent nodes in parallel.

    Supports both thread-based and async-based execution with error handling,
    timeouts, and result aggregation.

    Args:
        config: Configuration for the executor (optional, uses defaults if not provided)

    Example:
        >>> config = ExecutorConfig(mode=ExecutionMode.THREADS, max_workers=4)
        >>> with ParallelExecutor(config) as executor:
        ...     results = executor.execute_batch(
        ...         nodes=[node1, node2, node3],
        ...         execute_fn=graph._execute_node,
        ...         state=current_state,
        ...         llm_model=llm,
        ...         llm_model_name="gpt-4"
        ...     )
        ...     for result in results:
        ...         if result.success:
        ...             print(f"{result.node_name}: {result.exec_time}s")
    """

    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()
        self._executor = None

    def __enter__(self):
        """Context manager entry - initialize thread pool if needed."""
        if self.config.mode == ExecutionMode.THREADS:
            self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup thread pool."""
        if self._executor:
            self._executor.shutdown(wait=True)

    def execute_batch(
        self,
        nodes: List[Any],
        execute_fn: Callable[[Any, dict, Any, str], Tuple[dict, float, Optional[dict]]],
        state: dict,
        llm_model: Any,
        llm_model_name: str,
    ) -> List[NodeExecutionResult]:
        """
        Execute a batch of independent nodes in parallel.

        Args:
            nodes: List of node instances to execute
            execute_fn: Function to execute each node (e.g., BaseGraph._execute_node)
                       Should have signature: (node, state, llm_model, llm_model_name)
                       Should return: (result_state, exec_time, cb_data)
            state: Current graph state (shared read-only)
            llm_model: LLM model instance
            llm_model_name: LLM model name

        Returns:
            List[NodeExecutionResult]: Results for each node

        Example:
            >>> results = executor.execute_batch(
            ...     nodes=[validate_node, transform_node],
            ...     execute_fn=self._execute_node,
            ...     state=state,
            ...     llm_model=llm_model,
            ...     llm_model_name="gpt-4"
            ... )
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
        llm_model_name: str,
    ) -> List[NodeExecutionResult]:
        """
        Execute nodes using ThreadPoolExecutor.

        This method submits all nodes to a thread pool and collects results
        as they complete, with support for early termination on failure.
        """
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
                llm_model_name,
            )
            futures_to_nodes[future] = node

        # Collect results as they complete
        try:
            for future in as_completed(
                futures_to_nodes, timeout=self.config.timeout_per_node
            ):
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
                        success=False,
                    )
                    results.append(result)

                    if self.config.fail_fast:
                        # Cancel remaining tasks
                        for f in futures_to_nodes:
                            if not f.done():
                                f.cancel()
                        break

        except TimeoutError:
            # Handle overall timeout
            for future in futures_to_nodes:
                if not future.done():
                    future.cancel()
            # Add timeout results for incomplete nodes
            for future, node in futures_to_nodes.items():
                if not future.done() or future.cancelled():
                    results.append(
                        NodeExecutionResult(
                            node_name=node.node_name,
                            state=state,
                            exec_time=0.0,
                            error=TimeoutError(
                                f"Node {node.node_name} exceeded timeout"
                            ),
                            success=False,
                        )
                    )

        return results

    async def _execute_batch_async(
        self,
        nodes: List[Any],
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str,
    ) -> List[NodeExecutionResult]:
        """
        Execute nodes using asyncio.

        This method creates async tasks for all nodes and gathers results,
        with support for early termination on failure.
        """
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
                r
                if isinstance(r, NodeExecutionResult)
                else NodeExecutionResult(
                    node_name="unknown",
                    state=state,
                    exec_time=0.0,
                    error=r if isinstance(r, Exception) else None,
                    success=False,
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
        llm_model_name: str,
    ) -> List[NodeExecutionResult]:
        """
        Fallback: Execute nodes sequentially.

        This is used when parallel execution is not available or as a fallback.
        """
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
        llm_model_name: str,
    ) -> NodeExecutionResult:
        """
        Wrapper to execute a single node and capture result/errors.

        This wrapper ensures that node execution errors are caught and
        returned as NodeExecutionResult objects rather than raising exceptions.

        Note: State mutations need careful handling in parallel execution.
        Each parallel node receives a copy of the input state.
        """
        start_time = time.time()

        try:
            # Make a shallow copy of state for this node to avoid conflicts
            # Each parallel node gets its own state copy
            node_state = state.copy()

            # Execute node
            result_state, exec_time, cb_data = execute_fn(
                node, node_state, llm_model, llm_model_name
            )

            return NodeExecutionResult(
                node_name=node.node_name,
                state=result_state,
                exec_time=exec_time,
                cb_data=cb_data,
                success=True,
            )

        except Exception as e:
            return NodeExecutionResult(
                node_name=node.node_name,
                state=state,
                exec_time=time.time() - start_time,
                error=e,
                success=False,
            )

    async def _execute_node_async(
        self,
        node: Any,
        execute_fn: Callable,
        state: dict,
        llm_model: Any,
        llm_model_name: str,
    ) -> NodeExecutionResult:
        """
        Async wrapper for node execution.

        If execute_fn is not async, run it in executor to avoid blocking
        the event loop.
        """
        # If execute_fn is not async, run it in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._execute_node_wrapper,
            node,
            execute_fn,
            state,
            llm_model,
            llm_model_name,
        )
