"""
Stage Definition System

Provides reusable stage definitions for graph composition.
Each stage represents a logical unit of processing that can be
included/excluded based on configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StageType(Enum):
    """Standard stage types in scraping pipelines."""

    FETCH = "fetch"
    PARSE = "parse"
    REASONING = "reasoning"
    GENERATE = "generate"
    VALIDATE = "validate"
    REATTEMPT = "reattempt"


@dataclass
class StageDefinition:
    """
    Defines a reusable graph stage (one or more nodes).

    A stage represents a logical unit of processing that can be:
    - Included/excluded based on configuration
    - Composed with other stages
    - Reused across different graph types

    Attributes:
        name: Unique identifier for the stage
        stage_type: Type of stage from StageType enum
        node_factory: Function that creates nodes for this stage
        required: Whether stage must be included regardless of config
        enabled_by: Config key that controls stage inclusion (None = always enabled)
        skip_if: Config key that causes stage to be skipped (opposite of enabled_by)
        depends_on: List of stage names this stage depends on
    """

    name: str
    stage_type: StageType
    node_factory: Callable[[Dict[str, Any]], List[Any]]
    required: bool = False
    enabled_by: Optional[str] = None
    skip_if: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)

    def create_nodes(self, config: Dict[str, Any]) -> List[Any]:
        """
        Create nodes for this stage with given configuration.

        Args:
            config: Configuration dictionary containing node settings

        Returns:
            List of node instances created by the factory
        """
        return self.node_factory(config)

    def is_enabled(self, config: Dict[str, Any]) -> bool:
        """
        Check if stage should be included based on config.

        Logic:
        1. Required stages are always enabled
        2. If skip_if is set and that config value is True, stage is disabled
        3. If enabled_by is set, stage is only enabled if that config value is True
        4. Otherwise, stage is enabled by default

        Args:
            config: Configuration dictionary

        Returns:
            True if stage should be included, False otherwise
        """
        if self.required:
            return True
        if self.skip_if and config.get(self.skip_if, False):
            return False
        if self.enabled_by:
            return config.get(self.enabled_by, False)
        return True


# Standard stage factory functions


def create_fetch_stage() -> StageDefinition:
    """
    Standard fetch stage for retrieving web content.

    Always required as the entry point for scraping pipelines.
    """

    def factory(config):
        from ...nodes import FetchNode

        return [
            FetchNode(
                input="url | local_dir",
                output=["doc"],
                node_config={
                    "llm_model": config.get("llm_model"),
                    "force": config.get("force", False),
                    "cut": config.get("cut", True),
                    "loader_kwargs": config.get("loader_kwargs", {}),
                    "browser_base": config.get("browser_base"),
                    "scrape_do": config.get("scrape_do"),
                    "storage_state": config.get("storage_state"),
                },
            )
        ]

    return StageDefinition(
        name="fetch",
        stage_type=StageType.FETCH,
        node_factory=factory,
        required=True,
    )


def create_parse_stage() -> StageDefinition:
    """
    Parse stage for processing HTML/documents.

    Skipped when html_mode=True (raw HTML processing mode).
    """

    def factory(config):
        from ...nodes import ParseNode

        return [
            ParseNode(
                input="doc",
                output=["parsed_doc"],
                node_config={
                    "llm_model": config.get("llm_model"),
                    "chunk_size": config.get("model_token"),
                },
            )
        ]

    return StageDefinition(
        name="parse",
        stage_type=StageType.PARSE,
        node_factory=factory,
        skip_if="html_mode",  # Skip if html_mode=True
        depends_on=["fetch"],
    )


def create_reasoning_stage() -> StageDefinition:
    """
    Reasoning stage for analytical processing.

    Enabled when reasoning=True in configuration.
    """

    def factory(config):
        from ...nodes import ReasoningNode

        return [
            ReasoningNode(
                input="user_prompt & (relevant_chunks | parsed_doc | doc)",
                output=["answer"],
                node_config={
                    "llm_model": config.get("llm_model"),
                    "additional_info": config.get("additional_info"),
                    "schema": config.get("schema"),
                },
            )
        ]

    return StageDefinition(
        name="reasoning",
        stage_type=StageType.REASONING,
        node_factory=factory,
        enabled_by="reasoning",
        depends_on=["fetch"],  # Can depend on either fetch or parse
    )


def create_generate_stage() -> StageDefinition:
    """
    Generate stage for creating final output.

    Always required as the output stage for most pipelines.
    Input adapts based on whether reasoning is enabled.
    """

    def factory(config):
        from ...nodes import GenerateAnswerNode

        # Determine input based on reasoning configuration
        input_spec = "user_prompt & (relevant_chunks | parsed_doc | doc)"

        return [
            GenerateAnswerNode(
                input=input_spec,
                output=["answer"],
                node_config={
                    "llm_model": config.get("llm_model"),
                    "additional_info": config.get("additional_info"),
                    "schema": config.get("schema"),
                },
            )
        ]

    return StageDefinition(
        name="generate",
        stage_type=StageType.GENERATE,
        node_factory=factory,
        required=True,
        depends_on=["fetch"],  # Depends on fetch, may use parse/reasoning if available
    )


def create_reattempt_stage() -> StageDefinition:
    """
    Reattempt stage for validation and regeneration.

    Enabled when reattempt=True in configuration.
    Creates a conditional loop that can retry generation if validation fails.
    """

    def factory(config):
        from ...nodes import ConditionalNode, GenerateAnswerNode
        from ...prompts import REGEN_ADDITIONAL_INFO

        cond_node = ConditionalNode(
            input="answer",
            output=["answer"],
            node_name="ConditionalNode",
            node_config={
                "key_name": "answer",
                "condition": 'not answer or answer=="NA"',
            },
        )

        regen_node = GenerateAnswerNode(
            input="user_prompt & answer",
            output=["answer"],
            node_config={
                "llm_model": config.get("llm_model"),
                "additional_info": REGEN_ADDITIONAL_INFO,
                "schema": config.get("schema"),
            },
        )

        return [cond_node, regen_node]

    return StageDefinition(
        name="reattempt",
        stage_type=StageType.REATTEMPT,
        node_factory=factory,
        enabled_by="reattempt",
        depends_on=["generate"],
    )
