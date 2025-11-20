"""
Unit tests for pipeline templates
"""

import pytest

from scrapegraphai.graphs.templates.pipelines import (
    LitePipeline,
    PipelineTemplate,
    SmartScraperPipeline,
)
from scrapegraphai.graphs.templates.stages import StageType


class TestPipelineTemplate:
    """Tests for PipelineTemplate base class"""

    def test_base_template_not_implemented(self):
        """Test that base template raises NotImplementedError"""
        with pytest.raises(NotImplementedError):
            PipelineTemplate.get_stages()


class TestSmartScraperPipeline:
    """Tests for SmartScraperPipeline"""

    def test_get_stages(self):
        """Test that SmartScraperPipeline returns correct stages"""
        stages = SmartScraperPipeline.get_stages()

        assert len(stages) == 5
        stage_names = [s.name for s in stages]
        assert "fetch" in stage_names
        assert "parse" in stage_names
        assert "reasoning" in stage_names
        assert "generate" in stage_names
        assert "reattempt" in stage_names

    def test_get_stages_types(self):
        """Test that stages have correct types"""
        stages = SmartScraperPipeline.get_stages()
        stage_types = {s.name: s.stage_type for s in stages}

        assert stage_types["fetch"] == StageType.FETCH
        assert stage_types["parse"] == StageType.PARSE
        assert stage_types["reasoning"] == StageType.REASONING
        assert stage_types["generate"] == StageType.GENERATE
        assert stage_types["reattempt"] == StageType.REATTEMPT

    def test_stage_requirements(self):
        """Test that required stages are marked correctly"""
        stages = SmartScraperPipeline.get_stages()
        stage_required = {s.name: s.required for s in stages}

        assert stage_required["fetch"] is True
        assert stage_required["generate"] is True
        assert stage_required["parse"] is False
        assert stage_required["reasoning"] is False
        assert stage_required["reattempt"] is False

    def test_stage_dependencies(self):
        """Test that stage dependencies are correct"""
        stages = SmartScraperPipeline.get_stages()
        stage_deps = {s.name: s.depends_on for s in stages}

        assert stage_deps["fetch"] == []
        assert stage_deps["parse"] == ["fetch"]
        assert stage_deps["reasoning"] == ["fetch"]
        assert stage_deps["generate"] == ["fetch"]
        assert stage_deps["reattempt"] == ["generate"]


class TestLitePipeline:
    """Tests for LitePipeline"""

    def test_get_stages(self):
        """Test that LitePipeline returns correct stages"""
        stages = LitePipeline.get_stages()

        assert len(stages) == 2
        stage_names = [s.name for s in stages]
        assert "fetch" in stage_names
        assert "parse" in stage_names


class TestPipelineConfiguration:
    """Integration tests for pipeline configuration scenarios"""

    def test_all_stage_combinations(self):
        """Test all 8 combinations of html_mode, reasoning, reattempt"""
        test_cases = [
            (False, False, False),  # Base: fetch -> parse -> generate
            (True, False, False),  # HTML mode: fetch -> generate
            (False, True, False),  # Reasoning: fetch -> parse -> reasoning -> generate
            (True, True, False),  # HTML + reasoning: fetch -> reasoning -> generate
            (False, False, True),  # Reattempt: fetch -> parse -> generate -> cond -> regen
            (True, False, True),  # HTML + reattempt
            (False, True, True),  # Reasoning + reattempt
            (True, True, True),  # All features
        ]

        for html_mode, reasoning, reattempt in test_cases:
            stages = SmartScraperPipeline.get_stages()
            config = {
                "html_mode": html_mode,
                "reasoning": reasoning,
                "reattempt": reattempt,
            }

            enabled_stages = [s for s in stages if s.is_enabled(config)]
            enabled_names = [s.name for s in enabled_stages]

            # Fetch and generate should always be present
            assert "fetch" in enabled_names
            assert "generate" in enabled_names

            # Parse should be present unless html_mode=True
            if html_mode:
                assert "parse" not in enabled_names
            else:
                assert "parse" in enabled_names

            # Reasoning should be present only if reasoning=True
            if reasoning:
                assert "reasoning" in enabled_names
            else:
                assert "reasoning" not in enabled_names

            # Reattempt should be present only if reattempt=True
            if reattempt:
                assert "reattempt" in enabled_names
            else:
                assert "reattempt" not in enabled_names

    def test_stage_count_variations(self):
        """Test that different configurations produce different stage counts"""
        test_configs = [
            ({"html_mode": False, "reasoning": False, "reattempt": False}, 3),  # Base
            ({"html_mode": True, "reasoning": False, "reattempt": False}, 2),  # Skip parse
            ({"html_mode": False, "reasoning": True, "reattempt": False}, 4),  # Add reasoning
            ({"html_mode": False, "reasoning": False, "reattempt": True}, 4),  # Add reattempt
            ({"html_mode": True, "reasoning": True, "reattempt": True}, 4),  # All but parse
            ({"html_mode": False, "reasoning": True, "reattempt": True}, 5),  # All stages
        ]

        for config, expected_count in test_configs:
            stages = SmartScraperPipeline.get_stages()
            enabled_stages = [s for s in stages if s.is_enabled(config)]
            assert (
                len(enabled_stages) == expected_count
            ), f"Config {config} should produce {expected_count} stages, got {len(enabled_stages)}"
