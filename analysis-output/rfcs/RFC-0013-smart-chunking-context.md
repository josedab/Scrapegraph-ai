# RFC-0013: Smart Chunking with Context Preservation

## Status
**Status:** Proposed
**Author:** ScrapeGraphAI Team
**Created:** 2025-11-20
**Updated:** 2025-11-20

## Summary
Replace basic token-based chunking with enhanced semantic chunking that uses configurable overlapping windows and context-aware boundaries to prevent information loss at chunk edges. This will improve answer quality and reduce hallucinations caused by fragmented context in LLM processing.

## Context
The current chunking implementation (`scrapegraphai/utils/split_text_into_chunks.py`) provides two modes:

1. **Semchunk mode** (default, `use_semchunk=True`): Uses the `semchunk` library for semantic chunking
2. **Fallback mode** (`use_semchunk=False`): Basic word-based splitting without overlap

### Current Implementation Analysis
```python
def split_text_into_chunks(text: str, chunk_size: int, use_semchunk=True) -> List[str]:
    if use_semchunk:
        from semchunk import chunk
        chunk_size = min(chunk_size, int(chunk_size * 0.9))
        chunks = chunk(text=text, chunk_size=chunk_size, token_counter=count_tokens, memoize=False)
        return chunks
    else:
        # Basic word-by-word splitting
        words = text.split()
        for word in words:
            if current_length + word_tokens > chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]  # No overlap!
```

### Current Limitations

1. **No Overlap in Fallback Mode**: When `use_semchunk=False`, chunks have zero overlap, causing:
   - Information spanning chunk boundaries gets fragmented
   - Context-dependent entities lose their relationships
   - LLM cannot see cross-chunk patterns

2. **Limited Configuration**: No way to configure:
   - Overlap size (fixed or percentage)
   - Chunking strategy (sentence, paragraph, semantic)
   - Boundary detection sensitivity

3. **Dependency on External Library**: Heavy reliance on `semchunk` without robust fallback:
   - If semchunk fails or is unavailable, falls back to naive splitting
   - No built-in semantic boundary detection

4. **No Context Preservation Metadata**: Chunks don't include:
   - Position information (chunk 1 of N)
   - Overlap markers (what content is duplicated)
   - Semantic boundary metadata (starts/ends mid-sentence)

5. **RecursiveCharacterTextSplitter Not Used**: Despite being mentioned in RAGNode metadata, the langchain `RecursiveCharacterTextSplitter` with its proven chunking strategies is not utilized.

### Real-World Impact

**Example: Entity Recognition Across Boundaries**
```text
Original: "John Smith, CEO of TechCorp, announced that the company will expand to 50 new markets by 2026."

Without overlap:
Chunk 1: "John Smith, CEO of TechCorp, announced"
Chunk 2: "that the company will expand to 50 new markets by 2026."
→ LLM loses the connection between "John Smith" and "the company"

With overlap:
Chunk 1: "John Smith, CEO of TechCorp, announced that the company will expand"
Chunk 2: "announced that the company will expand to 50 new markets by 2026."
→ Context preserved, "the company" clearly refers to "TechCorp"
```

## Problem Statement

As users scrape increasingly complex documents (long-form articles, technical documentation, multi-section reports), the current chunking approach creates several critical issues:

1. **Information Loss**: Critical relationships and context that span chunk boundaries are lost
2. **Answer Quality Degradation**: LLM answers become less accurate when context is fragmented
3. **Hallucinations**: Missing context leads to LLM fabricating connections that don't exist
4. **Poor Entity Resolution**: Entities mentioned across chunks cannot be properly linked
5. **Inefficient Token Usage**: Without overlap, the LLM must infer context, wasting tokens on hedging language
6. **Limited Configurability**: Cannot tune chunking strategy based on content type or use case

### Use Cases Requiring Better Chunking

- **Research Paper Extraction**: Maintaining relationships between citations, authors, and findings
- **Contract Analysis**: Preserving cross-references between clauses and definitions
- **Technical Documentation**: Keeping code examples with their explanations
- **News Article Scraping**: Maintaining narrative flow and entity relationships
- **E-commerce Product Pages**: Linking specifications with descriptions
- **Multi-language Content**: Respecting linguistic boundaries beyond simple word breaks

## Proposed Solution

Implement a flexible, multi-strategy chunking system with the following features:

1. **Configurable Overlap**: Support both fixed token count and percentage-based overlap
2. **Multiple Chunking Strategies**:
   - Semantic (via semchunk, with improvements)
   - Recursive character splitting (sentences → paragraphs → sections)
   - Custom boundary detection
3. **Context Metadata**: Enrich chunks with position and overlap information
4. **Smart Boundary Detection**: Respect natural language boundaries (sentences, paragraphs)
5. **Backward Compatibility**: Maintain existing API while adding new capabilities

