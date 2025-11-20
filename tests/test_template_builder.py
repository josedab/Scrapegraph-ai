"""
Unit tests for GraphBuilder
"""

import pytest

from scrapegraphai.graphs.templates.builder import GraphBuilder
from scrapegraphai.graphs.templates.stages import StageDefinition, StageType


class MockNode:
    """Mock node for testing"""

    def __init__(self, name, node_type="standard"):
        self.node_name = name
        self.node_type = node_type

    def __repr__(self):
        return f"MockNode({self.node_name})"


class TestGraphBuilder:
    """Tests for GraphBuilder class"""

    def test_builder_initialization(self):
        """Test builder initializes correctly"""
        config = {"test": "value"}
        builder = GraphBuilder(config)

        assert builder.config == config
        assert builder.stages == []
        assert builder._nodes == []
        assert builder._edges == []

    def test_add_stage_enabled(self):
        """Test adding an enabled stage"""

        def factory(config):
            return [MockNode("test_node")]

        stage = StageDefinition(
            name="test",
            stage_type=StageType.FETCH,
            node_factory=factory,
            required=True,
        )

        builder = GraphBuilder({})
        builder.add_stage(stage)

        assert len(builder.stages) == 1
        assert builder.stages[0] == stage

    def test_add_stage_disabled(self):
        """Test that disabled stages are not added"""

        def factory(config):
            return [MockNode("test_node")]

        stage = StageDefinition(
            name="optional",
            stage_type=StageType.REASONING,
            node_factory=factory,
            enabled_by="reasoning",
        )

        builder = GraphBuilder({"reasoning": False})
        builder.add_stage(stage)

        assert len(builder.stages) == 0

    def test_add_stages_multiple(self):
        """Test adding multiple stages at once"""

        def factory1(config):
            return [MockNode("node1")]

        def factory2(config):
            return [MockNode("node2")]

        stage1 = StageDefinition(
            name="stage1", stage_type=StageType.FETCH, node_factory=factory1, required=True
        )
        stage2 = StageDefinition(
            name="stage2", stage_type=StageType.GENERATE, node_factory=factory2, required=True
        )

        builder = GraphBuilder({})
        builder.add_stages([stage1, stage2])

        assert len(builder.stages) == 2

    def test_skip_if_condition_false(self):
        """Test skip_if adds stage when condition is False"""

        def factory(config):
            return [MockNode("node")]

        stage = StageDefinition(
            name="stage", stage_type=StageType.PARSE, node_factory=factory
        )

        builder = GraphBuilder({"html_mode": False})
        builder.skip_if("html_mode", stage)

        assert len(builder.stages) == 1

    def test_skip_if_condition_true(self):
        """Test skip_if doesn't add stage when condition is True"""

        def factory(config):
            return [MockNode("node")]

        stage = StageDefinition(
            name="stage", stage_type=StageType.PARSE, node_factory=factory
        )

        builder = GraphBuilder({"html_mode": True})
        builder.skip_if("html_mode", stage)

        assert len(builder.stages) == 0

    def test_insert_if_condition_true(self):
        """Test insert_if adds stage when condition is True"""

        def factory(config):
            return [MockNode("node")]

        stage = StageDefinition(
            name="stage", stage_type=StageType.REASONING, node_factory=factory
        )

        builder = GraphBuilder({"reasoning": True})
        builder.insert_if("reasoning", stage)

        assert len(builder.stages) == 1

    def test_insert_if_condition_false(self):
        """Test insert_if doesn't add stage when condition is False"""

        def factory(config):
            return [MockNode("node")]

        stage = StageDefinition(
            name="stage", stage_type=StageType.REASONING, node_factory=factory
        )

        builder = GraphBuilder({"reasoning": False})
        builder.insert_if("reasoning", stage)

        assert len(builder.stages) == 0

    def test_fluent_api_chaining(self):
        """Test that builder methods can be chained"""

        def factory(config):
            return [MockNode("node")]

        stage1 = StageDefinition(
            name="stage1", stage_type=StageType.FETCH, node_factory=factory, required=True
        )
        stage2 = StageDefinition(
            name="stage2", stage_type=StageType.GENERATE, node_factory=factory, required=True
        )

        builder = GraphBuilder({})
        result = builder.add_stage(stage1).add_stage(stage2)

        assert result is builder
        assert len(builder.stages) == 2

    def test_create_nodes_from_stages(self):
        """Test node creation from stages"""

        def factory1(config):
            return [MockNode("node1")]

        def factory2(config):
            return [MockNode("node2"), MockNode("node3")]

        stage1 = StageDefinition(
            name="stage1", stage_type=StageType.FETCH, node_factory=factory1, required=True
        )
        stage2 = StageDefinition(
            name="stage2", stage_type=StageType.GENERATE, node_factory=factory2, required=True
        )

        builder = GraphBuilder({})
        builder.add_stages([stage1, stage2])
        builder._create_nodes_from_stages()

        assert len(builder._nodes) == 3
        assert builder._node_map["stage1"] == [builder._nodes[0]]
        assert builder._node_map["stage2"] == [builder._nodes[1], builder._nodes[2]]

    def test_validate_dependencies_satisfied(self):
        """Test dependency validation with satisfied dependencies"""

        def factory(config):
            return [MockNode("node")]

        stage1 = StageDefinition(
            name="fetch", stage_type=StageType.FETCH, node_factory=factory, required=True
        )
        stage2 = StageDefinition(
            name="parse",
            stage_type=StageType.PARSE,
            node_factory=factory,
            depends_on=["fetch"],
        )

        builder = GraphBuilder({})
        builder.add_stages([stage1, stage2])

        # Should not raise
        builder._validate_dependencies()

    def test_validate_dependencies_unsatisfied_required(self):
        """Test dependency validation fails for unsatisfied required dependency"""

        def factory(config):
            return [MockNode("node")]

        stage = StageDefinition(
            name="parse",
            stage_type=StageType.PARSE,
            node_factory=factory,
            required=True,
            depends_on=["fetch"],
        )

        builder = GraphBuilder({})
        builder.add_stage(stage)

        with pytest.raises(ValueError, match="requires 'fetch'"):
            builder._validate_dependencies()

    def test_build_empty_graph_raises(self):
        """Test building empty graph raises error"""
        builder = GraphBuilder({})

        with pytest.raises(ValueError, match="no stages produced any nodes"):
            builder.build()

    def test_infer_edges_sequential_pipeline(self):
        """Test edge inference for sequential pipeline"""

        def factory(config):
            return [MockNode(config["name"])]

        fetch_stage = StageDefinition(
            name="fetch",
            stage_type=StageType.FETCH,
            node_factory=lambda c: factory({"name": "fetch_node"}),
            required=True,
        )
        parse_stage = StageDefinition(
            name="parse",
            stage_type=StageType.PARSE,
            node_factory=lambda c: factory({"name": "parse_node"}),
            depends_on=["fetch"],
        )
        generate_stage = StageDefinition(
            name="generate",
            stage_type=StageType.GENERATE,
            node_factory=lambda c: factory({"name": "generate_node"}),
            required=True,
            depends_on=["fetch"],
        )

        builder = GraphBuilder({})
        builder.add_stages([fetch_stage, parse_stage, generate_stage])
        builder._create_nodes_from_stages()
        edges = builder._infer_edges()

        # Should have edges: fetch -> parse -> generate
        assert len(edges) >= 2
        edge_names = [(e[0].node_name, e[1].node_name) for e in edges if e[1] is not None]
        assert ("fetch_node", "parse_node") in edge_names
        assert ("parse_node", "generate_node") in edge_names


