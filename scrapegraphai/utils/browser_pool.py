"""
Browser Connection Pool Module

This module provides browser connection pooling and lifecycle management for Playwright
browser instances, dramatically reducing startup overhead and improving scraping performance.

Classes:
    BrowserInstance: Represents a managed browser instance in the pool
    PoolConfig: Configuration dataclass for the browser pool
    BrowserPool: Manages a pool of reusable browser instances
    BrowserPoolManager: Singleton manager for the global browser pool
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import asyncio
import time
import os
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from ..utils import get_logger

logger = get_logger("browser-pool")


@dataclass
class BrowserInstance:
    """Represents a managed browser instance in the pool."""
    browser: Browser
    contexts: List[BrowserContext] = field(default_factory=list)
    last_used: float = field(default_factory=time.time)
    in_use: bool = False
    health_check_failures: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class PoolConfig:
    """Configuration for the browser pool."""
    min_browsers: int = 1
    max_browsers: int = 10
    max_contexts_per_browser: int = 5
    browser_ttl_seconds: int = 300  # 5 minutes
    context_ttl_seconds: int = 120  # 2 minutes
    health_check_interval: int = 30
    max_health_check_failures: int = 3
    browser_type: str = "chromium"
    headless: bool = True
    launch_options: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'PoolConfig':
        """Create a PoolConfig from a dictionary, filtering unknown keys."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_config = {k: v for k, v in config_dict.items() if k in valid_fields}
        return cls(**filtered_config)

    @classmethod
    def from_env(cls) -> 'PoolConfig':
        """Create a PoolConfig from environment variables."""
        return cls(
            min_browsers=int(os.getenv('SCRAPEGRAPH_BROWSER_POOL_MIN_BROWSERS', '1')),
            max_browsers=int(os.getenv('SCRAPEGRAPH_BROWSER_POOL_MAX_BROWSERS', '10')),
            max_contexts_per_browser=int(os.getenv('SCRAPEGRAPH_BROWSER_POOL_MAX_CONTEXTS', '5')),
            browser_ttl_seconds=int(os.getenv('SCRAPEGRAPH_BROWSER_POOL_BROWSER_TTL', '300')),
            context_ttl_seconds=int(os.getenv('SCRAPEGRAPH_BROWSER_POOL_CONTEXT_TTL', '120')),
            headless=os.getenv('SCRAPEGRAPH_BROWSER_POOL_HEADLESS', 'true').lower() == 'true',
        )


