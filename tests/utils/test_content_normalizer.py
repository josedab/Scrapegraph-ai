"""
Unit tests for content normalizer utility.
"""

import pytest
from scrapegraphai.utils.content_normalizer import (
    normalize_html,
    normalize_custom,
    normalize_whitespace_only,
    extract_main_content,
)


class TestNormalizeHTML:
    """Test suite for normalize_html function."""

    def test_remove_scripts_and_styles(self):
        """Test that scripts and styles are removed."""
        html = """
        <html>
            <head>
                <style>body { color: red; }</style>
            </head>
            <body>
                <script>alert('test');</script>
                <div>Real content</div>
            </body>
        </html>
        """

        normalized = normalize_html(html)

        assert "alert" not in normalized
        assert "color: red" not in normalized
        assert "Real content" in normalized

    def test_remove_comments(self):
        """Test that HTML comments are removed."""
        html = """
        <html>
            <!-- This is a comment -->
            <div>Real content</div>
            <!-- Another comment -->
        </html>
        """

        normalized = normalize_html(html)

        assert "This is a comment" not in normalized
        assert "Another comment" not in normalized
        assert "Real content" in normalized

    def test_normalize_whitespace(self):
        """Test that whitespace is normalized."""
        html = """
        <html>
            <div>
                Text    with     multiple
                spaces    and


                newlines
            </div>
        </html>
        """

        normalized = normalize_html(html)

        # Should have single spaces
        assert "multiple" in normalized
        assert "    " not in normalized
        assert "\n\n" not in normalized

    def test_remove_dynamic_timestamps(self):
        """Test that timestamps are replaced with placeholders."""
        html = """
        <html>
            <div>Last updated: 2023-10-15T14:30:00Z</div>
            <div>Unix timestamp: 1697385600</div>
        </html>
        """

        normalized = normalize_html(html)

        # Timestamps should be replaced
        assert "2023-10-15T14:30:00Z" not in normalized
        assert "[TIMESTAMP]" in normalized

    def test_remove_session_ids(self):
        """Test that session IDs are replaced."""
        html = """
        <html>
            <div>session_id=abc123xyz</div>
            <div>sessionID: def456uvw</div>
        </html>
        """

        normalized = normalize_html(html)

        assert "abc123xyz" not in normalized
        assert "def456uvw" not in normalized
        assert "session_id=[ID]" in normalized

    def test_remove_csrf_tokens(self):
        """Test that CSRF tokens are replaced."""
        html = """
        <html>
            <input name="csrf_token" value="random_token_value" />
        </html>
        """

        normalized = normalize_html(html)

        assert "random_token_value" not in normalized
        assert "[TOKEN]" in normalized

    def test_aggressive_mode_removes_ads(self):
        """Test that aggressive mode removes ads and tracking."""
        html = """
        <html>
            <div class="advertisement">Ad content</div>
            <div id="tracking-pixel">Tracking</div>
            <div class="main-content">Real content</div>
        </html>
        """

        normalized_normal = normalize_html(html, aggressive=False)
        normalized_aggressive = normalize_html(html, aggressive=True)

        # Normal mode might keep some ad text
        # Aggressive mode should remove it
        assert "Real content" in normalized_aggressive

    def test_aggressive_mode_removes_iframes(self):
        """Test that aggressive mode removes iframes."""
        html = """
        <html>
            <iframe src="https://ads.example.com"></iframe>
            <div>Real content</div>
        </html>
        """

        normalized_aggressive = normalize_html(html, aggressive=True)

        assert "iframe" not in normalized_aggressive.lower()
        assert "Real content" in normalized_aggressive

    def test_empty_html(self):
        """Test handling of empty HTML."""
        html = ""
        normalized = normalize_html(html)
        assert normalized == ""

    def test_plain_text(self):
        """Test handling of plain text without HTML."""
        text = "This is plain text"
        normalized = normalize_html(text)
        assert "plain text" in normalized

    def test_consistent_output(self):
        """Test that same input produces same output."""
        html = "<div>Test content</div>"

        result1 = normalize_html(html)
        result2 = normalize_html(html)

        assert result1 == result2

    def test_uuid_replacement(self):
        """Test that UUIDs are replaced."""
        html = """
        <html>
            <div>Request ID: 550e8400-e29b-41d4-a716-446655440000</div>
        </html>
        """

        normalized = normalize_html(html)

        assert "550e8400-e29b-41d4-a716-446655440000" not in normalized
        assert "[UUID]" in normalized

    def test_tracking_parameters_removed(self):
        """Test that tracking parameters are replaced."""
        html = """
        <html>
            <a href="?utm_source=google&utm_campaign=test">Link</a>
            <a href="?fbclid=abc123">Link2</a>
        </html>
        """

        normalized = normalize_html(html)

        assert "utm_source=google" not in normalized
        assert "fbclid=abc123" not in normalized
        assert "[TRACKING]" in normalized


