# ScrapeGraphAI: Terminology Glossary

**Analysis Date:** 2025-11-20
**Commit SHA:** [32d5636ac3465edd0a8af47c6242f16a0beb35f5](https://github.com/ScrapeGraphAI/Scrapegraph-ai/commit/32d5636ac3465edd0a8af47c6242f16a0beb35f5)

---

## 📖 Core Concepts

### Graph
**Definition:** A directed acyclic graph (DAG) composed of nodes connected by edges that defines a scraping pipeline.

**Example:**
```python
FetchNode → ParseNode → GenerateAnswerNode
```

**Related Terms:** Pipeline, Workflow, DAG

**Code Reference:** [`scrapegraphai/graphs/base_graph.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/graphs/base_graph.py)

---

### Node
**Definition:** A single processing unit in a graph that performs a specific task (fetching, parsing, generation, etc.).

**Types:**
- **Processing Node** (`node_type="node"`) - Performs transformation
- **Conditional Node** (`node_type="conditional_node"`) - Branching logic

**Base Class:** [`BaseNode`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/base_node.py)

**Example:**
```python
class FetchNode(BaseNode):
    def execute(self, state: dict) -> dict:
        # Fetch content from URL
        return state
```

---

### State
**Definition:** A dictionary that flows through the graph, carrying data between nodes.

**Structure:**
```python
{
    "user_prompt": "Extract product names",
    "url": "https://example.com",
    "doc": [Document],           # After FetchNode
    "parsed_doc": "...",          # After ParseNode
    "answer": {...}               # After GenerateAnswerNode
}
```

**Purpose:** Accumulates data at each processing stage.

---

### Edge
**Definition:** A connection between two nodes defining execution flow.

**Example:**
```python
edges = [
    (fetch_node, parse_node),     # fetch_node → parse_node
    (parse_node, generate_node),  # parse_node → generate_node
]
```

**Code Reference:** [`base_graph.py:_create_edges()`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/graphs/base_graph.py#L83)

---

## 🎨 Graph Types

### SmartScraperGraph
**Definition:** The most common graph type for single-page scraping using LLM-based extraction.

**Pipeline:**
```
FetchNode → ParseNode → GenerateAnswerNode
```

**Use Case:** Extract specific information from a single webpage.

**Example:**
```python
graph = SmartScraperGraph(
    prompt="Extract article title and author",
    source="https://example.com/article",
    config={"llm": {"model": "openai/gpt-4o"}}
)
```

**Code:** [`smart_scraper_graph.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/graphs/smart_scraper_graph.py)

---

### SearchGraph
**Definition:** Multi-page graph that searches the web and scrapes top results.

**Pipeline:**
```
SearchInternetNode → FetchNode → ParseNode → GenerateAnswerNode → MergeAnswersNode
```

**Use Case:** Research topics by scraping multiple search results.

**Code:** [`search_graph.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/graphs/search_graph.py)

---

### DocumentScraperGraph
**Definition:** Graph specialized for extracting information from local documents (PDF, Markdown, etc.).

**Use Case:** Process downloaded files or local document archives.

---

### MultiGraph
**Definition:** Variants of graphs that process multiple sources in parallel.

**Examples:**
- `SmartScraperMultiGraph` - Multiple URLs, separate results
- `SmartScraperMultiConcatGraph` - Multiple URLs, concatenated results

**Trade-off:** ✅ Parallel execution, ⚠️ Higher LLM costs

---

## 🔧 Node Types

### FetchNode
**Definition:** Downloads content from a URL or loads from a local file.

**Technology:** Playwright (browser automation)

**Configuration:**
- `headless`: Run browser in headless mode
- `timeout`: Request timeout in seconds
- `loader_kwargs`: Proxy, user agent, etc.

**Output:** Adds `doc` key to state containing `Document` objects

**Code:** [`fetch_node.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/fetch_node.py)

---

### ParseNode
**Definition:** Extracts text from HTML and chunks it for LLM processing.

**Process:**
1. Clean HTML (remove scripts, styles)
2. Extract text
3. Chunk text (semchunk library)

**Output:** Adds `parsed_doc` key with chunked text

**Code:** [`parse_node.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/parse_node.py)

---

### GenerateAnswerNode
**Definition:** Uses LLM to extract specific information based on user prompt.

**Process:**
1. Select appropriate prompt template
2. Send content + prompt to LLM
3. Parse JSON response
4. Optionally merge multiple chunks

**Output:** Adds `answer` key with structured extraction

**Code:** [`generate_answer_node.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/generate_answer_node.py)

---

### RAGNode
**Definition:** Retrieval-Augmented Generation node that uses vector similarity search.

**Technology:** Qdrant vector database (optional dependency)

**Use Case:** Large documents where only relevant sections should be sent to LLM

**Code:** [`rag_node.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/rag_node.py)

---

### SearchInternetNode
**Definition:** Performs web search and returns top result URLs.

**Providers:**
- **DuckDuckGo** (default, no API key)
- **Serper** (requires API key)

**Output:** Adds `url` key with list of URLs

**Code:** [`search_internet_node.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/search_internet_node.py)

---

### ConditionalNode
**Definition:** A node that implements branching logic based on state.

**Use Case:** Retry logic, error handling, conditional processing

**Example:**
```python
class ConditionalNode(BaseNode):
    def __init__(self, ...):
        super().__init__(..., node_type="conditional_node")

    def execute(self, state: dict) -> str:
        # Return name of next node to execute
        if state.get("answer"):
            return "success_node"
        return "retry_node"
```

---

## 🤖 LLM Terms

### LLM Model
**Definition:** The language model used for extraction.

**Format:** `"provider/model_name"`

**Examples:**
```python
"openai/gpt-4o"
"ollama/llama3"
"anthropic/claude-3-5-sonnet"
"groq/mixtral-8x7b"
```

**Code:** [`abstract_graph.py:_create_llm()`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/graphs/abstract_graph.py#L117)

---

### Model Tokens
**Definition:** Maximum context window size for a model.

**Source:** [`models_tokens.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/helpers/models_tokens.py)

**Examples:**
```python
"gpt-4o": 128000 tokens
"gpt-3.5-turbo": 16385 tokens
"llama3": 8192 tokens
```

**Why Important:** Determines how much content can be processed in one call.

---

### Prompt Template
**Definition:** Pre-defined prompt structure for specific node types.

**Location:** [`scrapegraphai/prompts/`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/prompts/)

**Examples:**
- `TEMPLATE_NO_CHUNKS` - Simple extraction without chunking
- `TEMPLATE_CHUNKS` - Extraction with text chunks
- `TEMPLATE_MERGE` - Merge multiple chunk results

---

### Schema
**Definition:** Pydantic model defining expected output structure.

**Example:**
```python
from pydantic import BaseModel

class Article(BaseModel):
    title: str
    author: str
    date: str

graph = SmartScraperGraph(
    prompt="Extract article information",
    source="https://example.com",
    schema=Article,
    config={...}
)
```

**Benefit:** Structured, validated output from LLM.

---

## 🛠️ Configuration Terms

### Config Dictionary
**Definition:** Configuration object passed to graph initialization.

**Required Keys:**
```python
config = {
    "llm": {                      # REQUIRED
        "model": "openai/gpt-4o",
        "api_key": "sk-..."
    }
}
```

**Optional Keys:**
```python
config = {
    "verbose": True,              # Debug logging
    "headless": True,             # Headless browser
    "timeout": 480,               # Execution timeout (s)
    "loader_kwargs": {...},       # Browser options
    "burr_kwargs": {...},         # Workflow management
    "cache_path": False,          # Cache content
    "reattempt": True,            # Retry on empty answer
}
```

---

### Loader Kwargs
**Definition:** Browser/loader configuration options.

**Common Options:**
```python
loader_kwargs = {
    "proxy": "http://proxy:8080",
    "user_agent": "Mozilla/5.0...",
    "wait_until": "networkidle",
    "cookies": [{...}],
}
```

**Passed to:** Playwright browser context

---

### Burr Integration
**Definition:** Optional workflow management framework integration.

**Benefits:**
- Better observability
- Workflow tracking
- State persistence

**Configuration:**
```python
config = {
    "burr_kwargs": {
        "app_instance_id": "my-scraper-123"
    }
}
```

**Code:** [`burr_bridge.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/integrations/burr_bridge.py)

---

## 📊 Execution Terms

### Execution Info
**Definition:** Metadata collected during graph execution.

**Contains:**
```python
execution_info = [
    {
        "node_name": "FetchNode",
        "total_tokens": 0,
        "exec_time": 1.23
    },
    {
        "node_name": "GenerateAnswerNode",
        "total_tokens": 1500,
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_cost_USD": 0.02,
        "exec_time": 2.45
    }
]
```

**Access:**
```python
result = graph.run()
info = graph.get_execution_info()
```

---

### Callback Manager
**Definition:** Tracks LLM token usage and costs during execution.

**Class:** `CustomLLMCallbackManager`

**Purpose:** Cost tracking, debugging, monitoring

**Code:** [`llm_callback_manager.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/utils/llm_callback_manager.py)

---

### Final State
**Definition:** The complete state dictionary after graph execution.

**Access:**
```python
result = graph.run()  # Returns state["answer"]
full_state = graph.get_state()  # Returns entire state
```

**Keys:**
- `user_prompt`: Original user prompt
- `url`/`local_dir`: Content source
- `doc`: Raw documents
- `parsed_doc`: Parsed text
- `answer`: Final extracted data

---

## 🎯 Advanced Concepts

### Graph Builder
**Definition:** Dynamically constructs graphs from natural language prompts.

**Use Case:** User describes desired scraping workflow, system builds graph automatically.

**Code:** [`graph_builder.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/builders/graph_builder.py)

---

### GraphIteratorNode
**Definition:** A special node that applies a graph to multiple inputs.

**Use Case:** Process multiple documents with the same graph.

**Code:** [`graph_iterator_node.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/nodes/graph_iterator_node.py)

---

### Chunking
**Definition:** Splitting large documents into smaller pieces for LLM processing.

**Library:** `semchunk` (semantic chunking)

**Why:** LLMs have token limits; chunking allows processing large documents.

**Strategy:**
1. Parse document into chunks
2. Process each chunk separately
3. Merge results

---

### Headless Mode
**Definition:** Running browser automation without visible UI.

**Benefits:**
- ✅ Faster execution
- ✅ Lower memory usage
- ✅ Server-friendly

**Configuration:**
```python
config = {"headless": True}  # Default
```

---

### robots.txt
**Definition:** Web standard file that specifies scraping rules.

**Node:** `RobotsNode` checks robots.txt before scraping

**Best Practice:** Respect robots.txt rules to be a good internet citizen.

---

## 🔧 Utility Terms

### Cleanup HTML
**Definition:** Remove unnecessary HTML elements (scripts, styles, etc.)

**Purpose:** Reduce token count, improve LLM focus

**Function:** [`cleanup_html()`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/utils/cleanup_html.py)

---

### Token Counting
**Definition:** Calculating number of tokens in text for LLM cost estimation.

**Libraries:**
- `tiktoken` (OpenAI models)
- Custom tokenizers for other providers

**Location:** [`scrapegraphai/utils/tokenizers/`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/utils/tokenizers/)

---

### Rate Limiting
**Definition:** Throttling API requests to avoid rate limits.

**Configuration:**
```python
config = {
    "llm": {
        "rate_limit": {
            "requests_per_second": 1,
            "max_retries": 3
        }
    }
}
```

**Implementation:** `InMemoryRateLimiter` from LangChain

---

## 📡 Integration Terms

### BrowserBase
**Definition:** Third-party browser infrastructure service.

**Purpose:** Managed browser automation (no Playwright installation needed)

**Configuration:**
```python
config = {
    "browser_base": {
        "api_key": "...",
        "project_id": "..."
    }
}
```

---

### ScrapeD
**Definition:** Third-party scraping service integration.

**Similar to:** BrowserBase, ScraperAPI

---

### Telemetry
**Definition:** Anonymous usage tracking for product improvement.

**Provider:** PostHog

**Opt-out:**
```bash
export SCRAPEGRAPHAI_TELEMETRY_ENABLED=false
```

**Code:** [`telemetry.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/telemetry/telemetry.py)

---

## 🎓 Acronyms

| Acronym | Full Term | Meaning |
|---------|-----------|---------|
| **LLM** | Large Language Model | AI models like GPT, Claude, Llama |
| **RAG** | Retrieval-Augmented Generation | Vector search + LLM generation |
| **DAG** | Directed Acyclic Graph | Graph with no cycles |
| **LOC** | Lines of Code | Code size metric |
| **API** | Application Programming Interface | Programmatic access |
| **JSON** | JavaScript Object Notation | Data format |
| **HTML** | HyperText Markup Language | Web page format |
| **PDF** | Portable Document Format | Document format |
| **OCR** | Optical Character Recognition | Image-to-text |
| **TTS** | Text-to-Speech | Audio generation |
| **CI/CD** | Continuous Integration/Deployment | Automated testing/deployment |

---

## 🔗 Related Concepts

### LangChain
**Definition:** Python framework for building LLM applications.

**Role in ScrapeGraphAI:** Core dependency, provides LLM abstraction layer.

**Website:** https://langchain.com

---

### Playwright
**Definition:** Browser automation framework by Microsoft.

**Role:** Fetching web pages, handling JavaScript-rendered content.

**Alternative to:** Selenium, Puppeteer

---

### Pydantic
**Definition:** Data validation library using Python type hints.

**Role:** Schema definition, output validation.

**Version:** 2.10.2+ (v2 with Rust optimizations)

---

## 📖 Usage Patterns

### Basic Scraping Pattern
```python
from scrapegraphai.graphs import SmartScraperGraph

# 1. Define configuration
config = {
    "llm": {
        "model": "openai/gpt-4o",
        "api_key": "sk-..."
    }
}

# 2. Create graph
graph = SmartScraperGraph(
    prompt="What to extract",
    source="Where to extract from",
    config=config
)

# 3. Execute
result = graph.run()
```

---

### Custom Graph Pattern
```python
from scrapegraphai.graphs import AbstractGraph, BaseGraph
from scrapegraphai.nodes import FetchNode, ParseNode, GenerateAnswerNode

class MyCustomGraph(AbstractGraph):
    def _create_graph(self) -> BaseGraph:
        # Define nodes
        fetch = FetchNode(...)
        parse = ParseNode(...)
        generate = GenerateAnswerNode(...)

        # Return configured graph
        return BaseGraph(
            nodes=[fetch, parse, generate],
            edges=[(fetch, parse), (parse, generate)],
            entry_point=fetch
        )
```

---

## 🔍 Debugging Terms

### Verbose Mode
**Definition:** Detailed logging of graph execution.

**Enable:**
```python
config = {"verbose": True}
```

**Output:** Step-by-step node execution, state changes, LLM calls

---

### Logger
**Definition:** Centralized logging instance.

**Access:**
```python
from scrapegraphai.utils import get_logger
logger = get_logger(__name__)
```

**Configuration:** [`logging.py`](https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/32d5636ac3465edd0a8af47c6242f16a0beb35f5/scrapegraphai/utils/logging.py)

---

## 🔗 Next Steps

For deeper understanding:
- Read **[00-quick-start.md](./00-quick-start.md)** for overview
- Check **[../blog-series/](../blog-series/)** for detailed explanations
- Review **[../rfcs/](../rfcs/)** for planned improvements
