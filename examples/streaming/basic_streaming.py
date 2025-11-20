"""
Basic Streaming Example for ScrapeGraphAI

This example demonstrates how to enable streaming LLM responses
and receive tokens in real-time as they are generated.
"""

from scrapegraphai.graphs import SmartScraperGraph
import os


def main():
    """
    Basic streaming example that prints tokens as they arrive.
    """
    # Define callback to receive tokens
    def on_token(token: str, metadata: dict):
        """
        Callback function that receives each token as it's generated.

        Args:
            token: The token string
            metadata: Dictionary with metadata about the token
                - event: "start", "token", "end", or "error"
                - node: Name of the node emitting the token
                - accumulated: Full accumulated response so far
                - etc.
        """
        # Handle different events
        event = metadata.get("event")

        if event == "start":
            print("\n🤖 Starting generation...")
            print("─" * 50)
        elif event == "end":
            print("\n" + "─" * 50)
            print("✅ Generation complete!")
        elif event == "error":
            print(f"\n❌ Error: {metadata.get('error')}")
        elif token:
            # Print token without newline
            print(token, end="", flush=True)

    # Configuration with streaming enabled
    config = {
        "llm": {
            "model": "openai/gpt-4",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "streaming": True,  # Enable streaming
        },
        "verbose": False,
    }

    # Create graph
    graph = SmartScraperGraph(
        prompt="Summarize this article in 3 bullet points",
        source="https://example.com",
        config=config
    )

    # Register streaming callback
    graph.add_streaming_callback(on_token)

    print("Starting scrape with streaming enabled...")
    print("Watch tokens appear in real-time:\n")

    # Run the graph - tokens will stream to callback
    result = graph.run()

    print("\n\nFinal Result:")
    print("=" * 50)
    print(result)


if __name__ == "__main__":
    main()
