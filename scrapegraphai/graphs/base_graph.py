"""
base_graph module
"""

import time
import warnings
from typing import Tuple

from ..telemetry import log_graph_execution
from ..utils import CustomLLMCallbackManager
from ..utils.logging import get_logger

logger = get_logger(__name__)

# ANSI escape sequence for hyperlink
CLICKABLE_URL = "\033]8;;https://scrapegraphai.com\033\\https://scrapegraphai.com\033]8;;\033\\"

class BaseGraph:
    """
    BaseGraph manages the execution flow of a graph composed of interconnected nodes.

    Attributes:
        nodes (list): A dictionary mapping each node's name to its corresponding node instance.
        edges (list): A dictionary representing the directed edges of the graph where each
                      key-value pair corresponds to the from-node and to-node relationship.
        entry_point (str): The name of the entry point node from which the graph execution begins.

    Args:
        nodes (iterable): An iterable of node instances that will be part of the graph.
        edges (iterable): An iterable of tuples where each tuple represents a directed edge
                          in the graph, defined by a pair of nodes (from_node, to_node).
        entry_point (BaseNode): The node instance that represents the entry point of the graph.

    Raises:
        Warning: If the entry point node is not the first node in the list.

    Example:
        >>> BaseGraph(
        ...    nodes=[
        ...        fetch_node,
        ...        parse_node,
        ...        rag_node,
        ...        generate_answer_node,
        ...    ],
        ...    edges=[
        ...        (fetch_node, parse_node),
        ...        (parse_node, rag_node),
        ...        (rag_node, generate_answer_node)
        ...    ],
        ...    entry_point=fetch_node,
        ...    use_burr=True,
        ...    burr_config={"app_instance_id": "example-instance"}
        ... )
    """

    def __init__(
        self,
        nodes: list,
        edges: list,
        entry_point: str,
        use_burr: bool = False,
        burr_config: dict = None,
        graph_name: str = "Custom",
        enable_parallel: bool = False,
        parallel_config: dict = None,
    ):
        self.nodes = nodes
        self.raw_edges = edges
        self.edges = self._create_edges(set(edges))
        self.entry_point = entry_point.node_name
        self.graph_name = graph_name
        self.initial_state = {}
        self.callback_manager = CustomLLMCallbackManager()

        if nodes[0].node_name != entry_point.node_name:
            warnings.warn(
                "Careful! The entry point node is different from the first node in the graph."
            )

        self._set_conditional_node_edges()

        self.use_burr = use_burr
        self.burr_config = burr_config or {}

        # NEW: Enhanced DAG representation for parallel execution
        self.adjacency_list = self._create_adjacency_list(edges)
        self.reverse_adjacency_list = self._create_reverse_adjacency_list(edges)

        # NEW: Parallel execution configuration
        self.enable_parallel = enable_parallel
        self.parallel_config = parallel_config or {}

        # Initialize DAG analyzer if parallel execution enabled
        if self.enable_parallel:
            from ..utils.dag_analyzer import DAGAnalyzer

            self.dag_analyzer = DAGAnalyzer(
                self.adjacency_list, self.reverse_adjacency_list
            )

            # Validate graph (detect cycles)
            has_cycle, cycle = self.dag_analyzer.detect_cycles()
            if has_cycle:
                raise ValueError(
                    f"Cannot enable parallel execution: graph contains cycle: "
                    f"{' → '.join(cycle)}"
                )

    def _create_edges(self, edges: list) -> dict:
        """
        Helper method to create a dictionary of edges from the given iterable of tuples.

        Args:
            edges (iterable): An iterable of tuples representing the directed edges.

        Returns:
            dict: A dictionary of edges with the from-node as keys and to-node as values.
        """

        edge_dict = {}
        for from_node, to_node in edges:
            if from_node.node_type != "conditional_node":
                edge_dict[from_node.node_name] = to_node.node_name
        return edge_dict

    def _create_adjacency_list(self, edges: list) -> dict:
        """
        Create adjacency list representation for DAG analysis.

        This method creates a complete adjacency list that can represent
        multiple successors per node, enabling proper DAG analysis for
        parallel execution.

        Args:
            edges: List of edge tuples (from_node, to_node)

        Returns:
            dict: {node_name: [successor1, successor2, ...]}
        """
        adj_list = {node.node_name: [] for node in self.nodes}

        for from_node, to_node in edges:
            if to_node is not None:  # Handle terminal nodes
                if to_node.node_name not in adj_list[from_node.node_name]:
                    adj_list[from_node.node_name].append(to_node.node_name)

        return adj_list

    def _create_reverse_adjacency_list(self, edges: list) -> dict:
        """
        Create reverse adjacency list for dependency tracking.

        This method creates a reverse mapping showing which nodes depend
        on each node, used for determining when nodes are ready to execute.

        Args:
            edges: List of edge tuples (from_node, to_node)

        Returns:
            dict: {node_name: [predecessor1, predecessor2, ...]}
        """
        rev_adj_list = {node.node_name: [] for node in self.nodes}

        for from_node, to_node in edges:
            if to_node is not None:
                if from_node.node_name not in rev_adj_list[to_node.node_name]:
                    rev_adj_list[to_node.node_name].append(from_node.node_name)

        return rev_adj_list

    def _set_conditional_node_edges(self):
        """
        Sets the true_node_name and false_node_name for each ConditionalNode.
        """
        for node in self.nodes:
            if node.node_type == "conditional_node":
                outgoing_edges = [
                    (from_node, to_node)
                    for from_node, to_node in self.raw_edges
                    if from_node.node_name == node.node_name
                ]
                if len(outgoing_edges) != 2:
                    raise ValueError(
                        f"ConditionalNode '{node.node_name}' must have exactly two outgoing edges."
                    )
                node.true_node_name = outgoing_edges[0][1].node_name
                try:
                    node.false_node_name = outgoing_edges[1][1].node_name
                except (IndexError, AttributeError) as e:
                    # IndexError: If outgoing_edges[1] doesn't exist
                    # AttributeError: If to_node is None or doesn't have node_name
                    node.false_node_name = None
                    raise ValueError(
                        f"Failed to set false_node_name for ConditionalNode '{node.node_name}'"
                    ) from e

    def _get_node_by_name(self, node_name: str):
        """Returns a node instance by its name."""
        return next(node for node in self.nodes if node.node_name == node_name)

    def _update_source_info(self, current_node, state):
        """Updates source type and source information from FetchNode."""
        source_type = None
        source = []
        prompt = None

        if current_node.__class__.__name__ == "FetchNode":
            source_type = list(state.keys())[1]
            if state.get("user_prompt", None):
                prompt = (
                    state["user_prompt"]
                    if isinstance(state["user_prompt"], str)
                    else None
                )

            if source_type == "local_dir":
                source_type = "html_dir"
            elif source_type == "url":
                if isinstance(state[source_type], list):
                    source.extend(
                        url for url in state[source_type] if isinstance(url, str)
                    )
                elif isinstance(state[source_type], str):
                    source.append(state[source_type])

        return source_type, source, prompt

    def _get_model_info(self, current_node):
        """Extracts LLM and embedder model information from the node."""
        llm_model = None
        llm_model_name = None
        embedder_model = None

        if hasattr(current_node, "llm_model"):
            llm_model = current_node.llm_model
            if hasattr(llm_model, "model_name"):
                llm_model_name = llm_model.model_name
            elif hasattr(llm_model, "model"):
                llm_model_name = llm_model.model
            elif hasattr(llm_model, "model_id"):
                llm_model_name = llm_model.model_id

        if hasattr(current_node, "embedder_model"):
            embedder_model = current_node.embedder_model
            if hasattr(embedder_model, "model_name"):
                embedder_model = embedder_model.model_name
            elif hasattr(embedder_model, "model"):
                embedder_model = embedder_model.model

        return llm_model, llm_model_name, embedder_model

    def _get_schema(self, current_node):
        """Extracts schema information from the node configuration."""
        if not hasattr(current_node, "node_config"):
            return None

        if not isinstance(current_node.node_config, dict):
            return None

        schema_config = current_node.node_config.get("schema")
        if not schema_config or isinstance(schema_config, dict):
            return None

        try:
            return schema_config.schema()
        except Exception:
            return None

    def _execute_node(self, current_node, state, llm_model, llm_model_name):
        """Executes a single node and returns execution information."""
        curr_time = time.time()

        with self.callback_manager.exclusive_get_callback(
            llm_model, llm_model_name
        ) as cb:
            result = current_node.execute(state)
            node_exec_time = time.time() - curr_time

            cb_data = None
            if cb is not None:
                cb_data = {
                    "node_name": current_node.node_name,
                    "total_tokens": cb.total_tokens,
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "successful_requests": cb.successful_requests,
                    "total_cost_USD": cb.total_cost,
                    "exec_time": node_exec_time,
                }

        return result, node_exec_time, cb_data

    def _get_next_node(self, current_node, result):
        """Determines the next node to execute based on current node type and result."""
        if current_node.node_type == "conditional_node":
            node_names = {node.node_name for node in self.nodes}
            if result in node_names:
                return result
            elif result is None:
                return None
            raise ValueError(
                f"Conditional Node returned a node name '{result}' that does not exist in the graph"
            )

        return self.edges.get(current_node.node_name)

    def _execute_standard(self, initial_state: dict) -> Tuple[dict, list]:
        """
        Executes the graph by traversing nodes
        starting from the entry point using the standard method.
        """
        current_node_name = self.entry_point
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

        start_time = time.time()
        error_node = None
        source_type = None
        llm_model = None
        llm_model_name = None
        embedder_model = None
        source = []
        prompt = None
        schema = None

        while current_node_name:
            current_node = self._get_node_by_name(current_node_name)

            if source_type is None:
                source_type, source, prompt = self._update_source_info(
                    current_node, state
                )

            if llm_model is None:
                llm_model, llm_model_name, embedder_model = self._get_model_info(
                    current_node
                )

            if schema is None:
                schema = self._get_schema(current_node)

            try:
                result, node_exec_time, cb_data = self._execute_node(
                    current_node, state, llm_model, llm_model_name
                )
                total_exec_time += node_exec_time

                if cb_data:
                    exec_info.append(cb_data)
                    for key in cb_total:
                        cb_total[key] += cb_data[key]

                current_node_name = self._get_next_node(current_node, result)

            except Exception as e:
                error_node = current_node.node_name
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

        exec_info.append(
            {
                "node_name": "TOTAL RESULT",
                "total_tokens": cb_total["total_tokens"],
                "prompt_tokens": cb_total["prompt_tokens"],
                "completion_tokens": cb_total["completion_tokens"],
                "successful_requests": cb_total["successful_requests"],
                "total_cost_USD": cb_total["total_cost_USD"],
                "exec_time": total_exec_time,
            }
        )

        graph_execution_time = time.time() - start_time
        response = state.get("answer", None) if source_type == "url" else None
        content = state.get("parsed_doc", None) if response is not None else None

        log_graph_execution(
            graph_name=self.graph_name,
            source=source,
            prompt=prompt,
            schema=schema,
            llm_model=llm_model_name,
            embedder_model=embedder_model,
            source_type=source_type,
            content=content,
            response=response,
            execution_time=graph_execution_time,
            total_tokens=(
                cb_total["total_tokens"] if cb_total["total_tokens"] > 0 else None
            ),
        )

        return state, exec_info

    def _execute_parallel(self, initial_state: dict) -> Tuple[dict, list]:
        """
        Execute graph with parallel execution of independent nodes.

        Algorithm:
        1. Calculate execution levels using DAG analysis
        2. For each level, execute all nodes in parallel
        3. Wait for level completion before proceeding
        4. Aggregate results and update state

        Args:
            initial_state (dict): The initial state to pass to the entry point node.

        Returns:
            Tuple[dict, list]: A tuple containing the final state and a list of execution info.
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

        logger.info(f"Executing graph '{self.graph_name}' with {len(execution_levels)} parallel levels")

        # Create parallel executor
        mode_str = self.parallel_config.get("mode", "threads")
        try:
            mode = ExecutionMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid execution mode '{mode_str}', falling back to threads")
            mode = ExecutionMode.THREADS

        executor_config = ExecutorConfig(
            mode=mode,
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
                    logger.info(f"Executing level {level_idx}: {level_nodes} ({len(level_nodes)} nodes)")

                    # Get node instances
                    nodes_to_execute = [
                        self._get_node_by_name(node_name) for node_name in level_nodes
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
                        llm_model_name,
                    )
                    level_time = time.time() - level_start

                    logger.info(
                        f"Level {level_idx} completed in {level_time:.2f}s "
                        f"({len(results)} nodes executed)"
                    )

                    # Process results
                    for result in results:
                        if not result.success:
                            error_node = result.node_name
                            error_msg = str(result.error) if result.error else "Unknown error"
                            logger.error(f"Node {error_node} failed: {error_msg}")
                            raise result.error

                        # Update state with node results
                        # Merge the node's state updates into the main state
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

        # Add total result summary
        exec_info.append(
            {
                "node_name": "TOTAL RESULT",
                "total_tokens": cb_total["total_tokens"],
                "prompt_tokens": cb_total["prompt_tokens"],
                "completion_tokens": cb_total["completion_tokens"],
                "successful_requests": cb_total["successful_requests"],
                "total_cost_USD": cb_total["total_cost_USD"],
                "exec_time": total_exec_time,
            }
        )

        # Success logging
        graph_execution_time = time.time() - start_time
        response = state.get("answer", None) if source_type == "url" else None
        content = state.get("parsed_doc", None) if response is not None else None

        log_graph_execution(
            graph_name=self.graph_name,
            source=source,
            prompt=prompt,
            schema=schema,
            llm_model=llm_model_name,
            embedder_model=embedder_model,
            source_type=source_type,
            content=content,
            response=response,
            execution_time=graph_execution_time,
            total_tokens=(
                cb_total["total_tokens"] if cb_total["total_tokens"] > 0 else None
            ),
        )

        logger.info(
            f"Graph '{self.graph_name}' completed in {graph_execution_time:.2f}s "
            f"(parallel execution with {len(execution_levels)} levels)"
        )

        return state, exec_info

    def execute(self, initial_state: dict) -> Tuple[dict, list]:
        """
        Executes the graph by either using BurrBridge, parallel execution, or the standard method.

        Args:
            initial_state (dict): The initial state to pass to the entry point node.

        Returns:
            Tuple[dict, list]: A tuple containing the final state and a list of execution info.
        """

        self.initial_state = initial_state
        if self.use_burr:
            from ..integrations import BurrBridge

            bridge = BurrBridge(self, self.burr_config)
            result = bridge.execute(initial_state)
            state, exec_info = (result["_state"], [])
        elif self.enable_parallel:
            state, exec_info = self._execute_parallel(initial_state)
        else:
            state, exec_info = self._execute_standard(initial_state)

        # Print the result first
        if "answer" in state:
            print(state["answer"])
        elif "parsed_doc" in state:
            print(state["parsed_doc"])
        elif "generated_code" in state:
            print(state["generated_code"])
        elif "merged_script" in state:
            print(state["merged_script"])

        # Then show the message ONLY ONCE
        print(f"✨ Try enhanced version of ScrapegraphAI at {CLICKABLE_URL} ✨")

        return state, exec_info

    def append_node(self, node):
        """
        Adds a node to the graph.

        Args:
            node (BaseNode): The node instance to add to the graph.
        """

        # if node name already exists in the graph, raise an exception
        if node.node_name in {n.node_name for n in self.nodes}:
            raise ValueError(
                f"""Node with name '{node.node_name}' already exists in the graph.
                             You can change it by setting the 'node_name' attribute."""
            )

        last_node = self.nodes[-1]
        self.raw_edges.append((last_node, node))
        self.nodes.append(node)
        self.edges = self._create_edges(set(self.raw_edges))