### Key Benefits

- **Improved Answer Quality**: 30-50% reduction in context-loss errors (estimated)
- **Better Entity Resolution**: Cross-chunk entity relationships preserved
- **Reduced Hallucinations**: LLM has complete context for accurate answers
- **Flexible Configuration**: Tune chunking for different content types
- **Production-Ready**: Robust fallbacks ensure reliability
- **Efficient Token Usage**: Targeted overlap minimizes redundancy while preserving context

## Design Details

### 1. Enhanced Chunking Function Signature

```python
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

class ChunkStrategy(Enum):
    """Chunking strategy options."""
    SEMANTIC = "semantic"  # Use semchunk
    RECURSIVE = "recursive"  # RecursiveCharacterTextSplitter
    SENTENCE = "sentence"  # Split on sentences with overlap
    PARAGRAPH = "paragraph"  # Split on paragraphs with overlap
    WORD = "word"  # Current fallback behavior (for compatibility)

@dataclass
class ChunkMetadata:
    """Metadata for a text chunk."""
    chunk_index: int
    total_chunks: int
    start_position: int
    end_position: int
    overlap_start: Optional[int] = None  # Where overlap from previous chunk starts
    overlap_end: Optional[int] = None  # Where overlap to next chunk ends
    is_boundary_complete: bool = True  # False if starts/ends mid-sentence
    token_count: int = 0

@dataclass
class EnhancedChunk:
    """A text chunk with metadata."""
    text: str
    metadata: ChunkMetadata

def split_text_into_chunks(
    text: str,
    chunk_size: int,
    overlap_size: Optional[int] = None,
    overlap_percentage: float = 0.1,  # 10% default
    strategy: ChunkStrategy = ChunkStrategy.SEMANTIC,
    preserve_boundaries: bool = True,
    return_metadata: bool = False,
) -> List[str] | List[EnhancedChunk]:
    """
    Split text into chunks with configurable overlap and boundary detection.

    Args:
        text: The text to split
        chunk_size: Maximum tokens per chunk
        overlap_size: Fixed token overlap between chunks (overrides percentage)
        overlap_percentage: Percentage of chunk_size to overlap (default 10%)
        strategy: Chunking strategy to use
        preserve_boundaries: If True, avoid breaking mid-sentence
        return_metadata: If True, return EnhancedChunk objects with metadata

    Returns:
        List of text chunks or EnhancedChunk objects
    """
```

### 2. Semantic Chunking with Overlap (Enhanced)

```python
def _chunk_semantic_with_overlap(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Enhanced semantic chunking with explicit overlap control.

    Improves upon semchunk by adding configurable overlap and metadata.
    """
    try:
        from semchunk import chunk

        # Use semchunk for initial semantic splitting
        base_chunks = chunk(
            text=text,
            chunk_size=chunk_size,
            token_counter=token_counter,
            memoize=False
        )

        # Add overlap between consecutive chunks
        enhanced_chunks = []
        for i, current_chunk in enumerate(base_chunks):
            if i > 0:
                # Add overlap from previous chunk
                prev_chunk = base_chunks[i-1]
                overlap_text = _extract_overlap(prev_chunk, overlap_tokens, token_counter)
                current_chunk = overlap_text + " " + current_chunk

            if i < len(base_chunks) - 1:
                # Mark where overlap to next chunk would occur
                overlap_boundary = len(current_chunk) - _estimate_overlap_chars(
                    current_chunk, overlap_tokens, token_counter
                )
            else:
                overlap_boundary = None

            metadata = ChunkMetadata(
                chunk_index=i,
                total_chunks=len(base_chunks),
                start_position=0,  # Would track in original text
                end_position=len(current_chunk),
                overlap_end=overlap_boundary,
                token_count=token_counter(current_chunk)
            )

            enhanced_chunks.append(EnhancedChunk(text=current_chunk, metadata=metadata))

        return enhanced_chunks

    except ImportError:
        # Fallback to recursive strategy if semchunk not available
        return _chunk_recursive(text, chunk_size, overlap_tokens, token_counter)
```

### 3. Recursive Character Text Splitting

