# RFC-0006: Streaming LLM Response Support

## Status
**Status:** Proposed
**Author:** ScrapeGraphAI Team
**Created:** 2025-11-20
**Updated:** 2025-11-20

## Summary
Enable streaming token-by-token output from LLMs to provide progressive UI updates and faster perceived performance. Currently, the system hardcodes `streaming: False` in `abstract_graph.py:131`, preventing users from receiving real-time token streams even when they configure streaming support. This RFC proposes a comprehensive solution to enable streaming across the entire ScrapeGraphAI platform.

## Context
The current implementation has streaming capabilities hardcoded to disabled state:

```python
# scrapegraphai/graphs/abstract_graph.py:131
llm_defaults = {"streaming": False}
```

While the codebase has infrastructure for streaming (callback handlers with `on_llm_new_token` methods), the actual streaming functionality is:
- **Disabled by default**: Hardcoded to False, overriding user configuration
- **Non-functional in nodes**: `generate_answer_node.py` uses synchronous `.invoke()` calls that don't support streaming
- **Lacks callback propagation**: No mechanism to pass streaming callbacks through the graph execution pipeline
- **Missing UI integration**: No examples or utilities for consuming streaming responses

### Current State Analysis

**Abstract Graph (`abstract_graph.py`)**
```python
llm_defaults = {"streaming": False}
llm_params = {**llm_defaults, **llm_config}
# User's streaming config gets overridden by default
```

**Generate Answer Node (`generate_answer_node.py`)**
```python
# Uses synchronous invoke - no streaming support
response = chain.invoke(inputs)
```

**Callback Infrastructure (`custom_callback.py`)**
```python
# Already has streaming support, but unused
def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
    """Print out the token."""
    pass  # Currently does nothing
```

## Problem Statement
Users cannot leverage streaming LLM responses, resulting in:

1. **Poor User Experience**: Long waits without feedback for large documents or complex queries
2. **Perceived Latency**: No progressive output, making the system feel slower than it actually is
3. **Configuration Ignored**: Users setting `streaming: True` have their config silently overridden
4. **Missed Opportunities**: Cannot build real-time UI features like typing animations or progressive results
5. **Debugging Difficulty**: Harder to understand LLM behavior without seeing tokens as they arrive
6. **Incompatibility**: Modern LLM applications expect streaming by default (ChatGPT, Claude, etc.)

### Use Cases Requiring Streaming

**Real-time Web Scraping Dashboard**
```python
# User wants to see answer being generated in real-time
graph = SmartScraperGraph(
    prompt="Summarize this article",
    source="https://example.com",
    config={"llm": {"streaming": True}}  # Currently ignored!
)
```

**Interactive Chat Interface**
- Users expect to see responses appear progressively
- Better perceived performance compared to waiting for full response

**Long-form Content Generation**
- Processing multi-page documents
- Generating comprehensive summaries
- Users need progress feedback

**Debugging and Development**
- Developers want to see LLM reasoning in real-time
- Helps identify prompt issues faster
- Better understanding of model behavior

## Proposed Solution
Implement comprehensive streaming support through:

1. **Configuration Respect**: Honor user's `streaming` configuration instead of hardcoding False
2. **Streaming Chain Support**: Replace `.invoke()` with `.stream()` in nodes when streaming enabled
3. **Callback Propagation**: Pass streaming callbacks through graph execution pipeline
4. **Progressive State Updates**: Emit state updates as tokens arrive
5. **Backward Compatibility**: Default to non-streaming for existing code
6. **Event-based Architecture**: Provide event hooks for UI integration

### Key Benefits
- **Improved UX**: Users see progress in real-time, reducing perceived latency
- **Configuration Control**: Users can enable/disable streaming per graph instance
- **Modern Experience**: Matches expectations from ChatGPT, Claude, and other LLM tools
- **Better Debugging**: Developers can observe LLM behavior as it happens
- **Flexible Integration**: Support both streaming and non-streaming use cases
- **Progressive Enhancement**: Existing code works unchanged, new code can opt-in

## Design Details

### 1. Configuration System

