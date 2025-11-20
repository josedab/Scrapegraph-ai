"""
Content Normalizer for Incremental Scraping

This module provides functions to normalize HTML content to reduce
false positives in change detection. It removes dynamic elements
like timestamps, session IDs, and ads that don't represent real
content changes.
"""

import re
from typing import Optional, List, Tuple

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    BeautifulSoup = None
    Comment = None


def normalize_html(html: str, aggressive: bool = False) -> str:
    """
    Normalize HTML content to reduce false positives in change detection.

    This function removes dynamic elements that frequently change but don't
    represent meaningful content updates:
    - Scripts and styles
    - Comments
    - Timestamps and dates
    - Session IDs and tokens
    - Optionally: ads, tracking, iframes

    Args:
        html: Raw HTML content
        aggressive: If True, remove more dynamic elements (ads, iframes, etc.)

    Returns:
        Normalized text string with reduced false positive markers
    """
    if BeautifulSoup is None:
        # Fallback to regex-based normalization if BeautifulSoup not available
        return _normalize_html_regex(html, aggressive)

    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception:
        # Fallback if parsing fails
        return _normalize_html_regex(html, aggressive)

    # Remove script and style tags
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    # Remove comments
    if Comment:
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    if aggressive:
        # Remove common dynamic elements
        for tag in soup.find_all(['iframe', 'embed', 'object']):
            tag.decompose()

        # Remove ads and tracking (common class/id patterns)
        ad_patterns = re.compile(
            r'ad|advertisement|tracking|analytics|banner|sponsor',
            re.IGNORECASE
        )

        for tag in soup.find_all(class_=ad_patterns):
            tag.decompose()

        for tag in soup.find_all(id=ad_patterns):
            tag.decompose()

    # Get text and normalize whitespace
    text = soup.get_text(separator=' ', strip=True)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove common dynamic patterns
    text = _remove_dynamic_patterns(text)

    return text.strip()


def _normalize_html_regex(html: str, aggressive: bool = False) -> str:
    """
    Regex-based normalization fallback when BeautifulSoup is not available.

    Args:
        html: Raw HTML content
        aggressive: If True, remove more dynamic elements

    Returns:
        Normalized text string
    """
    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML comments
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    if aggressive:
        # Remove iframes, embeds, objects
        html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<embed[^>]*/?>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<object[^>]*>.*?</object>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)

    # Decode HTML entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove dynamic patterns
    text = _remove_dynamic_patterns(text)

    return text.strip()


def _remove_dynamic_patterns(text: str) -> str:
    """
    Remove common dynamic patterns from text.

    Args:
        text: Text content

    Returns:
        Text with dynamic patterns replaced
    """
    # ISO 8601 timestamps
    text = re.sub(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?',
        '[TIMESTAMP]',
        text
    )

    # Unix timestamps (10-13 digits)
    text = re.sub(r'\b\d{10,13}\b', '[TIMESTAMP]', text)

    # Common date formats
    text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', '[DATE]', text)
    text = re.sub(r'\b\d{1,2}-\d{1,2}-\d{2,4}\b', '[DATE]', text)

    # Session IDs
    text = re.sub(
        r'session[_-]?id[=:]\s*[a-zA-Z0-9_-]+',
        'session_id=[ID]',
        text,
        flags=re.IGNORECASE
    )

    # CSRF tokens
    text = re.sub(
        r'csrf[_-]?token[=:]\s*[a-zA-Z0-9_-]+',
        'csrf_token=[TOKEN]',
        text,
        flags=re.IGNORECASE
    )

    # UUIDs
    text = re.sub(
        r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b',
        '[UUID]',
        text,
        flags=re.IGNORECASE
    )

    # Common tracking parameters
    text = re.sub(r'utm_[a-z]+=[^&\s]+', 'utm_param=[TRACKING]', text, flags=re.IGNORECASE)
    text = re.sub(r'fbclid=[^&\s]+', 'fbclid=[TRACKING]', text, flags=re.IGNORECASE)
    text = re.sub(r'gclid=[^&\s]+', 'gclid=[TRACKING]', text, flags=re.IGNORECASE)

    return text


def normalize_custom(html: str, patterns: List[Tuple[str, str]]) -> str:
    """
    Apply custom normalization patterns to HTML content.

    This allows users to define their own patterns for content that
    should be normalized to reduce false positives.

    Args:
        html: Raw HTML content
        patterns: List of (regex_pattern, replacement) tuples

    Returns:
        Normalized HTML string with custom patterns applied

    Example:
        >>> patterns = [
        ...     (r'Last updated: .*', 'Last updated: [DATE]'),
        ...     (r'Viewed \d+ times', 'Viewed [N] times'),
        ... ]
        >>> normalized = normalize_custom(html, patterns)
    """
    # First apply standard normalization
    text = normalize_html(html, aggressive=True)

    # Then apply custom patterns
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)

    return text


def normalize_whitespace_only(text: str) -> str:
    """
    Normalize only whitespace without removing any content.

    Useful when you want to compare text but ignore whitespace differences.

    Args:
        text: Input text

    Returns:
        Text with normalized whitespace
    """
    # Replace all whitespace with single spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


def extract_main_content(html: str) -> str:
    """
    Extract main content from HTML, removing headers, footers, sidebars.

    This uses heuristics to identify and extract the main content area,
    which is useful for focusing on meaningful content changes.

    Args:
        html: Raw HTML content

    Returns:
        Extracted main content as text
    """
    if BeautifulSoup is None:
        return normalize_html(html)

    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception:
        return normalize_html(html)

    # Try to find main content using common patterns
    main_content = None

    # Look for semantic HTML5 tags
    for tag in ['main', 'article']:
        main_content = soup.find(tag)
        if main_content:
            break

    # Look for common content class/id patterns
    if not main_content:
        content_patterns = re.compile(
            r'content|main|article|post|entry|body',
            re.IGNORECASE
        )
        main_content = soup.find(id=content_patterns)
        if not main_content:
            main_content = soup.find(class_=content_patterns)

    # If still not found, use the body
    if not main_content:
        main_content = soup.find('body')

    # If even body not found, use entire soup
    if not main_content:
        main_content = soup

    # Remove unwanted elements from main content
    for tag in main_content.find_all(['header', 'footer', 'nav', 'aside']):
        tag.decompose()

    return normalize_html(str(main_content))
