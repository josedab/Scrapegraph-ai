"""
Streaming callback handler for LLM token-by-token output.

This module provides callback handlers for streaming LLM responses,
enabling real-time token emission for progressive UI updates.
"""

from typing import Any, Callable, Dict, Optional
from langchain_core.callbacks import BaseCallbackHandler


class StreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming token output."""

    def __init__(self, on_token: Callable[[str, Dict], None]):
        """
        Initialize streaming callback handler.

        Args:
            on_token: Function to call with each new token
                Signature: on_token(token: str, metadata: dict)
        """
        super().__init__()
        self.on_token = on_token
        self.current_run_id = None

    @property
    def always_verbose(self) -> bool:
        """Always receive callbacks."""
        return True

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Called when LLM starts generating."""
        run_id = kwargs.get("run_id")
        self.current_run_id = run_id

        # Notify start of streaming
        self.on_token("", {
            "event": "start",
            "run_id": str(run_id),
            "prompts": prompts
        })

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Called when LLM generates a new token."""
        self.on_token(token, {
            "event": "token",
            "run_id": str(kwargs.get("run_id", self.current_run_id))
        })

    def on_llm_end(self, response, **kwargs: Any) -> None:
        """Called when LLM finishes generating."""
        self.on_token("", {
            "event": "end",
            "run_id": str(kwargs.get("run_id", self.current_run_id))
        })

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when LLM encounters an error."""
        self.on_token("", {
            "event": "error",
            "error": str(error),
            "run_id": str(kwargs.get("run_id", self.current_run_id))
        })


class BufferedStreamingCallback:
    """Buffer tokens before emitting for better performance."""

    def __init__(self, callback: Callable, buffer_size: int = 5):
        """
        Initialize buffered streaming callback.

        Args:
            callback: Function to call with buffered tokens
            buffer_size: Number of tokens to buffer before emitting
        """
        self.callback = callback
        self.buffer_size = buffer_size
        self.buffer = []

    def on_token(self, token: str, metadata: dict):
        """Buffer tokens and emit in batches."""
        if metadata.get("event") in ["start", "end", "error"]:
            # Flush buffer and emit event immediately
            self.flush()
            self.callback(token, metadata)
            return

        self.buffer.append(token)

        if len(self.buffer) >= self.buffer_size:
            # Emit buffered tokens
            buffered_text = "".join(self.buffer)
            self.callback(buffered_text, metadata)
            self.buffer = []

    def flush(self):
        """Flush remaining tokens."""
        if self.buffer:
            buffered_text = "".join(self.buffer)
            self.callback(buffered_text, {})
            self.buffer = []