#### 1.1 Respect User Configuration
```python
# scrapegraphai/graphs/abstract_graph.py

def _create_llm(self, llm_config: dict):
    """
    Create language model with user's streaming preference.

    Previous behavior:
        llm_defaults = {"streaming": False}  # Always False!

    New behavior:
        llm_defaults = {"streaming": False}  # Default only if not specified
    """
    # Only use default if user hasn't specified
    llm_defaults = {}
    if "streaming" not in llm_config:
        llm_defaults["streaming"] = False

    llm_params = {**llm_defaults, **llm_config}
    # Now user's streaming config is preserved

    # Store streaming state for nodes to access
    self._streaming_enabled = llm_params.get("streaming", False)

    return llm_params
```

#### 1.2 Graph-level Streaming State
```python
class AbstractGraph(ABC):
    """Enhanced with streaming state management."""

    def __init__(self, prompt: str, config: dict, source: str = None, schema: BaseModel = None):
        # ... existing init ...

        # Track streaming configuration
        self._streaming_enabled = config.get("llm", {}).get("streaming", False)
        self._streaming_callbacks = []

    def add_streaming_callback(self, callback: callable) -> None:
        """
        Add a callback to receive streaming tokens.

        Args:
            callback: Function called with each token. Signature: callback(token: str, metadata: dict)
        """
        self._streaming_callbacks.append(callback)

    def _emit_token(self, token: str, metadata: dict = None) -> None:
        """Emit token to all registered callbacks."""
        for callback in self._streaming_callbacks:
            try:
                callback(token, metadata or {})
            except Exception as e:
                logger.error(f"Error in streaming callback: {e}")
```

### 2. Node-level Streaming Support

#### 2.1 Enhanced Generate Answer Node
```python
# scrapegraphai/nodes/generate_answer_node.py

class GenerateAnswerNode(BaseNode):
    """Enhanced with streaming support."""

    def __init__(self, input: str, output: List[str], node_config: Optional[dict] = None, node_name: str = "GenerateAnswer"):
        super().__init__(node_name, "node", input, output, 2, node_config)
        self.llm_model = node_config["llm_model"]
        self.streaming_enabled = node_config.get("streaming", False)
        self.streaming_callback = node_config.get("streaming_callback", None)
        # ... existing init ...

    def execute(self, state: dict) -> dict:
        """Execute with optional streaming support."""
        self.logger.info(f"--- Executing {self.node_name} Node ---")

        # ... existing setup code ...

        if self.streaming_enabled:
            return self._execute_streaming(state, chain, user_prompt, doc)
        else:
            return self._execute_non_streaming(state, chain, user_prompt, doc)

    def _execute_non_streaming(self, state: dict, chain, user_prompt: str, doc) -> dict:
        """Existing synchronous execution path."""
        # Current implementation remains unchanged
        answer = self.invoke_with_timeout(chain, {"content": doc, "question": user_prompt}, self.timeout)
        state.update({self.output[0]: answer})
        return state

    def _execute_streaming(self, state: dict, chain, user_prompt: str, doc) -> dict:
        """New streaming execution path."""
        accumulated_response = ""

        try:
            # Use .stream() instead of .invoke()
            for chunk in chain.stream({"content": doc, "question": user_prompt}):
                token = self._extract_token(chunk)
                accumulated_response += token

                # Emit token through callback
                if self.streaming_callback:
                    self.streaming_callback(
                        token=token,
                        metadata={
                            "node": self.node_name,
                            "accumulated": accumulated_response,
                            "state_key": self.output[0]
                        }
                    )

                # Update state progressively
                state.update({self.output[0]: accumulated_response})

            # Parse final accumulated response
            if hasattr(chain, "output_parser"):
                # Need to parse the accumulated JSON
                final_answer = self._parse_accumulated_response(accumulated_response)
                state.update({self.output[0]: final_answer})

            return state

        except Exception as e:
            self.logger.error(f"Error in streaming execution: {str(e)}")
            raise

    def _extract_token(self, chunk) -> str:
        """Extract token from streaming chunk."""
        if isinstance(chunk, str):
            return chunk
        elif isinstance(chunk, dict):
            return chunk.get("content", "")
        elif hasattr(chunk, "content"):
            return chunk.content
        else:
            return str(chunk)

    def _parse_accumulated_response(self, response: str):
        """Parse accumulated streaming response."""
        try:
            # For JSON responses, parse the complete accumulated text
            import json
            return json.loads(response)
        except json.JSONDecodeError:
            # If not JSON, return as-is
            return response
```

