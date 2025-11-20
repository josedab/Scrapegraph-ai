"""
split_text_into_chunks module with enhanced semantic chunking and overlap support
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

from .tokenizer import num_tokens_calculus


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


def _extract_overlap(text: str, overlap_tokens: int, token_counter: callable) -> str:
    """
    Extract the last N tokens worth of text for overlap.

    Args:
        text: The text to extract overlap from
        overlap_tokens: Number of tokens to extract
        token_counter: Function to count tokens

    Returns:
        str: The overlap text
    """
    if overlap_tokens == 0 or not text:
        return ""

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
    """
    Check if text starts and ends at complete sentence boundaries.

    Args:
        text: The text to check

    Returns:
        bool: True if text has complete boundaries
    """
    if not text:
        return True

    text = text.strip()

    # Check if starts with capital letter or quote
    starts_complete = text[0].isupper() or text[0] in ['"', "'", '(', '[']

    # Check if ends with sentence-ending punctuation
    ends_complete = text[-1] in ['.', '!', '?', '"', "'", ')', ']']

    return starts_complete and ends_complete


def _estimate_overlap_chars(text: str, overlap_tokens: int, token_counter: callable) -> int:
    """
    Estimate character count for given token overlap.

    Args:
        text: The text to estimate from
        overlap_tokens: Number of tokens for overlap
        token_counter: Function to count tokens

    Returns:
        int: Estimated character count
    """
    if overlap_tokens == 0 or not text:
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


def _chunk_semantic_with_overlap(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Enhanced semantic chunking with explicit overlap control.

    Improves upon semchunk by adding configurable overlap and metadata.

    Args:
        text: The text to chunk
        chunk_size: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap
        token_counter: Function to count tokens

    Returns:
        List[EnhancedChunk]: List of enhanced chunks with metadata
    """
    try:
        from semchunk import chunk

        # Use semchunk for initial semantic splitting
        # Reduce chunk size slightly to account for overlap
        adjusted_chunk_size = min(chunk_size, int(chunk_size * 0.9))
        base_chunks = chunk(
            text=text,
            chunk_size=adjusted_chunk_size,
            token_counter=token_counter,
            memoize=False
        )

        # Add overlap between consecutive chunks
        enhanced_chunks = []
        for i, current_chunk in enumerate(base_chunks):
            chunk_text = current_chunk

            if i > 0:
                # Add overlap from previous chunk
                prev_chunk = base_chunks[i-1]
                overlap_text = _extract_overlap(prev_chunk, overlap_tokens, token_counter)
                if overlap_text:
                    chunk_text = overlap_text + " " + current_chunk

            # Calculate overlap boundary for next chunk
            if i < len(base_chunks) - 1:
                overlap_boundary = len(chunk_text) - _estimate_overlap_chars(
                    chunk_text, overlap_tokens, token_counter
                )
            else:
                overlap_boundary = None

            metadata = ChunkMetadata(
                chunk_index=i,
                total_chunks=len(base_chunks),
                start_position=0,  # Would track in original text
                end_position=len(chunk_text),
                overlap_end=overlap_boundary,
                is_boundary_complete=_check_boundary_completeness(chunk_text),
                token_count=token_counter(chunk_text)
            )

            enhanced_chunks.append(EnhancedChunk(text=chunk_text, metadata=metadata))

        return enhanced_chunks

    except ImportError:
        # Fallback to recursive strategy if semchunk not available
        return _chunk_recursive(text, chunk_size, overlap_tokens, token_counter)


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

    Args:
        text: The text to chunk
        chunk_size: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap
        token_counter: Function to count tokens

    Returns:
        List[EnhancedChunk]: List of enhanced chunks with metadata
    """
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        # Fallback if langchain not available
        return _chunk_by_words_with_overlap(text, chunk_size, overlap_tokens, token_counter)

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


def _chunk_by_sentences(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Split text into chunks at sentence boundaries with overlap.

    Ensures no sentence is ever split across chunks.

    Args:
        text: The text to chunk
        chunk_size: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap
        token_counter: Function to count tokens

    Returns:
        List[EnhancedChunk]: List of enhanced chunks with metadata
    """
    try:
        import nltk
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
            nltk.download('punkt_tab', quiet=True)

        # Split into sentences
        sentences = nltk.sent_tokenize(text)
    except (ImportError, LookupError):
        # Fallback to simple sentence splitting if NLTK not available
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)

    chunks = []
    current_chunk = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = token_counter(sentence)

        # Check if adding this sentence exceeds chunk size
        if current_tokens + sentence_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)

            # Calculate overlap: keep last N sentences that fit in overlap_tokens
            overlap_sentences = []
            overlap_token_count = 0
            for s in reversed(current_chunk):
                s_tokens = token_counter(s)
                if overlap_token_count + s_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_token_count += s_tokens
                else:
                    break

            # Start new chunk with overlap
            current_chunk = overlap_sentences + [sentence]
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