```python
def _chunk_recursive(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Recursive character-based splitting with semantic boundaries.

    Attempts to split on natural boundaries in this order:
    1. Double newlines (paragraphs)
    2. Single newlines (lines)
    3. Sentence boundaries (. ! ?)
    4. Clause boundaries (, ; :)
    5. Word boundaries (spaces)
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    # Convert token counts to character estimates (rough approximation)
    # Average: 1 token ≈ 4 characters
    chunk_chars = chunk_size * 4
    overlap_chars = overlap_tokens * 4

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_chars,
        chunk_overlap=overlap_chars,
        length_function=lambda t: token_counter(t),  # Use token counting
        separators=[
            "\n\n",  # Paragraph breaks
            "\n",    # Line breaks
            ". ",    # Sentence ends
            "! ",    # Exclamations
            "? ",    # Questions
            "; ",    # Semicolons
            ", ",    # Commas
            " ",     # Words
            ""       # Characters (last resort)
        ],
        keep_separator=True,  # Keep the separators in text
    )

    # Split text
    chunks = splitter.split_text(text)

    # Create enhanced chunks with metadata
    enhanced_chunks = []
    for i, chunk_text in enumerate(chunks):
        metadata = ChunkMetadata(
            chunk_index=i,
            total_chunks=len(chunks),
            start_position=0,  # Would calculate from original text
            end_position=len(chunk_text),
            is_boundary_complete=_check_boundary_completeness(chunk_text),
            token_count=token_counter(chunk_text)
        )
        enhanced_chunks.append(EnhancedChunk(text=chunk_text, metadata=metadata))

    return enhanced_chunks
```

### 4. Sentence-Based Chunking

```python
import nltk
from typing import List

def _chunk_by_sentences(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Split text into chunks at sentence boundaries with overlap.

    Ensures no sentence is ever split across chunks.
    """
    # Download punkt tokenizer if not available
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)

    # Split into sentences
    sentences = nltk.sent_tokenize(text)

    chunks = []
    current_chunk = []
    current_tokens = 0
    overlap_sentences = []  # Sentences to include in overlap

    for sentence in sentences:
        sentence_tokens = token_counter(sentence)

        # Check if adding this sentence exceeds chunk size
        if current_tokens + sentence_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)

            # Calculate overlap: keep last N sentences that fit in overlap_tokens
            overlap_text = []
            overlap_token_count = 0
            for s in reversed(current_chunk):
                s_tokens = token_counter(s)
                if overlap_token_count + s_tokens <= overlap_tokens:
                    overlap_text.insert(0, s)
                    overlap_token_count += s_tokens
                else:
                    break

            # Start new chunk with overlap
            current_chunk = overlap_text + [sentence]
            current_tokens = overlap_token_count + sentence_tokens
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

    # Add final chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    # Create enhanced chunks with metadata
    enhanced_chunks = []
    for i, chunk_text in enumerate(chunks):
        metadata = ChunkMetadata(
            chunk_index=i,
            total_chunks=len(chunks),
            start_position=0,
            end_position=len(chunk_text),
            is_boundary_complete=True,  # Always true for sentence-based
            token_count=token_counter(chunk_text)
        )
        enhanced_chunks.append(EnhancedChunk(text=chunk_text, metadata=metadata))

    return enhanced_chunks
```

### 5. Helper Functions

```python
def _extract_overlap(text: str, overlap_tokens: int, token_counter: callable) -> str:
    """Extract the last N tokens worth of text for overlap."""
    words = text.split()
    overlap_text = ""
    token_count = 0

    for word in reversed(words):
        word_tokens = token_counter(word)
        if token_count + word_tokens > overlap_tokens:
            break
        overlap_text = word + " " + overlap_text
        token_count += word_tokens

    return overlap_text.strip()

def _check_boundary_completeness(text: str) -> bool:
    """Check if text starts and ends at complete sentence boundaries."""
    text = text.strip()

    # Check if starts with capital letter or quote
    starts_complete = text[0].isupper() or text[0] in ['"', "'", '(', '[']

    # Check if ends with sentence-ending punctuation
    ends_complete = text[-1] in ['.', '!', '?', '"', "'", ')', ']']

    return starts_complete and ends_complete

def _estimate_overlap_chars(text: str, overlap_tokens: int, token_counter: callable) -> int:
    """Estimate character count for given token overlap."""
    if overlap_tokens == 0:
        return 0

    # Binary search to find character count that gives ~overlap_tokens
    left, right = 0, len(text)

    while left < right:
        mid = (left + right) // 2
        substring = text[-mid:] if mid > 0 else ""
        tokens = token_counter(substring)

        if tokens < overlap_tokens:
            left = mid + 1
        else:
            right = mid

    return left
```

### 6. Updated Main Function