#### 2.2 Handle Multi-chunk Processing
```python
def _execute_streaming_multi_chunk(self, state: dict, chains_dict: dict, user_prompt: str) -> dict:
    """
    Stream responses for multi-chunk processing.
    Note: Parallel streaming is complex - process sequentially with streaming
    """
    chunk_results = {}

    for chain_name, chain in tqdm(chains_dict.items(), desc="Processing chunks", disable=not self.verbose):
        accumulated = ""

        for chunk in chain.stream({"question": user_prompt}):
            token = self._extract_token(chunk)
            accumulated += token

            if self.streaming_callback:
                self.streaming_callback(
                    token=token,
                    metadata={
                        "node": self.node_name,
                        "chunk": chain_name,
                        "phase": "chunk_processing"
                    }
                )

        chunk_results[chain_name] = self._parse_accumulated_response(accumulated)

    # Now merge with streaming
    merge_chain = self._create_merge_chain()
    accumulated_merge = ""

    for chunk in merge_chain.stream({"content": chunk_results, "question": user_prompt}):
        token = self._extract_token(chunk)
        accumulated_merge += token

        if self.streaming_callback:
            self.streaming_callback(
                token=token,
                metadata={
                    "node": self.node_name,
                    "phase": "merging"
                }
            )

    final_answer = self._parse_accumulated_response(accumulated_merge)
    state.update({self.output[0]: final_answer})
    return state
```

### 3. Callback Handler Enhancement

#### 3.1 Streaming Callback Handler
```python
# scrapegraphai/utils/streaming_callback.py

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
```

#### 3.2 Integrate with Existing Custom Callback
```python
# scrapegraphai/utils/custom_callback.py

class CustomCallbackHandler(BaseCallbackHandler):
    """Enhanced with streaming token emission."""

    def __init__(self, llm_model_name: str, on_token: Optional[Callable] = None):
        super().__init__()
        self._lock = threading.Lock()
        self.model_name = llm_model_name if llm_model_name else "unknown"
        self.on_token = on_token  # New: optional token callback

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Emit token to callback if provided."""
        if self.on_token:
            try:
                self.on_token(token, {"model": self.model_name})
            except Exception as e:
                # Don't let callback errors break streaming
                pass
```

### 4. Graph Integration

#### 4.1 Pass Callbacks Through Execution
```python
# scrapegraphai/graphs/abstract_graph.py

def run(self, *args, **kwargs):
    """Execute graph with streaming support."""
    # Setup streaming callback if enabled
    streaming_callback = None
    if self._streaming_enabled:
        streaming_callback = self._create_streaming_callback()

    # Pass to nodes through config
    for node in self.nodes:
        if hasattr(node, "streaming_callback"):
            node.streaming_callback = streaming_callback

    # Execute graph
    result = self._execute(*args, **kwargs)

    return result

def _create_streaming_callback(self):
    """Create callback that emits to all registered callbacks."""
    def callback(token: str, metadata: dict):
        self._emit_token(token, metadata)
    return callback
```

#### 4.2 Smart Scraper Graph Example
```python
# scrapegraphai/graphs/smart_scraper_graph.py

class SmartScraperGraph(AbstractGraph):
    """Enhanced with streaming support."""

    def run(self) -> dict:
        """Execute scraping with optional streaming."""
        if self._streaming_enabled:
            logger.info("Running SmartScraperGraph with streaming enabled")

        # ... existing execution logic ...

        # Nodes automatically receive streaming callbacks
        result = super().run()

        return result
```

### 5. Usage Examples

#### 5.1 Basic Streaming Usage
```python
from scrapegraphai.graphs import SmartScraperGraph

# Define callback to receive tokens
def on_token(token: str, metadata: dict):
    print(token, end="", flush=True)
    # metadata contains: node, accumulated, state_key, event, etc.

# Create graph with streaming enabled
graph = SmartScraperGraph(
    prompt="What is this article about?",
    source="https://example.com/article",
    config={
        "llm": {
            "model": "openai/gpt-4",
            "streaming": True  # Enable streaming
        }
    }
)

# Register callback
graph.add_streaming_callback(on_token)

# Run - tokens will stream to callback
result = graph.run()
```

