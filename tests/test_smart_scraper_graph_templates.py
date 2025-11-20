"""
Integration tests for SmartScraperGraph with template system

These tests verify that the template-based implementation produces
correct graph structures for all 8 combinations of configuration flags.
"""

import pytest


class TestSmartScraperGraphTemplateIntegration:
    """Integration tests for SmartScraperGraph using templates"""

    def test_basic_configuration(self):
        """Test basic configuration: fetch -> parse -> generate"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,  # Mock model
            "html_mode": False,
            "reasoning": False,
            "reattempt": False,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        assert graph is not None
        assert len(graph.nodes) == 3  # fetch, parse, generate
        assert graph.entry_point == "FetchNode"

        # Verify node types
        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" in node_names
        assert "GenerateAnswerNode" in node_names

    def test_html_mode_configuration(self):
        """Test html_mode=True: fetch -> generate (skip parse)"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": True,
            "reasoning": False,
            "reattempt": False,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        assert len(graph.nodes) == 2  # fetch, generate (no parse)

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" not in node_names  # Should be skipped
        assert "GenerateAnswerNode" in node_names

    def test_reasoning_configuration(self):
        """Test reasoning=True: fetch -> parse -> reasoning -> generate"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": False,
            "reasoning": True,
            "reattempt": False,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        assert len(graph.nodes) == 4  # fetch, parse, reasoning, generate

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" in node_names
        assert "ReasoningNode" in node_names
        assert "GenerateAnswerNode" in node_names

    def test_reasoning_html_mode_configuration(self):
        """Test reasoning=True, html_mode=True: fetch -> reasoning -> generate"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": True,
            "reasoning": True,
            "reattempt": False,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        assert len(graph.nodes) == 3  # fetch, reasoning, generate (no parse)

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" not in node_names  # Should be skipped
        assert "ReasoningNode" in node_names
        assert "GenerateAnswerNode" in node_names

    def test_reattempt_configuration(self):
        """Test reattempt=True: fetch -> parse -> generate -> conditional -> regen"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": False,
            "reasoning": False,
            "reattempt": True,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        # 3 base + 2 reattempt (conditional + regen) = 5 nodes
        assert len(graph.nodes) == 5

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" in node_names
        assert "GenerateAnswerNode" in node_names
        assert "ConditionalNode" in node_names
        # Second GenerateAnswerNode for regeneration
        assert node_names.count("GenerateAnswerNode") == 2

    def test_reasoning_reattempt_configuration(self):
        """Test reasoning=True, reattempt=True: full pipeline"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": False,
            "reasoning": True,
            "reattempt": True,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        # All stages enabled: fetch, parse, reasoning, generate, conditional, regen = 6 nodes
        assert len(graph.nodes) == 6

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" in node_names
        assert "ReasoningNode" in node_names
        assert "GenerateAnswerNode" in node_names
        assert "ConditionalNode" in node_names

    def test_html_mode_reattempt_configuration(self):
        """Test html_mode=True, reattempt=True"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": True,
            "reasoning": False,
            "reattempt": True,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        # fetch, generate, conditional, regen = 4 nodes (no parse)
        assert len(graph.nodes) == 4

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" not in node_names
        assert "GenerateAnswerNode" in node_names
        assert "ConditionalNode" in node_names

    def test_all_features_enabled(self):
        """Test all features enabled: html_mode=True, reasoning=True, reattempt=True"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": True,
            "reasoning": True,
            "reattempt": True,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify graph structure
        # fetch, reasoning, generate, conditional, regen = 5 nodes (no parse)
        assert len(graph.nodes) == 5

        node_names = [node.node_name for node in graph.nodes]
        assert "FetchNode" in node_names
        assert "ParseNode" not in node_names
        assert "ReasoningNode" in node_names
        assert "GenerateAnswerNode" in node_names
        assert "ConditionalNode" in node_names

    def test_edge_count_basic(self):
        """Test that basic configuration has correct number of edges"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": False,
            "reasoning": False,
            "reattempt": False,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Basic pipeline should have 2 edges: fetch->parse, parse->generate
        assert len(graph.raw_edges) == 2

    def test_edge_count_reattempt(self):
        """Test that reattempt configuration has correct number of edges"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        config = {
            "llm_model": None,
            "html_mode": False,
            "reasoning": False,
            "reattempt": True,
            "model_token": 1000,
            "schema": None,
        }

        graph = SmartScraperPipeline.build(config)

        # Should have: fetch->parse, parse->generate, generate->cond, cond->regen, cond->None
        assert len(graph.raw_edges) == 5


class TestSmartScraperGraphConfiguration:
    """Tests for configuration value correctness"""

    def test_node_config_propagation(self):
        """Test that configuration values are correctly propagated to nodes"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        test_config = {
            "llm_model": "test-model",
            "model_token": 2000,
            "force": True,
            "cut": False,
            "html_mode": False,
            "reasoning": False,
            "reattempt": False,
        }

        graph = SmartScraperPipeline.build(test_config)

        # Verify that nodes received correct configuration
        fetch_node = next(n for n in graph.nodes if n.node_name == "FetchNode")
        assert fetch_node.node_config["force"] is True
        assert fetch_node.node_config["cut"] is False

        parse_node = next(n for n in graph.nodes if n.node_name == "ParseNode")
        assert parse_node.node_config["chunk_size"] == 2000

    def test_schema_propagation(self):
        """Test that schema is correctly propagated to generate node"""
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            field1: str

        config = {
            "llm_model": None,
            "html_mode": False,
            "reasoning": False,
            "reattempt": False,
            "model_token": 1000,
            "schema": TestSchema,
        }

        graph = SmartScraperPipeline.build(config)

        # Verify schema is in generate node
        generate_node = next(n for n in graph.nodes if n.node_name == "GenerateAnswerNode")
        assert generate_node.node_config["schema"] == TestSchema


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing API"""

    def test_all_eight_variations(self):
        """
        Test all 8 combinations of flags to ensure they produce valid graphs.
        This mimics the 8 variations from the original hardcoded implementation.
        """
        from scrapegraphai.graphs.templates.pipelines import SmartScraperPipeline

        test_cases = [
            (False, False, False, 3),  # Base: fetch, parse, generate
            (True, False, False, 2),  # HTML mode: fetch, generate
            (False, True, False, 4),  # Reasoning: fetch, parse, reasoning, generate
            (True, True, False, 3),  # HTML + reasoning: fetch, reasoning, generate
            (False, False, True, 5),  # Reattempt: base + conditional + regen
            (True, False, True, 4),  # HTML + reattempt
            (False, True, True, 6),  # Reasoning + reattempt: all nodes
            (True, True, True, 5),  # All features except parse
        ]

        for html_mode, reasoning, reattempt, expected_nodes in test_cases:
            config = {
                "llm_model": None,
                "html_mode": html_mode,
                "reasoning": reasoning,
                "reattempt": reattempt,
                "model_token": 1000,
                "schema": None,
            }

            graph = SmartScraperPipeline.build(config)

            assert graph is not None, f"Failed for config: {config}"
            assert (
                len(graph.nodes) == expected_nodes
            ), f"Expected {expected_nodes} nodes for {config}, got {len(graph.nodes)}"