class TestGraphBuilderIntegration:
    """Integration tests for GraphBuilder with realistic scenarios"""

    def test_basic_pipeline(self):
        """Test building a basic fetch -> parse -> generate pipeline"""

        def fetch_factory(config):
            return [MockNode("fetch")]

        def parse_factory(config):
            return [MockNode("parse")]

        def generate_factory(config):
            return [MockNode("generate")]

        fetch_stage = StageDefinition(
            name="fetch", stage_type=StageType.FETCH, node_factory=fetch_factory, required=True
        )
        parse_stage = StageDefinition(
            name="parse",
            stage_type=StageType.PARSE,
            node_factory=parse_factory,
            depends_on=["fetch"],
        )
        generate_stage = StageDefinition(
            name="generate",
            stage_type=StageType.GENERATE,
            node_factory=generate_factory,
            required=True,
            depends_on=["fetch"],
        )

        builder = GraphBuilder({})
        graph = builder.add_stages([fetch_stage, parse_stage, generate_stage]).build()

        assert graph is not None
        assert len(graph.nodes) == 3
        assert graph.entry_point == "fetch"

    def test_html_mode_pipeline(self):
        """Test building pipeline with html_mode (skip parse)"""

        def fetch_factory(config):
            return [MockNode("fetch")]

        def parse_factory(config):
            return [MockNode("parse")]

        def generate_factory(config):
            return [MockNode("generate")]

        fetch_stage = StageDefinition(
            name="fetch", stage_type=StageType.FETCH, node_factory=fetch_factory, required=True
        )
        parse_stage = StageDefinition(
            name="parse",
            stage_type=StageType.PARSE,
            node_factory=parse_factory,
            skip_if="html_mode",
            depends_on=["fetch"],
        )
        generate_stage = StageDefinition(
            name="generate",
            stage_type=StageType.GENERATE,
            node_factory=generate_factory,
            required=True,
            depends_on=["fetch"],
        )

        builder = GraphBuilder({"html_mode": True})
        graph = builder.add_stages([fetch_stage, parse_stage, generate_stage]).build()

        assert graph is not None
        assert len(graph.nodes) == 2  # fetch and generate only
        node_names = [n.node_name for n in graph.nodes]
        assert "parse" not in node_names