class BrowserPool:
    """
    Manages a pool of reusable Playwright browser instances.

    Features:
    - Lazy initialization: browsers created on-demand
    - TTL-based expiration: stale browsers are recycled
    - Health checking: unhealthy browsers are removed
    - Context pooling: reuse contexts within browsers
    - Graceful degradation: falls back to creating new browsers on pool exhaustion
    """

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()
        self._playwright: Optional[Playwright] = None
        self._browsers: List[BrowserInstance] = []
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self._initialized = False

    async def initialize(self):
        """Initialize the pool and start background tasks."""
        if self._initialized:
            return

        logger.info("Initializing browser pool...")
        self._playwright = await async_playwright().start()

        # Pre-warm the pool with minimum browsers
        for _ in range(self.config.min_browsers):
            try:
                await self._create_browser()
            except Exception as e:
                logger.error(f"Failed to create browser during initialization: {e}")

        # Start health check background task
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._initialized = True
        logger.info(f"Browser pool initialized with {len(self._browsers)} browsers")

    async def _create_browser(self) -> BrowserInstance:
        """Create a new browser instance with configured options."""
        browser_launcher = getattr(self._playwright, self.config.browser_type)

        logger.debug(f"Creating new {self.config.browser_type} browser instance")
        browser = await browser_launcher.launch(
            headless=self.config.headless,
            **self.config.launch_options
        )

        instance = BrowserInstance(browser=browser)
        self._browsers.append(instance)
        logger.debug(f"Browser created. Pool size: {len(self._browsers)}")
        return instance

    async def acquire_context(
        self,
        stealth: bool = True,
        storage_state: Optional[str] = None,
        **context_options
    ) -> tuple[Browser, BrowserContext]:
        """
        Acquire a browser context from the pool.

        Args:
            stealth: Whether to apply stealth mode to the context
            storage_state: Optional storage state for the context
            **context_options: Additional context options

        Returns:
            A tuple of (browser, context) that should be released
            via release_context() when done.

        Raises:
            RuntimeError: If the pool is exhausted and cannot create new browsers
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            # Try to find an available browser with capacity
            instance = self._find_available_browser()

            if instance is None:
                # No available browser, create new if under limit
                if len(self._browsers) < self.config.max_browsers:
                    logger.debug("No available browser found, creating new one")
                    instance = await self._create_browser()
                else:
                    # Pool exhausted - try to find least busy browser
                    logger.warning("Browser pool exhausted, using least busy browser")
                    instance = min(self._browsers, key=lambda b: len(b.contexts))

            # Mark browser as in-use
            instance.in_use = True
            instance.last_used = time.time()

        # Create context outside the lock to avoid blocking other operations
        context = await instance.browser.new_context(
            storage_state=storage_state,
            ignore_https_errors=True,
            **context_options
        )

        # Apply stealth if requested
        if stealth:
            try:
                from undetected_playwright import Malenia
                await Malenia.apply_stealth(context)
                logger.debug("Stealth mode applied to context")
            except ImportError:
                logger.warning("undetected_playwright not available, skipping stealth mode")

        async with self._lock:
            instance.contexts.append(context)
            logger.debug(f"Context acquired. Browser has {len(instance.contexts)} contexts")

        return instance.browser, context

    async def release_context(
        self,
        browser: Browser,
        context: BrowserContext,
        close_context: bool = True
    ):
        """
        Release a context back to the pool.

        Args:
            browser: The browser instance
            context: The context to release
            close_context: Whether to close the context or keep it for reuse
        """
        async with self._lock:
            instance = self._find_browser_instance(browser)
            if instance:
                if close_context:
                    try:
                        await context.close()
                        if context in instance.contexts:
                            instance.contexts.remove(context)
                        logger.debug(f"Context released and closed. Browser has {len(instance.contexts)} contexts")
                    except Exception as e:
                        logger.error(f"Error closing context: {e}")
                        if context in instance.contexts:
                            instance.contexts.remove(context)
                else:
                    logger.debug("Context released but kept open for reuse")

                instance.in_use = False
                instance.last_used = time.time()
            else:
                logger.warning("Could not find browser instance for released context")

    def _find_available_browser(self) -> Optional[BrowserInstance]:
        """Find a browser with available context capacity."""
        now = time.time()

        for instance in self._browsers:
            # Skip if browser is too old
            if now - instance.created_at > self.config.browser_ttl_seconds:
                continue

            # Skip if browser has failed health checks
            if instance.health_check_failures >= self.config.max_health_check_failures:
                continue

            # Check if browser has capacity
            if (not instance.in_use and
                len(instance.contexts) < self.config.max_contexts_per_browser):
                return instance

        return None

    def _find_browser_instance(self, browser: Browser) -> Optional[BrowserInstance]:
        """Find the BrowserInstance for a given Browser."""
        for instance in self._browsers:
            if instance.browser == browser:
                return instance
        return None

    async def _health_check_loop(self):
        """Background task that periodically checks browser health."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

    async def _perform_health_checks(self):
        """Check health of all browsers and remove unhealthy ones."""
        async with self._lock:
            now = time.time()
            browsers_to_remove = []

            for instance in self._browsers:
                # Check TTL expiration
                if now - instance.created_at > self.config.browser_ttl_seconds:
                    logger.debug(f"Browser expired (TTL), marking for removal")
                    browsers_to_remove.append(instance)
                    continue

                # Check context TTL
                expired_contexts = [
                    ctx for ctx in instance.contexts
                    if now - instance.last_used > self.config.context_ttl_seconds
                ]
                for ctx in expired_contexts:
                    try:
                        await ctx.close()
                        instance.contexts.remove(ctx)
                        logger.debug("Expired context removed")
                    except Exception as e:
                        logger.error(f"Error closing expired context: {e}")

                # Perform actual health check
                if not instance.in_use:
                    try:
                        # Simple health check: try to create and close a page
                        page = await instance.browser.new_page()
                        await page.close()
                        instance.health_check_failures = 0
                    except Exception as e:
                        instance.health_check_failures += 1
                        logger.warning(f"Browser health check failed: {e} (failures: {instance.health_check_failures})")
                        if instance.health_check_failures >= self.config.max_health_check_failures:
                            browsers_to_remove.append(instance)

            # Remove unhealthy browsers
            for instance in browsers_to_remove:
                await self._remove_browser(instance)

            # Ensure minimum pool size
            while len(self._browsers) < self.config.min_browsers:
                try:
                    await self._create_browser()
                except Exception as e:
                    logger.error(f"Failed to create browser to maintain minimum pool size: {e}")
                    break

    async def _remove_browser(self, instance: BrowserInstance):
        """Remove and cleanup a browser instance."""
        try:
            for context in instance.contexts[:]:
                try:
                    await context.close()
                except Exception as e:
                    logger.error(f"Error closing context during browser removal: {e}")

            await instance.browser.close()
            logger.debug("Browser closed and removed from pool")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

        if instance in self._browsers:
            self._browsers.remove(instance)

    async def shutdown(self):
        """Gracefully shutdown the pool and cleanup all resources."""
        if not self._initialized:
            return

        logger.info("Shutting down browser pool...")
        self._shutdown = True

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all browsers
        async with self._lock:
            for instance in self._browsers[:]:
                await self._remove_browser(instance)

        # Stop playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.error(f"Error stopping playwright: {e}")

        self._initialized = False
        logger.info("Browser pool shut down")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()

    def get_stats(self) -> Dict[str, Any]:
        """Get current pool statistics."""
        total_contexts = sum(len(b.contexts) for b in self._browsers)
        return {
            "total_browsers": len(self._browsers),
            "total_contexts": total_contexts,
            "browsers_in_use": sum(1 for b in self._browsers if b.in_use),
            "unhealthy_browsers": sum(1 for b in self._browsers if b.health_check_failures > 0),
            "config": {
                "min_browsers": self.config.min_browsers,
                "max_browsers": self.config.max_browsers,
                "max_contexts_per_browser": self.config.max_contexts_per_browser,
            }
        }


