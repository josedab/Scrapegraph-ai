"""
Integration tests for ParseNode with enhanced chunking
"""

import pytest
from langchain_core.documents import Document
from scrapegraphai.nodes import ParseNode
from scrapegraphai.utils.split_text_into_chunks import ChunkStrategy


class TestParseNodeChunking:
    """Test ParseNode with enhanced chunking features."""

    def test_parse_node_default_chunking(self):
        """Test ParseNode with default chunking configuration."""
        node_config = {
            "llm_model": None,
            "chunk_size": 100,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        # Create a test document
        test_content = "This is a test document. " * 50
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Verify chunks were created
        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1
        assert all(isinstance(chunk, str) for chunk in result["parsed_doc"])

    def test_parse_node_with_overlap_percentage(self):
        """Test ParseNode with custom overlap percentage."""
        node_config = {
            "llm_model": None,
            "chunk_size": 50,
            "chunk_overlap_percentage": 0.2,  # 20% overlap
            "chunk_strategy": "semantic",
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "Sentence one. Sentence two. Sentence three. " * 20
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Verify chunks were created
        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_with_fixed_overlap(self):
        """Test ParseNode with fixed overlap size."""
        node_config = {
            "llm_model": None,
            "chunk_size": 50,
            "chunk_overlap_size": 10,  # Fixed 10 token overlap
            "chunk_strategy": "semantic",
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "Test content for fixed overlap. " * 30
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_sentence_strategy(self):
        """Test ParseNode with sentence chunking strategy."""
        node_config = {
            "llm_model": None,
            "chunk_size": 30,
            "chunk_overlap_percentage": 0.15,
            "chunk_strategy": "sentence",
            "preserve_boundaries": True,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "First sentence here. Second sentence here. Third sentence here. " * 10
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_recursive_strategy(self):
        """Test ParseNode with recursive chunking strategy."""
        node_config = {
            "llm_model": None,
            "chunk_size": 40,
            "chunk_overlap_percentage": 0.1,
            "chunk_strategy": "recursive",
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = """
Paragraph one.

Paragraph two.

Paragraph three.
""" * 10
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_paragraph_strategy(self):
        """Test ParseNode with paragraph chunking strategy."""
        node_config = {
            "llm_model": None,
            "chunk_size": 40,
            "chunk_overlap_percentage": 0.1,
            "chunk_strategy": "paragraph",
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\n" * 10
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_without_html_parsing(self):
        """Test ParseNode with parse_html=False."""
        node_config = {
            "llm_model": None,
            "chunk_size": 50,
            "chunk_overlap_percentage": 0.1,
            "chunk_strategy": "semantic",
            "parse_html": False,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc"],
            node_config=node_config
        )

        test_content = "Test content without HTML parsing. " * 20
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_small_document(self):
        """Test ParseNode with document smaller than chunk size."""
        node_config = {
            "llm_model": None,
            "chunk_size": 1000,
            "chunk_overlap_percentage": 0.1,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "This is a small test document."
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Should return single chunk
        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) == 1
        assert test_content in result["parsed_doc"][0]

    def test_parse_node_backwards_compatibility(self):
        """Test that ParseNode maintains backward compatibility."""
        # Old-style configuration without new parameters
        node_config = {
            "llm_model": None,
            "chunk_size": 100,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "Backward compatibility test. " * 30
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Should still work with default values
        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1

    def test_parse_node_preserves_all_content(self):
        """Test that chunking preserves all content (accounting for overlap)."""
        node_config = {
            "llm_model": None,
            "chunk_size": 20,
            "chunk_overlap_percentage": 0.15,
            "chunk_strategy": "sentence",
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_sentences = [
            "First unique sentence.",
            "Second unique sentence.",
            "Third unique sentence.",
            "Fourth unique sentence.",
            "Fifth unique sentence.",
        ]
        test_content = " ".join(test_sentences)
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Combine all chunks
        all_chunks = " ".join(result["parsed_doc"])

        # Verify that all sentences appear somewhere in the chunks
        for sentence in test_sentences:
            # Remove period for more flexible matching
            sentence_core = sentence.replace(".", "").strip()
            assert sentence_core in all_chunks


class TestParseNodeEdgeCases:
    """Test edge cases for ParseNode chunking."""

    def test_parse_node_empty_document(self):
        """Test ParseNode with empty document."""
        node_config = {
            "llm_model": None,
            "chunk_size": 100,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_doc = Document(page_content="")

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Should handle empty document gracefully
        assert "parsed_doc" in result
        # Empty document should result in empty or single empty chunk
        assert len(result["parsed_doc"]) <= 1

    def test_parse_node_very_long_document(self):
        """Test ParseNode with very long document."""
        node_config = {
            "llm_model": None,
            "chunk_size": 100,
            "chunk_overlap_percentage": 0.1,
            "chunk_strategy": "semantic",
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        # Create a very long document
        test_content = " ".join([
            f"Paragraph {i} with content about topic {i}."
            for i in range(500)
        ])
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        # Should create many chunks
        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) > 10

    def test_parse_node_special_characters(self):
        """Test ParseNode with special characters."""
        node_config = {
            "llm_model": None,
            "chunk_size": 50,
            "chunk_overlap_percentage": 0.1,
        }

        parse_node = ParseNode(
            input="document & url",
            output=["parsed_doc", "link_urls", "img_urls"],
            node_config=node_config
        )

        test_content = "Test with special chars: @#$%^&*(). More text here! Question? " * 10
        test_doc = Document(page_content=test_content)

        state = {
            "document": [test_doc],
            "url": "https://example.com"
        }

        result = parse_node.execute(state)

        assert "parsed_doc" in result
        assert len(result["parsed_doc"]) >= 1