def _chunk_by_paragraphs(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Split text into chunks at paragraph boundaries with overlap.

    Ensures no paragraph is split across chunks when possible.

    Args:
        text: The text to chunk
        chunk_size: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap
        token_counter: Function to count tokens

    Returns:
        List[EnhancedChunk]: List of enhanced chunks with metadata
    """
    # Split into paragraphs (double newline)
    paragraphs = text.split('\n\n')

    chunks = []
    current_chunk = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        paragraph_tokens = token_counter(paragraph)

        # Check if adding this paragraph exceeds chunk size
        if current_tokens + paragraph_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)

            # Calculate overlap: keep last N paragraphs that fit in overlap_tokens
            overlap_paragraphs = []
            overlap_token_count = 0
            for p in reversed(current_chunk):
                p_tokens = token_counter(p)
                if overlap_token_count + p_tokens <= overlap_tokens:
                    overlap_paragraphs.insert(0, p)
                    overlap_token_count += p_tokens
                else:
                    break

            # Start new chunk with overlap
            current_chunk = overlap_paragraphs + [paragraph]
            current_tokens = overlap_token_count + paragraph_tokens
        else:
            current_chunk.append(paragraph)
            current_tokens += paragraph_tokens

    # Add final chunk
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    # Create enhanced chunks with metadata
    enhanced_chunks = []
    for i, chunk_text in enumerate(chunks):
        metadata = ChunkMetadata(
            chunk_index=i,
            total_chunks=len(chunks),
            start_position=0,
            end_position=len(chunk_text),
            is_boundary_complete=_check_boundary_completeness(chunk_text),
            token_count=token_counter(chunk_text)
        )
        enhanced_chunks.append(EnhancedChunk(text=chunk_text, metadata=metadata))

    return enhanced_chunks


def _chunk_by_words_legacy(
    text: str,
    chunk_size: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Legacy word-based chunking without overlap (for backward compatibility).

    Args:
        text: The text to chunk
        chunk_size: Maximum tokens per chunk
        token_counter: Function to count tokens

    Returns:
        List[EnhancedChunk]: List of enhanced chunks with metadata
    """
    tokens = token_counter(text)

    if tokens <= chunk_size:
        metadata = ChunkMetadata(
            chunk_index=0,
            total_chunks=1,
            start_position=0,
            end_position=len(text),
            is_boundary_complete=True,
            token_count=tokens
        )
        return [EnhancedChunk(text=text, metadata=metadata)]

    chunks = []
    current_chunk = []
    current_length = 0

    words = text.split()
    for word in words:
        word_tokens = token_counter(word)
        if current_length + word_tokens > chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_tokens
        else:
            current_chunk.append(word)
            current_length += word_tokens

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
            is_boundary_complete=False,  # Word-based often breaks mid-sentence
            token_count=token_counter(chunk_text)
        )
        enhanced_chunks.append(EnhancedChunk(text=chunk_text, metadata=metadata))

    return enhanced_chunks


