# Streaming LLM Responses in ScrapeGraphAI

## Overview

ScrapeGraphAI now supports **streaming LLM responses**, enabling token-by-token output for real-time feedback and progressive UI updates. This feature allows you to see results as they're generated, improving user experience and perceived performance.

## What is Streaming?

Streaming delivers LLM responses progressively, token by token, instead of waiting for the complete response. This provides:

- **Real-time feedback**: See results immediately as they're generated
- **Better UX**: Reduced perceived latency, similar to ChatGPT/Claude
- **Progressive rendering**: Update UI incrementally as tokens arrive
- **Debugging**: Observe LLM behavior in real-time
- **Interactivity**: Build responsive applications with live updates

## Quick Start

### Basic Usage

```python
from scrapegraphai.graphs import SmartScraperGraph

# Define callback to receive tokens
def on_token(token: str, metadata: dict):
    print(token, end="", flush=True)

# Create graph with streaming enabled
graph = SmartScraperGraph(
    prompt="What is this article about?",
    source="https://example.com",
    config={
        "llm": {
            "model": "openai/gpt-4",
            "api_key": "your-api-key",
            "streaming": True  # Enable streaming
        }
    }
)

# Register callback
graph.add_streaming_callback(on_token)

# Run - tokens will stream to callback
result = graph.run()
```

## Configuration

### Enabling Streaming

Streaming is configured via the `llm` section of the graph config:

```python
config = {
    "llm": {
        "model": "openai/gpt-4",
        "api_key": "your-api-key",
        "streaming": True  # Enable streaming (default: False)
    }
}
```

### Backward Compatibility

Streaming is **disabled by default** to maintain backward compatibility. Existing code continues to work unchanged:

```python
# Existing code - streaming disabled (default)
graph = SmartScraperGraph(
    prompt="test",
    source="http://example.com",
    config={"llm": {"model": "openai/gpt-4"}}
)
result = graph.run()  # Works exactly as before
```

## Callback System

### Callback Function Signature

The callback function receives two parameters:

```python
def callback(token: str, metadata: dict):
    """
    Callback function for receiving streaming tokens.

    Args:
        token (str): The generated token string
        metadata (dict): Metadata about the token
            - event (str): Event type ("start", "token", "end", "error")
            - node (str): Name of the node emitting the token
            - accumulated (str): Full accumulated response so far
            - chunk (str): Chunk identifier (for multi-chunk processing)
            - phase (str): Processing phase ("chunk_processing", "merging")
            - run_id (str): Unique identifier for this generation run
    """
    pass
```

### Event Types

The callback receives different event types via the `metadata["event"]` field:

| Event | Description | Token Content |
|-------|-------------|---------------|
| `start` | LLM generation started | Empty string |
| `token` | New token generated | The token string |
| `end` | LLM generation completed | Empty string |
| `error` | Error occurred | Empty string |

### Event Handling Example

```python
def callback(token: str, metadata: dict):
    event = metadata.get("event")

    if event == "start":
        print("\n🚀 Starting generation...")
    elif event == "token":
        print(token, end="", flush=True)
    elif event == "end":
        print("\n✅ Complete!")
    elif event == "error":
        print(f"\n❌ Error: {metadata['error']}")
```

### Multiple Callbacks

Register multiple callbacks to handle tokens differently:

```python
def console_callback(token, metadata):
    """Print to console"""
    if metadata.get("event") == "token":
        print(token, end="", flush=True)

def file_callback(token, metadata):
    """Write to file"""
    if metadata.get("event") == "token":
        with open("output.txt", "a") as f:
            f.write(token)

graph.add_streaming_callback(console_callback)
graph.add_streaming_callback(file_callback)
```

## Performance Optimization

### Buffered Streaming

For better performance, use buffered streaming to reduce callback overhead:

```python
from scrapegraphai.utils.streaming_callback import BufferedStreamingCallback

def my_callback(text, metadata):
    print(text, end="", flush=True)

# Create buffered callback
buffered = BufferedStreamingCallback(
    callback=my_callback,
    buffer_size=5  # Emit every 5 tokens
)

graph.add_streaming_callback(buffered.on_token)

# Don't forget to flush at the end
result = graph.run()
buffered.flush()
```

### Performance Considerations

- **Token overhead**: ~0.1-0.5ms per token emission (negligible)
- **Callback overhead**: Keep callbacks fast (<1ms recommended)
- **Buffering**: Can reduce callback frequency by 5-10x
- **Network**: SSE adds ~100 bytes per event

## Advanced Usage

### Node-Specific Processing

Process tokens differently based on which node is emitting them:

```python
def callback(token, metadata):
    node = metadata.get("node")

    if node == "GenerateAnswer":
        # Main answer generation
        print(f"[ANSWER] {token}", end="")
    elif node == "FetchNode":
        # Fetching phase
        pass  # Usually no tokens during fetch
```

### Phase-Specific Processing

Handle different processing phases:

```python
def callback(token, metadata):
    phase = metadata.get("phase")

    if phase == "chunk_processing":
        chunk = metadata.get("chunk")
        print(f"[{chunk}] {token}", end="")
    elif phase == "merging":
        print(f"[MERGE] {token}", end="")
```

### Accumulated Response Tracking

Access the full accumulated response:

```python
def callback(token, metadata):
    accumulated = metadata.get("accumulated", "")

    # Update UI with full response
    update_ui(accumulated)

    # Or check for specific patterns
    if "FINAL ANSWER:" in accumulated:
        highlight_final_answer()
```

## Integration Patterns

### Web Applications

#### FastAPI with Server-Sent Events

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/scrape/stream")
async def scrape_with_streaming(request: dict):
    async def generate():
        buffer = []

        def on_token(token, metadata):
            event = {"token": token, "metadata": metadata}
            buffer.append(f"data: {json.dumps(event)}\n\n")

        graph = SmartScraperGraph(
            prompt=request["prompt"],
            source=request["url"],
            config={"llm": {"streaming": True}}
        )
        graph.add_streaming_callback(on_token)

        # Run in executor
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, graph.run)

        # Yield buffered events
        for event in buffer:
            yield event

    return StreamingResponse(generate(), media_type="text/event-stream")
```

#### React/JavaScript Client

```javascript
const streamScrapeResults = async (prompt, source) => {
  const response = await fetch('/scrape/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, source })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let result = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));

        if (data.token) {
          result += data.token;
          updateUI(result);  // Progressive update
        }

        if (data.metadata.event === 'end') {
          console.log('Complete!');
        }
      }
    }
  }
};
```

### CLI Applications

```python
import sys

def cli_callback(token, metadata):
    """Stream to terminal with formatting"""
    event = metadata.get("event")

    if event == "start":
        print("\n" + "="*60)
        print("🚀 Generating Response")
        print("="*60 + "\n")
    elif event == "token":
        sys.stdout.write(token)
        sys.stdout.flush()
    elif event == "end":
        print("\n" + "="*60)
        print("✅ Complete")
        print("="*60)

graph.add_streaming_callback(cli_callback)
```

## Supported Models

Streaming works with any LLM that supports streaming in LangChain:

- ✅ **OpenAI**: GPT-4, GPT-4-turbo, GPT-3.5-turbo
- ✅ **Anthropic**: Claude 3 (Opus, Sonnet, Haiku)
- ✅ **Google**: Gemini Pro, Gemini Ultra
- ✅ **Azure OpenAI**: All Azure-hosted models
- ✅ **Ollama**: Local models (llama2, mistral, etc.)
- ✅ **Groq**: Fast inference models
- ✅ **Bedrock**: AWS Bedrock models
- ✅ **HuggingFace**: Compatible models
- ✅ **DeepSeek**: DeepSeek models

## Error Handling

### Callback Errors

Errors in callbacks are caught and logged, but don't break streaming:

```python
def risky_callback(token, metadata):
    # This error won't break streaming
    raise Exception("Callback error!")

graph.add_streaming_callback(risky_callback)
result = graph.run()  # Still completes successfully
```

### Network Errors

Handle network errors in async contexts:

```python
async def safe_streaming():
    try:
        graph = SmartScraperGraph(...)
        graph.add_streaming_callback(callback)
        result = await graph.run_safe_async()
    except Exception as e:
        print(f"Error: {e}")
        # Handle error appropriately
```

### Timeout Handling

Streaming respects the configured timeout:

```python
config = {
    "llm": {
        "model": "openai/gpt-4",
        "streaming": True
    },
    "timeout": 300  # 5 minute timeout
}
```

## Testing

### Unit Testing Callbacks

```python
import pytest

def test_callback_receives_tokens():
    tokens = []

    def callback(token, metadata):
        tokens.append(token)

    # Test with mock graph
    graph = create_mock_graph()
    graph.add_streaming_callback(callback)

    result = graph.run()

    assert len(tokens) > 0
    assert "".join(tokens) in str(result)