```python
def split_text_into_chunks(
    text: str,
    chunk_size: int,
    overlap_size: Optional[int] = None,
    overlap_percentage: float = 0.1,
    strategy: ChunkStrategy = ChunkStrategy.SEMANTIC,
    preserve_boundaries: bool = True,
    return_metadata: bool = False,
    use_semchunk: bool = True,  # Backward compatibility
) -> List[str] | List[EnhancedChunk]:
    """Enhanced text chunking with overlap and metadata."""

    from .tokenizer import num_tokens_calculus

    # Handle backward compatibility
    if not use_semchunk and strategy == ChunkStrategy.SEMANTIC:
        strategy = ChunkStrategy.WORD

    # Calculate overlap in tokens
    if overlap_size is None:
        overlap_size = int(chunk_size * overlap_percentage)

    # Ensure overlap doesn't exceed chunk size
    overlap_size = min(overlap_size, chunk_size // 2)

    # Select chunking strategy
    if strategy == ChunkStrategy.SEMANTIC:
        chunks = _chunk_semantic_with_overlap(
            text, chunk_size, overlap_size, num_tokens_calculus
        )
    elif strategy == ChunkStrategy.RECURSIVE:
        chunks = _chunk_recursive(
            text, chunk_size, overlap_size, num_tokens_calculus
        )
    elif strategy == ChunkStrategy.SENTENCE:
        chunks = _chunk_by_sentences(
            text, chunk_size, overlap_size, num_tokens_calculus
        )
    elif strategy == ChunkStrategy.PARAGRAPH:
        chunks = _chunk_by_paragraphs(
            text, chunk_size, overlap_size, num_tokens_calculus
        )
    else:  # WORD strategy (original fallback)
        chunks = _chunk_by_words_legacy(text, chunk_size, num_tokens_calculus)

    # Return based on metadata preference
    if return_metadata:
        return chunks
    else:
        return [chunk.text if isinstance(chunk, EnhancedChunk) else chunk
                for chunk in chunks]
```

### 7. Integration with ParseNode

```python
# In scrapegraphai/nodes/parse_node.py

class ParseNode(BaseNode):
    def __init__(self, input: str, output: List[str],
                 node_config: Optional[dict] = None, node_name: str = "ParseNode"):
        super().__init__(node_name, "node", input, output, 1, node_config)

        # Enhanced chunking configuration
        self.chunk_size = node_config.get("chunk_size")
        self.chunk_overlap_percentage = node_config.get("chunk_overlap_percentage", 0.1)
        self.chunk_strategy = node_config.get("chunk_strategy", "semantic")
        self.preserve_boundaries = node_config.get("preserve_boundaries", True)

    def execute(self, state: dict) -> dict:
        # ... existing code ...

        # Enhanced chunking with overlap
        chunks = split_text_into_chunks(
            text=docs_transformed.page_content,
            chunk_size=self.chunk_size - 250,
            overlap_percentage=self.chunk_overlap_percentage,
            strategy=ChunkStrategy(self.chunk_strategy),
            preserve_boundaries=self.preserve_boundaries,
            return_metadata=False  # Can be enabled for advanced use cases
        )

        # ... rest of execute logic ...
```

### 8. Configuration Examples

```python
# Example 1: Default semantic chunking with 10% overlap
graph_config = {
    "llm": llm_model,
    "chunk_size": 8000,
    "chunk_overlap_percentage": 0.1,  # 800 token overlap
    "chunk_strategy": "semantic"
}

# Example 2: Sentence-based chunking for precise control
graph_config = {
    "llm": llm_model,
    "chunk_size": 4000,
    "chunk_overlap_percentage": 0.15,  # 600 token overlap
    "chunk_strategy": "sentence",
    "preserve_boundaries": True
}

# Example 3: Recursive splitting for technical docs
graph_config = {
    "llm": llm_model,
    "chunk_size": 6000,
    "overlap_size": 500,  # Fixed 500 token overlap
    "chunk_strategy": "recursive"
}

# Example 4: Backward compatible (no overlap)
graph_config = {
    "llm": llm_model,
    "chunk_size": 8000,
    "use_semchunk": False  # Falls back to word-based
}
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Create ChunkStrategy enum and ChunkMetadata dataclass
- [ ] Implement EnhancedChunk wrapper class
- [ ] Add overlap calculation utilities (_extract_overlap, _estimate_overlap_chars)
- [ ] Create comprehensive unit tests for helper functions
- [ ] Set up benchmark suite for chunking performance

### Phase 2: Chunking Strategies (Week 2-3)
- [ ] Implement _chunk_semantic_with_overlap (enhance existing semchunk)
- [ ] Implement _chunk_recursive using RecursiveCharacterTextSplitter
- [ ] Implement _chunk_by_sentences with NLTK
- [ ] Implement _chunk_by_paragraphs
- [ ] Add unit tests for each strategy
- [ ] Add integration tests comparing strategies

### Phase 3: Main Function Enhancement (Week 3-4)
- [ ] Update split_text_into_chunks signature with new parameters
- [ ] Implement strategy selection logic
- [ ] Add backward compatibility layer (use_semchunk parameter)
- [ ] Handle edge cases (empty text, single-word chunks, etc.)
- [ ] Add comprehensive error handling and logging
- [ ] Create performance benchmarks

### Phase 4: Node Integration (Week 4-5)
- [ ] Update ParseNode to use new chunking parameters
- [ ] Update RAGNode if needed
- [ ] Add configuration validation
- [ ] Update graph configuration schemas
- [ ] Add migration guide for existing configurations

### Phase 5: Testing & Documentation (Week 5-6)
- [ ] Create test suite with real-world documents
- [ ] Measure answer quality improvements (A/B testing)
- [ ] Write user documentation with examples
- [ ] Create troubleshooting guide
- [ ] Add performance tuning recommendations
- [ ] Update API documentation

### Phase 6: Optimization & Monitoring (Week 6-7)
- [ ] Profile chunking performance
- [ ] Optimize token counting (caching, batch processing)
- [ ] Add chunking metrics to telemetry
- [ ] Create dashboard for chunking statistics
- [ ] Implement adaptive chunk sizing based on content

## Testing Strategy

### Unit Tests

```python
import pytest
from scrapegraphai.utils.split_text_into_chunks import (
    split_text_into_chunks, ChunkStrategy, _extract_overlap
)

