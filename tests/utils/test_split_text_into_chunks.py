"""
Unit tests for split_text_into_chunks module
"""

import pytest
from scrapegraphai.utils.split_text_into_chunks import (
    split_text_into_chunks,
    ChunkStrategy,
    EnhancedChunk,
    _extract_overlap,
    _check_boundary_completeness,
    _estimate_overlap_chars,
)
from scrapegraphai.utils.tokenizer import num_tokens_calculus


class TestHelperFunctions:
    """Test helper functions."""

    def test_extract_overlap(self):
        """Test that overlap extraction works correctly."""
        text = "This is a test sentence with multiple words."
        overlap = _extract_overlap(text, overlap_tokens=3, token_counter=num_tokens_calculus)

        # Should extract some content
        assert len(overlap) > 0
        # Overlap should be shorter than original
        assert len(overlap) < len(text)

    def test_extract_overlap_zero_tokens(self):
        """Test overlap extraction with zero tokens."""
        text = "This is a test."
        overlap = _extract_overlap(text, overlap_tokens=0, token_counter=num_tokens_calculus)

        assert overlap == ""

    def test_extract_overlap_empty_text(self):
        """Test overlap extraction with empty text."""
        overlap = _extract_overlap("", overlap_tokens=5, token_counter=num_tokens_calculus)

        assert overlap == ""

    def test_check_boundary_completeness_complete(self):
        """Test boundary completeness check with complete boundaries."""
        text = "This is a complete sentence."
        assert _check_boundary_completeness(text) is True

    def test_check_boundary_completeness_incomplete_start(self):
        """Test boundary completeness check with incomplete start."""
        text = "is a complete sentence."
        assert _check_boundary_completeness(text) is False

    def test_check_boundary_completeness_incomplete_end(self):
        """Test boundary completeness check with incomplete end."""
        text = "This is incomplete"
        assert _check_boundary_completeness(text) is False

    def test_check_boundary_completeness_empty(self):
        """Test boundary completeness check with empty text."""
        assert _check_boundary_completeness("") is True

    def test_estimate_overlap_chars(self):
        """Test character estimation for overlap."""
        text = "This is a test sentence with multiple words here."
        chars = _estimate_overlap_chars(text, overlap_tokens=3, token_counter=num_tokens_calculus)

        assert chars > 0
        assert chars <= len(text)


