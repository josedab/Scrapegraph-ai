"""
GraphBuilder - Fluent API for building graphs from stages

Provides a fluent interface for composing graphs from stage definitions,
automatically inferring edges and validating dependencies.
"""

from typing import Any, Dict, List, Optional, Tuple

from .stages import StageDefinition, StageType


class GraphBuilder:
    """
    Fluent API for building graphs from stages.

    The builder handles:
    - Stage inclusion based on configuration
    - Automatic edge inference based on stage dependencies
    - Dependency validation
    - Special handling for conditional nodes (reattempt stage)

    Example:
        builder = GraphBuilder(config)
        graph = (builder
            .add_stage(fetch_stage)
            .add_stage(parse_stage)
            .add_stage(generate_stage)
            .build())
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the builder with configuration.

        Args:
            config: Configuration dictionary for node creation and stage enabling
        """
        self.config = config
        self.stages: List[StageDefinition] = []
        self._nodes: List[Any] = []
        self._edges: List[Tuple] = []
        self._node_map: Dict[str, List[Any]] = {}

    def add_stage(self, stage: StageDefinition) -> "GraphBuilder":
        """
        Add a stage to the pipeline if it's enabled by configuration.

        Args:
            stage: Stage definition to add

        Returns:
            Self for method chaining
        """
        if stage.is_enabled(self.config):
            self.stages.append(stage)
        return self

    def add_stages(self, stages: List[StageDefinition]) -> "GraphBuilder":
        """
        Add multiple stages at once.

        Args:
            stages: List of stage definitions to add

        Returns:
            Self for method chaining
        """
        for stage in stages:
            self.add_stage(stage)
        return self

    def skip_if(self, condition: str, stage: StageDefinition) -> "GraphBuilder":
        """
        Conditionally skip a stage based on config.

        Args:
            condition: Config key to check
            stage: Stage to add if condition is False

        Returns:
            Self for method chaining
        """
        if not self.config.get(condition, False):
            self.add_stage(stage)
        return self

    def insert_if(self, condition: str, stage: StageDefinition) -> "GraphBuilder":
        """
        Conditionally insert a stage based on config.

        Args:
            condition: Config key to check
            stage: Stage to add if condition is True

        Returns:
            Self for method chaining
        """
        if self.config.get(condition, False):
            self.add_stage(stage)
        return self

    def _create_nodes_from_stages(self) -> None:
        """
        Create nodes from all stages and build the node map.

        Populates self._nodes and self._node_map.
        """
        self._nodes = []
        self._node_map = {}

        for stage in self.stages:
            nodes = stage.create_nodes(self.config)
            self._node_map[stage.name] = nodes
            self._nodes.extend(nodes)

    def _infer_edges(self) -> List[Tuple]:
        """
        Automatically infer edges between nodes based on stage dependencies.

        Edge inference logic:
        1. For most stages: connect last node of each dependency to first node of current stage
        2. For reasoning stage: insert after parse (if exists) or fetch, before generate
        3. For reattempt stage: add conditional edges after generate

        Returns:
            List of edge tuples (from_node, to_node)
        """
        edges = []

        # Build a mapping of stage names to their positions
        stage_names = {stage.name: idx for idx, stage in enumerate(self.stages)}

        # Track which stages have been connected
        connected_stages = set()

        # First, handle the main pipeline flow (excluding reattempt and reasoning)
        pipeline_stages = [
            s for s in self.stages if s.stage_type not in (StageType.REATTEMPT, StageType.REASONING)
        ]

        # Connect pipeline stages sequentially
        for i in range(len(pipeline_stages) - 1):
            current_stage = pipeline_stages[i]
            next_stage = pipeline_stages[i + 1]

            current_nodes = self._node_map[current_stage.name]
            next_nodes = self._node_map[next_stage.name]

            if current_nodes and next_nodes:
                # Connect last node of current to first node of next
                edges.append((current_nodes[-1], next_nodes[0]))
                connected_stages.add(current_stage.name)
                connected_stages.add(next_stage.name)

        # Handle reasoning stage - insert between parse/fetch and generate
        reasoning_stage = next(
            (s for s in self.stages if s.stage_type == StageType.REASONING), None
        )
        if reasoning_stage:
            reasoning_nodes = self._node_map["reasoning"]

            # Find the stage before reasoning (parse or fetch)
            before_stage = None
            if "parse" in self._node_map:
                before_stage = "parse"
            elif "fetch" in self._node_map:
                before_stage = "fetch"

            # Find generate stage
            generate_stage = "generate" if "generate" in self._node_map else None

            if before_stage and generate_stage:
                before_nodes = self._node_map[before_stage]
                generate_nodes = self._node_map[generate_stage]

                # Remove direct edge from before_stage to generate if it exists
                edges = [
                    e
                    for e in edges
                    if not (e[0] in before_nodes and e[1] in generate_nodes)
                ]

                # Add edges: before -> reasoning -> generate
                edges.append((before_nodes[-1], reasoning_nodes[0]))
                edges.append((reasoning_nodes[-1], generate_nodes[0]))

        # Handle reattempt stage - creates conditional loop after generate
        reattempt_stage = next(
            (s for s in self.stages if s.stage_type == StageType.REATTEMPT), None
        )
        if reattempt_stage:
            reattempt_nodes = self._node_map["reattempt"]
            if len(reattempt_nodes) >= 2:
                cond_node, regen_node = reattempt_nodes[0], reattempt_nodes[1]

                # Find generate stage
                if "generate" in self._node_map:
                    generate_nodes = self._node_map["generate"]

                    # Add edges: generate -> conditional -> regen
                    # Also add conditional -> None for success path
                    edges.append((generate_nodes[-1], cond_node))
                    edges.append((cond_node, regen_node))
                    edges.append((cond_node, None))

        return edges

    def _validate_dependencies(self) -> None:
        """
        Ensure all stage dependencies are satisfied.

        Raises:
            ValueError: If a required stage's dependency is not satisfied
        """
        stage_names = {stage.name for stage in self.stages}

        for stage in self.stages:
            for dep in stage.depends_on:
                if dep not in stage_names:
                    # Dependency might be optional (skipped via config)
                    if stage.required:
                        all_stages = [s.name for s in self.stages]
                        raise ValueError(
                            f"Stage '{stage.name}' requires '{dep}' "
                            f"but it's not in pipeline: {all_stages}"
                        )

    def build(self) -> "BaseGraph":
        """
        Build the final graph.

        Steps:
        1. Validate dependencies
        2. Create nodes from stages
        3. Infer edges based on stage dependencies
        4. Build and return BaseGraph

        Returns:
            BaseGraph instance

        Raises:
            ValueError: If dependencies are not satisfied
        """
        from ..base_graph import BaseGraph

        # Validate dependencies
        self._validate_dependencies()

        # Create nodes from stages
        self._create_nodes_from_stages()

        # Infer edges
        self._edges = self._infer_edges()

        # Determine entry point (first node of first stage)
        entry_point = self._nodes[0] if self._nodes else None

        if not entry_point:
            raise ValueError("Cannot build graph: no stages produced any nodes")

        return BaseGraph(
            nodes=self._nodes,
            edges=self._edges,
            entry_point=entry_point,
            graph_name="ComposedGraph",
        )