#### 5.2 Web Application Integration
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/scrape/stream")
async def scrape_with_streaming(request: ScrapeRequest):
    """Endpoint that streams scraping results."""

    async def generate():
        """Generator that yields streaming tokens."""
        buffer = []

        def on_token(token: str, metadata: dict):
            # Send token as Server-Sent Event
            event = {
                "token": token,
                "metadata": metadata
            }
            buffer.append(f"data: {json.dumps(event)}\n\n")

        # Create and run graph
        graph = SmartScraperGraph(
            prompt=request.prompt,
            source=request.source,
            config={"llm": {"streaming": True}}
        )
        graph.add_streaming_callback(on_token)

        # Run in background, yield buffered tokens
        import asyncio
        loop = asyncio.get_event_loop()

        async def run_graph():
            result = await loop.run_in_executor(None, graph.run)
            buffer.append(f"data: {json.dumps({'event': 'complete', 'result': result})}\n\n")

        task = asyncio.create_task(run_graph())

        while not task.done() or buffer:
            if buffer:
                yield buffer.pop(0)
            await asyncio.sleep(0.01)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

#### 5.3 Real-time UI Example (React)
```javascript
// Frontend code consuming streaming endpoint
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
          // Update UI progressively
          updateResultDisplay(result);
        }

        if (data.event === 'complete') {
          // Final result ready
          handleComplete(data.result);
        }
      }
    }
  }
};
```

#### 5.4 CLI Streaming Example
```python
# examples/streaming_cli.py

from scrapegraphai.graphs import SmartScraperGraph
import sys

def stream_to_console(token: str, metadata: dict):
    """Print tokens to console as they arrive."""
    if metadata.get("event") == "start":
        print("\n🤖 Starting generation...\n")
    elif metadata.get("event") == "end":
        print("\n\n✅ Complete!")
    elif metadata.get("event") == "error":
        print(f"\n❌ Error: {metadata['error']}")
    elif token:
        # Print token without newline
        sys.stdout.write(token)
        sys.stdout.flush()

if __name__ == "__main__":
    graph = SmartScraperGraph(
        prompt="Summarize this article in 3 bullet points",
        source="https://example.com/article",
        config={
            "llm": {
                "model": "openai/gpt-4",
                "streaming": True
            }
        }
    )

    graph.add_streaming_callback(stream_to_console)
    result = graph.run()

    print(f"\n\nFinal result: {result}")
```

### 6. Configuration Options

#### 6.1 Streaming Configuration Schema
```python
streaming_config = {
    "llm": {
        # Enable/disable streaming
        "streaming": True,  # Default: False for backward compatibility

        # Buffer size before emitting (for performance)
        "streaming_buffer_size": 1,  # Emit every N tokens

        # Streaming timeout
        "streaming_timeout": 300,  # Seconds
    }
}
```

#### 6.2 Environment Variables
```bash
# Enable streaming by default
export SCRAPEGRAPH_STREAMING=true

# Configure buffer size
export SCRAPEGRAPH_STREAMING_BUFFER=5
```

### 7. Performance Considerations

#### 7.1 Buffering Strategy
```python
class BufferedStreamingCallback:
    """Buffer tokens before emitting for better performance."""

    def __init__(self, callback: Callable, buffer_size: int = 5):
        self.callback = callback
        self.buffer_size = buffer_size
        self.buffer = []

    def on_token(self, token: str, metadata: dict):
        """Buffer tokens and emit in batches."""
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
```

#### 7.2 Performance Metrics
- **Token Overhead**: ~0.1-0.5ms per token emission (negligible)
- **Callback Overhead**: Depends on user implementation, recommend <1ms
- **Network Overhead**: SSE adds ~100 bytes per event
- **Latency Improvement**: First token in ~500ms vs ~5s for full response

## Implementation Plan

### Phase 1: Core Streaming Infrastructure (Week 1)
- [ ] Remove hardcoded `streaming: False` in `abstract_graph.py`
- [ ] Implement configuration respect logic
- [ ] Create `StreamingCallbackHandler` class
- [ ] Add `_streaming_enabled` state to `AbstractGraph`
- [ ] Implement `add_streaming_callback()` and `_emit_token()` methods
- [ ] Add comprehensive unit tests

### Phase 2: Node Integration (Week 2)
- [ ] Update `GenerateAnswerNode` with `_execute_streaming()` method
- [ ] Implement token extraction logic
- [ ] Add streaming support for single-chunk processing
- [ ] Handle multi-chunk streaming (sequential with streaming)
- [ ] Update `FetchNode`, `ParseNode` if needed
- [ ] Add integration tests

