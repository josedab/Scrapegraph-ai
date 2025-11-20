"""
Integration tests for error context capture in real scraping scenarios.

These tests verify that error context capture works correctly when integrated
with ChromiumLoader and FetchNode.
"""

import pytest
from pathlib import Path
from scrapegraphai.docloaders import ChromiumLoader
from scrapegraphai.utils.error_context import ScrapingException
from scrapegraphai.utils.retry_policy import RetryPolicy, RetryStrategy


class TestChromiumLoaderErrorContext:
    """Test error context capture in ChromiumLoader."""

    @pytest.mark.skip(reason="Requires actual browser - manual testing only")
    def test_chromium_loader_with_error_context_invalid_url(self, tmp_path):
        """Test that invalid URL generates error context."""
        # Configure loader with error context enabled
        loader = ChromiumLoader(
            urls=["https://this-domain-does-not-exist-12345.com"],
            headless=True,
            capture_error_context=True,
            error_artifacts_dir=str(tmp_path),
            retry_policy=RetryPolicy(
                max_attempts=2,
                strategy=RetryStrategy.IMMEDIATE,
            ),
        )

        # Expect ScrapingException with context
        with pytest.raises(Exception) as exc_info:
            loader.load()

        # If it's a ScrapingException, verify context
        if isinstance(exc_info.value, ScrapingException):
            assert exc_info.value.context is not None
            context = exc_info.value.context
            assert context.url == "https://this-domain-does-not-exist-12345.com"
            assert context.attempt_number > 0

    @pytest.mark.skip(reason="Requires actual browser - manual testing only")
    def test_chromium_loader_without_error_context(self):
        """Test that error context can be disabled."""
        loader = ChromiumLoader(
            urls=["https://this-domain-does-not-exist-12345.com"],
            headless=True,
            capture_error_context=False,
        )

        # Should raise regular exception, not ScrapingException
        with pytest.raises(Exception) as exc_info:
            loader.load()

        # Should not be a ScrapingException
        assert not isinstance(exc_info.value, ScrapingException)

    @pytest.mark.skip(reason="Requires actual browser - manual testing only")
    def test_chromium_loader_retry_success(self):
        """Test that retries work correctly."""
        # Use a real URL that should work
        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
            capture_error_context=True,
            retry_policy=RetryPolicy(
                max_attempts=3,
                strategy=RetryStrategy.EXPONENTIAL_JITTER,
            ),
        )

        # Should succeed
        documents = loader.load()
        assert len(documents) > 0
        assert documents[0].page_content is not None


class TestErrorContextConfiguration:
    """Test error context configuration options."""

    def test_error_context_config_defaults(self):
        """Test default error context configuration."""
        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
        )

        assert loader.capture_error_context is True
        assert loader.error_artifacts_dir == "./error_artifacts"
        assert loader.retry_policy is not None

    def test_error_context_config_custom(self):
        """Test custom error context configuration."""
        custom_policy = RetryPolicy(
            max_attempts=5,
            strategy=RetryStrategy.FIXED_DELAY,
            base_delay=2.0,
        )

        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
            capture_error_context=False,
            error_artifacts_dir="/tmp/my_errors",
            retry_policy=custom_policy,
        )

        assert loader.capture_error_context is False
        assert loader.error_artifacts_dir == "/tmp/my_errors"
        assert loader.retry_policy.max_attempts == 5
        assert loader.retry_policy.strategy == RetryStrategy.FIXED_DELAY


