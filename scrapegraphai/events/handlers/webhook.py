"""
Webhook event handlers for ScrapeGraphAI.
"""

import logging
from typing import Dict, Any, Optional
import time

from ..emitter import EventHandler
from ..event_types import Event

logger = logging.getLogger(__name__)


class WebhookHandler(EventHandler):
    """
    Sends events to webhook URLs via HTTP POST.

    Features:
    - Automatic retries with exponential backoff
    - Custom headers and authentication
    - Timeout configuration
    - Payload transformation
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize webhook handler.

        Config options:
            url: Webhook URL to POST to (required)
            method: HTTP method (default: POST)
            headers: Custom headers dict
            auth: Auth tuple (username, password) for basic auth
            timeout: Request timeout in seconds (default: 30)
            retry_count: Number of retries on failure (default: 3)
            retry_backoff: Backoff multiplier for retries (default: 2)
            verify_ssl: Verify SSL certificates (default: True)
            payload_template: Jinja2 template for payload customization
        """
        super().__init__(config)

        self.url = config.get("url")
        if not self.url:
            raise ValueError("Webhook handler requires 'url' in config")

        self.method = config.get("method", "POST").upper()
        self.headers = config.get("headers", {}).copy()
        self.auth = config.get("auth")
        self.timeout = config.get("timeout", 30)
        self.retry_count = config.get("retry_count", 3)
        self.retry_backoff = config.get("retry_backoff", 2)
        self.verify_ssl = config.get("verify_ssl", True)
        self.payload_template = config.get("payload_template")

        # Set default content type if not specified
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"

    def handle(self, event: Event):
        """Send event to webhook URL."""
        try:
            import requests
        except ImportError:
            logger.error("requests package required for webhook handler. Install with: pip install requests")
            return

        payload = self._prepare_payload(event)

        for attempt in range(self.retry_count + 1):
            try:
                response = requests.request(
                    method=self.method,
                    url=self.url,
                    json=payload,
                    headers=self.headers,
                    auth=self.auth,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )

                response.raise_for_status()

                logger.info(
                    f"Webhook delivered successfully: {event.event_type} "
                    f"(id: {event.event_id}, status: {response.status_code})"
                )
                return

            except Exception as e:
                logger.warning(
                    f"Webhook delivery failed (attempt {attempt + 1}/{self.retry_count + 1}): {e}"
                )

                if attempt < self.retry_count:
                    # Exponential backoff
                    sleep_time = (self.retry_backoff ** attempt)
                    time.sleep(sleep_time)
                else:
                    # Final attempt failed
                    logger.error(
                        f"Webhook delivery failed after {self.retry_count + 1} attempts: "
                        f"{event.event_type} (id: {event.event_id})"
                    )

    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare the webhook payload."""
        if self.payload_template:
            # Use custom template
            try:
                from jinja2 import Template
                template = Template(self.payload_template)
                import json
                return json.loads(template.render(event=event))
            except ImportError:
                logger.error("jinja2 package required for payload templates. Install with: pip install jinja2")
                return event.to_dict()
        else:
            # Use default event dictionary
            return event.to_dict()


class ZapierWebhookHandler(WebhookHandler):
    """Specialized webhook handler for Zapier integration."""

    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare Zapier-optimized payload."""
        payload = event.to_dict()

        # Zapier-specific transformations
        # Flatten nested structures for easier field mapping
        if "data" in payload and isinstance(payload["data"], dict):
            for key, value in payload["data"].items():
                # Prefix data fields to avoid collisions
                payload[f"data_{key}"] = value

        return payload


class N8nWebhookHandler(WebhookHandler):
    """Specialized webhook handler for n8n integration."""

    def _prepare_payload(self, event: Event) -> Dict[str, Any]:
        """Prepare n8n-optimized payload."""
        # n8n expects specific structure for easy processing
        return {
            "event": event.event_type.value,
            "id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "body": event.data,
            "metadata": {
                "graph_id": event.graph_id,
                "graph_name": event.graph_name,
                "node_name": event.node_name,
            },
            "error": {
                "message": event.error,
                "type": event.error_type,
            } if event.error else None,
        }
