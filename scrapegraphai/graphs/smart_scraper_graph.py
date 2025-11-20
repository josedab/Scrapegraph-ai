"""
SmartScraperGraph Module
"""

import logging
from typing import Optional, Type

from pydantic import BaseModel

# Initialize logger
logger = logging.getLogger(__name__)

from ..nodes import (
    ConditionalNode,
    FetchNode,
    GenerateAnswerNode,
    ParseNode,
    ReasoningNode,
)
from ..prompts import REGEN_ADDITIONAL_INFO
from .abstract_graph import AbstractGraph
from .base_graph import BaseGraph


class SmartScraperGraph(AbstractGraph):
    """
    SmartScraper is a scraping pipeline that automates the process of
    extracting information from web pages
    using a natural language model to interpret and answer prompts.

    Attributes:
        prompt (str): The prompt for the graph.
        source (str): The source of the graph.
        config (dict): Configuration parameters for the graph.
        schema (BaseModel): The schema for the graph output.
        llm_model: An instance of a language model client, configured for generating answers.
        embedder_model: An instance of an embedding model client,
        configured for generating embeddings.
        verbose (bool): A flag indicating whether to show print statements during execution.
        headless (bool): A flag indicating whether to run the graph in headless mode.

    Args:
        prompt (str): The prompt for the graph.
        source (str): The source of the graph.
        config (dict): Configuration parameters for the graph.
        schema (BaseModel): The schema for the graph output.

    Example:
        >>> smart_scraper = SmartScraperGraph(
        ...     "List me all the attractions in Chioggia.",
        ...     "https://en.wikipedia.org/wiki/Chioggia",
        ...     {"llm": {"model": "openai/gpt-3.5-turbo"}}
        ... )
        >>> result = smart_scraper.run()
        )
    """

    def __init__(
        self,
        prompt: str,
        source: str,
        config: dict,
        schema: Optional[Type[BaseModel]] = None,
    ):
        super().__init__(prompt, config, source, schema)

        self.input_key = "url" if source.startswith("http") else "local_dir"

        # for detailed logging of the SmartScraper API set it to True
        self.verbose = config.get("verbose", False)

    def _create_graph(self) -> BaseGraph:
        """
        Creates the graph of nodes representing the workflow for web scraping.

        This implementation uses the template system to compose the graph
        based on configuration flags, replacing 84 lines of duplicated
        configuration with a clean, composable approach.

        Configuration flags:
            html_mode (bool): Skip HTML parsing if True (default: False)
            reasoning (bool): Enable reasoning stage if True (default: False)
            reattempt (bool): Enable validation/regeneration if True (default: False)

        Returns:
            BaseGraph: A graph instance representing the web scraping workflow.
        """
        if self.llm_model == "scrapegraphai/smart-scraper":
            try:
                from scrapegraph_py import Client
                from scrapegraph_py.logger import sgai_logger
            except ImportError:
                raise ImportError(
                    "scrapegraph_py is not installed. Please install it using 'pip install scrapegraph-py'."
                )

            sgai_logger.set_logging(level="INFO")

            # Initialize the client with explicit API key
            sgai_client = Client(api_key=self.config.get("api_key"))

            # SmartScraper request
            response = sgai_client.smartscraper(
                website_url=self.source,
                user_prompt=self.prompt,
            )

            # Use logging instead of print for better production practices
            if 'request_id' in response and 'result' in response:
                logger.info(f"Request ID: {response['request_id']}")
                logger.info(f"Result: {response['result']}")
            else:
                logger.warning("Missing expected keys in response.")

            sgai_client.close()

            return response

        # Use template system for graph composition
        from .templates.pipelines import SmartScraperPipeline

        # Prepare configuration for template
        node_config = {
            "llm_model": self.llm_model,
            "force": self.config.get("force", False),
            "cut": self.config.get("cut", True),
            "loader_kwargs": self.config.get("loader_kwargs", {}),
            "browser_base": self.config.get("browser_base"),
            "scrape_do": self.config.get("scrape_do"),
            "storage_state": self.config.get("storage_state"),
            "model_token": self.model_token,
            "additional_info": self.config.get("additional_info"),
            "schema": self.schema,
            # Template control flags
            "html_mode": self.config.get("html_mode", False),
            "reasoning": self.config.get("reasoning", False),
            "reattempt": self.config.get("reattempt", False),
        }

        return SmartScraperPipeline.build(node_config)

    def run(self) -> str:
        """
        Executes the scraping process and returns the answer to the prompt.

        Returns:
            str: The answer to the prompt.
        """

        inputs = {"user_prompt": self.prompt, self.input_key: self.source}
        self.final_state, self.execution_info = self.graph.execute(inputs)

        return self.final_state.get("answer", "No answer found.")