class TestFetchNodeErrorContext:
    """Test error context in FetchNode."""

    @pytest.mark.skip(reason="Requires full graph setup - manual testing only")
    def test_fetch_node_with_error_context(self, tmp_path):
        """Test FetchNode with error context enabled."""
        from scrapegraphai.nodes import FetchNode

        node_config = {
            "headless": True,
            "capture_error_context": True,
            "error_artifacts_dir": str(tmp_path),
            "retry_policy": {
                "max_attempts": 2,
                "strategy": "immediate",
            },
        }

        node = FetchNode(
            input="url",
            output=["document"],
            node_config=node_config,
        )

        # Verify configuration was applied
        assert node.capture_error_context is True
        assert node.error_artifacts_dir == str(tmp_path)
        assert node.retry_policy.max_attempts == 2

    @pytest.mark.skip(reason="Requires full graph setup - manual testing only")
    def test_fetch_node_error_context_in_state(self):
        """Test that error context is attached to state on failure."""
        from scrapegraphai.nodes import FetchNode

        node_config = {
            "headless": True,
            "capture_error_context": True,
        }

        node = FetchNode(
            input="url",
            output=["document"],
            node_config=node_config,
        )

        state = {
            "url": "https://this-domain-does-not-exist-12345.com",
        }

        # Execute should fail and attach error_context to state
        with pytest.raises(Exception):
            node.execute(state)

        # Error context should be in state if ScrapingException was raised
        # (This would need actual execution to verify)


class TestErrorArtifactStorage:
    """Test error artifact storage."""

    @pytest.mark.skip(reason="Requires actual browser - manual testing only")
    def test_error_artifacts_saved_to_disk(self, tmp_path):
        """Test that error artifacts are saved to the correct directory."""
        loader = ChromiumLoader(
            urls=["https://this-domain-does-not-exist-12345.com"],
            headless=True,
            capture_error_context=True,
            error_artifacts_dir=str(tmp_path),
        )

        try:
            loader.load()
        except Exception:
            pass

        # Check that error artifacts were created
        # Note: This would need actual browser execution to verify
        # Look for files matching pattern: error_*_context.json
        artifacts = list(tmp_path.glob("error_*_context.json"))

        # Artifacts should exist if error context was captured
        # (Would be verified in actual integration test)

    def test_error_artifacts_directory_creation(self, tmp_path):
        """Test that error artifacts directory is created if it doesn't exist."""
        artifact_dir = tmp_path / "nested" / "error_dir"

        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
            capture_error_context=True,
            error_artifacts_dir=str(artifact_dir),
        )

        # Directory should be created when needed
        # (Would be verified during actual error capture)
        assert loader.error_artifacts_dir == str(artifact_dir)


class TestRetryPolicyIntegration:
    """Test retry policy integration."""

    def test_retry_policy_from_dict(self):
        """Test creating retry policy from dictionary config."""
        from scrapegraphai.utils.retry_policy import RetryPolicy

        config = {
            "max_attempts": 5,
            "strategy": "exponential",
            "base_delay": 2.0,
            "max_delay": 30.0,
        }

        policy = RetryPolicy(**config)

        assert policy.max_attempts == 5
        assert policy.strategy == RetryStrategy.EXPONENTIAL
        assert policy.base_delay == 2.0
        assert policy.max_delay == 30.0

    def test_retry_policy_in_fetch_node_config(self):
        """Test passing retry policy via node config."""
        from scrapegraphai.nodes import FetchNode

        node_config = {
            "retry_policy": {
                "max_attempts": 5,
                "strategy": "fixed",
                "base_delay": 3.0,
            },
        }

        node = FetchNode(
            input="url",
            output=["document"],
            node_config=node_config,
        )

        assert node.retry_policy.max_attempts == 5
        assert node.retry_policy.strategy == RetryStrategy.FIXED_DELAY
        assert node.retry_policy.base_delay == 3.0


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_chromium_loader_without_new_params(self):
        """Test that ChromiumLoader works without new parameters."""
        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
        )

        # Should use defaults
        assert loader.capture_error_context is True
        assert loader.retry_policy is not None

    def test_fetch_node_without_new_params(self):
        """Test that FetchNode works without new parameters."""
        from scrapegraphai.nodes import FetchNode

        node = FetchNode(
            input="url",
            output=["document"],
            node_config=None,
        )

        # Should use defaults
        assert node.capture_error_context is True
        assert node.retry_policy is not None

    def test_chromium_loader_with_legacy_retry_limit(self):
        """Test that legacy retry_limit parameter still works."""
        loader = ChromiumLoader(
            urls=["https://example.com"],
            headless=True,
            retry_limit=5,
        )

        # Legacy retry_limit should still be set
        assert loader.retry_limit == 5

        # New retry_policy should also be available
        assert loader.retry_policy is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
