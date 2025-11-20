"""
Unit tests for template stage definitions
"""

import pytest

from scrapegraphai.graphs.templates.stages import (
    StageDefinition,
    StageType,
    create_fetch_stage,
    create_generate_stage,
    create_parse_stage,
    create_reattempt_stage,
    create_reasoning_stage,
)


class TestStageDefinition:
    """Tests for StageDefinition class"""

    def test_stage_definition_creation(self):
        """Test creating a basic stage definition"""

        def dummy_factory(config):
            return ["node1", "node2"]

        stage = StageDefinition(
            name="test_stage",
            stage_type=StageType.FETCH,
            node_factory=dummy_factory,
            required=True,
        )

        assert stage.name == "test_stage"
        assert stage.stage_type == StageType.FETCH
        assert stage.required is True
        assert stage.enabled_by is None
        assert stage.skip_if is None
        assert stage.depends_on == []

    def test_is_enabled_required_stage(self):
        """Test that required stages are always enabled"""

        def dummy_factory(config):
            return []

        stage = StageDefinition(
            name="required_stage",
            stage_type=StageType.FETCH,
            node_factory=dummy_factory,
            required=True,
        )

        assert stage.is_enabled({}) is True
        assert stage.is_enabled({"some_flag": False}) is True

    def test_is_enabled_with_enabled_by(self):
        """Test stage enabled by config flag"""

        def dummy_factory(config):
            return []

        stage = StageDefinition(
            name="optional_stage",
            stage_type=StageType.REASONING,
            node_factory=dummy_factory,
            enabled_by="reasoning",
        )

        assert stage.is_enabled({"reasoning": True}) is True
        assert stage.is_enabled({"reasoning": False}) is False
        assert stage.is_enabled({}) is False

    def test_is_enabled_with_skip_if(self):
        """Test stage skipped by config flag"""

        def dummy_factory(config):
            return []

        stage = StageDefinition(
            name="parse_stage",
            stage_type=StageType.PARSE,
            node_factory=dummy_factory,
            skip_if="html_mode",
        )

        assert stage.is_enabled({"html_mode": True}) is False
        assert stage.is_enabled({"html_mode": False}) is True
        assert stage.is_enabled({}) is True

    def test_create_nodes(self):
        """Test creating nodes from factory"""

        def factory(config):
            model = config.get("llm_model", "default")
            return [f"node_{model}"]

        stage = StageDefinition(
            name="test_stage",
            stage_type=StageType.GENERATE,
            node_factory=factory,
        )

        nodes = stage.create_nodes({"llm_model": "gpt-4"})
        assert nodes == ["node_gpt-4"]

        nodes = stage.create_nodes({})
        assert nodes == ["node_default"]


class TestStandardStages:
    """Tests for standard stage factory functions"""

    def test_create_fetch_stage(self):
        """Test fetch stage creation"""
        stage = create_fetch_stage()

        assert stage.name == "fetch"
        assert stage.stage_type == StageType.FETCH
        assert stage.required is True
        assert stage.is_enabled({}) is True

    def test_create_parse_stage(self):
        """Test parse stage creation"""
        stage = create_parse_stage()

        assert stage.name == "parse"
        assert stage.stage_type == StageType.PARSE
        assert stage.skip_if == "html_mode"
        assert stage.depends_on == ["fetch"]

        # Parse should be enabled by default
        assert stage.is_enabled({}) is True
        # Parse should be skipped when html_mode=True
        assert stage.is_enabled({"html_mode": True}) is False
        # Parse should be enabled when html_mode=False
        assert stage.is_enabled({"html_mode": False}) is True

    def test_create_reasoning_stage(self):
        """Test reasoning stage creation"""
        stage = create_reasoning_stage()

        assert stage.name == "reasoning"
        assert stage.stage_type == StageType.REASONING
        assert stage.enabled_by == "reasoning"
        assert stage.depends_on == ["fetch"]

        # Reasoning should be disabled by default
        assert stage.is_enabled({}) is False
        # Reasoning should be enabled when reasoning=True
        assert stage.is_enabled({"reasoning": True}) is True

    def test_create_generate_stage(self):
        """Test generate stage creation"""
        stage = create_generate_stage()

        assert stage.name == "generate"
        assert stage.stage_type == StageType.GENERATE
        assert stage.required is True
        assert stage.depends_on == ["fetch"]

    def test_create_reattempt_stage(self):
        """Test reattempt stage creation"""
        stage = create_reattempt_stage()

        assert stage.name == "reattempt"
        assert stage.stage_type == StageType.REATTEMPT
        assert stage.enabled_by == "reattempt"
        assert stage.depends_on == ["generate"]

        # Reattempt should be disabled by default
        assert stage.is_enabled({}) is False
        # Reattempt should be enabled when reattempt=True
        assert stage.is_enabled({"reattempt": True}) is True


class TestStageConfiguration:
    """Tests for stage configuration combinations"""

    def test_all_stages_disabled_config(self):
        """Test config with all optional stages disabled"""
        config = {"html_mode": False, "reasoning": False, "reattempt": False}

        fetch = create_fetch_stage()
        parse = create_parse_stage()
        reasoning = create_reasoning_stage()
        generate = create_generate_stage()
        reattempt = create_reattempt_stage()

        assert fetch.is_enabled(config) is True
        assert parse.is_enabled(config) is True
        assert reasoning.is_enabled(config) is False
        assert generate.is_enabled(config) is True
        assert reattempt.is_enabled(config) is False

    def test_all_stages_enabled_config(self):
        """Test config with all optional stages enabled"""
        config = {"html_mode": False, "reasoning": True, "reattempt": True}

        fetch = create_fetch_stage()
        parse = create_parse_stage()
        reasoning = create_reasoning_stage()
        generate = create_generate_stage()
        reattempt = create_reattempt_stage()

        assert fetch.is_enabled(config) is True
        assert parse.is_enabled(config) is True
        assert reasoning.is_enabled(config) is True
        assert generate.is_enabled(config) is True
        assert reattempt.is_enabled(config) is True

    def test_html_mode_config(self):
        """Test config with html_mode enabled"""
        config = {"html_mode": True, "reasoning": False, "reattempt": False}

        fetch = create_fetch_stage()
        parse = create_parse_stage()
        reasoning = create_reasoning_stage()
        generate = create_generate_stage()

        assert fetch.is_enabled(config) is True
        assert parse.is_enabled(config) is False  # Skipped in html_mode
        assert reasoning.is_enabled(config) is False
        assert generate.is_enabled(config) is True