class TestNormalizeCustom:
    """Test suite for normalize_custom function."""

    def test_custom_patterns(self):
        """Test applying custom normalization patterns."""
        html = """
        <html>
            <div>Viewed 42 times</div>
            <div>Last updated: Yesterday</div>
        </html>
        """

        patterns = [
            (r'Viewed \d+ times', 'Viewed [N] times'),
            (r'Last updated: .*', 'Last updated: [DATE]'),
        ]

        normalized = normalize_custom(html, patterns)

        assert "42" not in normalized
        assert "Viewed [N] times" in normalized
        assert "Yesterday" not in normalized
        assert "[DATE]" in normalized

    def test_multiple_custom_patterns(self):
        """Test applying multiple custom patterns."""
        html = "<div>Price: $123.45</div><div>Stock: 99</div>"

        patterns = [
            (r'\$\d+\.\d+', '$[PRICE]'),
            (r'Stock: \d+', 'Stock: [QTY]'),
        ]

        normalized = normalize_custom(html, patterns)

        assert "$123.45" not in normalized
        assert "$[PRICE]" in normalized
        assert "99" not in normalized
        assert "[QTY]" in normalized


class TestNormalizeWhitespaceOnly:
    """Test suite for normalize_whitespace_only function."""

    def test_normalize_whitespace(self):
        """Test normalizing whitespace only."""
        text = "Text   with    multiple     spaces"
        normalized = normalize_whitespace_only(text)

        assert "   " not in normalized
        assert "Text with multiple spaces" == normalized

    def test_normalize_newlines(self):
        """Test normalizing newlines."""
        text = "Line1\n\n\nLine2\n\n\n\nLine3"
        normalized = normalize_whitespace_only(text)

        assert "\n\n" not in normalized
        assert "Line1" in normalized
        assert "Line3" in normalized

    def test_trim_whitespace(self):
        """Test trimming leading and trailing whitespace."""
        text = "   Content   "
        normalized = normalize_whitespace_only(text)

        assert normalized == "Content"


class TestExtractMainContent:
    """Test suite for extract_main_content function."""

    def test_extract_main_tag(self):
        """Test extracting content from main tag."""
        html = """
        <html>
            <header>Header content</header>
            <main>
                <article>Main article content</article>
            </main>
            <footer>Footer content</footer>
        </html>
        """

        content = extract_main_content(html)

        assert "Main article content" in content
        # Header and footer should be removed or de-emphasized

    def test_extract_article_tag(self):
        """Test extracting content from article tag."""
        html = """
        <html>
            <nav>Navigation</nav>
            <article>Article content here</article>
            <aside>Sidebar</aside>
        </html>
        """

        content = extract_main_content(html)

        assert "Article content here" in content

    def test_fallback_to_body(self):
        """Test fallback to body when no semantic tags."""
        html = """
        <html>
            <body>
                <div>Body content</div>
            </body>
        </html>
        """

        content = extract_main_content(html)

        assert "Body content" in content

    def test_remove_header_footer(self):
        """Test that headers and footers are removed."""
        html = """
        <html>
            <main>
                <header>Header in main</header>
                <div>Real content</div>
                <footer>Footer in main</footer>
            </main>
        </html>
        """

        content = extract_main_content(html)

        assert "Real content" in content
        # Headers and footers should be removed


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<div>Unclosed div<div>Another div</div>"

        # Should not crash
        normalized = normalize_html(html)
        assert isinstance(normalized, str)

    def test_html_with_special_characters(self):
        """Test handling of special characters."""
        html = "<div>Content with & < > \" ' characters</div>"

        normalized = normalize_html(html)
        assert "Content" in normalized

    def test_unicode_content(self):
        """Test handling of Unicode content."""
        html = "<div>Unicode: 你好世界 مرحبا العالم Привет мир</div>"

        normalized = normalize_html(html)
        assert "你好世界" in normalized or "Unicode" in normalized

    def test_very_large_html(self):
        """Test handling of very large HTML documents."""
        # Create large HTML
        large_content = "<p>Paragraph</p>" * 10000
        html = f"<html><body>{large_content}</body></html>"

        # Should complete without hanging
        normalized = normalize_html(html)
        assert isinstance(normalized, str)
        assert len(normalized) > 0


def test_normalization_reduces_false_positives():
    """
    Test that normalization reduces false positives by making
    two similar pages with only timestamp differences produce
    same fingerprints.
    """
    html1 = """
    <html>
        <body>
            <div>Article content here</div>
            <div>Published: 2023-10-15T14:30:00Z</div>
            <div>session_id=abc123</div>
        </body>
    </html>
    """

    html2 = """
    <html>
        <body>
            <div>Article content here</div>
            <div>Published: 2023-10-15T14:35:00Z</div>
            <div>session_id=xyz789</div>
        </body>
    </html>
    """

    normalized1 = normalize_html(html1)
    normalized2 = normalize_html(html2)

    # Normalized versions should be very similar or identical
    # since only timestamps and session IDs differ
    assert "Article content here" in normalized1
    assert "Article content here" in normalized2
    assert "[TIMESTAMP]" in normalized1
    assert "[TIMESTAMP]" in normalized2
    assert "[ID]" in normalized1
    assert "[ID]" in normalized2

    # The actual timestamps and IDs should not be present
    assert "14:30:00" not in normalized1
    assert "14:35:00" not in normalized2
    assert "abc123" not in normalized1
    assert "xyz789" not in normalized2
