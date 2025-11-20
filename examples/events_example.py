"""
Example demonstrating the webhook and event system for ScrapeGraphAI.

This example shows how to:
1. Enable events in your graph configuration
2. Use webhook handlers to send events to external services
3. Use log handlers to record events to files
4. Use queue handlers to send events to message queues
5. Create custom event handlers

For more information, see RFC-0009-webhook-event-system.md
"""

import os

# Example 1: Basic Webhook Integration with Zapier
# This sends graph completion events to a Zapier webhook

graph_config_zapier = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "async_delivery": True,
        "event_handlers": [
            {
                "type": "webhook",
                "url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
                "event_types": [
                    "graph.completed",
                    "graph.failed"
                ],
                "retry_count": 3,
                "headers": {
                    "X-Custom-Header": "my-value"
                }
            }
        ]
    }
}

# Example 2: n8n Workflow Integration
# This sends events to n8n with an optimized payload structure

graph_config_n8n = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "webhook",
                "class": "scrapegraphai.events.handlers.webhook.N8nWebhookHandler",
                "url": "https://myinstance.n8n.cloud/webhook/scrapegraph",
                "event_types": ["graph.completed"]
            }
        ]
    }
}

# Example 3: Background Job Queue with Redis
# This sends events to a Redis queue for background processing

graph_config_redis = {
    "llm": {"model": "openai/gpt-4"},
    "graph_id": "unique-job-id-123",
    "events": {
        "enabled": True,
        "async_delivery": True,
        "event_handlers": [
            {
                "type": "queue",
                "queue_type": "redis",
                "connection_string": "redis://localhost:6379",
                "queue_name": "scraping_results",
                "event_types": ["graph.completed", "graph.failed"]
            }
        ]
    }
}

# Example 4: File Logging for Audit Trail
# This logs all events to a file in JSON format

graph_config_logging = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "log",
                "log_file": "/var/log/scrapegraph/events.log",
                "log_format": "json",
                "event_types": []  # Empty = log all events
            }
        ]
    }
}

# Example 5: Multi-Handler Configuration
# This sends events to multiple destinations simultaneously

graph_config_multi = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "async_delivery": True,
        "max_result_length": 500,  # Limit result size in events
        "event_handlers": [
            # Webhook for Zapier
            {
                "type": "webhook",
                "url": os.environ.get("ZAPIER_WEBHOOK_URL", "https://hooks.zapier.com/test"),
                "event_types": ["graph.completed"],
            },
            # Redis queue for background processing
            {
                "type": "queue",
                "queue_type": "redis",
                "connection_string": os.environ.get("REDIS_URL", "redis://localhost:6379"),
                "queue_name": "scraping_jobs",
                "event_types": ["graph.completed", "graph.failed"],
            },
            # File logging for audit trail
            {
                "type": "log",
                "log_file": "./events.log",
                "event_types": [],  # Log all events
            }
        ]
    }
}

# Example 6: Progress Monitoring
# This sends all node events for real-time progress tracking

graph_config_progress = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "webhook",
                "url": "http://localhost:8000/progress",
                "event_types": [
                    "graph.started",
                    "node.started",
                    "node.completed",
                    "graph.completed"
                ]
            }
        ]
    }
}

# Example 7: Custom Event Handler
# This shows how to create a custom event handler

from scrapegraphai.events import EventHandler, Event

class SlackNotificationHandler(EventHandler):
    """Custom handler that sends Slack notifications."""

    def __init__(self, config):
        super().__init__(config)
        self.webhook_url = config.get("slack_webhook_url")
        self.channel = config.get("channel", "#scraping-alerts")

    def handle(self, event: Event):
        """Send Slack notification."""
        import requests

        # Format message based on event type
        if event.event_type == "graph.completed":
            message = f"✅ Scraping completed: {event.graph_name}"
            color = "good"
        elif event.event_type == "graph.failed":
            message = f"❌ Scraping failed: {event.error}"
            color = "danger"
        else:
            return  # Only handle completion/failure

        payload = {
            "channel": self.channel,
            "attachments": [{
                "color": color,
                "title": message,
                "fields": [
                    {"title": "Graph ID", "value": event.graph_id, "short": True},
                    {"title": "Timestamp", "value": event.timestamp.isoformat(), "short": True}
                ]
            }]
        }

        try:
            requests.post(self.webhook_url, json=payload)
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")

