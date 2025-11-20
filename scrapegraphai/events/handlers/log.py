"""
Log event handler for ScrapeGraphAI.
"""

import logging
import json
from typing import Dict, Any
from pathlib import Path

from ..emitter import EventHandler
from ..event_types import Event

logger = logging.getLogger(__name__)


class LogHandler(EventHandler):
    """
    Logs events to a file in JSON format.

    Features:
    - File-based logging
    - JSON event formatting
    - Automatic directory creation
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize log handler.

        Config options:
            log_file: Path to log file (required)
            log_format: Format for log entries (default: json)
            append: Append to existing file (default: True)
        """
        super().__init__(config)

        self.log_file = config.get("log_file")
        if not self.log_file:
            raise ValueError("Log handler requires 'log_file' in config")

        self.log_format = config.get("log_format", "json")
        self.append = config.get("append", True)

        # Create directory if it doesn't exist
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open log file
        mode = "a" if self.append else "w"
        self._file_handle = open(self.log_file, mode, encoding="utf-8")

    def handle(self, event: Event):
        """Write event to log file."""
        try:
            if self.log_format == "json":
                # Write as JSON (one event per line)
                self._file_handle.write(event.to_json())
                self._file_handle.write("\n")
            else:
                # Write as plain text
                self._file_handle.write(
                    f"[{event.timestamp.isoformat()}] {event.event_type.value} - "
                    f"Graph: {event.graph_name}, Node: {event.node_name}\n"
                )

            self._file_handle.flush()

        except Exception as e:
            logger.error(f"Failed to write event to log file: {e}")

    def cleanup(self):
        """Close log file."""
        if hasattr(self, '_file_handle') and self._file_handle:
            try:
                self._file_handle.close()
            except Exception as e:
                logger.error(f"Failed to close log file: {e}")
