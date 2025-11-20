# ScrapeGraphAI: Repository Structure

**Analysis Date:** 2025-11-20
**Commit SHA:** [32d5636ac3465edd0a8af47c6242f16a0beb35f5](https://github.com/ScrapeGraphAI/Scrapegraph-ai/commit/32d5636ac3465edd0a8af47c6242f16a0beb35f5)

---

## 📂 Complete Directory Tree

```
Scrapegraph-ai/
├── 📦 scrapegraphai/                   # Main package (14,711 LOC)
│   ├── __init__.py                    # Package initialization
│   │
│   ├── 📊 graphs/                     # Graph Implementations (27 files)
│   │   ├── abstract_graph.py          # 339 lines - Base abstract class
│   │   ├── base_graph.py              # 398 lines - Execution engine
│   │   ├── smart_scraper_graph.py     # 305 lines - Single-page scraper
│   │   ├── search_graph.py            # Multi-page search scraper
│   │   ├── smart_scraper_multi_graph.py
│   │   ├── document_scraper_graph.py  # PDF/document scraping
│   │   ├── json_scraper_graph.py      # JSON extraction
│   │   ├── xml_scraper_graph.py       # XML extraction
│   │   ├── csv_scraper_graph.py       # CSV extraction
│   │   ├── code_generator_graph.py    # Python code generation
│   │   ├── script_creator_graph.py    # Script generation
│   │   ├── speech_graph.py            # Text-to-speech
│   │   ├── omni_scraper_graph.py      # Universal format
│   │   ├── screenshot_scraper_graph.py
│   │   ├── depth_search_graph.py      # Recursive depth searching
│   │   └── [15 more graph variants]
│   │
│   ├── 🔧 nodes/                      # Processing Nodes (31 files)
│   │   ├── base_node.py               # 236 lines - Abstract base node
│   │   │
│   │   ├── Fetching Nodes:
│   │   │   ├── fetch_node.py          # 14.9K - Browser-based fetching
│   │   │   ├── fetch_node_level_k.py  # Multi-level depth fetching
│   │   │   ├── fetch_screen_node.py   # Screenshot capture
│   │   │   └── robots_node.py         # robots.txt checking
│   │   │
│   │   ├── Parsing Nodes:
│   │   │   ├── parse_node.py          # 7.3K - HTML to text + chunking
│   │   │   ├── parse_node_depth_k.py  # Multi-level parsing
│   │   │   └── markdownify_node.py    # HTML to Markdown
│   │   │
│   │   ├── Analysis Nodes:
│   │   │   ├── html_analyzer_node.py  # Extract probable tags
│   │   │   ├── get_probable_tags_node.py
│   │   │   ├── description_node.py    # Generate descriptions
│   │   │   └── reasoning_node.py      # Logical reasoning
│   │   │
│   │   ├── Generation Nodes:
│   │   │   ├── generate_answer_node.py    # 10.3K - Core LLM answer gen
│   │   │   ├── generate_answer_node_klevel.py
│   │   │   ├── generate_answer_csv_node.py
│   │   │   ├── generate_answer_omni_node.py
│   │   │   ├── generate_code_node.py      # 17.7K - Code generation
│   │   │   └── generate_scraper_node.py   # Scraper function gen
│   │   │
│   │   ├── Search Nodes:
│   │   │   ├── search_internet_node.py    # Web search integration
│   │   │   ├── search_link_node.py        # Extract and search links
│   │   │   └── search_links_with_context.py
│   │   │
│   │   ├── Merging Nodes:
│   │   │   ├── merge_answers_node.py      # Combine multiple answers
│   │   │   ├── concat_answers_node.py     # Concatenate results
│   │   │   └── merge_generated_scripts_node.py
│   │   │
│   │   └── Advanced Nodes:
│   │       ├── rag_node.py             # 3.6K - Vector DB RAG
│   │       ├── prompt_refiner_node.py  # Refine prompts
│   │       ├── graph_iterator_node.py  # Iterate over graphs
│   │       ├── image_to_text_node.py   # OCR/image-to-text
│   │       └── text_to_speech_node.py  # TTS generation
│   │
│   ├── 🤖 models/                     # Model Wrappers (7 files)
│   │   ├── clod.py                    # CLoD model integration
│   │   ├── deepseek.py                # DeepSeek integration
│   │   ├── xai.py                     # X.AI integration
│   │   ├── ernie.py                   # Baidu ERNIE
│   │   ├── oneapi.py                  # OneAPI wrapper
│   │   └── [OpenAI/Gemini via LangChain]
│   │
│   ├── 💬 prompts/                    # LLM Prompt Templates (17 files)
│   │   ├── generate_answer_node_prompts.py
│   │   ├── generate_code_node_prompts.py
│   │   ├── generate_scraper_node_prompts.py
│   │   ├── reasoning_node_prompts.py
│   │   └── [13 more prompt definitions]
│   │
│   ├── 🛠️ helpers/                    # Utility Helpers (6 files)
│   │   ├── models_tokens.py           # Token counts for 50+ models
│   │   ├── nodes_metadata.py          # Node descriptions & schemas
│   │   ├── default_filters.py         # HTML filters
│   │   ├── schemas.py                 # Pydantic schemas
│   │   └── robot_check.py             # robots.txt parser
│   │
│   ├── 🏗️ builders/                   # Graph Building (1 file)
│   │   └── graph_builder.py           # Dynamic graph from prompts
│   │
│   ├── 🔨 utils/                      # Core Utilities (25 files)
│   │   ├── cleanup_html.py            # HTML cleaning
│   │   ├── code_error_analysis.py     # Code error detection
│   │   ├── code_error_correction.py   # Code error fixing
│   │   ├── logging.py                 # Custom logging config
│   │   ├── llm_callback_manager.py    # Token tracking
│   │   ├── research_web.py            # Web search implementation
│   │   ├── proxy_rotation.py          # Proxy management
│   │   ├── convert_to_md.py           # HTML to Markdown
│   │   ├── output_parser.py           # Parse LLM outputs
│   │   ├── remover.py                 # Content removal utilities
│   │   ├── save_code_to_file.py       # Code persistence
│   │   ├── split_text_in_chunks.py    # Text chunking
│   │   │
│   │   ├── 📸 screenshot_scraping/    # Screenshot capture
│   │   │   ├── screenshot_preparation.py
│   │   │   └── screenshot_to_text.py
│   │   │
│   │   └── 🔢 tokenizers/             # Token counting
│   │       ├── anthropic_tokenizer.py
│   │       ├── gemini_tokenizer.py
│   │       └── text_tokenizer.py
│   │
│   ├── 📄 docloaders/                 # Document Loaders (3 files)
│   │   ├── chromium.py                # 21K - Playwright-based loader
│   │   ├── browser_base.py            # BrowserBase integration
│   │   └── scrape_do.py               # ScrapeDo integration
│   │
│   ├── 🔌 integrations/               # Framework Integrations (2 files)
│   │   ├── burr_bridge.py             # Burr framework integration
│   │   └── indexify_node.py           # Indexify integration
│   │
│   └── 📊 telemetry/                  # Analytics (1 file)
│       └── telemetry.py               # PostHog-based usage tracking
│
├── 🧪 tests/                          # Test Suite (41 test files)
│   ├── test_fetch_node_timeout.py
│   ├── test_generate_answer_node.py
│   ├── test_models_tokens.py
│   ├── test_cleanup_html.py
│   ├── test_remover.py
│   ├── test_split_text_in_chunks.py
│   │
│   ├── graphs/                        # Graph Integration Tests (17 files)
│   │   ├── smart_scraper_openai_test.py
│   │   ├── smart_scraper_ollama_test.py
│   │   ├── search_graph_openai_test.py
│   │   ├── document_scraper_test.py
│   │   └── [13 more graph tests]
│   │
│   ├── nodes/                         # Node-specific Tests
│   │   └── [node tests]
│   │
│   └── inputs/                        # Test Data/Fixtures
│       ├── sample.html
│       ├── sample.pdf
│       └── [test data files]
│
├── 📚 examples/                       # Usage Examples (16 directories)
│   ├── smart_scraper_graph/           # Single page scraping
│   ├── search_graph/                  # Multi-page search
│   ├── csv_scraper_graph/             # CSV extraction
│   ├── json_scraper_graph/            # JSON extraction
│   ├── xml_scraper_graph/             # XML extraction
│   ├── document_scraper_graph/        # PDF/document handling
│   ├── code_generator_graph/          # Python code generation
│   ├── script_generator_graph/        # Script generation
│   ├── speech_graph/                  # Text-to-speech
│   ├── custom_graph/                  # Custom graph creation
│   ├── omni_scraper_graph/            # Universal format
│   └── [5 more example types]
│
├── 📖 docs/                           # Documentation
│   ├── README.md                      # Docs introduction
│   ├── Makefile                       # Sphinx build automation
│   ├── requirements.txt               # Doc dependencies
│   │
│   └── source/                        # Sphinx Documentation
│       ├── conf.py                    # Sphinx configuration
│       ├── index.rst                  # Main docs page
│       ├── introduction/              # Getting started
│       ├── scrapers/                  # Graph-specific docs
│       ├── modules/                   # API reference
│       └── getting_started/           # Quick start guides
│
├── 🔧 Configuration Files
│   ├── pyproject.toml                 # Project metadata & dependencies
│   ├── requirements.txt               # Core dependencies
│   ├── requirements-dev.txt           # Dev dependencies
│   ├── Makefile                       # Build automation
│   ├── .pre-commit-config.yaml        # Pre-commit hooks
│   └── .gitignore                     # Git ignore patterns
│
├── 🚀 CI/CD
│   └── .github/workflows/
│       ├── code-quality.yml           # Linting, formatting
│       ├── codeql.yml                 # Security scanning
│       ├── dependency-review.yml      # Dependency checks
│       └── release.yml                # Automated releases
│
├── 📝 Documentation
│   ├── README.md                      # Main project README
│   ├── CONTRIBUTING.md                # Contribution guidelines
│   ├── LICENSE                        # MIT License
│   └── ScrapegraphAI_cookbook.ipynb   # Jupyter notebook tutorial
│
└── 🎯 Project Root Files
    ├── .python-version                # Python version (3.10+)
    └── uv.lock                        # Locked dependencies (uv)
```

---

## 🔍 Directory Purpose & Responsibilities

### Core Package (`scrapegraphai/`)

| Directory | Files | LOC | Purpose |
|-----------|-------|-----|---------|
| `graphs/` | 27 | ~8,000 | Graph implementations for different scraping scenarios |
| `nodes/` | 31 | ~4,500 | Processing units that perform specific tasks |
| `models/` | 7 | ~800 | LLM provider wrappers and custom implementations |
| `prompts/` | 17 | ~1,200 | LLM prompt templates for different node types |
| `utils/` | 25 | ~3,000 | Utility functions (logging, HTML cleanup, tokenization) |
| `helpers/` | 6 | ~1,000 | Configuration helpers, token counts, schemas |
| `docloaders/` | 3 | ~1,500 | Document loading implementations (Playwright, etc.) |
| `builders/` | 1 | ~300 | Dynamic graph construction from prompts |
| `integrations/` | 2 | ~200 | Third-party framework integrations (Burr, Indexify) |
| `telemetry/` | 1 | ~200 | Anonymous usage tracking (PostHog) |

### Supporting Directories

| Directory | Purpose | Key Contents |
|-----------|---------|--------------|
| `tests/` | Unit & integration tests | 41 test files covering graphs, nodes, utilities |
| `examples/` | Usage examples | 16 directories with real-world use cases |
| `docs/` | Documentation | Sphinx-based API docs, ReadTheDocs configuration |
| `.github/workflows/` | CI/CD | 4 GitHub Actions workflows |

---

## 📊 File Size Distribution

### Largest Files (>10KB)

| File | Size | Purpose |
|------|------|---------|
| `docloaders/chromium.py` | 21.0K | Playwright-based web page fetching |
| `nodes/generate_code_node.py` | 17.7K | Python code generation from prompts |
| `nodes/fetch_node.py` | 14.9K | URL/file fetching with timeout support |
| `nodes/generate_answer_node.py` | 10.3K | Core LLM-based answer generation |

### Core Architecture Files

| File | Lines | Purpose |
|------|-------|---------|
| `graphs/base_graph.py` | 398 | Graph execution engine, node traversal |
| `graphs/abstract_graph.py` | 339 | Base abstract class, LLM factory |
| `graphs/smart_scraper_graph.py` | 305 | Most common graph implementation |
| `nodes/base_node.py` | 236 | Abstract base node class |

---

## 🔗 Module Dependencies

### External Dependencies (pyproject.toml)

```python
Core Dependencies:
├── langchain>=0.3.0              # LLM framework
├── langchain-openai>=0.1.22      # OpenAI integration
├── langchain-mistralai>=0.1.12   # Mistral integration
├── langchain_community>=0.2.9    # Community integrations
├── langchain-aws>=0.1.3          # AWS Bedrock
├── langchain-ollama>=0.1.3       # Ollama local models
│
├── playwright>=1.43.0            # Browser automation
├── beautifulsoup4>=4.12.3        # HTML parsing
├── pydantic>=2.10.2              # Data validation
│
├── tiktoken>=0.7                 # Token counting
├── duckduckgo-search>=7.2.1      # Web search
├── html2text>=2024.2.26          # HTML to text conversion
│
└── scrapegraph-py>=0.1.0         # Official API SDK
```

### Internal Module Flow

```
Entry Point (User Code)
    ↓
Graph Classes (graphs/)
    ↓ instantiate
AbstractGraph._create_llm() → models/
    ↓ use
BaseGraph.execute() → nodes/
    ↓ use
Nodes → utils/, helpers/, prompts/
    ↓ load content
docloaders/ → Playwright/requests
    ↓ track
telemetry/ → PostHog (opt-out)
```

---

## 🎯 Entry Points & User-Facing APIs

### Primary Entry Points

1. **Graph Classes** - `/scrapegraphai/graphs/*.py`
   - `SmartScraperGraph` - Most common single-page scraper
   - `SearchGraph` - Multi-page search and scrape
   - `DocumentScraperGraph` - PDF/document extraction
   - 24 other specialized graphs

2. **Node Classes** - `/scrapegraphai/nodes/*.py`
   - For custom graph construction
   - All inherit from `BaseNode`

3. **GraphBuilder** - `/scrapegraphai/builders/graph_builder.py`
   - Dynamic graph creation from natural language prompts

### Import Patterns

```python
# Most common imports
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.nodes import FetchNode, ParseNode, GenerateAnswerNode
from scrapegraphai.builders import GraphBuilder
```

---

## 🔧 Configuration & Setup Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies, tool configurations |
| `Makefile` | Development workflow automation (test, lint, build) |
| `.pre-commit-config.yaml` | Pre-commit hooks for code quality |
| `requirements.txt` | Core dependencies (for pip users) |
| `requirements-dev.txt` | Development dependencies |
| `uv.lock` | Locked dependency versions (uv package manager) |

---

## 📈 Growth Areas

Based on file counts and complexity:

1. **Graphs** (27 files) - Growing steadily with new use cases
2. **Nodes** (31 files) - Core processing units, stable
3. **Utils** (25 files) - Utility functions, gradual growth
4. **Prompts** (17 files) - LLM templates, tied to node growth

---

## 🚧 Areas Needing Attention

### Missing Directories

1. **`benchmarks/`** - No performance benchmarking infrastructure
2. **`scripts/`** - No deployment or utility scripts
3. **`migrations/`** - No database or config migration support

### Test Coverage Gaps

- Limited load testing
- No end-to-end integration tests with real LLM providers
- Missing performance regression tests

### Documentation Gaps

- No architectural decision records (ADRs)
- Limited inline documentation for design choices
- No API versioning strategy documented

---

## 📝 Key Observations

1. **Well-Organized**: Clear separation of concerns (graphs, nodes, utils)
2. **Modular**: Easy to find and modify specific functionality
3. **Test Coverage**: Good unit test coverage (41 files)
4. **Examples**: Comprehensive examples for all graph types
5. **Documentation**: Multiple documentation formats (Sphinx, Docusaurus, Jupyter)

---

## 🔗 Next Steps

- Review **[dependency-graph.md](./dependency-graph.md)** for dependency analysis
- Check **[metrics-summary.md](./metrics-summary.md)** for quantitative metrics
- See **[terminology-glossary.md](./terminology-glossary.md)** for project-specific terms
