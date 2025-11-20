# Extending and Integrating ScrapeGraphAI

**Technical Blog Series - Part 4 of 7**
**Difficulty:** Intermediate
**Commit SHA:** 32d5636ac3465edd0a8af47c6242f16a0beb35f5

---

## Table of Contents

1. [Introduction](#introduction)
2. [Creating Custom Nodes](#creating-custom-nodes)
3. [Building Custom Graphs](#building-custom-graphs)
4. [Integrating with Web Frameworks](#integrating-with-web-frameworks)
5. [Using RAGNode for Large Documents](#using-ragnode-for-large-documents)
6. [Burr Integration for Workflow Management](#burr-integration-for-workflow-management)
7. [Pydantic Schemas for Structured Output](#pydantic-schemas-for-structured-output)
8. [Real-World Integration Patterns](#real-world-integration-patterns)
9. [Key Takeaways](#key-takeaways)

---

## Introduction

ScrapeGraphAI's extensibility is one of its most powerful features. While the framework provides a rich set of pre-built graphs and nodes, real-world applications often require custom functionality, integration with existing systems, and specialized workflows.

### Integration Scenarios

Common integration needs include:

- **Custom Processing Logic**: Adding domain-specific validation, transformation, or enrichment steps
- **Web API Wrappers**: Exposing scraping capabilities through REST APIs
- **Microservices Integration**: Embedding ScrapeGraphAI in larger application architectures
- **Data Pipeline Integration**: Connecting with ETL systems, databases, and analytics platforms
- **Workflow Orchestration**: Integrating with workflow engines like Burr for observability
- **Type Safety**: Using Pydantic schemas for guaranteed output structure

### Extension Points

ScrapeGraphAI provides several extension points:

1. **Custom Nodes**: Implement `BaseNode` to add new processing steps
2. **Custom Graphs**: Compose nodes into specialized workflows using `BaseGraph`
3. **Conditional Logic**: Use `ConditionalNode` for dynamic execution paths
4. **Schema Validation**: Leverage Pydantic models for structured output
5. **Integration Adapters**: Build bridges to other frameworks and systems

Let's explore each of these in depth with practical, production-ready examples.

---

## Creating Custom Nodes

Custom nodes allow you to extend ScrapeGraphAI's functionality with your own processing logic. Every node must inherit from `BaseNode` and implement the `execute` method.

### Understanding BaseNode

The `BaseNode` class from `/home/user/Scrapegraph-ai/scrapegraphai/nodes/base_node.py` provides the foundation:

```python
class BaseNode(ABC):
    def __init__(
        self,
        node_name: str,
        node_type: str,  # "node" or "conditional_node"
        input: str,       # Boolean expression: "key1 & key2 | key3"
        output: List[str], # Keys to add to state
        min_input_len: int = 1,
        node_config: Optional[dict] = None,
    ):
        # Initialization logic

    @abstractmethod
    def execute(self, state: dict) -> dict:
        """Execute node logic and return updated state"""
        pass
```

### Complete Custom Node Example: Data Validation Node

Here's a production-ready custom node that validates and sanitizes scraped data:

```python
"""
Custom validation node with comprehensive error handling
File: custom_nodes/validation_node.py
"""
from typing import List, Optional, Dict, Any
import re
from datetime import datetime
from scrapegraphai.nodes import BaseNode


class ValidationNode(BaseNode):
    """
    Validates and sanitizes data extracted by scraping nodes.

    Performs:
    - Required field validation
    - Type checking and coercion
    - Pattern matching (emails, URLs, phone numbers)
    - Range validation for numeric fields
    - Custom validation rules

    Configuration:
        validation_rules (dict): Validation specifications per field
        strict_mode (bool): If True, raise errors; if False, filter invalid items
        default_values (dict): Default values for missing optional fields
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "Validation",
    ):
        super().__init__(node_name, "node", input, output, 1, node_config)

        self.validation_rules = node_config.get("validation_rules", {})
        self.strict_mode = node_config.get("strict_mode", False)
        self.default_values = node_config.get("default_values", {})
        self.verbose = node_config.get("verbose", False)

    def execute(self, state: dict) -> dict:
        """
        Validate and sanitize data from state.

        Args:
            state: Graph state containing data to validate

        Returns:
            Updated state with validated data or validation errors
        """
        self.logger.info(f"--- Executing {self.node_name} Node ---")

        # Get input data
        input_keys = self.get_input_keys(state)
        data = state.get(input_keys[0])

        if not data:
            self.logger.warning(f"No data found in key: {input_keys[0]}")
            state["validated_data"] = []
            state["validation_errors"] = ["No input data"]
            return state

        # Handle both single items and lists
        items = data if isinstance(data, list) else [data]

        validated_items = []
        validation_errors = []

        for idx, item in enumerate(items):
            try:
                validated_item, errors = self._validate_item(item, idx)

                if errors and self.strict_mode:
                    error_msg = f"Item {idx} validation failed: {errors}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

                if not errors:
                    validated_items.append(validated_item)
                else:
                    validation_errors.extend(errors)
                    if self.verbose:
                        self.logger.warning(f"Item {idx} has validation errors: {errors}")

            except Exception as e:
                error_msg = f"Error validating item {idx}: {str(e)}"
                self.logger.error(error_msg)
                validation_errors.append(error_msg)
                if self.strict_mode:
                    raise

        # Update state
        state["validated_data"] = validated_items
        state["validation_errors"] = validation_errors
        state["validation_stats"] = {
            "total_items": len(items),
            "valid_items": len(validated_items),
            "invalid_items": len(items) - len(validated_items),
            "timestamp": datetime.utcnow().isoformat()
        }

        if self.verbose:
            self.logger.info(
                f"Validation complete: {len(validated_items)}/{len(items)} items valid"
            )

        return state

    def _validate_item(self, item: Dict[str, Any], idx: int) -> tuple:
        """Validate a single item against rules."""
        validated_item = item.copy()
        errors = []

        for field, rules in self.validation_rules.items():
            value = item.get(field)

            # Required field check
            if rules.get("required", False) and not value:
                if field in self.default_values:
                    validated_item[field] = self.default_values[field]
                else:
                    errors.append(f"Required field '{field}' missing")
                    continue

            if value is None:
                continue

            # Type validation and coercion
            expected_type = rules.get("type")
            if expected_type:
                try:
                    validated_item[field] = self._coerce_type(value, expected_type)
                except (ValueError, TypeError) as e:
                    errors.append(f"Field '{field}' type error: {str(e)}")
                    continue

            # Pattern validation
            pattern = rules.get("pattern")
            if pattern and isinstance(value, str):
                if not re.match(pattern, value):
                    errors.append(f"Field '{field}' doesn't match pattern: {pattern}")

            # Range validation
            min_val = rules.get("min")
            max_val = rules.get("max")
            if isinstance(value, (int, float)):
                if min_val is not None and value < min_val:
                    errors.append(f"Field '{field}' below minimum: {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"Field '{field}' above maximum: {max_val}")

            # Length validation for strings
            min_length = rules.get("min_length")
            max_length = rules.get("max_length")
            if isinstance(value, str):
                if min_length and len(value) < min_length:
                    errors.append(f"Field '{field}' too short (min: {min_length})")
                if max_length and len(value) > max_length:
                    errors.append(f"Field '{field}' too long (max: {max_length})")

            # Custom validator function
            validator_func = rules.get("validator")
            if validator_func and callable(validator_func):
                try:
                    if not validator_func(value):
                        errors.append(f"Field '{field}' failed custom validation")
                except Exception as e:
                    errors.append(f"Field '{field}' validator error: {str(e)}")

        return validated_item, errors

    def _coerce_type(self, value: Any, expected_type: str) -> Any:
        """Coerce value to expected type."""
        type_map = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
        }

        converter = type_map.get(expected_type)
        if not converter:
            raise ValueError(f"Unknown type: {expected_type}")

        try:
            return converter(value)
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert {value} to {expected_type}")


# Example usage with the validation node
def example_validation_node():
    """Demonstrates using the custom ValidationNode"""
    from langchain_openai import ChatOpenAI
    from scrapegraphai.graphs import BaseGraph
    from scrapegraphai.nodes import FetchNode, ParseNode, GenerateAnswerNode

    llm = ChatOpenAI(model="gpt-4o", api_key="your-api-key")

    # Define validation rules
    validation_config = {
        "validation_rules": {
            "name": {
                "required": True,
                "type": "str",
                "min_length": 2,
                "max_length": 100
            },
            "email": {
                "required": True,
                "type": "str",
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            },
            "age": {
                "required": False,
                "type": "int",
                "min": 0,
                "max": 150
            },
            "website": {
                "required": False,
                "type": "str",
                "pattern": r"^https?://.*"
            }
        },
        "strict_mode": False,
        "default_values": {"age": 0},
        "verbose": True
    }

    # Create nodes
    fetch_node = FetchNode(
        input="url",
        output=["doc"],
        node_config={"headless": True}
    )

    parse_node = ParseNode(
        input="doc",
        output=["parsed_doc"],
        node_config={"chunk_size": 4096}
    )

    generate_node = GenerateAnswerNode(
        input="user_prompt & parsed_doc",
        output=["answer"],
        node_config={"llm_model": llm}
    )

    validation_node = ValidationNode(
        input="answer",
        output=["validated_data", "validation_errors"],
        node_config=validation_config
    )

    # Build graph
    graph = BaseGraph(
        nodes=[fetch_node, parse_node, generate_node, validation_node],
        edges=[
            (fetch_node, parse_node),
            (parse_node, generate_node),
            (generate_node, validation_node)
        ],
        entry_point=fetch_node
    )

    # Execute
    result, _ = graph.execute({
        "user_prompt": "Extract contact information as JSON",
        "url": "https://example.com/contacts"
    })

    print(f"Valid items: {len(result['validated_data'])}")
    print(f"Errors: {result['validation_errors']}")
    print(f"Stats: {result['validation_stats']}")
```

### Testing Custom Nodes

Always test your custom nodes thoroughly:

```python
"""
Test suite for ValidationNode
File: tests/test_validation_node.py
"""
import pytest
from custom_nodes.validation_node import ValidationNode


def test_validation_node_required_fields():
    """Test that required field validation works"""
    node = ValidationNode(
        input="data",
        output=["validated_data", "validation_errors"],
        node_config={
            "validation_rules": {
                "name": {"required": True}
            },
            "strict_mode": False
        }
    )

    # Test missing required field
    state = {"data": [{"age": 30}]}
    result = node.execute(state)

    assert len(result["validated_data"]) == 0
    assert len(result["validation_errors"]) > 0
    assert "Required field 'name' missing" in result["validation_errors"][0]


def test_validation_node_type_coercion():
    """Test type coercion works correctly"""
    node = ValidationNode(
        input="data",
        output=["validated_data", "validation_errors"],
        node_config={
            "validation_rules": {
                "age": {"type": "int"}
            }
        }
    )

    state = {"data": [{"age": "25"}]}
    result = node.execute(state)

    assert len(result["validated_data"]) == 1
    assert result["validated_data"][0]["age"] == 25
    assert isinstance(result["validated_data"][0]["age"], int)


def test_validation_node_pattern_matching():
    """Test pattern validation for emails"""
    node = ValidationNode(
        input="data",
        output=["validated_data", "validation_errors"],
        node_config={
            "validation_rules": {
                "email": {
                    "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                }
            },
            "strict_mode": False
        }
    )

    state = {"data": [
        {"email": "valid@example.com"},
        {"email": "invalid-email"}
    ]}
    result = node.execute(state)

    assert len(result["validated_data"]) == 1
    assert result["validated_data"][0]["email"] == "valid@example.com"


def test_validation_node_strict_mode():
    """Test that strict mode raises exceptions"""
    node = ValidationNode(
        input="data",
        output=["validated_data", "validation_errors"],
        node_config={
            "validation_rules": {
                "name": {"required": True}
            },
            "strict_mode": True
        }
    )

    state = {"data": [{"age": 30}]}

    with pytest.raises(ValueError, match="validation failed"):
        node.execute(state)
```

---

## Building Custom Graphs

Custom graphs combine nodes into specialized workflows. They provide complete control over execution flow, including conditional logic and dynamic routing.

### Custom Graph with Conditional Logic

Here's a complete example that demonstrates building a custom graph with conditional branching:

```python
"""
Custom graph with conditional logic for content quality assessment
File: custom_graphs/quality_scraper_graph.py
"""
from typing import List, Optional
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import (
    BaseNode,
    ConditionalNode,
    FetchNode,
    ParseNode,
    GenerateAnswerNode
)


class ContentQualityNode(BaseNode):
    """
    Analyzes content quality and assigns a score.
    Used to determine if content needs additional processing.
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "QualityCheck",
    ):
        super().__init__(node_name, "node", input, output, 1, node_config)
        self.llm_model = node_config.get("llm_model")
        self.min_quality_score = node_config.get("min_quality_score", 0.7)

    def execute(self, state: dict) -> dict:
        """Assess content quality"""
        self.logger.info(f"--- Executing {self.node_name} Node ---")

        parsed_content = state.get("parsed_doc", "")

        # Calculate quality metrics
        quality_score = self._calculate_quality(parsed_content)

        state["quality_score"] = quality_score
        state["is_high_quality"] = quality_score >= self.min_quality_score

        self.logger.info(f"Content quality score: {quality_score:.2f}")

        return state

    def _calculate_quality(self, content: str) -> float:
        """Calculate quality score based on various metrics"""
        if not content:
            return 0.0

        score = 0.0

        # Length score (0-0.3)
        word_count = len(content.split())
        if word_count > 100:
            score += 0.3
        elif word_count > 50:
            score += 0.2
        elif word_count > 20:
            score += 0.1

        # Structure score (0-0.3)
        has_headings = any(marker in content for marker in ['#', '##', '###'])
        has_lists = any(marker in content for marker in ['-', '*', '1.'])
        has_links = 'http' in content

        if has_headings:
            score += 0.1
        if has_lists:
            score += 0.1
        if has_links:
            score += 0.1

        # Content diversity score (0-0.4)
        unique_words = len(set(content.lower().split()))
        if unique_words > 100:
            score += 0.4
        elif unique_words > 50:
            score += 0.3
        elif unique_words > 25:
            score += 0.2
        else:
            score += 0.1

        return min(score, 1.0)


class EnrichmentNode(BaseNode):
    """
    Enriches low-quality content with additional context.
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "Enrich",
    ):
        super().__init__(node_name, "node", input, output, 1, node_config)
        self.llm_model = node_config.get("llm_model")

    def execute(self, state: dict) -> dict:
        """Enrich content with additional information"""
        self.logger.info(f"--- Executing {self.node_name} Node ---")

        parsed_content = state.get("parsed_doc", "")

        # Use LLM to enrich content
        from langchain.prompts import PromptTemplate

        prompt = PromptTemplate(
            template="""The following content is sparse or low-quality.
            Please expand it with relevant context and details while maintaining accuracy:

            Content: {content}

            Enriched version:""",
            input_variables=["content"]
        )

        chain = prompt | self.llm_model
        enriched = chain.invoke({"content": parsed_content})

        # Handle different response types
        if hasattr(enriched, 'content'):
            enriched_content = enriched.content
        else:
            enriched_content = str(enriched)

        state["parsed_doc"] = enriched_content
        state["was_enriched"] = True

        self.logger.info("Content enrichment complete")

        return state


class QualityScraperGraph:
    """
    Custom graph that conditionally enriches content based on quality.

    Flow:
    1. Fetch content
    2. Parse content
    3. Check quality
    4. If low quality -> Enrich content
    5. Generate final answer
    """

    def __init__(self, llm_model, config: Optional[dict] = None):
        self.llm_model = llm_model
        self.config = config or {}
        self.graph = self._create_graph()

    def _create_graph(self) -> BaseGraph:
        """Create the graph with conditional logic"""

        # Define all nodes
        fetch_node = FetchNode(
            input="url",
            output=["doc"],
            node_config={
                "headless": self.config.get("headless", True),
                "verbose": self.config.get("verbose", False)
            }
        )

        parse_node = ParseNode(
            input="doc",
            output=["parsed_doc"],
            node_config={
                "chunk_size": self.config.get("chunk_size", 4096),
                "verbose": self.config.get("verbose", False)
            }
        )

        quality_node = ContentQualityNode(
            input="parsed_doc",
            output=["quality_score", "is_high_quality"],
            node_config={
                "llm_model": self.llm_model,
                "min_quality_score": self.config.get("min_quality_score", 0.7),
                "verbose": self.config.get("verbose", False)
            }
        )

        # Conditional node - decides if enrichment is needed
        quality_conditional = ConditionalNode(
            input="is_high_quality",
            output=[],
            node_config={
                "key_name": "is_high_quality",
                "condition": "not is_high_quality"  # True path if low quality
            },
            node_name="QualityCheck"
        )

        enrichment_node = EnrichmentNode(
            input="parsed_doc",
            output=["parsed_doc", "was_enriched"],
            node_config={
                "llm_model": self.llm_model,
                "verbose": self.config.get("verbose", False)
            }
        )

        generate_node = GenerateAnswerNode(
            input="user_prompt & parsed_doc",
            output=["answer"],
            node_config={
                "llm_model": self.llm_model,
                "verbose": self.config.get("verbose", False)
            }
        )

        # Build graph with conditional edge
        graph = BaseGraph(
            nodes=[
                fetch_node,
                parse_node,
                quality_node,
                quality_conditional,
                enrichment_node,
                generate_node
            ],
            edges=[
                (fetch_node, parse_node),
                (parse_node, quality_node),
                (quality_node, quality_conditional),
                # Conditional edges: if low quality -> enrich, else -> generate
                (quality_conditional, enrichment_node),  # True path (needs enrichment)
                (quality_conditional, generate_node),    # False path (high quality)
                (enrichment_node, generate_node)
            ],
            entry_point=fetch_node,
            graph_name="QualityScraper"
        )

        return graph

    def run(self, prompt: str, url: str):
        """Execute the graph"""
        state, exec_info = self.graph.execute({
            "user_prompt": prompt,
            "url": url
        })

        return {
            "answer": state.get("answer"),
            "quality_score": state.get("quality_score"),
            "was_enriched": state.get("was_enriched", False),
            "execution_info": exec_info
        }


# Example usage
def example_quality_scraper():
    """Demonstrates the custom quality scraper graph"""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o", api_key="your-api-key")

    scraper = QualityScraperGraph(
        llm_model=llm,
        config={
            "min_quality_score": 0.7,
            "verbose": True,
            "headless": True
        }
    )

    # Test with potentially low-quality content
    result = scraper.run(
        prompt="Summarize the main points",
        url="https://example.com/short-article"
    )

    print(f"Answer: {result['answer']}")
    print(f"Quality Score: {result['quality_score']:.2f}")
    print(f"Was Enriched: {result['was_enriched']}")
```

### Graph Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              Quality Scraper Graph Flow                      │
└─────────────────────────────────────────────────────────────┘

        ┌──────────┐
        │  Fetch   │
        │   Node   │
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │  Parse   │
        │   Node   │
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │ Quality  │
        │ Analysis │
        └────┬─────┘
             │
             ▼
    ┌─────────────────┐
    │  Conditional:   │
    │  Quality Check  │
    └───┬─────────┬───┘
        │         │
  Low   │         │  High
Quality │         │  Quality
        │         │
        ▼         │
   ┌─────────┐   │
   │ Enrich  │   │
   │  Node   │   │
   └────┬────┘   │
        │        │
        └────┬───┘
             │
             ▼
       ┌──────────┐
       │ Generate │
       │  Answer  │
       └──────────┘
```

---

## Integrating with Web Frameworks

Wrapping ScrapeGraphAI in a web API allows you to expose scraping capabilities as a service. Here's a production-ready FastAPI integration:

```python
"""
Production FastAPI integration for ScrapeGraphAI
File: integrations/fastapi_app.py
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio
from datetime import datetime
import uuid
from langchain_openai import ChatOpenAI
from scrapegraphai.graphs import SmartScraperGraph
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="ScrapeGraphAI API",
    description="REST API for web scraping with ScrapeGraphAI",
    version="1.0.0"
)

# In-memory job storage (use Redis/Database in production)
jobs_store: Dict[str, Dict[str, Any]] = {}


# Pydantic models for request/response
class GraphType(str, Enum):
    SMART_SCRAPER = "smart_scraper"
    SEARCH = "search"
    SPEECH = "speech"


class ScrapeRequest(BaseModel):
    """Request model for scraping operations"""
    url: HttpUrl = Field(..., description="URL to scrape")
    prompt: str = Field(..., description="Prompt describing what to extract")
    graph_type: GraphType = Field(
        default=GraphType.SMART_SCRAPER,
        description="Type of graph to use"
    )
    llm_model: str = Field(default="gpt-4o", description="LLM model to use")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    verbose: bool = Field(default=False, description="Enable verbose logging")
    schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Pydantic schema for structured output"
    )

    @validator('prompt')
    def validate_prompt(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Prompt must be at least 3 characters')
        return v.strip()


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeResponse(BaseModel):
    """Response model for scrape requests"""
    job_id: str
    status: JobStatus
    message: str


class JobResult(BaseModel):
    """Model for job results"""
    job_id: str
    status: JobStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None


# Dependency for LLM model
async def get_llm_model(model_name: str = "gpt-4o"):
    """Dependency to get LLM model instance"""
    try:
        return ChatOpenAI(
            model=model_name,
            api_key="your-api-key",  # Load from environment in production
            temperature=0
        )
    except Exception as e:
        logger.error(f"Error initializing LLM: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize LLM")


# Background task for async scraping
async def run_scraping_task(job_id: str, request: ScrapeRequest):
    """
    Background task that runs the scraping operation.
    Updates job status in the jobs store.
    """
    try:
        logger.info(f"Starting job {job_id}")
        jobs_store[job_id]["status"] = JobStatus.RUNNING

        start_time = datetime.utcnow()

        # Create graph configuration
        graph_config = {
            "llm": {
                "model": request.llm_model,
                "api_key": "your-api-key"  # Load from environment
            },
            "headless": request.headless,
            "verbose": request.verbose
        }

        # Create and run graph
        graph = SmartScraperGraph(
            prompt=request.prompt,
            source=str(request.url),
            config=graph_config,
            schema=request.schema
        )

        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, graph.run)

        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        # Update job with results
        jobs_store[job_id].update({
            "status": JobStatus.COMPLETED,
            "result": result,
            "completed_at": end_time,
            "execution_time": execution_time
        })

        logger.info(f"Job {job_id} completed in {execution_time:.2f}s")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        jobs_store[job_id].update({
            "status": JobStatus.FAILED,
            "error": str(e),
            "completed_at": datetime.utcnow()
        })


@app.post("/scrape", response_model=ScrapeResponse, status_code=202)
async def scrape_endpoint(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Initiate a scraping job.

    Returns a job ID that can be used to check status and retrieve results.
    """
    job_id = str(uuid.uuid4())

    # Initialize job in store
    jobs_store[job_id] = {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "request": request.dict(),
        "created_at": datetime.utcnow(),
        "result": None,
        "error": None,
        "completed_at": None
    }

    # Add background task
    background_tasks.add_task(run_scraping_task, job_id, request)

    return ScrapeResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Job created successfully"
    )


@app.get("/jobs/{job_id}", response_model=JobResult)
async def get_job_status(job_id: str):
    """
    Get the status and result of a scraping job.
    """
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs_store[job_id]

    return JobResult(
        job_id=job["job_id"],
        status=job["status"],
        result=job.get("result"),
        error=job.get("error"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        execution_time=job.get("execution_time")
    )


@app.get("/jobs", response_model=List[JobResult])
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 10
):
    """
    List all jobs, optionally filtered by status.
    """
    jobs = list(jobs_store.values())

    if status:
        jobs = [j for j in jobs if j["status"] == status]

    # Sort by created_at descending
    jobs.sort(key=lambda x: x["created_at"], reverse=True)

    # Apply limit
    jobs = jobs[:limit]

    return [
        JobResult(
            job_id=job["job_id"],
            status=job["status"],
            result=job.get("result"),
            error=job.get("error"),
            created_at=job["created_at"],
            completed_at=job.get("completed_at"),
            execution_time=job.get("execution_time")
        )
        for job in jobs
    ]


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job from the store."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")

    del jobs_store[job_id]

    return {"message": "Job deleted successfully"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "jobs_count": len(jobs_store)
    }


# Example client usage
"""
# Install: pip install httpx

import httpx
import asyncio
import time

async def example_client():
    base_url = "http://localhost:8000"

    # Create scraping job
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/scrape",
            json={
                "url": "https://example.com",
                "prompt": "Extract the main heading and description",
                "llm_model": "gpt-4o",
                "headless": True
            }
        )
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["job_id"]
        print(f"Job created: {job_id}")

        # Poll for results
        while True:
            response = await client.get(f"{base_url}/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()

            print(f"Status: {job['status']}")

            if job["status"] in ["completed", "failed"]:
                print(f"Result: {job.get('result')}")
                print(f"Error: {job.get('error')}")
                break

            await asyncio.sleep(2)

# Run: asyncio.run(example_client())
"""

# Run with: uvicorn integrations.fastapi_app:app --reload
```

---

## Using RAGNode for Large Documents

The `RAGNode` from `/home/user/Scrapegraph-ai/scrapegraphai/nodes/rag_node.py` enables processing of large documents by using vector databases for efficient retrieval.

### RAGNode Implementation Example

```python
"""
Advanced RAG implementation with vector database
File: examples/rag_large_documents.py
"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import FetchNode, ParseNode, RAGNode, GenerateAnswerNode


def create_rag_scraper(api_key: str):
    """
    Create a scraper that handles large documents using RAG.

    Perfect for:
    - Long articles or documentation
    - PDF documents
    - Multi-page content
    - Content exceeding LLM context limits
    """

    # Initialize models
    llm = ChatOpenAI(model="gpt-4o", api_key=api_key, temperature=0)
    embedder = OpenAIEmbeddings(api_key=api_key)

    # Configure nodes
    fetch_node = FetchNode(
        input="url",
        output=["doc"],
        node_config={
            "headless": True,
            "verbose": True
        }
    )

    parse_node = ParseNode(
        input="doc",
        output=["parsed_doc"],
        node_config={
            "chunk_size": 4096,  # Size of chunks for processing
            "verbose": True
        }
    )

    # RAG node configuration
    rag_node = RAGNode(
        input="user_prompt & parsed_doc",
        output=["relevant_chunks"],
        node_config={
            "llm_model": llm,
            "embedder_model": embedder,
            "client_type": "memory",  # Options: memory, local_db, image
            "verbose": True
        }
    )

    generate_node = GenerateAnswerNode(
        input="user_prompt & relevant_chunks",
        output=["answer"],
        node_config={
            "llm_model": llm,
            "verbose": True
        }
    )

    # Build graph
    graph = BaseGraph(
        nodes=[fetch_node, parse_node, rag_node, generate_node],
        edges=[
            (fetch_node, parse_node),
            (parse_node, rag_node),
            (rag_node, generate_node)
        ],
        entry_point=fetch_node,
        graph_name="RAGScraper"
    )

    return graph


def example_large_document():
    """Process a large document with RAG"""

    graph = create_rag_scraper(api_key="your-api-key")

    # Execute on large document
    result, exec_info = graph.execute({
        "user_prompt": "Summarize the key technical concepts and provide code examples",
        "url": "https://example.com/long-technical-article"
    })

    print("Answer:", result["answer"])
    print("\nExecution Info:")
    for info in exec_info:
        print(f"  {info['node_name']}: {info['exec_time']:.2f}s")


# Advanced: Custom RAG with Qdrant persistence
def create_persistent_rag_scraper(api_key: str, qdrant_path: str):
    """
    Create RAG scraper with persistent vector database.
    Useful for repeated queries on the same documents.
    """
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from scrapegraphai.graphs import BaseGraph
    from scrapegraphai.nodes import FetchNode, ParseNode, RAGNode, GenerateAnswerNode

    llm = ChatOpenAI(model="gpt-4o", api_key=api_key)
    embedder = OpenAIEmbeddings(api_key=api_key)

    fetch_node = FetchNode(
        input="url",
        output=["doc"],
        node_config={"headless": True}
    )

    parse_node = ParseNode(
        input="doc",
        output=["parsed_doc"],
        node_config={"chunk_size": 4096}
    )

    # Persistent Qdrant database
    rag_node = RAGNode(
        input="user_prompt & parsed_doc",
        output=["relevant_chunks"],
        node_config={
            "llm_model": llm,
            "embedder_model": embedder,
            "client_type": "local_db",  # Persistent storage
            "db_path": qdrant_path,
            "collection_name": "documents",
            "verbose": True
        }
    )

    generate_node = GenerateAnswerNode(
        input="user_prompt & relevant_chunks",
        output=["answer"],
        node_config={"llm_model": llm}
    )

    graph = BaseGraph(
        nodes=[fetch_node, parse_node, rag_node, generate_node],
        edges=[
            (fetch_node, parse_node),
            (parse_node, rag_node),
            (rag_node, generate_node)
        ],
        entry_point=fetch_node
    )

    return graph
```

### RAG Workflow Diagram

```
┌────────────────────────────────────────────────────────────┐
│                  RAG Workflow Architecture                  │
└────────────────────────────────────────────────────────────┘

   ┌─────────┐
   │  Fetch  │ ──► Retrieve large document
   └────┬────┘
        │
        ▼
   ┌─────────┐
   │  Parse  │ ──► Split into chunks (4096 tokens)
   └────┬────┘
        │
        ▼
   ┌─────────────────────────────────────┐
   │          RAG Node                    │
   │                                      │
   │  ┌──────────────────────────────┐  │
   │  │ 1. Create Embeddings          │  │
   │  │    └─► OpenAI Embeddings      │  │
   │  └──────────────────────────────┘  │
   │                                      │
   │  ┌──────────────────────────────┐  │
   │  │ 2. Store in Vector DB         │  │
   │  │    └─► Qdrant (memory/disk)   │  │
   │  └──────────────────────────────┘  │
   │                                      │
   │  ┌──────────────────────────────┐  │
   │  │ 3. Query with User Prompt     │  │
   │  │    └─► Semantic search        │  │
   │  └──────────────────────────────┘  │
   │                                      │
   │  ┌──────────────────────────────┐  │
   │  │ 4. Retrieve Relevant Chunks   │  │
   │  │    └─► Top-K similarity       │  │
   │  └──────────────────────────────┘  │
   └────────┬─────────────────────────┘
            │
            ▼ relevant_chunks
       ┌─────────┐
       │Generate │ ──► Synthesize answer from relevant chunks
       │ Answer  │
       └─────────┘
```

---

## Burr Integration for Workflow Management

Burr integration from `/home/user/Scrapegraph-ai/scrapegraphai/integrations/burr_bridge.py` provides observability, tracking, and debugging capabilities.

### Complete Burr Integration Example

```python
"""
Burr integration for workflow observability
File: examples/burr_integration.py
"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.nodes import (
    FetchNode,
    ParseNode,
    RAGNode,
    GenerateAnswerNode
)


def create_graph_with_burr(api_key: str, project_name: str = "scraping_project"):
    """
    Create a graph with Burr integration for tracking and observability.

    Burr provides:
    - Step-by-step execution tracking
    - State snapshots at each node
    - Performance metrics
    - Visual workflow inspection
    - Debugging capabilities
    """

    llm = ChatOpenAI(model="gpt-4o", api_key=api_key)
    embedder = OpenAIEmbeddings(api_key=api_key)

    # Define nodes
    fetch_node = FetchNode(
        input="url",
        output=["doc"],
        node_config={"headless": True, "verbose": True}
    )

    parse_node = ParseNode(
        input="doc",
        output=["parsed_doc"],
        node_config={"chunk_size": 4096, "verbose": True}
    )

    rag_node = RAGNode(
        input="user_prompt & parsed_doc",
        output=["relevant_chunks"],
        node_config={
            "llm_model": llm,
            "embedder_model": embedder,
            "verbose": True
        }
    )

    generate_node = GenerateAnswerNode(
        input="user_prompt & relevant_chunks",
        output=["answer"],
        node_config={"llm_model": llm, "verbose": True}
    )

    # Create graph with Burr enabled
    graph = BaseGraph(
        nodes=[fetch_node, parse_node, rag_node, generate_node],
        edges=[
            (fetch_node, parse_node),
            (parse_node, rag_node),
            (rag_node, generate_node)
        ],
        entry_point=fetch_node,
        use_burr=True,  # Enable Burr integration
        burr_config={
            "project_name": project_name,
            "app_instance_id": "scraper-001"
        }
    )

    return graph


def example_with_burr_tracking():
    """
    Example showing Burr tracking in action.

    After running, you can view the execution:
    1. Install Burr UI: pip install "burr[start]"
    2. Start UI: burr
    3. Navigate to http://localhost:7241
    """

    graph = create_graph_with_burr(
        api_key="your-api-key",
        project_name="my_scraping_project"
    )

    result, exec_info = graph.execute({
        "user_prompt": "Extract key information about the product",
        "url": "https://example.com/product"
    })

    print("Result:", result["answer"])
    print("\n✅ Execution tracked in Burr")
    print("📊 View at: http://localhost:7241")


# Advanced: Custom Burr hooks for monitoring
def create_graph_with_custom_hooks(api_key: str):
    """
    Add custom hooks for monitoring and alerting.
    """
    try:
        from burr.lifecycle import PostRunStepHook, PreRunStepHook
        from burr.core import Action, State
        from typing import Any
    except ImportError:
        print("Install burr: pip install 'scrapegraphai[burr]'")
        return None

    class PerformanceMonitorHook(PostRunStepHook, PreRunStepHook):
        """Custom hook to monitor node performance"""

        def __init__(self):
            self.start_times = {}

        def pre_run_step(self, *, state: State, action: Action, **kwargs: Any):
            import time
            self.start_times[action.name] = time.time()
            print(f"🚀 Starting: {action.name}")

        def post_run_step(self, *, state: State, action: Action, **kwargs: Any):
            import time
            elapsed = time.time() - self.start_times.get(action.name, 0)
            print(f"✅ Completed: {action.name} ({elapsed:.2f}s)")

            # Alert if node is slow
            if elapsed > 30:
                print(f"⚠️  WARNING: {action.name} took {elapsed:.2f}s")

    # This would require modifying BurrBridge to accept custom hooks
    # For demonstration purposes only
    print("Custom hooks would be integrated into BurrBridge")

    llm = ChatOpenAI(model="gpt-4o", api_key=api_key)

    fetch_node = FetchNode(
        input="url",
        output=["doc"],
        node_config={"headless": True}
    )

    parse_node = ParseNode(
        input="doc",
        output=["parsed_doc"],
        node_config={"chunk_size": 4096}
    )

    generate_node = GenerateAnswerNode(
        input="user_prompt & parsed_doc",
        output=["answer"],
        node_config={"llm_model": llm}
    )

    graph = BaseGraph(
        nodes=[fetch_node, parse_node, generate_node],
        edges=[
            (fetch_node, parse_node),
            (parse_node, generate_node)
        ],
        entry_point=fetch_node,
        use_burr=True,
        burr_config={
            "project_name": "monitored_scraping",
            "app_instance_id": "scraper-monitored"
        }
    )

    return graph
```

---

## Pydantic Schemas for Structured Output

Pydantic schemas guarantee type-safe, structured output. Example from `/home/user/Scrapegraph-ai/examples/search_graph/openai/search_graph_schema_openai.py`:

### Complete Pydantic Schema Examples

```python
"""
Comprehensive Pydantic schema examples for structured scraping
File: examples/pydantic_schemas.py
"""
from pydantic import BaseModel, Field, HttpUrl, EmailStr, validator
from typing import List, Optional
from datetime import datetime
from enum import Enum
from scrapegraphai.graphs import SmartScraperGraph


# Example 1: E-commerce Product Schema
class PriceInfo(BaseModel):
    """Nested model for price information"""
    amount: float = Field(..., description="Price amount", ge=0)
    currency: str = Field(default="USD", description="Currency code")
    original_price: Optional[float] = Field(None, description="Original price if on sale")
    discount_percentage: Optional[float] = Field(None, ge=0, le=100)


class ProductReview(BaseModel):
    """Product review information"""
    rating: float = Field(..., description="Review rating", ge=0, le=5)
    count: int = Field(..., description="Number of reviews", ge=0)


class Product(BaseModel):
    """Complete product information"""
    name: str = Field(..., description="Product name")
    description: str = Field(..., description="Product description")
    price: PriceInfo = Field(..., description="Price information")
    reviews: Optional[ProductReview] = Field(None, description="Review information")
    availability: bool = Field(..., description="Whether product is in stock")
    sku: Optional[str] = Field(None, description="Product SKU")
    image_url: Optional[HttpUrl] = Field(None, description="Main product image URL")

    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Product name too short')
        return v.strip()


# Example 2: Contact Information Schema
class ContactInfo(BaseModel):
    """Contact information with validation"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., description="Valid email address")
    phone: Optional[str] = Field(
        None,
        regex=r'^\+?1?\d{9,15}$',
        description="Phone number"
    )
    website: Optional[HttpUrl] = Field(None)
    address: Optional[str] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "website": "https://example.com",
                "address": "123 Main St, City, Country"
            }
        }


class ContactList(BaseModel):
    """List of contacts"""
    contacts: List[ContactInfo] = Field(..., description="List of contact information")
    total_count: Optional[int] = Field(None, description="Total number of contacts")


# Example 3: Article/Blog Post Schema
class Author(BaseModel):
    """Author information"""
    name: str = Field(..., description="Author name")
    bio: Optional[str] = Field(None, description="Author biography")
    url: Optional[HttpUrl] = Field(None, description="Author profile URL")


class Category(str, Enum):
    """Article categories"""
    TECHNOLOGY = "technology"
    BUSINESS = "business"
    SCIENCE = "science"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"


class Article(BaseModel):
    """Complete article information"""
    title: str = Field(..., description="Article title")
    author: Author = Field(..., description="Article author")
    published_date: Optional[str] = Field(None, description="Publication date")
    category: Category = Field(..., description="Article category")
    summary: str = Field(..., description="Article summary", max_length=500)
    content: str = Field(..., description="Full article content")
    tags: List[str] = Field(default_factory=list, description="Article tags")
    word_count: Optional[int] = Field(None, ge=0)
    reading_time: Optional[int] = Field(None, description="Reading time in minutes")


class ArticleList(BaseModel):
    """Collection of articles"""
    articles: List[Article]
    total: int = Field(..., description="Total number of articles")


# Example 4: Job Listing Schema
class SalaryRange(BaseModel):
    """Salary information"""
    min: Optional[float] = Field(None, ge=0)
    max: Optional[float] = Field(None, ge=0)
    currency: str = Field(default="USD")
    period: str = Field(default="year", regex=r'^(hour|day|month|year)$')


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"


class JobListing(BaseModel):
    """Job listing information"""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location")
    job_type: JobType = Field(..., description="Type of employment")
    salary: Optional[SalaryRange] = Field(None, description="Salary range")
    description: str = Field(..., description="Job description")
    requirements: List[str] = Field(..., description="Job requirements")
    posted_date: Optional[str] = Field(None, description="Posting date")
    apply_url: HttpUrl = Field(..., description="Application URL")


class JobListings(BaseModel):
    """Collection of job listings"""
    jobs: List[JobListing]
    total_count: int = Field(..., ge=0)


# Usage Examples
def example_product_scraping():
    """Scrape product with structured output"""

    graph_config = {
        "llm": {
            "api_key": "your-api-key",
            "model": "gpt-4o"
        },
        "verbose": True,
        "headless": True
    }

    scraper = SmartScraperGraph(
        prompt="Extract product information",
        source="https://example.com/product",
        config=graph_config,
        schema=Product  # Pass Pydantic model
    )

    result = scraper.run()

    # Result is automatically validated against schema
    # Type hints work in IDEs
    print(f"Product: {result.name}")
    print(f"Price: {result.price.amount} {result.price.currency}")
    print(f"In Stock: {result.availability}")


def example_contacts_scraping():
    """Scrape contacts with validation"""

    graph_config = {
        "llm": {
            "api_key": "your-api-key",
            "model": "gpt-4o"
        }
    }

    scraper = SmartScraperGraph(
        prompt="Extract all contact information",
        source="https://example.com/contacts",
        config=graph_config,
        schema=ContactList
    )

    result = scraper.run()

    # Validated contacts
    for contact in result.contacts:
        print(f"{contact.name}: {contact.email}")


def example_articles_scraping():
    """Scrape articles with nested schemas"""

    graph_config = {
        "llm": {
            "api_key": "your-api-key",
            "model": "gpt-4o"
        }
    }

    scraper = SmartScraperGraph(
        prompt="Extract all articles with author information",
        source="https://example.com/blog",
        config=graph_config,
        schema=ArticleList
    )

    result = scraper.run()

    # Type-safe access
    for article in result.articles:
        print(f"{article.title} by {article.author.name}")
        print(f"Category: {article.category.value}")
        print(f"Reading time: {article.reading_time} minutes\n")
```

---

## Real-World Integration Patterns

### Integration Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                  ScrapeGraphAI Integration Patterns                    │
└───────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      Microservices Architecture                      │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │   Frontend   │────────▶│  API Gateway │────────▶│  Auth Service│
    │  (React/Vue) │         │  (FastAPI)   │         │              │
    └──────────────┘         └───────┬──────┘         └──────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                  │
                    ▼                                  ▼
          ┌──────────────────┐            ┌──────────────────┐
          │  ScrapeGraphAI   │            │  Other Services  │
          │     Service      │            │  (Analytics...)  │
          └────────┬─────────┘            └──────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
   ┌──────────┐        ┌──────────┐
   │  Redis   │        │PostgreSQL│
   │  Queue   │        │ Database │
   └──────────┘        └──────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                       Data Pipeline Pattern                          │
└─────────────────────────────────────────────────────────────────────┘

  Data Sources          Scraping Layer          Processing          Storage

  ┌─────────┐          ┌───────────────┐      ┌──────────┐      ┌──────────┐
  │   Web   │─────────▶│ ScrapeGraphAI │─────▶│Transform │─────▶│  S3/GCS  │
  │  Sites  │          │               │      │ Validate │      │          │
  └─────────┘          └───────────────┘      └──────────┘      └──────────┘
                              │                     │                 │
  ┌─────────┐                 │                     │                 │
  │   APIs  │─────────────────┘                     ▼                 ▼
  └─────────┘                                  ┌──────────┐      ┌──────────┐
                                               │  Alert   │      │ Data     │
  ┌─────────┐                                  │  System  │      │ Warehouse│
  │   PDFs  │──────────────────────────────────┘          │      │(BigQuery)│
  └─────────┘                                              └──────┴──────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                    Event-Driven Architecture                         │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐         ┌────────────────┐         ┌─────────────┐
  │   Scheduler  │────────▶│  Message Queue │────────▶│  Scraper    │
  │   (Cron)     │         │  (RabbitMQ)    │         │  Workers    │
  └──────────────┘         └────────────────┘         └──────┬──────┘
                                                              │
                                                              │
                                               ┌──────────────┴────────────┐
                                               │                           │
                                               ▼                           ▼
                                        ┌─────────────┐           ┌──────────────┐
                                        │ Webhook     │           │  Burr        │
                                        │ Notifier    │           │  Tracking    │
                                        └─────────────┘           └──────────────┘
```

### Complete Production Integration Example

```python
"""
Production-grade integration with error handling, retry logic, and monitoring
File: integrations/production_integration.py
"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from functools import wraps
import time
from dataclasses import dataclass
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScrapingStatus(str, Enum):
    """Status of scraping operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ScrapingResult:
    """Result of a scraping operation"""
    status: ScrapingStatus
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    timestamp: datetime = datetime.utcnow()
    retry_count: int = 0


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries} retry attempts failed")

            raise last_exception
        return wrapper
    return decorator


class ScrapingOrchestrator:
    """
    Production orchestrator for scraping operations.

    Features:
    - Retry logic with exponential backoff
    - Rate limiting
    - Error handling and recovery
    - Monitoring and metrics
    - Result caching
    - Concurrent execution with limits
    """

    def __init__(
        self,
        llm_config: Dict[str, Any],
        max_concurrent: int = 5,
        rate_limit: int = 10,  # requests per minute
        enable_caching: bool = True
    ):
        self.llm_config = llm_config
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self.enable_caching = enable_caching

        # Internal state
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_limiter = asyncio.Semaphore(rate_limit)
        self._cache: Dict[str, ScrapingResult] = {}
        self._metrics: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "total_execution_time": 0.0
        }

    def _get_cache_key(self, url: str, prompt: str) -> str:
        """Generate cache key for request"""
        import hashlib
        content = f"{url}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()

    async def _rate_limit_wait(self):
        """Implement rate limiting"""
        async with self._rate_limiter:
            await asyncio.sleep(60.0 / self.rate_limit)

    @retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
    async def scrape_single(
        self,
        url: str,
        prompt: str,
        schema: Optional[Any] = None
    ) -> ScrapingResult:
        """
        Scrape a single URL with retry logic and error handling.
        """
        # Check cache
        cache_key = self._get_cache_key(url, prompt)
        if self.enable_caching and cache_key in self._cache:
            logger.info(f"Cache hit for {url}")
            self._metrics["cache_hits"] += 1
            return self._cache[cache_key]

        # Rate limiting
        await self._rate_limit_wait()

        # Track metrics
        self._metrics["total_requests"] += 1
        start_time = time.time()

        try:
            # Acquire semaphore for concurrency control
            async with self._semaphore:
                logger.info(f"Scraping {url}")

                # Create and run graph
                from langchain_openai import ChatOpenAI
                from scrapegraphai.graphs import SmartScraperGraph

                llm = ChatOpenAI(**self.llm_config)

                graph = SmartScraperGraph(
                    prompt=prompt,
                    source=url,
                    config={
                        "llm": self.llm_config,
                        "headless": True,
                        "verbose": False
                    },
                    schema=schema
                )

                # Run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, graph.run)

                execution_time = time.time() - start_time
                self._metrics["total_execution_time"] += execution_time
                self._metrics["successful_requests"] += 1

                result = ScrapingResult(
                    status=ScrapingStatus.COMPLETED,
                    data=data,
                    execution_time=execution_time
                )

                # Cache result
                if self.enable_caching:
                    self._cache[cache_key] = result

                logger.info(f"Successfully scraped {url} in {execution_time:.2f}s")
                return result

        except Exception as e:
            execution_time = time.time() - start_time
            self._metrics["failed_requests"] += 1

            logger.error(f"Failed to scrape {url}: {str(e)}")

            return ScrapingResult(
                status=ScrapingStatus.FAILED,
                error=str(e),
                execution_time=execution_time
            )

    async def scrape_batch(
        self,
        urls: List[str],
        prompt: str,
        schema: Optional[Any] = None
    ) -> List[ScrapingResult]:
        """
        Scrape multiple URLs concurrently with concurrency limits.
        """
        logger.info(f"Starting batch scraping of {len(urls)} URLs")

        tasks = [
            self.scrape_single(url, prompt, schema)
            for url in urls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    ScrapingResult(
                        status=ScrapingStatus.FAILED,
                        error=str(result)
                    )
                )
            else:
                processed_results.append(result)

        logger.info(f"Batch scraping complete: {len(processed_results)} results")
        return processed_results

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        metrics = self._metrics.copy()
        if metrics["successful_requests"] > 0:
            metrics["average_execution_time"] = (
                metrics["total_execution_time"] / metrics["successful_requests"]
            )
        else:
            metrics["average_execution_time"] = 0.0

        if metrics["total_requests"] > 0:
            metrics["success_rate"] = (
                metrics["successful_requests"] / metrics["total_requests"]
            )
            metrics["cache_hit_rate"] = (
                metrics["cache_hits"] / metrics["total_requests"]
            )
        else:
            metrics["success_rate"] = 0.0
            metrics["cache_hit_rate"] = 0.0

        return metrics

    def clear_cache(self):
        """Clear the result cache"""
        self._cache.clear()
        logger.info("Cache cleared")


# Example usage
async def example_production_integration():
    """Demonstrates production integration"""

    # Initialize orchestrator
    orchestrator = ScrapingOrchestrator(
        llm_config={
            "model": "gpt-4o",
            "api_key": "your-api-key",
            "temperature": 0
        },
        max_concurrent=5,
        rate_limit=10,
        enable_caching=True
    )

    # Single scrape with retry logic
    result = await orchestrator.scrape_single(
        url="https://example.com",
        prompt="Extract main content and summary"
    )

    print(f"Status: {result.status}")
    print(f"Data: {result.data}")
    print(f"Execution time: {result.execution_time:.2f}s")

    # Batch scraping
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page3",
    ]

    results = await orchestrator.scrape_batch(
        urls=urls,
        prompt="Extract product information"
    )

    # Print results
    for i, result in enumerate(results):
        print(f"\nResult {i + 1}:")
        print(f"  Status: {result.status}")
        if result.status == ScrapingStatus.COMPLETED:
            print(f"  Data: {result.data}")
        else:
            print(f"  Error: {result.error}")

    # Get metrics
    metrics = orchestrator.get_metrics()
    print("\nMetrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


# Run example
if __name__ == "__main__":
    asyncio.run(example_production_integration())
```

---

## Key Takeaways

### Extension Best Practices

1. **Custom Nodes**
   - Always inherit from `BaseNode`
   - Implement comprehensive error handling
   - Add logging for debugging
   - Write unit tests
   - Document input/output contracts

2. **Custom Graphs**
   - Use `ConditionalNode` for branching logic
   - Keep nodes focused and single-purpose
   - Design for reusability
   - Test edge cases

3. **Web Integration**
   - Use async patterns for scalability
   - Implement proper error handling
   - Add rate limiting
   - Include health checks
   - Document API contracts

4. **RAG for Large Documents**
   - Choose appropriate chunk sizes
   - Use persistent storage for repeated queries
   - Monitor vector database performance
   - Consider embedding costs

5. **Burr Integration**
   - Enable for complex workflows
   - Use for debugging and optimization
   - Monitor execution traces
   - Leverage visual inspection

6. **Pydantic Schemas**
   - Define clear field descriptions
   - Use appropriate validators
   - Provide examples
   - Version your schemas

7. **Production Considerations**
   - Implement retry logic with exponential backoff
   - Add comprehensive monitoring
   - Use caching strategically
   - Handle rate limits
   - Plan for scaling

### Integration Checklist

- [ ] Define clear interfaces and contracts
- [ ] Implement error handling and recovery
- [ ] Add logging and monitoring
- [ ] Write comprehensive tests
- [ ] Document configuration options
- [ ] Consider security implications
- [ ] Plan for scalability
- [ ] Implement rate limiting
- [ ] Add caching where appropriate
- [ ] Monitor resource usage
- [ ] Set up alerting
- [ ] Version your integrations

### Next Steps

In the next post, we'll explore **Advanced Topics and Optimization**, covering:
- Performance tuning techniques
- Cost optimization strategies
- Advanced RAG patterns
- Multi-modal scraping
- Distributed scraping architectures

---

**Previous:** [Patterns and Best Practices](/home/user/Scrapegraph-ai/analysis-output/blog-series/03-patterns-practices.md)
**Next:** Advanced Topics and Optimization (Coming Soon)

**Related Resources:**
- [ScrapeGraphAI Documentation](https://scrapegraph-ai.com)
- [Burr Documentation](https://github.com/DAGWorks-Inc/burr)
- [Pydantic Documentation](https://docs.pydantic.dev)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