### Phase 3: Callback Propagation (Week 3)
- [ ] Implement callback propagation through graph execution
- [ ] Update all graph types (SmartScraperGraph, JSONScraperGraph, etc.)
- [ ] Enhance `CustomCallbackHandler` with streaming support
- [ ] Add buffering capability for performance
- [ ] Test end-to-end streaming flow

### Phase 4: Examples and Documentation (Week 4)
- [ ] Create basic streaming example
- [ ] Add FastAPI streaming endpoint example
- [ ] Create CLI streaming example
- [ ] Add React/JavaScript frontend example
- [ ] Write comprehensive documentation
- [ ] Add configuration guide

### Phase 5: Advanced Features (Week 5)
- [ ] Implement buffered streaming for performance
- [ ] Add streaming events (start, end, error)
- [ ] Create streaming utilities and helpers
- [ ] Add monitoring and metrics for streaming
- [ ] Performance optimization and tuning
- [ ] Beta testing with real users

## Testing Strategy

### Unit Tests
```python
def test_streaming_configuration_respected():
    """Test that user's streaming config is not overridden."""
    config = {"llm": {"model": "openai/gpt-4", "streaming": True}}
    graph = SmartScraperGraph(prompt="test", source="http://example.com", config=config)

    assert graph._streaming_enabled == True

def test_streaming_callback_registration():
    """Test callback registration."""
    graph = SmartScraperGraph(prompt="test", source="http://example.com", config={})

    tokens = []
    def callback(token, metadata):
        tokens.append(token)

    graph.add_streaming_callback(callback)
    assert len(graph._streaming_callbacks) == 1

def test_token_emission():
    """Test token emission to callbacks."""
    graph = SmartScraperGraph(prompt="test", source="http://example.com", config={})

    received_tokens = []
    def callback(token, metadata):
        received_tokens.append((token, metadata))

    graph.add_streaming_callback(callback)
    graph._emit_token("Hello", {"node": "test"})

    assert len(received_tokens) == 1
    assert received_tokens[0][0] == "Hello"
    assert received_tokens[0][1]["node"] == "test"
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_end_to_end_streaming():
    """Test streaming from graph to callback."""
    tokens = []

    def on_token(token, metadata):
        tokens.append(token)

    graph = SmartScraperGraph(
        prompt="What is this?",
        source="https://example.com",
        config={"llm": {"streaming": True}}
    )
    graph.add_streaming_callback(on_token)

    result = graph.run()

    # Should have received tokens
    assert len(tokens) > 0
    # Tokens should form complete response
    assert "".join([t for t in tokens if t]) in str(result)

def test_streaming_with_multiple_callbacks():
    """Test multiple callbacks receive same tokens."""
    tokens1, tokens2 = [], []

    graph = SmartScraperGraph(
        prompt="test",
        source="http://example.com",
        config={"llm": {"streaming": True}}
    )

    graph.add_streaming_callback(lambda t, m: tokens1.append(t))
    graph.add_streaming_callback(lambda t, m: tokens2.append(t))

    graph.run()

    assert tokens1 == tokens2

def test_streaming_error_handling():
    """Test that callback errors don't break streaming."""
    success_tokens = []

    def failing_callback(token, metadata):
        raise Exception("Callback error")

    def success_callback(token, metadata):
        success_tokens.append(token)

    graph = SmartScraperGraph(
        prompt="test",
        source="http://example.com",
        config={"llm": {"streaming": True}}
    )

    graph.add_streaming_callback(failing_callback)
    graph.add_streaming_callback(success_callback)

    # Should complete despite failing callback
    result = graph.run()

    assert len(success_tokens) > 0
    assert result is not None
```

## Migration Strategy

### Backward Compatibility
The implementation maintains full backward compatibility:

```python
# Existing code works unchanged (streaming disabled by default)
graph = SmartScraperGraph(
    prompt="test",
    source="http://example.com",
    config={"llm": {"model": "openai/gpt-4"}}
)
result = graph.run()  # Works exactly as before

# New code can opt-in to streaming
graph = SmartScraperGraph(
    prompt="test",
    source="http://example.com",
    config={"llm": {"model": "openai/gpt-4", "streaming": True}}
)
graph.add_streaming_callback(my_callback)
result = graph.run()  # Now streams tokens
```

