"""
Queue event handler for ScrapeGraphAI.
"""

import logging
from typing import Dict, Any, Optional
import json

from ..emitter import EventHandler
from ..event_types import Event

logger = logging.getLogger(__name__)


class QueueHandler(EventHandler):
    """
    Sends events to message queue systems.

    Supported queues:
    - Redis (using redis-py)
    - RabbitMQ (using pika)
    - AWS SQS (using boto3)
    - Apache Kafka (using kafka-python)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize queue handler.

        Config options:
            queue_type: Type of queue (redis, rabbitmq, sqs, kafka)
            connection_string: Connection URL/details
            queue_name: Name of queue/topic
            **kwargs: Queue-specific options
        """
        super().__init__(config)

        self.queue_type = config.get("queue_type")
        if not self.queue_type:
            raise ValueError("Queue handler requires 'queue_type' in config")

        self.connection_string = config.get("connection_string")
        self.queue_name = config.get("queue_name", "scrapegraph_events")

        # Initialize queue connection
        self._client = self._initialize_client()

    def _initialize_client(self):
        """Initialize the appropriate queue client."""
        if self.queue_type == "redis":
            return self._initialize_redis()
        elif self.queue_type == "rabbitmq":
            return self._initialize_rabbitmq()
        elif self.queue_type == "sqs":
            return self._initialize_sqs()
        elif self.queue_type == "kafka":
            return self._initialize_kafka()
        else:
            raise ValueError(f"Unsupported queue type: {self.queue_type}")

    def _initialize_redis(self):
        """Initialize Redis client."""
        try:
            import redis
            return redis.from_url(self.connection_string)
        except ImportError:
            raise ImportError("redis package required for Redis queue handler. Install with: pip install redis")

    def _initialize_rabbitmq(self):
        """Initialize RabbitMQ client."""
        try:
            import pika
            params = pika.URLParameters(self.connection_string)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=self.queue_name, durable=True)
            return channel
        except ImportError:
            raise ImportError("pika package required for RabbitMQ queue handler. Install with: pip install pika")

    def _initialize_sqs(self):
        """Initialize AWS SQS client."""
        try:
            import boto3
            return boto3.client('sqs')
        except ImportError:
            raise ImportError("boto3 package required for SQS queue handler. Install with: pip install boto3")

    def _initialize_kafka(self):
        """Initialize Kafka producer."""
        try:
            from kafka import KafkaProducer
            return KafkaProducer(
                bootstrap_servers=self.connection_string,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
        except ImportError:
            raise ImportError("kafka-python package required for Kafka queue handler. Install with: pip install kafka-python")

    def handle(self, event: Event):
        """Send event to queue."""
        payload = json.dumps(event.to_dict())

        try:
            if self.queue_type == "redis":
                self._client.lpush(self.queue_name, payload)

            elif self.queue_type == "rabbitmq":
                import pika
                self._client.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=payload,
                    properties=pika.BasicProperties(delivery_mode=2)
                )

            elif self.queue_type == "sqs":
                queue_url = self.config.get("queue_url")
                self._client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=payload
                )

            elif self.queue_type == "kafka":
                self._client.send(self.queue_name, event.to_dict())

            logger.debug(f"Event sent to {self.queue_type} queue: {event.event_type}")

        except Exception as e:
            logger.error(f"Failed to send event to {self.queue_type} queue: {e}")

    def cleanup(self):
        """Cleanup queue connections."""
        try:
            if self.queue_type == "rabbitmq" and self._client:
                self._client.connection.close()
            elif self.queue_type == "kafka" and self._client:
                self._client.close()
        except Exception as e:
            logger.error(f"Failed to cleanup queue connection: {e}")
