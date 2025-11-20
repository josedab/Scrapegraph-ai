# Smart Chunking with Context Preservation

This guide explains how to use the enhanced chunking features in ScrapeGraphAI to improve answer quality and reduce information loss when processing large documents.

## Overview

The enhanced chunking system provides:

- **Configurable Overlap**: Prevent information loss at chunk boundaries
- **Multiple Strategies**: Choose the best chunking approach for your content type
- **Context Preservation**: Maintain relationships between entities across chunks
- **Metadata Support**: Track chunk position and overlap information

## Why Use Smart Chunking?

When processing large documents, basic chunking can fragment important context:

**Without Overlap:**
```
Chunk 1: "John Smith, CEO of TechCorp, announced"
Chunk 2: "that the company will expand to 50 new markets."
→ LLM loses connection between "John Smith" and "the company"
```

**With Overlap:**
```
Chunk 1: "John Smith, CEO of TechCorp, announced that the company will expand"
Chunk 2: "announced that the company will expand to 50 new markets by 2026."
→ Context preserved, "the company" clearly refers to "TechCorp"
```

## Chunking Strategies

### 1. Semantic Chunking (Default)

Uses the `semchunk` library for intelligent semantic boundary detection.

**Best for:** General-purpose text, articles, blog posts

```python
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": llm_model,
    "chunk_size": 8000,
    "chunk_overlap_percentage": 0.1,  # 10% overlap
    "chunk_strategy": "semantic"
}

graph = SmartScraperGraph(
    prompt="Extract key information",
    source="https://example.com",
    config=config
)
```

### 2. Recursive Character Splitting

Uses LangChain's `RecursiveCharacterTextSplitter` for hierarchical boundary detection.

**Best for:** Structured documents, technical documentation, markdown files

```python
config = {
    "llm": llm_model,
    "chunk_size": 6000,
    "overlap_size": 500,  # Fixed 500 token overlap
    "chunk_strategy": "recursive"
}
```

### 3. Sentence-Based Chunking

Ensures chunks always break at sentence boundaries.

**Best for:** Precise content extraction, Q&A tasks, citations

```python
config = {
    "llm": llm_model,
    "chunk_size": 4000,
    "chunk_overlap_percentage": 0.15,  # 15% overlap
    "chunk_strategy": "sentence",
    "preserve_boundaries": True
}
```

### 4. Paragraph-Based Chunking

Keeps paragraphs intact when possible.

**Best for:** Long-form content, essays, reports

```python
config = {
    "llm": llm_model,
    "chunk_size": 5000,
    "chunk_overlap_percentage": 0.1,
    "chunk_strategy": "paragraph"
}
```

### 5. Word-Based Chunking (Legacy)

Simple word-by-word splitting, maintains backward compatibility.

**Best for:** When you need the old behavior

```python
config = {
    "llm": llm_model,
    "chunk_size": 8000,
    "chunk_strategy": "word",
    "overlap_percentage": 0.0  # No overlap like the old implementation
}
```

## Configuration Parameters

### `chunk_size` (required)
Maximum number of tokens per chunk.

```python
"chunk_size": 8000
```

### `chunk_overlap_percentage` (optional, default: 0.1)
Percentage of chunk size to use for overlap between consecutive chunks.

```python
"chunk_overlap_percentage": 0.15  # 15% overlap
```

### `chunk_overlap_size` (optional)
Fixed number of tokens for overlap. Overrides `chunk_overlap_percentage` if specified.

```python
"chunk_overlap_size": 500  # Always 500 tokens
```

### `chunk_strategy` (optional, default: "semantic")
The chunking strategy to use. Options:
- `"semantic"`: Semantic chunking with semchunk
- `"recursive"`: Recursive character splitting
- `"sentence"`: Sentence boundary splitting
- `"paragraph"`: Paragraph boundary splitting
- `"word"`: Legacy word-based splitting

```python
"chunk_strategy": "sentence"
```

### `preserve_boundaries` (optional, default: True)
Whether to preserve sentence boundaries when possible.

```python
"preserve_boundaries": True
```

## Usage Examples

### Example 1: Default Configuration (Recommended)

```python
from scrapegraphai.graphs import SmartScraperGraph

config = {
    "llm": llm_model,
    "chunk_size": 8000,
    # Uses default 10% overlap with semantic strategy
}

graph = SmartScraperGraph(
    prompt="What are the main topics discussed?",
    source="https://example.com/long-article",
    config=config
)

result = graph.run()
```

### Example 2: Research Paper Extraction

```python
config = {
    "llm": llm_model,
    "chunk_size": 6000,
    "chunk_overlap_percentage": 0.2,  # More overlap for academic content
    "chunk_strategy": "sentence",
    "preserve_boundaries": True
}

graph = SmartScraperGraph(
    prompt="Extract all citations and their contexts",
    source="https://arxiv.org/paper.pdf",
    config=config
)
```

### Example 3: Contract Analysis

```python
config = {
    "llm": llm_model,
    "chunk_size": 5000,
    "chunk_overlap_size": 600,  # Fixed overlap for consistency
    "chunk_strategy": "recursive",
}

graph = SmartScraperGraph(
    prompt="Identify all clauses related to payment terms",
    source="contract.pdf",
    config=config
)
```

### Example 4: E-commerce Product Pages

```python
config = {
    "llm": llm_model,
    "chunk_size": 4000,
    "chunk_overlap_percentage": 0.1,
    "chunk_strategy": "paragraph",
}

graph = SmartScraperGraph(
    prompt="Extract product specifications and descriptions",
    source="https://shop.example.com/product",
    config=config
)
```

### Example 5: News Article Scraping