### Migration Steps
1. **Phase 1**: Deploy streaming infrastructure (no breaking changes)
2. **Phase 2**: Update documentation with streaming examples
3. **Phase 3**: Encourage adoption through blog posts and tutorials
4. **Phase 4**: Consider making streaming default in v2.0 (with opt-out)

### Deprecation Timeline
- **v1.x**: Streaming disabled by default (opt-in)
- **v1.9**: Add warning when streaming=False (deprecation notice)
- **v2.0**: Streaming enabled by default (opt-out with `streaming: False`)

## Performance Considerations

### Overhead Analysis
- **Token Emission**: ~0.1-0.5ms per token (negligible)
- **Callback Execution**: User-dependent, recommend <1ms per callback
- **Buffering**: Can reduce callback frequency by 5-10x
- **Network**: SSE adds ~100 bytes per event

### Optimization Strategies
1. **Buffering**: Emit tokens in batches (5-10 tokens)
2. **Async Callbacks**: Support async callbacks for I/O operations
3. **Sampling**: Allow users to sample every Nth token
4. **Lazy Evaluation**: Only enable streaming machinery when callbacks registered

### Memory Impact
- **Callback Registry**: ~100 bytes per callback
- **Token Buffer**: ~1-10 KB depending on buffer size
- **State Updates**: Minimal overhead, reuses existing state dict

## Alternatives Considered

### Alternative 1: Always Enable Streaming
**Pros:**
- Simpler implementation
- Modern default behavior
- Better user experience

**Cons:**
- Breaking change for existing users
- Overhead for users who don't need it
- Compatibility issues with some LLM providers

**Decision:** Opt-in for v1.x, consider for v2.0

### Alternative 2: Use Server-Sent Events Built-in
**Pros:**
- Standard protocol
- Browser support
- Well-understood

**Cons:**
- Requires web server integration
- Doesn't help CLI/library users
- Too prescriptive

**Decision:** Provide SSE example, but keep core implementation flexible

### Alternative 3: Use AsyncIterator Pattern
```python
async for token in graph.stream():
    print(token)
```

**Pros:**
- Pythonic
- Clear control flow
- Standard pattern

**Cons:**
- Requires async/await throughout
- Breaking change
- Complex migration

**Decision:** Consider for v2.0, use callbacks for v1.x

### Alternative 4: Separate Streaming Graph Class
```python
StreamingSmartScraperGraph  # New class for streaming
```

**Pros:**
- Clear separation
- No risk to existing code
- Easy to maintain

**Cons:**
- Code duplication
- Confusing for users
- Not DRY

**Decision:** Not viable, adds unnecessary complexity

## Open Questions

1. **Async Support**: Should callbacks support async functions?
   - *Suggestion:* Yes, detect async callbacks and await them

2. **Token Metadata**: What metadata should we include with each token?
   - *Suggestion:* `{node, accumulated, state_key, event, timestamp}`

3. **Error Recovery**: How to handle streaming errors mid-generation?
   - *Suggestion:* Emit error event, return partial results

4. **Multi-chunk Streaming**: Stream tokens while processing chunks in parallel?
   - *Suggestion:* Process chunks sequentially when streaming enabled

5. **Performance Threshold**: When is buffering recommended?
   - *Suggestion:* Buffer when >100 tokens/sec or network latency >50ms

6. **LLM Provider Support**: Which providers support streaming?
   - *Action:* Document streaming support per provider

## Success Metrics

- **Adoption Rate**: 30% of users enable streaming within 6 months
- **Perceived Performance**: 50% improvement in user-reported responsiveness
- **Token Latency**: First token in <500ms (down from 5s average)
- **Error Rate**: <1% streaming-related errors
- **Performance Overhead**: <5% execution time increase when streaming enabled
- **User Satisfaction**: >4.5/5 rating for streaming feature

## References

