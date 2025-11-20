"""
Events module for ScrapeGraphAI.

This module provides event emission and webhook integration capabilities
for asynchronous workflow integrations with tools like Zapier, n8n, Make,
and queue systems (RabbitMQ, Redis, Kafka).
"""

from .event_types import Event, EventType
from .emitter import EventEmitter, EventHandler

__all__ = ["Event", "EventType", "EventEmitter", "EventHandler"]