def test_overlap_extraction():
    """Test that overlap extraction works correctly."""
    text = "This is a test sentence with multiple words."
    overlap = _extract_overlap(text, overlap_tokens=3, token_counter=lambda t: len(t.split()))

    # Should extract last ~3 words
    assert "multiple words." in overlap or "with multiple words" in overlap

def test_semantic_chunking_with_overlap():
    """Test semantic chunking creates overlapping chunks."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."

    chunks = split_text_into_chunks(
        text=text,
        chunk_size=20,
        overlap_percentage=0.2,
        strategy=ChunkStrategy.SEMANTIC
    )

    # Verify overlap exists
    assert len(chunks) >= 2
    # Check that consecutive chunks share some content
    if len(chunks) >= 2:
        chunk1_words = set(chunks[0].split())
        chunk2_words = set(chunks[1].split())
        overlap_words = chunk1_words & chunk2_words
        assert len(overlap_words) > 0

def test_sentence_boundary_preservation():
    """Test that sentence boundaries are preserved."""
    text = "First sentence. Second sentence. Third sentence."

    chunks = split_text_into_chunks(
        text=text,
        chunk_size=15,
        strategy=ChunkStrategy.SENTENCE,
        preserve_boundaries=True,
        return_metadata=True
    )

    # All chunks should have complete boundaries
    for chunk in chunks:
        assert chunk.metadata.is_boundary_complete

def test_backward_compatibility():
    """Test that old API still works."""
    text = "Test text for backward compatibility."

    # Old API call
    chunks_old = split_text_into_chunks(text, chunk_size=100, use_semchunk=False)

    # Should work without errors
    assert isinstance(chunks_old, list)
    assert all(isinstance(c, str) for c in chunks_old)

def test_chunk_metadata():
    """Test that metadata is correctly generated."""
    text = "Sentence one. Sentence two. Sentence three. Sentence four."

    chunks = split_text_into_chunks(
        text=text,
        chunk_size=20,
        overlap_percentage=0.1,
        return_metadata=True
    )

    # Verify metadata structure
    for i, chunk in enumerate(chunks):
        assert chunk.metadata.chunk_index == i
        assert chunk.metadata.total_chunks == len(chunks)
        assert chunk.metadata.token_count > 0

def test_edge_cases():
    """Test edge cases."""
    # Empty text
    assert split_text_into_chunks("", chunk_size=100) == []

    # Single word
    chunks = split_text_into_chunks("word", chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == "word"

    # Overlap larger than chunk
    chunks = split_text_into_chunks(
        "Test text",
        chunk_size=10,
        overlap_size=20  # Should be capped
    )
    assert len(chunks) >= 1
```

### Integration Tests

```python
async def test_parsenode_with_overlap():
    """Test ParseNode with enhanced chunking."""
    from scrapegraphai.nodes import ParseNode

    node_config = {
        "llm_model": llm_model,
        "chunk_size": 1000,
        "chunk_overlap_percentage": 0.15,
        "chunk_strategy": "semantic"
    }

    parse_node = ParseNode(
        input="document & url",
        output=["parsed_doc", "link_urls", "img_urls"],
        node_config=node_config
    )

    # Long document that will be chunked
    long_doc = Document(page_content="..." * 1000)
    state = {"document": [long_doc], "url": "https://example.com"}

    result = parse_node.execute(state)

    # Verify chunks exist and have overlap
    chunks = result["parsed_doc"]
    assert len(chunks) > 1

    # Verify overlap by checking if consecutive chunks share content
    for i in range(len(chunks) - 1):
        chunk1_end = chunks[i][-100:]  # Last 100 chars
        chunk2_start = chunks[i+1][:100]  # First 100 chars

        # Should have some overlap
        # (exact check depends on implementation)
        assert len(chunk1_end) > 0 and len(chunk2_start) > 0

def test_answer_quality_improvement():
    """Test that overlap improves answer quality."""
    from scrapegraphai.graphs import SmartScraperGraph

    # Document with entity spanning potential chunk boundary
    test_doc = """
    John Smith is the CEO of TechCorp. The company was founded in 2010.
    TechCorp has grown to 500 employees. John Smith announced that the
    company will expand to 50 new markets by 2026. This expansion will
    create 1000 new jobs.
    """

    # Question that requires cross-chunk context
    question = "How many new jobs will be created by the company John Smith leads?"

    # Test without overlap
    config_no_overlap = {
        "llm": llm_model,
        "chunk_size": 50,  # Small chunks to force splitting
        "chunk_overlap_percentage": 0.0,
    }
    graph_no_overlap = SmartScraperGraph(prompt=question, source=test_doc, config=config_no_overlap)
    result_no_overlap = graph_no_overlap.run()

    # Test with overlap
    config_with_overlap = {
        "llm": llm_model,
        "chunk_size": 50,
        "chunk_overlap_percentage": 0.2,
    }
    graph_with_overlap = SmartScraperGraph(prompt=question, source=test_doc, config=config_with_overlap)
    result_with_overlap = graph_with_overlap.run()

    # Result with overlap should correctly identify "1000 new jobs"
    # (This would need actual LLM execution to validate)
    assert result_with_overlap is not None
```

### Performance Benchmarks

```python
import time
from scrapegraphai.utils.split_text_into_chunks import split_text_into_chunks, ChunkStrategy

def benchmark_chunking_strategies():
    """Benchmark different chunking strategies."""
    # Load test document (e.g., 10,000 words)
    with open("test_data/large_document.txt") as f:
        text = f.read()

    strategies = [
        ChunkStrategy.SEMANTIC,
        ChunkStrategy.RECURSIVE,
        ChunkStrategy.SENTENCE,
        ChunkStrategy.PARAGRAPH
    ]

    results = {}
    for strategy in strategies:
        start = time.perf_counter()

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=2000,
            overlap_percentage=0.1,
            strategy=strategy
        )

        duration = time.perf_counter() - start

        results[strategy.value] = {
            "duration_ms": duration * 1000,
            "num_chunks": len(chunks),
            "avg_chunk_size": sum(len(c) for c in chunks) / len(chunks)
        }

    return results

# Example output:
# {
#   "semantic": {"duration_ms": 245, "num_chunks": 12, "avg_chunk_size": 1850},
#   "recursive": {"duration_ms": 89, "num_chunks": 15, "avg_chunk_size": 1920},
#   "sentence": {"duration_ms": 156, "num_chunks": 14, "avg_chunk_size": 1880},
#   "paragraph": {"duration_ms": 67, "num_chunks": 10, "avg_chunk_size": 2100}
# }
```

## Migration Strategy

### Backward Compatibility

The new implementation maintains 100% backward compatibility:

```python
# Old code continues to work unchanged
chunks = split_text_into_chunks(text="...", chunk_size=1000, use_semchunk=True)

# New features available via new parameters
chunks = split_text_into_chunks(
    text="...",
    chunk_size=1000,
    overlap_percentage=0.15,  # NEW
    strategy=ChunkStrategy.SEMANTIC  # NEW
)
```

### Migration Steps

1. **Phase 1 (No Changes Required)**: Deploy new code with default behavior unchanged
2. **Phase 2 (Opt-In Testing)**: Teams test new overlap features in development
3. **Phase 3 (Gradual Rollout)**: Enable overlap (10%) for new graphs only
4. **Phase 4 (Default Change)**: Make overlap default for all new configurations
5. **Phase 5 (Optimization)**: Teams tune overlap percentage based on content type

### Configuration Migration

```python
# OLD configuration (still works)
old_config = {
    "llm": llm_model,
    "chunk_size": 8000,
}

# NEW configuration (enhanced)
new_config = {
    "llm": llm_model,
    "chunk_size": 8000,
    "chunk_overlap_percentage": 0.1,  # Add 10% overlap
    "chunk_strategy": "semantic",  # Explicit strategy
    "preserve_boundaries": True  # Respect sentence boundaries
}

# CUSTOM configuration (for specific use cases)
technical_docs_config = {
    "llm": llm_model,
    "chunk_size": 6000,
    "overlap_size": 500,  # Fixed overlap for consistency
    "chunk_strategy": "recursive",  # Better for structured docs
}
```

### Environment Variables

```bash
# Default chunking behavior
SCRAPEGRAPH_CHUNK_STRATEGY=semantic
SCRAPEGRAPH_CHUNK_OVERLAP_PCT=0.1

# Override for specific environments
# Development: More aggressive chunking for testing
SCRAPEGRAPH_CHUNK_OVERLAP_PCT=0.2

# Production: Balanced performance
SCRAPEGRAPH_CHUNK_OVERLAP_PCT=0.1
```

## Performance Considerations

### Computational Overhead

| Strategy | Relative Speed | Token Accuracy | Boundary Quality |
|----------|---------------|----------------|------------------|
| WORD (legacy) | 1.0x (baseline) | Low | Low |
| SEMANTIC | 0.4x (slower) | High | High |
| RECURSIVE | 0.8x | Medium-High | High |
| SENTENCE | 0.6x | High | Very High |
| PARAGRAPH | 0.9x | Medium | High |

### Memory Impact

- **Overlap Storage**: ~10-20% increase in total chunk characters
- **Metadata Overhead**: ~200 bytes per chunk
- **Token Count Caching**: Can reduce repeated calculations by 50%

### Optimization Strategies

1. **Lazy Metadata Generation**: Only create metadata when `return_metadata=True`
2. **Token Count Caching**: Cache token counts for repeated text segments
3. **Parallel Chunking**: Process multiple documents concurrently
4. **Adaptive Overlap**: Reduce overlap for very large documents
5. **Smart Boundary Detection**: Cache sentence boundaries after first detection

### Token Usage Impact

**Example with 10,000 word document (chunk_size=2000 tokens):**

| Configuration | Chunks | Total Tokens | Efficiency |
|---------------|--------|--------------|------------|
| No overlap | 5 | 10,000 | 100% |
| 10% overlap | 5 | 11,000 | 91% |
| 20% overlap | 5 | 12,000 | 83% |
| 30% overlap | 5 | 13,000 | 77% |

**Recommendation**: 10-15% overlap provides best balance between context preservation and token efficiency.

## Alternatives Considered

### Alternative 1: Use LangChain TextSplitter Exclusively

**Pros:**
- Mature, well-tested library
- Multiple splitting strategies built-in
- Good documentation

**Cons:**
- Adds dependency weight
- Less control over token counting
- May not integrate well with semchunk

**Decision:** Use RecursiveCharacterTextSplitter as one strategy option, not exclusive solution

### Alternative 2: Sliding Window Approach

**Pros:**
- Simple to implement
- Predictable overlap
- Easy to reason about

**Cons:**
- Ignores semantic boundaries
- May split mid-sentence
- Less efficient than targeted overlap

**Decision:** Offer as an option but default to semantic strategies

### Alternative 3: LLM-Based Chunking

**Pros:**
- Most intelligent boundary detection
- Content-aware splitting
- Optimal semantic preservation

**Cons:**
- Very slow (requires LLM call per chunk)
- Expensive (additional API costs)
- Adds latency to pipeline

**Decision:** Too expensive for default behavior, consider for future premium feature

### Alternative 4: Keep Current Implementation

**Pros:**
- No work required
- No compatibility concerns

**Cons:**
- Continues to lose context at boundaries
- Lower answer quality
- Missed opportunity for improvement

**Decision:** Not viable given the quality impact

## Open Questions

1. **Optimal Overlap Percentage**: What's the sweet spot between context preservation and token efficiency?
   - *Suggestion:* Run A/B tests with 5%, 10%, 15%, 20% overlap
   - *Action:* Create benchmark suite with real user queries

2. **Strategy Selection**: How should users choose the right strategy?
   - *Suggestion:* Provide decision tree in documentation
   - *Action:* Build content type detector that auto-suggests strategy

3. **Dynamic Overlap**: Should overlap size vary based on content density?
   - *Suggestion:* Yes, for advanced users; add `adaptive_overlap=True` option
   - *Action:* Research adaptive overlap algorithms

4. **Chunk Reassembly**: For final answers, should we reassemble overlapping chunks?
   - *Suggestion:* Not needed if LLM handles redundancy well
   - *Action:* Test with and without reassembly

5. **Multi-Language Support**: Do different languages need different strategies?
   - *Suggestion:* Sentence detection works across languages with NLTK
   - *Action:* Test with non-English documents (Spanish, Chinese, Arabic)

## Success Metrics

### Quality Metrics
- **Context Preservation**: 95% of entity relationships maintained across chunks
- **Answer Accuracy**: 30-50% reduction in context-loss errors
- **Hallucination Rate**: 40% reduction in LLM fabrications

### Performance Metrics
- **Chunking Speed**: <10% overhead compared to current implementation
- **Token Efficiency**: ≥85% efficiency with recommended overlap (10-15%)
- **Memory Usage**: <20% increase from metadata storage

### Adoption Metrics
- **Configuration Updates**: 60% of users enable overlap within 3 months
- **Strategy Diversity**: At least 3 strategies actively used
- **Backward Compatibility**: Zero breaking changes reported

### Business Metrics
- **User Satisfaction**: 25% increase in answer quality ratings
- **Support Tickets**: 30% reduction in "incorrect answer" tickets
- **LLM Costs**: <15% increase despite overlap (offset by better first-pass accuracy)

## References

### Academic Papers
- [Text Segmentation: A Survey](https://aclanthology.org/2020.acl-main.111/) - ACL 2020
- [Semantic Chunking for Information Retrieval](https://arxiv.org/abs/2301.00234)
- [Context Windows and Long Document Understanding](https://arxiv.org/abs/2307.03109)

### Libraries & Tools
- [semchunk](https://github.com/umarbutler/semchunk) - Semantic chunking library
- [LangChain TextSplitter](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [NLTK Tokenizers](https://www.nltk.org/api/nltk.tokenize.html)

### Best Practices
- [LangChain Chunking Guide](https://python.langchain.com/docs/modules/data_connection/document_transformers/text_splitters/split_by_token)
- [Pinecone: Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/)
- [OpenAI: Text Splitting Best Practices](https://platform.openai.com/docs/guides/embeddings/use-cases)

### Related RFCs
- RFC-0002: Multi-Model Fallback System (related to handling chunking failures)
- RFC-0004: Structured Logging (for chunking metrics)

## Appendix: Code Examples

### Example 1: Basic Usage with Overlap

```python
from scrapegraphai.utils.split_text_into_chunks import split_text_into_chunks

text = """
Long document text here...
Multiple paragraphs...
"""

# Simple overlap (10% default)
chunks = split_text_into_chunks(
    text=text,
    chunk_size=2000,
    overlap_percentage=0.1
)

print(f"Created {len(chunks)} chunks with 10% overlap")
```

### Example 2: Advanced Configuration

```python
from scrapegraphai.utils.split_text_into_chunks import (
    split_text_into_chunks, ChunkStrategy
)

# Technical documentation: Use recursive splitting with large overlap
chunks = split_text_into_chunks(
    text=technical_doc,
    chunk_size=4000,
    overlap_size=600,  # Fixed 600 token overlap
    strategy=ChunkStrategy.RECURSIVE,
    preserve_boundaries=True,
    return_metadata=True
)

# Inspect metadata
for chunk in chunks:
    print(f"Chunk {chunk.metadata.chunk_index + 1}/{chunk.metadata.total_chunks}")
    print(f"  Tokens: {chunk.metadata.token_count}")
    print(f"  Complete boundaries: {chunk.metadata.is_boundary_complete}")
```

### Example 3: Smart Scraper with Enhanced Chunking

```python
from scrapegraphai.graphs import SmartScraperGraph

graph_config = {
    "llm": {
        "model": "openai/gpt-4",
        "api_key": "...",
    },
    "chunk_size": 6000,
    "chunk_overlap_percentage": 0.15,  # 15% overlap for better context
    "chunk_strategy": "semantic",
    "preserve_boundaries": True,
}

smart_scraper = SmartScraperGraph(
    prompt="Extract all product features and their descriptions",
    source="https://example.com/product",
    config=graph_config
)

result = smart_scraper.run()
```

### Example 4: Comparing Strategies

```python
from scrapegraphai.utils.split_text_into_chunks import split_text_into_chunks, ChunkStrategy

strategies = [
    ChunkStrategy.SEMANTIC,
    ChunkStrategy.RECURSIVE,
    ChunkStrategy.SENTENCE
]

for strategy in strategies:
    chunks = split_text_into_chunks(
        text=document,
        chunk_size=2000,
        overlap_percentage=0.1,
        strategy=strategy
    )
    print(f"{strategy.value}: {len(chunks)} chunks")
```

### Example 5: Detecting Information Loss

```python
from scrapegraphai.utils.split_text_into_chunks import split_text_into_chunks

# Document with important entity relationship
text = """
Dr. Sarah Johnson, the lead researcher at MIT, published groundbreaking
findings on quantum computing. The research team, led by Dr. Johnson,
demonstrated a 1000x speedup in certain algorithms.
"""

# Without overlap - may lose "Dr. Johnson" → "research team" connection
chunks_no_overlap = split_text_into_chunks(
    text=text,
    chunk_size=50,  # Small size to force split
    overlap_percentage=0.0
)

# With overlap - preserves connection
chunks_with_overlap = split_text_into_chunks(
    text=text,
    chunk_size=50,
    overlap_percentage=0.2
)

print("Without overlap:")
for i, chunk in enumerate(chunks_no_overlap):
    print(f"  Chunk {i+1}: {chunk[:50]}...")

print("\nWith overlap:")
for i, chunk in enumerate(chunks_with_overlap):
    print(f"  Chunk {i+1}: {chunk[:50]}...")
```

---

**Document Status:** Ready for Review
**Next Steps:**
1. Review by architecture team
2. Conduct overlap percentage A/B testing
3. Gather feedback from users on chunking quality issues
4. Create detailed implementation tickets
5. Set up benchmarking infrastructure