- [LangChain Streaming Documentation](https://python.langchain.com/docs/expression_language/streaming)
- [OpenAI Streaming API](https://platform.openai.com/docs/api-reference/streaming)
- [Server-Sent Events Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI Streaming Response](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [LangChain Callbacks](https://python.langchain.com/docs/modules/callbacks/)
- [Anthropic Streaming](https://docs.anthropic.com/claude/reference/streaming)

## Appendix: Code Examples

### Example 1: Disable Streaming (Current Behavior)
```python
# This is the current default behavior - no change required
graph = SmartScraperGraph(
    prompt="Summarize this page",
    source="https://example.com",
    config={
        "llm": {"model": "openai/gpt-4"}
        # streaming defaults to False
    }
)
result = graph.run()  # Returns complete result
```

### Example 2: Enable Streaming with Simple Callback
```python
from scrapegraphai.graphs import SmartScraperGraph

tokens_received = []

def collect_tokens(token: str, metadata: dict):
    """Simple callback that collects tokens."""
    tokens_received.append(token)

graph = SmartScraperGraph(
    prompt="Analyze this article",
    source="https://news.example.com/article",
    config={
        "llm": {
            "model": "openai/gpt-4",
            "streaming": True  # Enable streaming
        }
    }
)

graph.add_streaming_callback(collect_tokens)
result = graph.run()

print(f"Received {len(tokens_received)} tokens")
print(f"Combined: {''.join(tokens_received)}")
```

### Example 3: Progress Bar with Streaming
```python
from scrapegraphai.graphs import SmartScraperGraph
from tqdm import tqdm

def create_progress_callback():
    """Create callback with progress bar."""
    pbar = tqdm(desc="Generating", unit=" tokens")

    def callback(token: str, metadata: dict):
        if metadata.get("event") == "start":
            pbar.reset()
        elif metadata.get("event") == "end":
            pbar.close()
        elif token:
            pbar.update(1)
            pbar.set_postfix_str(token[:20])  # Show last token

    return callback

graph = SmartScraperGraph(
    prompt="Extract all product names",
    source="https://shop.example.com",
    config={"llm": {"streaming": True}}
)

graph.add_streaming_callback(create_progress_callback())
result = graph.run()
```

### Example 4: WebSocket Streaming
```python
from fastapi import FastAPI, WebSocket
from scrapegraphai.graphs import SmartScraperGraph
import json

app = FastAPI()

@app.websocket("/ws/scrape")
async def websocket_scrape(websocket: WebSocket):
    """WebSocket endpoint for real-time scraping."""
    await websocket.accept()

    # Receive request
    data = await websocket.receive_json()

    # Create callback to send tokens via WebSocket
    async def send_token(token: str, metadata: dict):
        await websocket.send_json({
            "token": token,
            "metadata": metadata
        })

    # Create and run graph
    graph = SmartScraperGraph(
        prompt=data["prompt"],
        source=data["source"],
        config={"llm": {"streaming": True}}
    )

    graph.add_streaming_callback(send_token)
    result = graph.run()

    # Send final result
    await websocket.send_json({
        "event": "complete",
        "result": result
    })

    await websocket.close()
```

### Example 5: File Output Streaming
```python
from scrapegraphai.graphs import SmartScraperGraph
import sys

def stream_to_file(filepath: str):
    """Create callback that streams to file."""
    f = open(filepath, 'w')

    def callback(token: str, metadata: dict):
        if metadata.get("event") == "end":
            f.close()
        elif token:
            f.write(token)
            f.flush()  # Ensure immediate write

    return callback

graph = SmartScraperGraph(
    prompt="Write a comprehensive analysis",
    source="https://example.com/report",
    config={"llm": {"streaming": True}}
)

# Stream output to file as it's generated
graph.add_streaming_callback(stream_to_file("output.txt"))
graph.add_streaming_callback(lambda t, m: sys.stdout.write(t))  # Also to console

result = graph.run()
```

### Example 6: Conditional Streaming
```python
from scrapegraphai.graphs import SmartScraperGraph
import os

# Enable streaming based on environment
streaming_enabled = os.getenv("ENABLE_STREAMING", "false").lower() == "true"

config = {
    "llm": {
        "model": "openai/gpt-4",
        "streaming": streaming_enabled
    }
}

graph = SmartScraperGraph(
    prompt="Extract information",
    source="https://example.com",
    config=config
)

if streaming_enabled:
    graph.add_streaming_callback(
        lambda t, m: print(t, end="", flush=True)
    )

result = graph.run()
```

---

**Document Status:** Ready for Review
**Next Steps:**
1. Review by architecture team
2. Gather feedback from users on streaming requirements
3. Create implementation tickets
4. Prioritize LLM provider compatibility testing