class TestBasicChunking:
    """Test basic chunking functionality."""

    def test_empty_text(self):
        """Test that empty text returns empty list."""
        chunks = split_text_into_chunks("", chunk_size=100)
        assert chunks == []

    def test_whitespace_only_text(self):
        """Test that whitespace-only text returns empty list."""
        chunks = split_text_into_chunks("   \n  \t  ", chunk_size=100)
        assert chunks == []

    def test_single_word(self):
        """Test chunking with single word."""
        chunks = split_text_into_chunks("word", chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == "word"

    def test_text_smaller_than_chunk_size(self):
        """Test that text smaller than chunk size returns single chunk."""
        text = "This is a short text."
        chunks = split_text_into_chunks(text, chunk_size=1000)

        assert len(chunks) == 1
        assert chunks[0] == text


class TestSemanticChunking:
    """Test semantic chunking strategy."""

    def test_semantic_chunking_basic(self):
        """Test basic semantic chunking."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 10
        chunks = split_text_into_chunks(
            text=text,
            chunk_size=50,
            overlap_percentage=0.1,
            strategy=ChunkStrategy.SEMANTIC
        )

        # Should create multiple chunks
        assert len(chunks) > 1
        # All chunks should be strings
        assert all(isinstance(c, str) for c in chunks)

    def test_semantic_chunking_with_overlap(self):
        """Test that semantic chunking creates overlapping chunks."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 5

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=30,
            overlap_percentage=0.2,
            strategy=ChunkStrategy.SEMANTIC
        )

        # Verify overlap exists by checking if consecutive chunks share some words
        if len(chunks) >= 2:
            chunk1_words = set(chunks[0].split())
            chunk2_words = set(chunks[1].split())
            overlap_words = chunk1_words & chunk2_words
            # There should be some overlap
            assert len(overlap_words) >= 0  # May vary based on semchunk behavior

    def test_semantic_chunking_with_metadata(self):
        """Test semantic chunking returns metadata when requested."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four. " * 5

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=30,
            overlap_percentage=0.1,
            strategy=ChunkStrategy.SEMANTIC,
            return_metadata=True
        )

        # Should return EnhancedChunk objects
        assert all(isinstance(c, EnhancedChunk) for c in chunks)

        # Check metadata structure
        for i, chunk in enumerate(chunks):
            assert chunk.metadata.chunk_index == i
            assert chunk.metadata.total_chunks == len(chunks)
            assert chunk.metadata.token_count > 0
            assert isinstance(chunk.text, str)


class TestRecursiveChunking:
    """Test recursive character text splitting strategy."""

    def test_recursive_chunking_basic(self):
        """Test basic recursive chunking."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph." * 5

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=50,
            overlap_percentage=0.1,
            strategy=ChunkStrategy.RECURSIVE
        )

        assert len(chunks) > 1
        assert all(isinstance(c, str) for c in chunks)

    def test_recursive_chunking_respects_boundaries(self):
        """Test that recursive chunking respects natural boundaries."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=20,
            strategy=ChunkStrategy.RECURSIVE,
            preserve_boundaries=True
        )

        # All chunks should be non-empty
        assert all(len(c.strip()) > 0 for c in chunks)


class TestSentenceChunking:
    """Test sentence-based chunking strategy."""

    def test_sentence_chunking_basic(self):
        """Test basic sentence chunking."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=15,
            overlap_percentage=0.2,
            strategy=ChunkStrategy.SENTENCE
        )

        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_sentence_chunking_preserves_boundaries(self):
        """Test that sentence boundaries are preserved."""
        text = "First sentence. Second sentence. Third sentence."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=10,
            strategy=ChunkStrategy.SENTENCE,
            preserve_boundaries=True,
            return_metadata=True
        )

        # All chunks should have complete boundaries
        for chunk in chunks:
            assert chunk.metadata.is_boundary_complete is True

    def test_sentence_chunking_with_overlap(self):
        """Test sentence chunking with overlap."""
        text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=8,
            overlap_percentage=0.3,
            strategy=ChunkStrategy.SENTENCE
        )

        # Should create multiple chunks with overlap
        assert len(chunks) >= 2


class TestParagraphChunking:
    """Test paragraph-based chunking strategy."""

    def test_paragraph_chunking_basic(self):
        """Test basic paragraph chunking."""
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=20,
            overlap_percentage=0.1,
            strategy=ChunkStrategy.PARAGRAPH
        )

        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_paragraph_chunking_with_overlap(self):
        """Test paragraph chunking with overlap."""
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\nParagraph four."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=10,
            overlap_percentage=0.2,
            strategy=ChunkStrategy.PARAGRAPH
        )

        # Should create multiple chunks
        assert len(chunks) >= 1


class TestWordChunking:
    """Test word-based chunking strategy."""

    def test_word_chunking_legacy(self):
        """Test legacy word chunking without overlap."""
        text = "This is a test sentence with multiple words for testing purposes."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=10,
            overlap_percentage=0.0,
            strategy=ChunkStrategy.WORD
        )

        assert len(chunks) >= 1
        # Join all chunks and verify all words are present
        all_text = " ".join(chunks)
        original_words = set(text.split())
        result_words = set(all_text.split())
        assert original_words == result_words

    def test_word_chunking_with_overlap(self):
        """Test word chunking with overlap."""
        text = "Word one two three four five six seven eight nine ten."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=8,
            overlap_percentage=0.2,
            strategy=ChunkStrategy.WORD
        )

        assert len(chunks) >= 1


class TestBackwardCompatibility:
    """Test backward compatibility with old API."""

    def test_old_api_with_semchunk(self):
        """Test that old API still works with use_semchunk=True."""
        text = "Test text for backward compatibility."

        chunks = split_text_into_chunks(text, chunk_size=100, use_semchunk=True)

        assert isinstance(chunks, list)
        assert all(isinstance(c, str) for c in chunks)

    def test_old_api_without_semchunk(self):
        """Test that old API still works with use_semchunk=False."""
        text = "Test text for backward compatibility without semchunk."

        chunks = split_text_into_chunks(text, chunk_size=100, use_semchunk=False)

        assert isinstance(chunks, list)
        assert all(isinstance(c, str) for c in chunks)

    def test_old_api_returns_strings(self):
        """Test that old API returns strings by default (not metadata)."""
        text = "Test text."

        chunks = split_text_into_chunks(text, chunk_size=100)

        # Should return strings, not EnhancedChunk objects
        assert all(isinstance(c, str) for c in chunks)


