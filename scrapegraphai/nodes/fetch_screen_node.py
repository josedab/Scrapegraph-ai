"""
fetch_screen_node module
"""

import asyncio
from typing import List, Optional

from playwright.sync_api import sync_playwright

from .base_node import BaseNode


class FetchScreenNode(BaseNode):
    """
    FetchScreenNode captures screenshots from a given URL and stores the image data as bytes.
    Supports both synchronous and asynchronous execution with browser pooling.
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "FetchScreen",
    ):
        super().__init__(node_name, "node", input, output, 2, node_config)
        self.url = node_config.get("link") if node_config else None

        # Browser pool configuration
        self.use_pool = (
            True if node_config is None else node_config.get("use_pool", True)
        )
        self.pool_config = (
            None if node_config is None else node_config.get("pool_config", None)
        )
        self.headless = (
            True if node_config is None else node_config.get("headless", True)
        )

    def execute(self, state: dict) -> dict:
        """
        Captures screenshots from the input URL and stores them in the state dictionary as bytes.
        """
        self.logger.info(f"--- Executing {self.node_name} Node ---")

        # Try async execution with pooling first
        if self.use_pool:
            try:
                return asyncio.run(self._execute_async(state))
            except Exception as e:
                self.logger.warning(f"Async execution with pooling failed: {e}, falling back to sync")

        # Fallback to synchronous execution
        return self._execute_sync(state)

    def _execute_sync(self, state: dict) -> dict:
        """
        Synchronous execution (original behavior).
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto(self.url)

            viewport_height = page.viewport_size["height"]

            screenshot_counter = 1

            screenshot_data_list = []

            def capture_screenshot(scroll_position, counter):
                page.evaluate(f"window.scrollTo(0, {scroll_position});")
                screenshot_data = page.screenshot()
                screenshot_data_list.append(screenshot_data)

            capture_screenshot(0, screenshot_counter)
            screenshot_counter += 1
            capture_screenshot(viewport_height, screenshot_counter)

            browser.close()

        state["link"] = self.url
        state["screenshots"] = screenshot_data_list

        return state

    async def _execute_async(self, state: dict) -> dict:
        """
        Asynchronous execution with browser pooling support.
        """
        from ..utils.browser_pool import BrowserPoolManager, PoolConfig

        # Create pool config
        pool_config = None
        if self.pool_config:
            pool_config = PoolConfig.from_dict(self.pool_config)

        browser, context = await BrowserPoolManager.acquire_context(
            config=pool_config,
            stealth=False,
        )

        try:
            page = await context.new_page()
            await page.goto(self.url)

            viewport_size = page.viewport_size
            viewport_height = viewport_size["height"] if viewport_size else 800

            screenshot_data_list = []

            async def capture_screenshot(scroll_position):
                await page.evaluate(f"window.scrollTo(0, {scroll_position});")
                screenshot_data = await page.screenshot()
                screenshot_data_list.append(screenshot_data)

            # Capture screenshots at different scroll positions
            await capture_screenshot(0)
            await capture_screenshot(viewport_height)

            state["link"] = self.url
            state["screenshots"] = screenshot_data_list

            return state
        finally:
            await page.close()
            # Release context back to pool
            await BrowserPoolManager.release_context(
                browser, context, close_context=True
            )