class BrowserPoolManager:
    """
    Singleton manager for the global browser pool.

    Provides easy access to the browser pool throughout the application
    while ensuring only one pool instance exists.
    """

    _instance: Optional['BrowserPoolManager'] = None
    _pool: Optional[BrowserPool] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_pool(cls, config: Optional[PoolConfig] = None) -> BrowserPool:
        """Get or create the global browser pool."""
        async with cls._lock:
            if cls._pool is None:
                logger.info("Creating global browser pool")
                cls._pool = BrowserPool(config)
                await cls._pool.initialize()
            return cls._pool

    @classmethod
    async def shutdown_pool(cls):
        """Shutdown the global browser pool."""
        async with cls._lock:
            if cls._pool:
                await cls._pool.shutdown()
                cls._pool = None
                logger.info("Global browser pool shut down")

    @classmethod
    async def acquire_context(cls, config: Optional[PoolConfig] = None, **kwargs):
        """Convenience method to acquire a context from the pool."""
        pool = await cls.get_pool(config)
        return await pool.acquire_context(**kwargs)

    @classmethod
    async def release_context(cls, browser, context, **kwargs):
        """Convenience method to release a context to the pool."""
        if cls._pool:
            await cls._pool.release_context(browser, context, **kwargs)

    @classmethod
    async def get_stats(cls) -> Optional[Dict[str, Any]]:
        """Get current pool statistics."""
        if cls._pool:
            return cls._pool.get_stats()
        return None