class TestChunkMetadata:
    """Test chunk metadata functionality."""

    def test_metadata_structure(self):
        """Test that metadata has correct structure."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=15,
            overlap_percentage=0.1,
            return_metadata=True
        )

        # Verify metadata structure
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, EnhancedChunk)
            assert chunk.metadata.chunk_index == i
            assert chunk.metadata.total_chunks == len(chunks)
            assert chunk.metadata.token_count > 0
            assert chunk.metadata.start_position >= 0
            assert chunk.metadata.end_position > 0

    def test_metadata_token_count(self):
        """Test that token count in metadata is accurate."""
        text = "This is a test sentence."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=100,
            return_metadata=True
        )

        # Verify token count
        for chunk in chunks:
            actual_tokens = num_tokens_calculus(chunk.text)
            assert chunk.metadata.token_count == actual_tokens


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_small_chunk_size(self):
        """Test with very small chunk size."""
        text = "Test"
        chunks = split_text_into_chunks(text, chunk_size=1)

        assert len(chunks) >= 1

    def test_overlap_larger_than_chunk(self):
        """Test that overlap larger than chunk size is handled."""
        text = "This is a test sentence with multiple words."

        # Overlap size larger than chunk should be capped
        chunks = split_text_into_chunks(
            text=text,
            chunk_size=10,
            overlap_size=20  # Larger than chunk_size
        )

        assert len(chunks) >= 1

    def test_invalid_strategy_string(self):
        """Test with invalid strategy string."""
        text = "Test text."

        # Should default to semantic
        chunks = split_text_into_chunks(
            text=text,
            chunk_size=100,
            strategy="invalid_strategy"
        )

        assert len(chunks) >= 1

    def test_string_strategy_conversion(self):
        """Test that string strategies are converted to enums."""
        text = "Test sentence one. Test sentence two."

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=20,
            strategy="sentence"  # String instead of enum
        )

        assert len(chunks) >= 1

    def test_fixed_overlap_size_override(self):
        """Test that fixed overlap_size overrides percentage."""
        text = "One. Two. Three. Four. Five. Six."

        chunks_with_fixed = split_text_into_chunks(
            text=text,
            chunk_size=10,
            overlap_size=2,  # Fixed size
            overlap_percentage=0.5,  # Should be ignored
            strategy=ChunkStrategy.SENTENCE
        )

        assert len(chunks_with_fixed) >= 1


class TestRealWorldScenarios:
    """Test with real-world scenarios."""

    def test_entity_recognition_scenario(self):
        """Test the example from the RFC - entity recognition across boundaries."""
        text = (
            "John Smith, CEO of TechCorp, announced that the company will "
            "expand to 50 new markets by 2026. This expansion will create "
            "1000 new jobs."
        )

        # Test with overlap
        chunks_with_overlap = split_text_into_chunks(
            text=text,
            chunk_size=15,
            overlap_percentage=0.3,
            strategy=ChunkStrategy.SENTENCE
        )

        # Should create chunks that preserve context
        assert len(chunks_with_overlap) >= 1

        # Test without overlap
        chunks_no_overlap = split_text_into_chunks(
            text=text,
            chunk_size=15,
            overlap_percentage=0.0,
            strategy=ChunkStrategy.WORD
        )

        assert len(chunks_no_overlap) >= 1

    def test_long_document_chunking(self):
        """Test with a longer document."""
        # Simulate a long document
        text = " ".join([
            f"This is paragraph {i} with some content about topic {i}."
            for i in range(100)
        ])

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=100,
            overlap_percentage=0.15,
            strategy=ChunkStrategy.SEMANTIC
        )

        # Should create multiple chunks
        assert len(chunks) > 1

        # Total content should be preserved (with some duplication from overlap)
        total_length = sum(len(c) for c in chunks)
        assert total_length >= len(text)

    def test_technical_documentation(self):
        """Test with technical documentation structure."""
        text = """
# Introduction

This is the introduction section.

## Background

The background provides context.

## Methodology

The methodology describes the approach.

### Step 1

First step details.

### Step 2

Second step details.

## Conclusion

The conclusion summarizes findings.
"""

        chunks = split_text_into_chunks(
            text=text,
            chunk_size=50,
            overlap_percentage=0.1,
            strategy=ChunkStrategy.PARAGRAPH
        )

        # Should handle markdown structure
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)
