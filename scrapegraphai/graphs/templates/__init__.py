"""
Graph Template System

This package provides a composable template system for building graphs,
reducing code duplication and enabling flexible graph composition.

Components:
- StageDefinition: Reusable stage definitions
- GraphBuilder: Fluent API for building graphs
- PipelineTemplate: Base class for pipeline templates
"""

from .builder import GraphBuilder
from .pipelines import PipelineTemplate, SmartScraperPipeline
from .stages import (
    StageDefinition,
    StageType,
    create_fetch_stage,
    create_generate_stage,
    create_parse_stage,
    create_reattempt_stage,
    create_reasoning_stage,
)

__all__ = [
    "GraphBuilder",
    "PipelineTemplate",
    "SmartScraperPipeline",
    "StageDefinition",
    "StageType",
    "create_fetch_stage",
    "create_generate_stage",
    "create_parse_stage",
    "create_reattempt_stage",
    "create_reasoning_stage",
]