```python
config = {
    "llm": llm_model,
    "chunk_size": 7000,
    "chunk_overlap_percentage": 0.15,
    "chunk_strategy": "semantic",
}

graph = SmartScraperGraph(
    prompt="Extract key facts and quotes with attribution",
    source="https://news.example.com/article",
    config=config
)
```

## Advanced Usage: Direct API

You can also use the chunking functionality directly:

```python
from scrapegraphai.utils.split_text_into_chunks import (
    split_text_into_chunks,
    ChunkStrategy
)

# Basic usage
chunks = split_text_into_chunks(
    text="Your long text here...",
    chunk_size=1000,
    overlap_percentage=0.1,
    strategy=ChunkStrategy.SEMANTIC
)

# With metadata
chunks_with_metadata = split_text_into_chunks(
    text="Your long text here...",
    chunk_size=1000,
    overlap_percentage=0.15,
    strategy=ChunkStrategy.SENTENCE,
    return_metadata=True
)

for chunk in chunks_with_metadata:
    print(f"Chunk {chunk.metadata.chunk_index + 1}/{chunk.metadata.total_chunks}")
    print(f"Tokens: {chunk.metadata.token_count}")
    print(f"Text: {chunk.text[:100]}...")
    print()
```

## Choosing the Right Overlap

The optimal overlap depends on your use case:

| Use Case | Recommended Overlap | Rationale |
|----------|-------------------|-----------|
| General web scraping | 10-15% | Balance between context and efficiency |
| Academic/research papers | 15-20% | Preserve citations and references |
| Legal documents | 15-20% | Maintain clause relationships |
| Technical documentation | 10-15% | Keep code examples with explanations |
| News articles | 10-15% | Preserve entity relationships |
| Product descriptions | 5-10% | Specifications are usually self-contained |

## Performance Considerations

### Token Usage
Overlap increases total tokens processed:
- 10% overlap ≈ 10% more tokens
- 20% overlap ≈ 20% more tokens

### Processing Time
Different strategies have different performance characteristics:
- **Word-based**: Fastest (baseline)
- **Paragraph**: Fast (~1.5x slower)
- **Recursive**: Medium (~2-3x slower)
- **Sentence**: Medium (~2-4x slower, requires NLTK)
- **Semantic**: Slower (~3-5x slower, but best quality)

### Recommendations
- For development/testing: Use smaller chunk sizes and higher overlap
- For production: Balance chunk size, overlap, and strategy based on content type
- For cost optimization: Use lower overlap (5-10%) with semantic or sentence strategies

## Troubleshooting

### Issue: Chunks are too large

**Solution:** Reduce `chunk_size`:
```python
"chunk_size": 4000  # Instead of 8000
```

### Issue: Information is still being lost

**Solution:** Increase overlap:
```python
"chunk_overlap_percentage": 0.2  # Increase from 0.1 to 0.2
```

### Issue: Processing is too slow

**Solution:** Use a faster strategy:
```python
"chunk_strategy": "recursive"  # Instead of "semantic"
```

### Issue: NLTK punkt tokenizer not found

**Solution:** The library will automatically download it, but you can manually install:
```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

### Issue: Chunks breaking mid-sentence

**Solution:** Use sentence or semantic strategy:
```python
"chunk_strategy": "sentence",
"preserve_boundaries": True
```

## Migration from Old Implementation

The new implementation is **100% backward compatible**. Existing code will continue to work:

```python
# Old code (still works)
config = {
    "llm": llm_model,
    "chunk_size": 8000,
}

# New code (with enhanced features)
config = {
    "llm": llm_model,
    "chunk_size": 8000,
    "chunk_overlap_percentage": 0.1,  # NEW
    "chunk_strategy": "semantic",  # NEW
}
```

### Migration Steps

1. **No changes required** - Deploy and test
2. **Add overlap** - Start with 10% overlap
3. **Choose strategy** - Select based on content type
4. **Tune parameters** - Adjust based on results
5. **Monitor** - Check answer quality improvements

## Best Practices

1. **Start with defaults**: The default configuration (semantic with 10% overlap) works well for most cases
2. **Test different strategies**: Try different strategies with your specific content
3. **Monitor token usage**: Track costs when using higher overlap
4. **Preserve boundaries**: Enable `preserve_boundaries` for better quality
5. **Use metadata**: Enable metadata for debugging and optimization
6. **Match strategy to content**: Technical docs → recursive, articles → semantic, Q&A → sentence

## Examples by Content Type

### Blog Posts
```python
config = {"chunk_size": 6000, "chunk_overlap_percentage": 0.1, "chunk_strategy": "semantic"}
```

### Technical Documentation
```python
config = {"chunk_size": 5000, "chunk_overlap_percentage": 0.15, "chunk_strategy": "recursive"}
```

### News Articles
```python
config = {"chunk_size": 7000, "chunk_overlap_percentage": 0.12, "chunk_strategy": "semantic"}
```

### Academic Papers
```python
config = {"chunk_size": 6000, "chunk_overlap_percentage": 0.2, "chunk_strategy": "sentence"}
```

### Legal Documents
```python
config = {"chunk_size": 5000, "chunk_overlap_size": 600, "chunk_strategy": "recursive"}
```

### Product Pages
```python
config = {"chunk_size": 4000, "chunk_overlap_percentage": 0.08, "chunk_strategy": "paragraph"}
```

## Further Reading

- [RFC-0013: Smart Chunking with Context Preservation](../analysis-output/rfcs/RFC-0013-smart-chunking-context.md)
- [LangChain Text Splitters Documentation](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [Semchunk Library](https://github.com/umarbutler/semchunk)