```

### Integration Testing

```python
@pytest.mark.integration
def test_end_to_end_streaming():
    received_events = []

    def callback(token, metadata):
        received_events.append(metadata.get("event"))

    graph = SmartScraperGraph(
        prompt="test",
        source="http://example.com",
        config={"llm": {"streaming": True}}
    )

    graph.add_streaming_callback(callback)
    result = graph.run()

    assert "start" in received_events
    assert "end" in received_events
```

## Troubleshooting

### Problem: No tokens received

**Solutions:**
1. Verify `"streaming": True` in config
2. Check callback is registered before `run()`
3. Ensure LLM model supports streaming
4. Verify API key is valid

### Problem: Slow performance

**Solutions:**
1. Use `BufferedStreamingCallback` to reduce overhead
2. Minimize processing in callback functions
3. Avoid I/O operations in callbacks
4. Consider async callbacks for I/O-heavy operations

### Problem: Missing or corrupted tokens

**Solutions:**
1. Check callback error handling
2. Verify network stability
3. Check for timeout issues
4. Ensure proper character encoding

### Problem: Memory usage increasing

**Solutions:**
1. Don't store all tokens in memory
2. Use buffered streaming
3. Process and discard tokens incrementally
4. Monitor callback memory usage

## Best Practices

1. **Keep callbacks fast**: Minimize processing to avoid blocking token generation
2. **Use buffering**: For production, buffer tokens for better performance
3. **Handle all events**: Implement handlers for start, token, end, and error events
4. **Error handling**: Always handle errors gracefully in callbacks
5. **Clean up resources**: Flush buffers and close files properly
6. **Test both modes**: Verify functionality with streaming enabled and disabled
7. **Monitor performance**: Track callback execution time
8. **Async for I/O**: Use async callbacks for database or network operations

## Migration Guide

### From Non-Streaming to Streaming

**Before (non-streaming):**
```python
graph = SmartScraperGraph(
    prompt="What is this?",
    source="http://example.com",
    config={"llm": {"model": "openai/gpt-4"}}
)

result = graph.run()
print(result)  # Prints complete result
```

**After (streaming):**
```python
def callback(token, metadata):
    if metadata.get("event") == "token":
        print(token, end="", flush=True)

graph = SmartScraperGraph(
    prompt="What is this?",
    source="http://example.com",
    config={"llm": {"model": "openai/gpt-4", "streaming": True}}
)

graph.add_streaming_callback(callback)
result = graph.run()  # Same final result, but tokens streamed
```

## Examples

See the `examples/streaming/` directory for complete examples:

- `basic_streaming.py` - Simple streaming usage
- `cli_streaming.py` - Full-featured CLI with streaming
- `fastapi_streaming.py` - API server with SSE
- `react_streaming_client.jsx` - React frontend example

## API Reference

### AbstractGraph Methods

#### `add_streaming_callback(callback: callable) -> None`

Register a callback to receive streaming tokens.

**Parameters:**
- `callback`: Function with signature `callback(token: str, metadata: dict)`

**Example:**
```python
graph.add_streaming_callback(my_callback)
```

### Utility Classes

#### `StreamingCallbackHandler`

LangChain callback handler for streaming.

```python
from scrapegraphai.utils.streaming_callback import StreamingCallbackHandler

handler = StreamingCallbackHandler(on_token=callback)
```

#### `BufferedStreamingCallback`

Buffered callback for better performance.

```python
from scrapegraphai.utils.streaming_callback import BufferedStreamingCallback

buffered = BufferedStreamingCallback(
    callback=my_callback,
    buffer_size=5
)
```

## FAQ

**Q: Does streaming increase API costs?**
A: No, costs are the same. You're still generating the same number of tokens.

**Q: Can I use streaming with all graph types?**
A: Yes, streaming works with SmartScraperGraph, JSONScraperGraph, and all other graph types.

**Q: Does streaming work with local models?**
A: Yes, streaming works with Ollama and other local models.

**Q: Can I disable streaming for specific requests?**
A: Yes, set `"streaming": False` in the config for that request.

**Q: How do I know when streaming is complete?**
A: Watch for the `"end"` event in the metadata.

**Q: Can callbacks be async?**
A: Currently callbacks are synchronous. For async operations, use threading or queues.

## Contributing

To contribute to streaming functionality:

1. Read the RFC: `analysis-output/rfcs/RFC-0006-streaming-llm-responses.md`
2. Add tests for new features
3. Update documentation
4. Follow existing code patterns
5. Submit PR with examples

## Related Documentation

- [LangChain Streaming](https://python.langchain.com/docs/expression_language/streaming)
- [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [OpenAI Streaming](https://platform.openai.com/docs/api-reference/streaming)

## License

This feature is part of ScrapeGraphAI and follows the same license.
