"""
AbstractGraph Module
"""

import asyncio
import uuid
import warnings
import time
from abc import ABC, abstractmethod
from typing import Optional, Type

from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter
from pydantic import BaseModel

from ..helpers import models_tokens
from ..models import CLoD, DeepSeek, OneApi, XAI
from ..utils.logging import set_verbosity_info, set_verbosity_warning, get_logger
from ..telemetry import log_graph_execution
from ..resilience import (
    CircuitBreaker,
    ResilientLLMProvider,
    LLMProviderManager,
)

logger = get_logger(__name__)

# ANSI escape sequence for hyperlink
CLICKABLE_URL = "\033]8;;https://scrapegraphai.com\033\\https://scrapegraphai.com\033]8;;\033\\"

class AbstractGraph(ABC):
    """
    Scaffolding class for creating a graph representation and executing it.

        prompt (str): The prompt for the graph.
        source (str): The source of the graph.
        config (dict): Configuration parameters for the graph.
        schema (BaseModel): The schema for the graph output.
        llm_model: An instance of a language model client, configured for generating answers.
        verbose (bool): A flag indicating whether to show print statements during execution.
        headless (bool): A flag indicating whether to run the graph in headless mode.

    Args:
        prompt (str): The prompt for the graph.
        config (dict): Configuration parameters for the graph.
        source (str, optional): The source of the graph.
        schema (str, optional): The schema for the graph output.

    Example:
        >>> class MyGraph(AbstractGraph):
        ...     def _create_graph(self):
        ...         # Implementation of graph creation here
        ...         return graph
        ...
        >>> my_graph = MyGraph("Example Graph",
        {"llm": {"model": "gpt-3.5-turbo"}}, "example_source")
        >>> result = my_graph.run()
    """

    def __init__(
        self,
        prompt: str,
        config: dict,
        source: Optional[str] = None,
        schema: Optional[Type[BaseModel]] = None,
    ):
        self.prompt = prompt
        self.source = source
        self.config = config
        self.schema = schema
        self.llm_model = self._create_llm_manager(config["llm"])
        self.verbose = False if config is None else config.get("verbose", False)
        self.headless = True if self.config is None else config.get("headless", True)
        self.loader_kwargs = self.config.get("loader_kwargs", {})
        self.cache_path = self.config.get("cache_path", False)
        self.browser_base = self.config.get("browser_base")
        self.scrape_do = self.config.get("scrape_do")
        self.storage_state = self.config.get("storage_state")
        self.timeout = self.config.get("timeout", 480)

        self.graph = self._create_graph()
        self.final_state = None
        self.execution_info = None

        verbose = bool(config and config.get("verbose"))

        if verbose:
            set_verbosity_info()
        else:
            set_verbosity_warning()

        common_params = {
            "headless": self.headless,
            "verbose": self.verbose,
            "loader_kwargs": self.loader_kwargs,
            "llm_model": self.llm_model,
            "cache_path": self.cache_path,
            "timeout": self.timeout,
        }

        self.set_common_params(common_params, overwrite=True)

        self.burr_kwargs = config.get("burr_kwargs", None)
        if self.burr_kwargs is not None:
            self.graph.use_burr = True
            if "app_instance_id" not in self.burr_kwargs:
                self.burr_kwargs["app_instance_id"] = str(uuid.uuid4())

            self.graph.burr_config = self.burr_kwargs

    def set_common_params(self, params: dict, overwrite=False):
        """
        Pass parameters to every node in the graph unless otherwise defined in the graph.

        Args:
            params (dict): Common parameters and their values.
        """

        for node in self.graph.nodes:
            node.update_config(params, overwrite)

    def _create_llm(self, llm_config: dict) -> object:
        """
        Create a large language model instance based on the configuration provided.

        Args:
            llm_config (dict): Configuration parameters for the language model.

        Returns:
            object: An instance of the language model client.

        Raises:
            KeyError: If the model is not supported.
        """

        llm_defaults = {"streaming": False}
        llm_params = {**llm_defaults, **llm_config}
        rate_limit_params = llm_params.pop("rate_limit", {})

        if rate_limit_params:
            requests_per_second = rate_limit_params.get("requests_per_second")
            max_retries = rate_limit_params.get("max_retries")
            if requests_per_second is not None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    llm_params["rate_limiter"] = InMemoryRateLimiter(
                        requests_per_second=requests_per_second
                    )
            if max_retries is not None:
                llm_params["max_retries"] = max_retries

        if "model_instance" in llm_params:
            try:
                self.model_token = llm_params["model_tokens"]
            except KeyError as exc:
                raise KeyError("model_tokens not specified") from exc
            return llm_params["model_instance"]

        known_providers = {
            "openai",
            "azure_openai",
            "google_genai",
            "google_vertexai",
            "ollama",
            "oneapi",
            "nvidia",
            "groq",
            "anthropic",
            "bedrock",
            "mistralai",
            "hugging_face",
            "deepseek",
            "ernie",
            "fireworks",
            "clod",
            "togetherai",
            "xai",
        }

        if "/" in llm_params["model"]:
            split_model_provider = llm_params["model"].split("/", 1)
            llm_params["model_provider"] = split_model_provider[0]
            llm_params["model"] = split_model_provider[1]
        else:
            possible_providers = [
                provider
                for provider, models_d in models_tokens.items()
                if llm_params["model"] in models_d
            ]
            if len(possible_providers) <= 0:
                raise ValueError(
                    f"""Provider {llm_params["model_provider"]} is not supported.
                                If possible, try to use a model instance instead."""
                )
            llm_params["model_provider"] = possible_providers[0]
            print(
                (
                    f"Found providers {possible_providers} for model {llm_params['model']}, using {llm_params['model_provider']}.\n"
                    "If it was not intended please specify the model provider in the graph configuration"
                )
            )

        if llm_params["model_provider"] not in known_providers:
            raise ValueError(
                f"""Provider {llm_params["model_provider"]} is not supported.
                             If possible, try to use a model instance instead."""
            )

        if llm_params.get("model_tokens", None) is None:
            try:
                self.model_token = models_tokens[llm_params["model_provider"]][
                    llm_params["model"]
                ]
            except KeyError:
                print(
                    f"""Max input tokens for model {llm_params["model_provider"]}/{llm_params["model"]} not found,
                    please specify the model_tokens parameter in the llm section of the graph configuration.
                    Using default token size: 8192"""
                )
                self.model_token = 8192
        else:
            self.model_token = llm_params["model_tokens"]

        try:
            if llm_params["model_provider"] not in {
                "oneapi",
                "nvidia",
                "ernie",
                "deepseek",
                "togetherai",
                "clod",
                "xai",
            }:
                if llm_params["model_provider"] == "bedrock":
                    llm_params["model_kwargs"] = {
                        "temperature": llm_params.pop("temperature")
                    }
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    return init_chat_model(**llm_params)
            else:
                model_provider = llm_params.pop("model_provider")

                if model_provider == "clod":
                    return CLoD(**llm_params)

                if model_provider == "deepseek":
                    return DeepSeek(**llm_params)

                if model_provider == "ernie":
                    from langchain_community.chat_models import ErnieBotChat

                    return ErnieBotChat(**llm_params)

                elif model_provider == "oneapi":
                    return OneApi(**llm_params)

                elif model_provider == "xai":
                    return XAI(**llm_params)

                elif model_provider == "togetherai":
                    try:
                        from langchain_together import ChatTogether
                    except ImportError:
                        raise ImportError(
                            """The langchain_together module is not installed.
                                          Please install it using `pip install langchain-together`."""
                        )
                    return ChatTogether(**llm_params)

                elif model_provider == "nvidia":
                    try:
                        from langchain_nvidia_ai_endpoints import ChatNVIDIA
                    except ImportError:
                        raise ImportError(
                            """The langchain_nvidia_ai_endpoints module is not installed.
                                          Please install it using `pip install langchain-nvidia-ai-endpoints`."""
                        )
                    return ChatNVIDIA(**llm_params)

        except Exception as e:
            raise Exception(f"Error instancing model: {e}")

    def _create_llm_manager(self, llm_config: dict) -> object:
        """
        Create LLM provider manager with fallback support.

        This method creates an LLM provider manager that can automatically
        fall back to alternative providers if the primary fails. If fallback
        is not enabled in the configuration, it returns a simple provider
        manager with only the primary provider for backward compatibility.

        Args:
            llm_config (dict): Configuration parameters for the language model,
                              optionally including fallback configuration.

        Returns:
            object: LLMProviderManager instance or a simple wrapper for backward compatibility

        Example:
            Configuration with fallback:
            {
                "model": "gpt-4",
                "model_provider": "openai",
                "fallback": {
                    "enabled": True,
                    "providers": [
                        {
                            "model": "claude-3-sonnet",
                            "model_provider": "anthropic",
                            "priority": 1
                        }
                    ],
                    "circuit_breaker": {
                        "failure_threshold": 5,
                        "success_threshold": 2,
                        "timeout": 60
                    },
                    "retry": {
                        "max_attempts": 3,
                        "exponential_backoff": True
                    }
                }
            }
        """
        fallback_config = llm_config.get("fallback", {})

        # Check if fallback is enabled
        if not fallback_config.get("enabled", False):
            # Backward compatibility: single provider without resilience features
            llm = self._create_llm(llm_config)
            # Wrap in a simple manager that always uses the single provider
            primary = ResilientLLMProvider(
                provider=llm,
                circuit_breaker=CircuitBreaker(
                    failure_threshold=999999  # Effectively disable circuit breaker
                ),
                name=f"{llm_config.get('model_provider', 'unknown')}/{llm_config.get('model', 'unknown')}"
            )
            return LLMProviderManager(
                primary=primary,
                fallback_enabled=False
            )

        # Extract circuit breaker configuration
        cb_config = fallback_config.get("circuit_breaker", {})

        # Create primary provider with circuit breaker
        primary_llm = self._create_llm(llm_config)
        primary = ResilientLLMProvider(
            provider=primary_llm,
            circuit_breaker=CircuitBreaker(
                failure_threshold=cb_config.get("failure_threshold", 5),
                success_threshold=cb_config.get("success_threshold", 2),
                timeout=cb_config.get("timeout", 60),
                half_open_max_calls=cb_config.get("half_open_max_calls", 1)
            ),
            name=f"{llm_config.get('model_provider', 'primary')}/{llm_config.get('model', 'unknown')}",
            priority=0
        )

        # Create fallback providers
        fallbacks = []
        for fb_config in fallback_config.get("providers", []):
            # Merge primary config with fallback config (fallback takes precedence)
            merged_config = {**llm_config, **fb_config}
            # Remove fallback key from merged config to avoid recursion
            merged_config.pop("fallback", None)

            try:
                fallback_llm = self._create_llm(merged_config)
                fallback_provider = ResilientLLMProvider(
                    provider=fallback_llm,
                    circuit_breaker=CircuitBreaker(
                        failure_threshold=cb_config.get("failure_threshold", 5),
                        success_threshold=cb_config.get("success_threshold", 2),
                        timeout=cb_config.get("timeout", 60),
                        half_open_max_calls=cb_config.get("half_open_max_calls", 1)
                    ),
                    name=f"{fb_config.get('model_provider', 'fallback')}/{fb_config.get('model', 'unknown')}",
                    priority=fb_config.get("priority", 999)
                )
                fallbacks.append(fallback_provider)
            except Exception as e:
                logger.warning(
                    f"Failed to initialize fallback provider "
                    f"{fb_config.get('model_provider')}/{fb_config.get('model')}: {e}"
                )
                # Continue with other fallback providers

        # Sort fallbacks by priority
        fallbacks.sort(key=lambda x: x.priority)

        # Create and return the provider manager
        return LLMProviderManager(
            primary=primary,
            fallbacks=fallbacks,
            retry_config=fallback_config.get("retry", {}),
            health_check_config=fallback_config.get("health_check", {}),
            fallback_enabled=True
        )

    def get_state(self, key=None) -> dict:
        """ ""
        Get the final state of the graph.

        Args:
            key (str, optional): The key of the final state to retrieve.

        Returns:
            dict: The final state of the graph.
        """

        if key is not None:
            return self.final_state[key]
        return self.final_state

    def append_node(self, node):
        """
        Add a node to the graph.

        Args:
            node (BaseNode): The node to add to the graph.
        """

        self.graph.append_node(node)

    def get_execution_info(self):
        """
        Returns the execution information of the graph.

        Returns:
            dict: The execution information of the graph.
        """

        return self.execution_info

    @abstractmethod
    def _create_graph(self):
        """
        Abstract method to create a graph representation.
        """

    @abstractmethod
    def run(self) -> str:
        """
        Abstract method to execute the graph and return the result.
        """
        inputs = {"user_prompt": self.prompt, self.input_key: self.source}
        self.final_state, self.execution_info = self.graph.execute(inputs)
        result = self.final_state.get("answer", "No answer found.")
        return result

    async def run_safe_async(self) -> str:
        """
        Executes the run process asynchronously safety.

        Returns:
            str: The answer to the prompt.
        """

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run)
