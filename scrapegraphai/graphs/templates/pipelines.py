"""
Pipeline Templates

Provides reusable pipeline templates for common graph patterns.
Each template defines a standard set of stages that can be composed
based on configuration flags.
"""

from typing import Any, Dict, List

from .builder import GraphBuilder
from .stages import (
    StageDefinition,
    create_fetch_stage,
    create_generate_stage,
    create_parse_stage,
    create_reattempt_stage,
    create_reasoning_stage,
)


class PipelineTemplate:
    """
    Base class for reusable pipeline templates.

    Subclasses should implement get_stages() to define their stage composition.
    """

    @staticmethod
    def get_stages() -> List[StageDefinition]:
        """
        Return list of stages in this pipeline.

        Returns:
            List of StageDefinition objects

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement get_stages()")

    @classmethod
    def build(cls, config: Dict[str, Any]) -> "BaseGraph":
        """
        Build graph from template with given configuration.

        The builder automatically handles:
        - Stage inclusion based on configuration flags
        - Edge inference between stages
        - Dependency validation

        Args:
            config: Configuration dictionary containing:
                - Node configuration (llm_model, headless, etc.)
                - Stage control flags (html_mode, reasoning, reattempt)

        Returns:
            BaseGraph instance with nodes and edges configured

        Example:
            >>> config = {
            ...     "llm_model": model,
            ...     "html_mode": False,
            ...     "reasoning": True,
            ...     "reattempt": False,
            ... }
            >>> graph = SmartScraperPipeline.build(config)
        """
        builder = GraphBuilder(config)
        builder.add_stages(cls.get_stages())
        return builder.build()


class SmartScraperPipeline(PipelineTemplate):
    """
    Standard smart scraper pipeline with configurable stages.

    Replaces the 8 hardcoded variations with composition rules:
    - Base: fetch → parse → generate
    - html_mode=True: skip parse (fetch → generate)
    - reasoning=True: insert reasoning (fetch → parse → reasoning → generate)
    - reattempt=True: add reattempt stage (... → generate → conditional → regen)

    Configuration flags:
        html_mode (bool): Skip HTML parsing if True (default: False)
        reasoning (bool): Enable reasoning stage if True (default: False)
        reattempt (bool): Enable validation/regeneration if True (default: False)

    Example:
        >>> # Basic pipeline: fetch → parse → generate
        >>> config = {"llm_model": model}
        >>> graph = SmartScraperPipeline.build(config)

        >>> # With reasoning: fetch → parse → reasoning → generate
        >>> config = {"llm_model": model, "reasoning": True}
        >>> graph = SmartScraperPipeline.build(config)

        >>> # HTML mode: fetch → generate
        >>> config = {"llm_model": model, "html_mode": True}
        >>> graph = SmartScraperPipeline.build(config)

        >>> # All features: fetch → parse → reasoning → generate → conditional → regen
        >>> config = {
        ...     "llm_model": model,
        ...     "reasoning": True,
        ...     "reattempt": True,
        ... }
        >>> graph = SmartScraperPipeline.build(config)
    """

    @staticmethod
    def get_stages() -> List[StageDefinition]:
        """
        Get stages for SmartScraper pipeline.

        Returns:
            List of stage definitions:
            - fetch: Always included (required)
            - parse: Skipped if html_mode=True
            - reasoning: Included if reasoning=True
            - generate: Always included (required)
            - reattempt: Included if reattempt=True
        """
        return [
            create_fetch_stage(),
            create_parse_stage(),  # Skipped if html_mode=True
            create_reasoning_stage(),  # Added if reasoning=True
            create_generate_stage(),
            create_reattempt_stage(),  # Added if reattempt=True
        ]


class LitePipeline(PipelineTemplate):
    """
    Lightweight pipeline for simple scraping without generation.

    Pipeline: fetch → parse

    Use this for basic content extraction without LLM-based analysis.
    """

    @staticmethod
    def get_stages() -> List[StageDefinition]:
        """
        Get stages for Lite pipeline.

        Returns:
            List containing only fetch and parse stages
        """
        return [
            create_fetch_stage(),
            create_parse_stage(),
        ]
