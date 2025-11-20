# ScrapeGraphAI: Dependency Analysis

**Analysis Date:** 2025-11-20
**Commit SHA:** [32d5636ac3465edd0a8af47c6242f16a0beb35f5](https://github.com/ScrapeGraphAI/Scrapegraph-ai/commit/32d5636ac3465edd0a8af47c6242f16a0beb35f5)

---

## 📦 Core Dependencies

### Framework Dependencies

| Dependency | Version | Purpose | Last Major Update | Status |
|------------|---------|---------|-------------------|--------|
| **langchain** | ≥0.3.0 | LLM framework backbone | 2024 | ✅ Active |
| **langchain-openai** | ≥0.1.22 | OpenAI integration | 2024 | ✅ Active |
| **langchain-mistralai** | ≥0.1.12 | Mistral AI integration | 2024 | ✅ Active |
| **langchain_community** | ≥0.2.9 | Community integrations | 2024 | ✅ Active |
| **langchain-aws** | ≥0.1.3 | AWS Bedrock integration | 2024 | ✅ Active |
| **langchain-ollama** | ≥0.1.3 | Ollama local models | 2024 | ✅ Active |

**Analysis:**
- LangChain ecosystem is actively maintained
- Multiple provider-specific packages for flexibility
- Recent versions (all from 2024)
- **Trade-off**: Heavy dependency on LangChain ecosystem (vendor coupling)
- **Alternative**: Direct API calls would reduce dependencies but increase maintenance burden

---

### Web Scraping & Browser Automation

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **playwright** | ≥1.43.0 | Browser automation | ✅ Industry standard, actively maintained |
| **undetected-playwright** | ≥0.3.0 | Anti-detection browser | ⚠️ Less mature, more fragile |
| **beautifulsoup4** | ≥4.12.3 | HTML parsing | ✅ Stable, widely used |
| **html2text** | ≥2024.2.26 | HTML to text conversion | ✅ Active |
| **minify-html** | ≥0.15.0 | HTML minification | ✅ Fast Rust-based library |

**Analysis:**
- Playwright is excellent choice (maintained by Microsoft)
- `undetected-playwright` may need monitoring (anti-detection arms race)
- BeautifulSoup is stable and well-tested

**Security Note:** Browser automation introduces attack surface - ensure proper sandboxing.

---

### LLM & NLP Utilities

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **tiktoken** | ≥0.7 | Token counting (OpenAI) | ✅ Official OpenAI library |
| **semchunk** | ≥2.2.0 | Semantic text chunking | ⚠️ Smaller project, watch for updates |

**Analysis:**
- tiktoken is essential for accurate token counting
- semchunk is a nice-to-have but could be replaced with simpler chunking

---

### Data Validation & Configuration

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **pydantic** | ≥2.10.2 | Data validation | ✅ V2 - modern, fast, well-maintained |
| **python-dotenv** | ≥1.0.1 | Environment variables | ✅ Standard tool |
| **jsonschema** | ≥4.23.0 | JSON schema validation | ✅ Standard library |

**Analysis:**
- Pydantic v2 is excellent choice (performance + type safety)
- Standard tooling for configuration management

---

### Search & Proxy

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **duckduckgo-search** | ≥7.2.1 | Web search integration | ✅ Active, no API key needed |
| **free-proxy** | ≥1.1.1 | Free proxy rotation | ⚠️ Free proxies are unreliable |

**Analysis:**
- DuckDuckGo search is good choice (no API key, privacy-friendly)
- **Warning**: `free-proxy` may be unreliable in production
- **Recommendation**: Add support for paid proxy services (Bright Data, ScraperAPI)

---

### Utilities

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **tqdm** | ≥4.66.4 | Progress bars | ✅ Standard tool |
| **async-timeout** | ≥4.0.3 | Async timeout handling | ✅ Standard async utility |
| **simpleeval** | ≥1.0.0 | Safe expression evaluation | ⚠️ Security-sensitive |

**Analysis:**
- Standard utility libraries
- `simpleeval` is security-sensitive - ensure proper usage

---

### Official SDK

| Dependency | Version | Purpose | Notes |
|------------|---------|---------|-------|
| **scrapegraph-py** | ≥0.1.0 | Official API SDK | ✅ Self-maintained |

**Analysis:**
- Integration with commercial API offering
- Allows hybrid local/cloud usage

---

## 🔌 Optional Dependencies

### Burr Integration (Workflow Management)

```toml
[project.optional-dependencies]
burr = ["burr[start]==0.22.1"]
```

- **Purpose**: Advanced workflow management
- **Trade-off**: Adds complexity, but provides better observability
- **Status**: ✅ Active project

### Documentation Tools

```toml
docs = ["sphinx==6.0", "furo==2024.5.6"]
```

- **Purpose**: API documentation generation
- **Status**: ✅ Standard documentation stack

### OCR Support

```toml
ocr = [
    "surya-ocr>=0.5.0",
    "matplotlib>=3.7.2",
    "ipywidgets>=8.1.0",
    "pillow>=10.4.0",
]
```

- **Purpose**: Optical Character Recognition for images/PDFs
- **Status**: ✅ Modern OCR solution
- **Note**: Heavy dependencies, only install if needed

---

## 🛠️ Development Dependencies

### Testing Stack

| Dependency | Version | Purpose |
|------------|---------|---------|
| **pytest** | ≥8.0.0 | Test framework |
| **pytest-mock** | ≥3.14.0 | Mocking support |
| **pytest-asyncio** | ≥0.25.0 | Async test support |
| **pytest-sugar** | ≥1.0.0 | Better test output |
| **pytest-cov** | ≥4.1.0 | Coverage reporting |

**Analysis:** ✅ Modern, comprehensive testing stack

---

### Code Quality Tools

| Dependency | Version | Purpose | Config |
|------------|---------|---------|--------|
| **ruff** | ≥0.2.0 | Fast Python linter | `pyproject.toml` |
| **black** | ≥24.2.0 | Code formatter | Line length: 88 |
| **isort** | ≥5.13.2 | Import sorting | Profile: black |
| **pylint** | ≥3.2.5 | Traditional linter | Custom rules |
| **mypy** | ≥1.8.0 | Type checking | Strict mode |

**Analysis:**
- ✅ Excellent quality tooling
- Ruff is modern, fast alternative to flake8/pylint
- Black + isort ensure consistent formatting
- MyPy in strict mode catches type errors

---

### Build & Automation

| Dependency | Version | Purpose |
|------------|---------|---------|
| **hatchling** | 1.26.3 | Build backend |
| **poethepoet** | ≥0.32.0 | Task runner |
| **pre-commit** | ≥3.6.0 | Git hooks |

**Analysis:**
- Modern build tooling
- Pre-commit hooks ensure quality before commit

---

## 🔍 Dependency Risk Analysis

### Security Vulnerabilities

To check for known vulnerabilities:

```bash
# Check for security issues
pip-audit
# or
uv pip check
```

**Recommendation**: Run security checks in CI/CD pipeline.

---

### Deprecated or Abandoned Packages

| Package | Status | Risk | Recommendation |
|---------|--------|------|----------------|
| ✅ All core deps | Active | Low | Continue monitoring |
| ⚠️ free-proxy | Sporadic updates | Medium | Consider paid alternatives |
| ⚠️ undetected-playwright | Niche | Medium | Monitor for breaking changes |

---

### License Compatibility

All core dependencies use permissive licenses:
- **MIT**: langchain, playwright, pydantic, etc.
- **Apache 2.0**: Some LangChain components
- **BSD**: BeautifulSoup

**Analysis:** ✅ No license conflicts with MIT-licensed project

---

## 📊 Dependency Graph Visualization

### High-Level Architecture

```
┌─────────────────────────────────────────┐
│         User Application Code           │
└──────────────┬──────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────┐
│    ScrapeGraphAI (Public API)           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Graphs  │  │  Nodes  │  │ Builder │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└──────────┬─────────┬──────────┬─────────┘
           │         │          │
           ↓         ↓          ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  LangChain   │  │  Playwright  │  │   Pydantic   │
│  Ecosystem   │  │  + BS4       │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Dependency Layers

```
Layer 1: User Code
    ↓
Layer 2: ScrapeGraphAI Core (graphs, nodes)
    ↓
Layer 3: Framework Layer (LangChain, Playwright)
    ↓
Layer 4: Provider SDKs (OpenAI, Anthropic, etc.)
    ↓
Layer 5: HTTP/Network (requests, httpx)
```

---

## 🎯 Dependency Trade-offs Analysis

### 1. LangChain Dependency

**Chosen:** LangChain as LLM abstraction layer

**Alternatives:**
- Direct provider SDKs (OpenAI, Anthropic, etc.)
- LiteLLM (lighter abstraction)
- Custom abstraction layer

**Trade-offs:**
| Aspect | LangChain | Direct SDKs | Custom Layer |
|--------|-----------|-------------|--------------|
| **Dev Speed** | ✅ Fast | ⚠️ Slow | ⚠️ Very Slow |
| **Flexibility** | ✅ High | ⚠️ Low | ✅ High |
| **Maintenance** | ⚠️ External | ✅ Provider | ⚠️ Self |
| **Bundle Size** | ⚠️ Large | ✅ Small | ✅ Small |
| **Breaking Changes** | ⚠️ Frequent | ⚠️ Occasional | ✅ Controlled |

**Verdict:** ✅ LangChain is the right choice for this project
- Multi-provider support is core feature
- Rapid development outweighs bundle size concerns
- LangChain ecosystem is mature and active

---

### 2. Playwright vs Selenium

**Chosen:** Playwright

**Alternatives:** Selenium, Puppeteer, HTTPx

**Trade-offs:**
| Aspect | Playwright | Selenium | HTTPx |
|--------|------------|----------|-------|
| **Speed** | ✅ Fast | ⚠️ Slower | ✅ Fastest |
| **Modern Web** | ✅ Excellent | ⚠️ Good | ❌ Limited |
| **Anti-Detection** | ✅ Better | ⚠️ Detected | ✅ Best |
| **Headless** | ✅ Native | ⚠️ Clunky | N/A |
| **Maintenance** | ✅ Microsoft | ⚠️ Community | ✅ Encode |

**Verdict:** ✅ Playwright is excellent choice
- Modern, fast, well-maintained
- Better than Selenium for headless use
- HTTPx would miss JavaScript-rendered content

---

### 3. Pydantic v2

**Chosen:** Pydantic v2

**Alternatives:** dataclasses, attrs, marshmallow

**Trade-offs:**
| Aspect | Pydantic v2 | dataclasses | attrs |
|--------|-------------|-------------|-------|
| **Validation** | ✅ Built-in | ❌ Manual | ⚠️ Plugin |
| **Performance** | ✅ Fast (Rust) | ✅ Fast | ✅ Fast |
| **JSON Schema** | ✅ Native | ❌ Manual | ⚠️ Plugin |
| **Type Hints** | ✅ Excellent | ✅ Good | ✅ Good |

**Verdict:** ✅ Pydantic v2 is perfect fit
- Schema validation is core requirement
- JSON schema generation for LLMs
- Performance improvements in v2

---

## 🔄 Version Pinning Strategy

### Current Strategy

```toml
# Core dependencies use minimum version specifiers
langchain>=0.3.0
playwright>=1.43.0
pydantic>=2.10.2

# Dev dependencies use minimum version specifiers
pytest>=8.0.0
ruff>=0.2.0

# Build backend uses exact version
hatchling==1.26.3

# Optional: Burr uses exact version
burr[start]==0.22.1
```

**Analysis:**
- ✅ Flexible for users (minimum versions)
- ⚠️ Risk of breaking changes in minor versions
- ✅ `uv.lock` provides reproducibility

**Recommendation:**
- Continue minimum version strategy for libraries
- Use `uv.lock` for reproducible builds
- Test against latest versions in CI/CD
- Document tested version ranges

---

## 📈 Dependency Weight Analysis

### Bundle Size Implications

| Category | Est. Size | Impact |
|----------|-----------|--------|
| LangChain + providers | ~50MB | ⚠️ Heavy |
| Playwright + browsers | ~300MB | ⚠️ Very Heavy |
| ML/NLP (tiktoken) | ~5MB | ✅ Light |
| Utilities | ~10MB | ✅ Light |
| **Total** | **~365MB** | ⚠️ Heavy |

**Analysis:**
- Playwright browsers are the largest component (necessary trade-off)
- LangChain ecosystem is substantial but provides significant value
- **Not suitable** for serverless/edge deployments without optimization
- **Well-suited** for containers, VMs, local development

---

## 🚧 Missing Dependencies

### Observability
- ❌ No structured logging library (e.g., structlog)
- ❌ No tracing library (e.g., OpenTelemetry)
- ❌ No metrics library (e.g., Prometheus client)

**Recommendation:** Add observability dependencies (see RFC-0002)

---

### Caching
- ❌ No caching library (e.g., Redis, diskcache)
- ❌ No LLM response caching

**Recommendation:** Add caching layer (see RFC-0001)

---

### Performance
- ❌ No async HTTP library (httpx) for parallel fetching
- ❌ No connection pooling for APIs

**Recommendation:** Add httpx for parallel operations

---

## 🔐 Security Considerations

### Vulnerable Packages (Check Regularly)

```bash
# Check for known vulnerabilities
pip-audit

# Example findings (run to verify):
# - Check for CVEs in playwright, beautifulsoup4
# - Monitor undetected-playwright for security issues
```

### Dependency Confusion Risks

- ✅ All dependencies from PyPI (trusted source)
- ⚠️ `scrapegraph-py` is self-published - ensure PyPI account security

---

## 🎯 Recommendations

### Immediate (Quick Wins)

1. **Add security scanning to CI/CD**
   ```yaml
   - name: Security scan
     run: pip-audit
   ```

2. **Document tested version ranges**
   - Create TESTED_VERSIONS.md
   - List known working versions

3. **Add dependabot configuration**
   ```yaml
   # .github/dependabot.yml
   version: 2
   updates:
     - package-ecosystem: "pip"
       directory: "/"
       schedule:
         interval: "weekly"
   ```

### Short-term (1-2 months)

1. **Evaluate lighter LLM abstraction** (if bundle size becomes issue)
2. **Add caching dependencies** (Redis or diskcache)
3. **Add observability stack** (structlog, OpenTelemetry)

### Long-term (3-6 months)

1. **Create minimal install variant**
   ```toml
   [project.optional-dependencies]
   minimal = ["langchain-core", "httpx", "beautifulsoup4"]
   full = ["langchain", "playwright", ...]  # Current default
   ```

2. **Evaluate browser-less mode**
   - Use httpx for static pages
   - Playwright only for JS-heavy sites
   - Could reduce bundle size by 80%

---

## 📊 Dependency Health Score

| Category | Score | Notes |
|----------|-------|-------|
| **Maintenance** | 9/10 | All actively maintained |
| **Security** | 8/10 | Good, needs automated scanning |
| **Licensing** | 10/10 | All permissive licenses |
| **Stability** | 8/10 | Some niche deps (free-proxy) |
| **Performance** | 8/10 | Heavy but necessary |
| **Documentation** | 9/10 | Well-documented deps |

**Overall Health:** ✅ **8.7/10** - Excellent dependency management

---

## 🔗 Next Steps

- Review **[metrics-summary.md](./metrics-summary.md)** for code metrics
- Check **[terminology-glossary.md](./terminology-glossary.md)** for project terms
- See **[../rfcs/](../rfcs/)** for dependency-related improvement proposals
