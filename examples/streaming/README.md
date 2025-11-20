# Streaming Examples for ScrapeGraphAI

This directory contains examples demonstrating the streaming LLM response capabilities of ScrapeGraphAI. Streaming enables real-time token-by-token output, providing progressive UI updates and faster perceived performance.

## Overview

ScrapeGraphAI now supports streaming responses from LLMs, allowing you to:

- **See results in real-time** as tokens are generated
- **Build interactive UIs** with progressive rendering
- **Improve perceived performance** by showing immediate feedback
- **Debug more effectively** by watching LLM behavior as it happens

## Examples

### 1. Basic Streaming (`basic_streaming.py`)

The simplest example showing how to enable streaming and receive tokens via callback.

**Features:**
- Basic callback implementation
- Event handling (start, token, end, error)
- Token printing to console

**Usage:**
```bash
export OPENAI_API_KEY="your-api-key"
python basic_streaming.py
```

**Key Code:**
```python
def on_token(token: str, metadata: dict):
    print(token, end="", flush=True)

graph = SmartScraperGraph(
    prompt="Summarize this article",
    source="https://example.com",
    config={"llm": {"streaming": True}}
)

graph.add_streaming_callback(on_token)
result = graph.run()
```

### 2. CLI Streaming (`cli_streaming.py`)

A full-featured command-line interface with streaming support, formatting, and options.

**Features:**
- Argument parsing
- Verbose mode with node information
- Buffered streaming option
- Nice terminal formatting
- Error handling

**Usage:**
```bash
# Basic usage
python cli_streaming.py https://example.com

# With custom prompt
python cli_streaming.py https://example.com -p "Extract all product names"

# Verbose mode with buffering
python cli_streaming.py https://example.com -v --buffer-size 5

# Different model
python cli_streaming.py https://example.com -m "anthropic/claude-3-sonnet"
```

**Options:**
- `-p, --prompt`: Custom prompt (default: "What is this page about?")
- `-m, --model`: LLM model to use (default: "openai/gpt-4")
- `-v, --verbose`: Show node information
- `--buffer-size`: Token buffer size for performance (default: 1)

### 3. FastAPI Streaming (`fastapi_streaming.py`)

A complete API server with streaming endpoints using Server-Sent Events (SSE).

**Features:**
- RESTful API with FastAPI
- Server-Sent Events (SSE) for streaming
- Both streaming and non-streaming endpoints
- Async/await support
- OpenAPI documentation

**Installation:**
```bash
pip install fastapi uvicorn
```

**Usage:**
```bash
python fastapi_streaming.py
```

**Endpoints:**

1. **POST /scrape/stream** - Streaming endpoint
   ```bash
   curl -N -X POST http://localhost:8000/scrape/stream \
        -H "Content-Type: application/json" \
        -d '{
          "url": "https://example.com",
          "prompt": "What is this page about?",
          "model": "openai/gpt-4"
        }'
   ```

2. **POST /scrape** - Non-streaming endpoint
   ```bash
   curl -X POST http://localhost:8000/scrape \
        -H "Content-Type: application/json" \
        -d '{
          "url": "https://example.com",
          "prompt": "What is this page about?"
        }'
   ```

3. **GET /docs** - Interactive API documentation
   - Open http://localhost:8000/docs in browser

### 4. React Streaming Client (`react_streaming_client.jsx`)

A React component that consumes the streaming API and renders results progressively.

**Features:**
- Real-time UI updates
- Server-Sent Events consumption
- Progressive text rendering
- Blinking cursor during streaming
- Error handling

**Installation:**
```bash
npm install react
```

**Usage:**
```jsx
import StreamingScraper from './react_streaming_client';

function App() {
  return <StreamingScraper />;
}
```

**Features Demonstrated:**
- Fetch API with streaming response
- TextDecoder for reading stream chunks
- State management for progressive updates
- Visual feedback during streaming

## Configuration

### Enabling Streaming

Streaming is enabled via the `llm` configuration:

```python
config = {
    "llm": {
        "model": "openai/gpt-4",
        "api_key": "your-api-key",
        "streaming": True  # Enable streaming
    }
}
```

### Callback Function

The callback function receives two parameters:

```python
def callback(token: str, metadata: dict):
    """
    Args:
        token (str): The generated token
        metadata (dict): Information about the token
            - event: "start", "token", "end", or "error"
            - node: Name of the node emitting token
            - accumulated: Full accumulated response
            - chunk: Chunk identifier (for multi-chunk)
            - phase: Processing phase
    """
    pass
```

### Performance Optimization

For better performance, use buffered streaming:

```python
from scrapegraphai.utils.streaming_callback import BufferedStreamingCallback

buffered = BufferedStreamingCallback(
    callback=my_callback,
    buffer_size=5  # Emit every 5 tokens
)

graph.add_streaming_callback(buffered.on_token)
```

## Supported Models

Streaming works with any LLM that supports streaming in LangChain:

- ✅ OpenAI (GPT-4, GPT-3.5-turbo)
- ✅ Anthropic (Claude 3)
- ✅ Google (Gemini)
- ✅ Ollama (local models)
- ✅ Azure OpenAI
- ✅ And many more...

## Advanced Usage

### Multiple Callbacks

Register multiple callbacks to handle tokens differently:

```python
def console_callback(token, metadata):
    print(token, end="", flush=True)

def file_callback(token, metadata):
    with open("output.txt", "a") as f:
        f.write(token)

graph.add_streaming_callback(console_callback)
graph.add_streaming_callback(file_callback)
```

### Event Filtering

Handle specific events in your callback:

```python
def callback(token, metadata):
    event = metadata.get("event")

    if event == "start":
        print("🚀 Starting...")
    elif event == "token":
        print(token, end="")
    elif event == "end":
        print("\n✅ Done!")
    elif event == "error":
        print(f"❌ Error: {metadata['error']}")
```

### Node-Specific Handling

Process tokens differently based on the node:

```python
def callback(token, metadata):
    node = metadata.get("node")

    if node == "GenerateAnswer":
        # Main answer generation
        print(token, end="")
    elif node == "FetchNode":
        # Fetching phase (usually no tokens)
        pass
```

## Troubleshooting

### No Tokens Received

1. Verify streaming is enabled: `"streaming": True`
2. Check that callback is registered before `run()`
3. Ensure LLM supports streaming
4. Check API key is valid

### Slow Performance

1. Use buffered streaming to reduce callback overhead
2. Minimize work in callback function
3. Consider async callbacks for I/O operations

### Missing Tokens

1. Check callback error handling
2. Verify network connection is stable
3. Check for timeout issues

## Best Practices

1. **Keep callbacks fast**: Minimize processing in callback to avoid blocking
2. **Use buffering**: For production, use buffered callbacks for better performance
3. **Handle errors**: Always implement error handling in callbacks
4. **Clean up**: Flush buffers and close resources properly
5. **Test both modes**: Test with streaming enabled and disabled

## Contributing

To add more examples:

1. Create a new file in this directory
2. Follow the existing example structure
3. Add documentation to this README
4. Include error handling and best practices
5. Test with multiple LLM providers

## License

These examples are part of ScrapeGraphAI and follow the same license.
