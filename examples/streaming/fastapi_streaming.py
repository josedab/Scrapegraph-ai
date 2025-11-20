"""
FastAPI Streaming Example for ScrapeGraphAI

This example demonstrates how to create a streaming API endpoint
that uses Server-Sent Events (SSE) to stream scraping results to clients.

Installation:
    pip install fastapi uvicorn

Usage:
    python fastapi_streaming.py

    Then visit: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
from typing import Optional
import os
from scrapegraphai.graphs import SmartScraperGraph


app = FastAPI(
    title="ScrapeGraphAI Streaming API",
    description="API with streaming support for real-time scraping results",
    version="1.0.0"
)


class ScrapeRequest(BaseModel):
    """Request model for scrape endpoint."""
    url: str
    prompt: str
    model: Optional[str] = "openai/gpt-4"
    api_key: Optional[str] = None


class StreamingManager:
    """Manages streaming for async contexts."""

    def __init__(self):
        self.buffer = []
        self.complete = False
        self.error = None

    def on_token(self, token: str, metadata: dict):
        """Callback to receive tokens."""
        event = {
            "token": token,
            "metadata": metadata
        }
        self.buffer.append(event)

    async def stream_events(self):
        """Async generator that yields buffered events."""
        while not self.complete or self.buffer:
            if self.buffer:
                event = self.buffer.pop(0)
                yield event
            else:
                # Small delay to avoid busy waiting
                await asyncio.sleep(0.01)

        # Yield completion event
        if self.error:
            yield {
                "event": "error",
                "error": str(self.error)
            }
        else:
            yield {
                "event": "complete"
            }


@app.post("/scrape/stream")
async def scrape_with_streaming(request: ScrapeRequest):
    """
    Stream scraping results using Server-Sent Events.

    This endpoint streams tokens as they are generated,
    providing real-time feedback to the client.

    Example curl:
        curl -N -X POST http://localhost:8000/scrape/stream \
             -H "Content-Type: application/json" \
             -d '{"url": "https://example.com", "prompt": "What is this?"}'
    """
    manager = StreamingManager()

    async def generate():
        """Generator that yields Server-Sent Events."""
        try:
            # Configuration
            config = {
                "llm": {
                    "model": request.model,
                    "api_key": request.api_key or os.getenv("OPENAI_API_KEY"),
                    "streaming": True
                },
                "verbose": False
            }

            # Create graph
            graph = SmartScraperGraph(
                prompt=request.prompt,
                source=request.url,
                config=config
            )

            # Register callback
            graph.add_streaming_callback(manager.on_token)

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            async def run_graph():
                try:
                    result = await loop.run_in_executor(None, graph.run)
                    manager.buffer.append({
                        "event": "complete",
                        "result": result
                    })
                except Exception as e:
                    manager.error = e
                finally:
                    manager.complete = True

            # Start graph execution
            task = asyncio.create_task(run_graph())

            # Stream events as they arrive
            async for event in manager.stream_events():
                # Format as Server-Sent Event
                data = json.dumps(event)
                yield f"data: {data}\n\n"

            # Wait for task to complete
            await task

        except Exception as e:
            error_event = {
                "event": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/scrape")
async def scrape_without_streaming(request: ScrapeRequest):
    """
    Non-streaming endpoint for comparison.

    This endpoint returns the complete result once generation is finished.
    """
    try:
        config = {
            "llm": {
                "model": request.model,
                "api_key": request.api_key or os.getenv("OPENAI_API_KEY"),
                "streaming": False  # Disabled
            },
            "verbose": False
        }

        graph = SmartScraperGraph(
            prompt=request.prompt,
            source=request.url,
            config=config
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, graph.run)

        return {
            "status": "success",
            "result": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ScrapeGraphAI Streaming API",
        "endpoints": {
            "POST /scrape/stream": "Streaming scrape with SSE",
            "POST /scrape": "Non-streaming scrape",
            "GET /docs": "API documentation"
        }
    }


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting ScrapeGraphAI Streaming API...")
    print("📚 API Docs: http://localhost:8000/docs")
    print("🔄 Streaming endpoint: http://localhost:8000/scrape/stream")
    uvicorn.run(app, host="0.0.0.0", port=8000)