def _chunk_by_words_with_overlap(
    text: str,
    chunk_size: int,
    overlap_tokens: int,
    token_counter: callable
) -> List[EnhancedChunk]:
    """
    Word-based chunking with overlap.

    Args:
        text: The text to chunk
        chunk_size: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap
        token_counter: Function to count tokens

    Returns:
        List[EnhancedChunk]: List of enhanced chunks with metadata
    """
    tokens = token_counter(text)

    if tokens <= chunk_size:
        metadata = ChunkMetadata(
            chunk_index=0,
            total_chunks=1,
            start_position=0,
            end_position=len(text),
            is_boundary_complete=True,
            token_count=tokens
        )
        return [EnhancedChunk(text=text, metadata=metadata)]

    chunks = []
    words = text.split()
    current_chunk = []
    current_tokens = 0

    i = 0
    while i < len(words):
        word = words[i]
        word_tokens = token_counter(word)

        if current_tokens + word_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = " ".join(current_chunk)
            chunks.append(chunk_text)

            # Calculate overlap
            overlap_words = []
            overlap_token_count = 0
            for w in reversed(current_chunk):
                w_tokens = token_counter(w)
                if overlap_token_count + w_tokens <= overlap_tokens:
                    overlap_words.insert(0, w)
                    overlap_token_count += w_tokens
                else:
                    break

            # Start new chunk with overlap
            current_chunk = overlap_words
            current_tokens = overlap_token_count
        else:
            current_chunk.append(word)
            current_tokens += word_tokens
            i += 1

    # Add final chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    # Create enhanced chunks with metadata
    enhanced_chunks = []
    for idx, chunk_text in enumerate(chunks):
        metadata = ChunkMetadata(
            chunk_index=idx,
            total_chunks=len(chunks),
            start_position=0,
            end_position=len(chunk_text),
            is_boundary_complete=False,  # Word-based often breaks mid-sentence
            token_count=token_counter(chunk_text)
        )
        enhanced_chunks.append(EnhancedChunk(text=chunk_text, metadata=metadata))

    return enhanced_chunks


def split_text_into_chunks(
    text: str,
    chunk_size: int,
    overlap_size: Optional[int] = None,
    overlap_percentage: float = 0.1,
    strategy: Union[ChunkStrategy, str] = ChunkStrategy.SEMANTIC,
    preserve_boundaries: bool = True,
    return_metadata: bool = False,
    use_semchunk: bool = True,  # Backward compatibility
) -> Union[List[str], List[EnhancedChunk]]:
    """
    Split text into chunks with configurable overlap and boundary detection.

    Args:
        text: The text to split
        chunk_size: Maximum tokens per chunk
        overlap_size: Fixed token overlap between chunks (overrides percentage)
        overlap_percentage: Percentage of chunk_size to overlap (default 10%)
        strategy: Chunking strategy to use (ChunkStrategy enum or string)
        preserve_boundaries: If True, avoid breaking mid-sentence
        return_metadata: If True, return EnhancedChunk objects with metadata
        use_semchunk: Backward compatibility flag (deprecated, use strategy instead)

    Returns:
        List of text chunks or EnhancedChunk objects

    Examples:
        >>> # Default semantic chunking with 10% overlap
        >>> chunks = split_text_into_chunks(text, chunk_size=1000)

        >>> # Sentence-based chunking with 15% overlap
        >>> chunks = split_text_into_chunks(
        ...     text, chunk_size=1000,
        ...     overlap_percentage=0.15,
        ...     strategy=ChunkStrategy.SENTENCE
        ... )

        >>> # Fixed overlap with metadata
        >>> chunks = split_text_into_chunks(
        ...     text, chunk_size=1000,
        ...     overlap_size=100,
        ...     return_metadata=True
        ... )
    """
    # Validate input
    if not text or not text.strip():
        return []

    # Handle backward compatibility
    if not use_semchunk and strategy == ChunkStrategy.SEMANTIC:
        strategy = ChunkStrategy.WORD

    # Convert string strategy to enum if needed
    if isinstance(strategy, str):
        try:
            strategy = ChunkStrategy(strategy.lower())
        except ValueError:
            # Default to semantic if invalid strategy
            strategy = ChunkStrategy.SEMANTIC

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
        if overlap_size > 0:
            chunks = _chunk_by_words_with_overlap(
                text, chunk_size, overlap_size, num_tokens_calculus
            )
        else:
            chunks = _chunk_by_words_legacy(text, chunk_size, num_tokens_calculus)

    # Return based on metadata preference
    if return_metadata:
        return chunks
    else:
        return [chunk.text if isinstance(chunk, EnhancedChunk) else chunk
                for chunk in chunks]
