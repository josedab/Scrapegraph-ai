"""
CLI Streaming Example for ScrapeGraphAI

This example demonstrates a command-line interface that streams
LLM responses to the console with nice formatting.
"""

import sys
import argparse
from scrapegraphai.graphs import SmartScraperGraph
import os


class StreamingCLI:
    """CLI tool with streaming support."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.current_node = None

    def stream_to_console(self, token: str, metadata: dict):
        """
        Print tokens to console as they arrive with formatting.

        Args:
            token: The token to print
            metadata: Metadata about the token
        """
        event = metadata.get("event")
        node = metadata.get("node")

        if event == "start":
            print("\n" + "=" * 60)
            print("🚀 Starting LLM Generation")
            print("=" * 60)
            if self.verbose:
                prompts = metadata.get("prompts", [])
                if prompts:
                    print(f"Prompt: {prompts[0][:100]}...")
            print()
        elif event == "end":
            print("\n" + "=" * 60)
            print("✅ Generation Complete")
            print("=" * 60 + "\n")
        elif event == "error":
            print(f"\n❌ Error: {metadata['error']}\n")
        elif token:
            # Show node changes if verbose
            if self.verbose and node and node != self.current_node:
                if self.current_node is not None:
                    print()  # Add line break between nodes
                print(f"\n[{node}]")
                self.current_node = node

            # Print the token
            sys.stdout.write(token)
            sys.stdout.flush()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Stream scraping results to console"
    )
    parser.add_argument(
        "url",
        help="URL to scrape"
    )
    parser.add_argument(
        "-p", "--prompt",
        default="What is this page about?",
        help="Prompt for the scraper"
    )
    parser.add_argument(
        "-m", "--model",
        default="openai/gpt-4",
        help="LLM model to use"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with node information"
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=1,
        help="Token buffer size (1 = no buffering)"
    )

    args = parser.parse_args()

    # Create CLI instance
    cli = StreamingCLI(verbose=args.verbose)

    # Configuration
    config = {
        "llm": {
            "model": args.model,
            "api_key": os.getenv("OPENAI_API_KEY"),
            "streaming": True,
        },
        "verbose": args.verbose,
    }

    # Create graph
    print(f"📄 Scraping: {args.url}")
    print(f"🎯 Prompt: {args.prompt}")
    print(f"🤖 Model: {args.model}\n")

    graph = SmartScraperGraph(
        prompt=args.prompt,
        source=args.url,
        config=config
    )

    # Register callback
    if args.buffer_size > 1:
        # Use buffered callback for better performance
        from scrapegraphai.utils.streaming_callback import BufferedStreamingCallback
        buffered = BufferedStreamingCallback(
            cli.stream_to_console,
            buffer_size=args.buffer_size
        )
        graph.add_streaming_callback(buffered.on_token)
    else:
        graph.add_streaming_callback(cli.stream_to_console)

    # Run
    try:
        result = graph.run()

        print("\n\n📊 Final Result:")
        print("=" * 60)
        print(result)
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
