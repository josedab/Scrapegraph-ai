"""
Anti-bot evasion utilities for ScrapeGraphAI.

This module provides strategies to make browser automation less detectable
by anti-bot systems through user-agent rotation, header randomization, and
human-like behavior simulation.
"""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .logging import get_logger

logger = get_logger("anti-bot")


@dataclass
class AntiBotConfig:
    """Configuration for anti-bot evasion strategies."""

    rotate_user_agents: bool = True
    randomize_headers: bool = True
    randomize_viewport: bool = True
    simulate_human_timing: bool = True
    min_action_delay: float = 0.1  # Minimum delay between actions
    max_action_delay: float = 0.5  # Maximum delay between actions
    custom_user_agents: List[str] = field(default_factory=list)


class AntiBotManager:
    """
    Manages anti-bot evasion strategies.

    Features:
    - User-agent rotation
    - Request header randomization
    - Viewport size randomization
    - Human-like timing simulation
    - Cookie jar management
    """

    # Common desktop user agents (updated 2024)
    DEFAULT_USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    # Common viewport sizes
    VIEWPORT_SIZES = [
        {"width": 1920, "height": 1080},  # Full HD
        {"width": 1366, "height": 768},  # Common laptop
        {"width": 1536, "height": 864},  # Scaled laptop
        {"width": 1440, "height": 900},  # MacBook Pro
        {"width": 1280, "height": 720},  # HD
    ]

    def __init__(self, config: Optional[AntiBotConfig] = None):
        self.config = config or AntiBotConfig()
        self._user_agents = self.config.custom_user_agents or self.DEFAULT_USER_AGENTS

    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        if not self.config.rotate_user_agents:
            return self._user_agents[0]
        return random.choice(self._user_agents)

    def get_random_viewport(self) -> Dict[str, int]:
        """Get a random viewport size."""
        if not self.config.randomize_viewport:
            return self.VIEWPORT_SIZES[0]
        return random.choice(self.VIEWPORT_SIZES)

    def get_randomized_headers(self) -> Dict[str, str]:
        """
        Get randomized HTTP headers.

        Returns common headers with slight randomization to avoid fingerprinting.
        """
        if not self.config.randomize_headers:
            return {}

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(
                [
                    "en-US,en;q=0.9",
                    "en-GB,en;q=0.9",
                    "en-US,en;q=0.5",
                ]
            ),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": str(random.choice([0, 1])),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # Randomly include or exclude certain headers
        if random.random() > 0.3:
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = random.choice(
                ["none", "same-origin", "cross-site"]
            )

        return headers

    async def apply_human_timing(self):
        """
        Add a random delay to simulate human behavior.

        Call this between actions (clicks, scrolls, etc.) to appear more human-like.
        """
        if not self.config.simulate_human_timing:
            return

        delay = random.uniform(
            self.config.min_action_delay, self.config.max_action_delay
        )
        await asyncio.sleep(delay)

    async def apply_to_context(self, context, page=None):
        """
        Apply anti-bot measures to a Playwright context and/or page.

        Args:
            context: Playwright BrowserContext
            page: Optional Playwright Page
        """
        # Set random viewport
        if self.config.randomize_viewport and page:
            viewport = self.get_random_viewport()
            await page.set_viewport_size(viewport)

        # Set extra headers
        if self.config.randomize_headers:
            headers = self.get_randomized_headers()
            await context.set_extra_http_headers(headers)

    def get_context_options(self) -> Dict:
        """
        Get context options for Playwright with anti-bot settings.

        Returns:
            Dict of options to pass to browser.new_context()
        """
        options = {}

        if self.config.rotate_user_agents:
            options["user_agent"] = self.get_random_user_agent()

        if self.config.randomize_viewport:
            options["viewport"] = self.get_random_viewport()

        # Additional options for better evasion
        options["locale"] = random.choice(["en-US", "en-GB", "en-CA"])
        options["timezone_id"] = random.choice(
            [
                "America/New_York",
                "America/Los_Angeles",
                "America/Chicago",
                "Europe/London",
            ]
        )

        return options