# Use custom handler
graph_config_custom = {
    "llm": {"model": "openai/gpt-4"},
    "events": {
        "enabled": True,
        "event_handlers": [
            {
                "type": "custom",
                "class": "__main__.SlackNotificationHandler",
                "slack_webhook_url": os.environ.get("SLACK_WEBHOOK_URL"),
                "channel": "#scraping-alerts",
                "event_types": ["graph.completed", "graph.failed"]
            }
        ]
    }
}

# Example 8: Using Events with SmartScraperGraph
# This shows the complete usage in a real scraping scenario

def example_webhook_scraping():
    """Example of scraping with webhook events."""
    from scrapegraphai.graphs import SmartScraperGraph

    # Configure graph with webhook events
    config = {
        "llm": {
            "model": "openai/gpt-4",
            "api_key": os.environ.get("OPENAI_API_KEY"),
        },
        "events": {
            "enabled": True,
            "async_delivery": True,
            "event_handlers": [
                {
                    "type": "webhook",
                    "url": os.environ.get("WEBHOOK_URL", "https://example.com/webhook"),
                    "event_types": ["graph.completed", "graph.failed"],
                    "retry_count": 3,
                }
            ]
        }
    }

    # Create scraper
    scraper = SmartScraperGraph(
        prompt="Extract all product prices",
        source="https://example.com/products",
        config=config
    )

    # Run scraper - webhook will be notified on completion
    result = scraper.run()

    # Webhook receives:
    # {
    #   "event_type": "graph.completed",
    #   "event_id": "uuid-here",
    #   "timestamp": "2025-11-20T10:30:00Z",
    #   "graph_name": "SmartScraperGraph",
    #   "data": {
    #     "result_preview": "{'products': [...]}"
    #   }
    # }

    return result

# Example 9: Flask API with Background Jobs
# This shows how to build an async API using events

def example_flask_api():
    """Example Flask API with background job processing."""
    from flask import Flask, jsonify, request
    import uuid
    import threading

    app = Flask(__name__)
    jobs = {}

    @app.route("/scrape", methods=["POST"])
    def start_scraping():
        """Start a scraping job."""
        data = request.json
        job_id = str(uuid.uuid4())

        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "result": None,
        }

        # Configure scraper with events
        from scrapegraphai.graphs import SmartScraperGraph

        config = {
            "llm": {"model": "openai/gpt-4"},
            "graph_id": job_id,
            "events": {
                "enabled": True,
                "async_delivery": True,
                "event_handlers": [
                    {
                        "type": "queue",
                        "queue_type": "redis",
                        "connection_string": "redis://localhost:6379",
                        "queue_name": "scraping_events",
                        "event_types": ["graph.completed", "graph.failed"]
                    }
                ]
            }
        }

        # Start scraping in background
        def run_scraper():
            scraper = SmartScraperGraph(
                prompt=data.get("prompt"),
                source=data.get("url"),
                config=config
            )
            scraper.run()

        thread = threading.Thread(target=run_scraper)
        thread.start()

        return jsonify({
            "job_id": job_id,
            "status": "processing"
        }), 202

    @app.route("/job/<job_id>", methods=["GET"])
    def check_job_status(job_id):
        """Check job status."""
        if job_id not in jobs:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(jobs[job_id])

    return app


if __name__ == "__main__":
    print("Event System Examples")
    print("=" * 50)
    print()
    print("This file contains examples of using the ScrapeGraphAI event system.")
    print("Uncomment the example you want to run and make sure to set the required")
    print("environment variables (API keys, webhook URLs, etc.)")
    print()
    print("Examples:")
    print("1. Zapier webhook integration")
    print("2. n8n workflow integration")
    print("3. Redis queue for background jobs")
    print("4. File logging for audit trail")
    print("5. Multi-handler configuration")
    print("6. Progress monitoring")
    print("7. Custom event handler")
    print("8. Complete scraping with webhooks")
    print("9. Flask API with background jobs")
    print()
    print("For more details, see the RFC-0009 documentation.")
