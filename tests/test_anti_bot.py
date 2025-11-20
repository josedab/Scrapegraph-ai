"""
Tests for the AntiBotManager and related classes.
"""

import asyncio
import time
import pytest
from scrapegraphai.utils.anti_bot import AntiBotManager, AntiBotConfig


class TestAntiBotConfig:
    """Tests for AntiBotConfig dataclass."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = AntiBotConfig()
        assert config.rotate_user_agents is True
        assert config.randomize_headers is True
        assert config.randomize_viewport is True
        assert config.simulate_human_timing is True
        assert config.min_action_delay == 0.1
        assert config.max_action_delay == 0.5
        assert config.custom_user_agents == []

    def test_config_custom_values(self):
        """Test custom configuration values."""
        custom_agents = ["Custom Agent 1", "Custom Agent 2"]
        config = AntiBotConfig(
            rotate_user_agents=False,
            randomize_headers=False,
            randomize_viewport=False,
            simulate_human_timing=False,
            min_action_delay=0.2,
            max_action_delay=1.0,
            custom_user_agents=custom_agents,
        )
        assert config.rotate_user_agents is False
        assert config.randomize_headers is False
        assert config.randomize_viewport is False
        assert config.simulate_human_timing is False
        assert config.min_action_delay == 0.2
        assert config.max_action_delay == 1.0
        assert config.custom_user_agents == custom_agents


class TestAntiBotManager:
    """Tests for AntiBotManager class."""

    def test_initialization(self):
        """Test AntiBotManager initialization."""
        manager = AntiBotManager()
        assert manager.config is not None
        assert isinstance(manager.config, AntiBotConfig)
        assert len(manager._user_agents) > 0

    def test_initialization_with_config(self):
        """Test AntiBotManager initialization with custom config."""
        config = AntiBotConfig(rotate_user_agents=False)
        manager = AntiBotManager(config)
        assert manager.config.rotate_user_agents is False

    def test_initialization_with_custom_user_agents(self):
        """Test that custom user agents override defaults."""
        custom_agents = ["Custom Agent 1", "Custom Agent 2"]
        config = AntiBotConfig(custom_user_agents=custom_agents)
        manager = AntiBotManager(config)
        assert manager._user_agents == custom_agents

    def test_default_user_agents(self):
        """Test that default user agents are available."""
        manager = AntiBotManager()
        assert len(AntiBotManager.DEFAULT_USER_AGENTS) >= 6
        assert all(
            "Mozilla" in agent for agent in AntiBotManager.DEFAULT_USER_AGENTS
        )

    def test_viewport_sizes(self):
        """Test that viewport sizes are defined."""
        assert len(AntiBotManager.VIEWPORT_SIZES) >= 5
        assert all(
            "width" in size and "height" in size
            for size in AntiBotManager.VIEWPORT_SIZES
        )

    def test_get_random_user_agent_with_rotation(self):
        """Test getting random user agent with rotation enabled."""
        config = AntiBotConfig(rotate_user_agents=True)
        manager = AntiBotManager(config)

        # Get multiple user agents
        agents = [manager.get_random_user_agent() for _ in range(20)]

        # All should be valid
        assert all(agent in manager._user_agents for agent in agents)

        # With rotation, we should see some variation
        # (Note: there's a small chance this could fail due to random chance)
        assert len(set(agents)) > 1

    def test_get_random_user_agent_without_rotation(self):
        """Test getting user agent with rotation disabled."""
        config = AntiBotConfig(rotate_user_agents=False)
        manager = AntiBotManager(config)

        # Get multiple user agents
        agents = [manager.get_random_user_agent() for _ in range(10)]

        # All should be the same (first one)
        assert all(agent == manager._user_agents[0] for agent in agents)

    def test_get_random_viewport_with_randomization(self):
        """Test getting random viewport with randomization enabled."""
        config = AntiBotConfig(randomize_viewport=True)
        manager = AntiBotManager(config)

        # Get multiple viewports
        viewports = [manager.get_random_viewport() for _ in range(20)]

        # All should be valid
        assert all(
            viewport in AntiBotManager.VIEWPORT_SIZES for viewport in viewports
        )

        # With randomization, we should see some variation
        viewport_strs = [str(v) for v in viewports]
        assert len(set(viewport_strs)) > 1

    def test_get_random_viewport_without_randomization(self):
        """Test getting viewport without randomization."""
        config = AntiBotConfig(randomize_viewport=False)
        manager = AntiBotManager(config)

        # Get multiple viewports
        viewports = [manager.get_random_viewport() for _ in range(10)]

        # All should be the same (first one)
        assert all(viewport == AntiBotManager.VIEWPORT_SIZES[0] for viewport in viewports)

    def test_get_randomized_headers_enabled(self):
        """Test getting randomized headers when enabled."""
        config = AntiBotConfig(randomize_headers=True)
        manager = AntiBotManager(config)

        headers = manager.get_randomized_headers()

        # Check that common headers are present
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
        assert "DNT" in headers
        assert "Connection" in headers
        assert "Upgrade-Insecure-Requests" in headers

        # Check that values are valid
        assert headers["Accept"].startswith("text/html")
        assert headers["Connection"] == "keep-alive"
        assert headers["DNT"] in ["0", "1"]

    def test_get_randomized_headers_disabled(self):
        """Test getting headers when randomization is disabled."""
        config = AntiBotConfig(randomize_headers=False)
        manager = AntiBotManager(config)

        headers = manager.get_randomized_headers()

        # Should return empty dict
        assert headers == {}

    def test_get_randomized_headers_variation(self):
        """Test that headers show variation across multiple calls."""
        config = AntiBotConfig(randomize_headers=True)
        manager = AntiBotManager(config)

        # Get multiple sets of headers
        header_sets = [manager.get_randomized_headers() for _ in range(20)]

        # Check that Accept-Language varies
        languages = [h.get("Accept-Language") for h in header_sets]
        assert len(set(languages)) > 1

        # Check that DNT varies
        dnts = [h.get("DNT") for h in header_sets]
        assert len(set(dnts)) > 1

    @pytest.mark.asyncio
    async def test_apply_human_timing_enabled(self):
        """Test that human timing adds delay when enabled."""
        config = AntiBotConfig(
            simulate_human_timing=True,
            min_action_delay=0.1,
            max_action_delay=0.2,
        )
        manager = AntiBotManager(config)

        start = time.time()
        await manager.apply_human_timing()
        elapsed = time.time() - start

        # Should have a delay between min and max
        assert elapsed >= 0.09  # Allow some tolerance
        assert elapsed <= 0.25

    @pytest.mark.asyncio
    async def test_apply_human_timing_disabled(self):
        """Test that human timing is immediate when disabled."""
        config = AntiBotConfig(simulate_human_timing=False)
        manager = AntiBotManager(config)

        start = time.time()
        await manager.apply_human_timing()
        elapsed = time.time() - start

        # Should be immediate
        assert elapsed < 0.05

    def test_get_context_options_full(self):
        """Test getting context options with all features enabled."""
        config = AntiBotConfig(
            rotate_user_agents=True,
            randomize_viewport=True,
        )
        manager = AntiBotManager(config)

        options = manager.get_context_options()

        # Check that required fields are present
        assert "user_agent" in options
        assert "viewport" in options
        assert "locale" in options
        assert "timezone_id" in options

        # Check that values are valid
        assert options["user_agent"] in manager._user_agents
        assert options["viewport"] in AntiBotManager.VIEWPORT_SIZES
        assert options["locale"] in ["en-US", "en-GB", "en-CA"]
        assert options["timezone_id"] in [
            "America/New_York",
            "America/Los_Angeles",
            "America/Chicago",
            "Europe/London",
        ]

    def test_get_context_options_user_agent_disabled(self):
        """Test context options when user agent rotation is disabled."""
        config = AntiBotConfig(rotate_user_agents=False)
        manager = AntiBotManager(config)

        # Even with rotation disabled, should still include first user agent
        options = manager.get_context_options()
        assert "user_agent" in options
        assert options["user_agent"] == manager._user_agents[0]

    def test_get_context_options_viewport_disabled(self):
        """Test context options when viewport randomization is disabled."""
        config = AntiBotConfig(randomize_viewport=False)
        manager = AntiBotManager(config)

        options = manager.get_context_options()
        assert "viewport" in options
        assert options["viewport"] == AntiBotManager.VIEWPORT_SIZES[0]

    def test_get_context_options_variation(self):
        """Test that context options vary across multiple calls."""
        config = AntiBotConfig(
            rotate_user_agents=True,
            randomize_viewport=True,
        )
        manager = AntiBotManager(config)

        # Get multiple sets of options
        option_sets = [manager.get_context_options() for _ in range(20)]

        # Check for variation in user agents
        user_agents = [o["user_agent"] for o in option_sets]
        assert len(set(user_agents)) > 1

        # Check for variation in viewports
        viewports = [str(o["viewport"]) for o in option_sets]
        assert len(set(viewports)) > 1

        # Check for variation in locales
        locales = [o["locale"] for o in option_sets]
        assert len(set(locales)) > 1

        # Check for variation in timezones
        timezones = [o["timezone_id"] for o in option_sets]
        assert len(set(timezones)) > 1

    @pytest.mark.asyncio
    async def test_apply_to_context_basic(self):
        """Test applying anti-bot measures to a mock context."""
        manager = AntiBotManager()

        # Create a mock context
        class MockContext:
            def __init__(self):
                self.headers = None

            async def set_extra_http_headers(self, headers):
                self.headers = headers

        context = MockContext()

        # Apply to context
        await manager.apply_to_context(context)

        # Check that headers were set
        assert context.headers is not None
        assert len(context.headers) > 0

    @pytest.mark.asyncio
    async def test_apply_to_context_with_page(self):
        """Test applying anti-bot measures to context and page."""
        manager = AntiBotManager()

        # Create mock context and page
        class MockContext:
            def __init__(self):
                self.headers = None

            async def set_extra_http_headers(self, headers):
                self.headers = headers

        class MockPage:
            def __init__(self):
                self.viewport = None

            async def set_viewport_size(self, viewport):
                self.viewport = viewport

        context = MockContext()
        page = MockPage()

        # Apply to both
        await manager.apply_to_context(context, page)

        # Check that both were configured
        assert context.headers is not None
        assert page.viewport is not None

    @pytest.mark.asyncio
    async def test_apply_to_context_headers_disabled(self):
        """Test that headers aren't set when randomization is disabled."""
        config = AntiBotConfig(randomize_headers=False)
        manager = AntiBotManager(config)

        class MockContext:
            def __init__(self):
                self.headers = None

            async def set_extra_http_headers(self, headers):
                self.headers = headers

        context = MockContext()
        await manager.apply_to_context(context)

        # Headers should be empty
        assert context.headers == {}

    @pytest.mark.asyncio
    async def test_apply_to_context_viewport_disabled(self):
        """Test that viewport isn't set when randomization is disabled."""
        config = AntiBotConfig(randomize_viewport=False)
        manager = AntiBotManager(config)

        class MockContext:
            async def set_extra_http_headers(self, headers):
                pass

        class MockPage:
            def __init__(self):
                self.viewport = None

            async def set_viewport_size(self, viewport):
                self.viewport = viewport

        context = MockContext()
        page = MockPage()

        # Even with randomization disabled, viewport should still be set
        # (to the first default viewport)
        await manager.apply_to_context(context, page)
        assert page.viewport is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
