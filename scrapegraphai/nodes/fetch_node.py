"""
FetchNode Module
"""

import json
import hashlib
from typing import List, Optional
import concurrent.futures

import requests
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from ..docloaders import ChromiumLoader
from ..utils.cleanup_html import cleanup_html
from ..utils.convert_to_md import convert_to_md
from .base_node import BaseNode


class FetchNode(BaseNode):
    """
    A node responsible for fetching the HTML content of a specified URL and updating
    the graph's state with this content. It uses ChromiumLoader to fetch
    the content from a web page asynchronously (with proxy protection).

    This node acts as a starting point in many scraping workflows, preparing the state
    with the necessary HTML content for further processing by subsequent nodes in the graph.

    Attributes:
        headless (bool): A flag indicating whether the browser should run in headless mode.
        verbose (bool): A flag indicating whether to print verbose output during execution.

    Args:
        input (str): Boolean expression defining the input keys needed from the state.
        output (List[str]): List of output keys to be updated in the state.
        node_config (Optional[dict]): Additional configuration for the node.
        node_name (str): The unique identifier name for the node, defaulting to "Fetch".
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "Fetch",
    ):
        super().__init__(node_name, "node", input, output, 1, node_config)

        self.headless = (
            True if node_config is None else node_config.get("headless", True)
        )
        self.verbose = (
            False if node_config is None else node_config.get("verbose", False)
        )
        self.use_soup = (
            False if node_config is None else node_config.get("use_soup", False)
        )
        self.loader_kwargs = (
            {} if node_config is None else node_config.get("loader_kwargs", {})
        )
        self.llm_model = {} if node_config is None else node_config.get("llm_model", {})
        self.force = False if node_config is None else node_config.get("force", False)
        self.script_creator = (
            False if node_config is None else node_config.get("script_creator", False)
        )
        self.openai_md_enabled = (
            False
            if node_config is None
            else node_config.get("openai_md_enabled", False)
        )

        # Timeout in seconds for blocking operations (HTTP requests, PDF parsing, etc.).
        # If set to None, no timeout will be applied.
        self.timeout = None if node_config is None else node_config.get("timeout", 30)

        self.cut = False if node_config is None else node_config.get("cut", True)

        self.browser_base = (
            None if node_config is None else node_config.get("browser_base", None)
        )

        self.scrape_do = (
            None if node_config is None else node_config.get("scrape_do", None)
        )

        self.storage_state = (
            None if node_config is None else node_config.get("storage_state", None)
        )

        # Incremental scraping configuration
        self.incremental_config = (
            None if node_config is None else node_config.get("incremental", None)
        )

        # Initialize cache if incremental scraping is enabled
        self.cache = None
        if self.incremental_config and self.incremental_config.get("enabled", False):
            self._init_incremental_cache()

    def _init_incremental_cache(self):
        """Initialize the cache backend for incremental scraping."""
        from ..utils.cache import get_cache

        backend = self.incremental_config.get("cache_backend", "sqlite")

        try:
            if backend == "sqlite":
                cache_path = self.incremental_config.get(
                    "cache_path", ".scrapegraph_cache/fingerprints.db"
                )
                self.cache = get_cache("sqlite", cache_path=cache_path)
            elif backend == "memory":
                self.cache = get_cache("memory")
            else:
                raise ValueError(f"Unsupported cache backend: {backend}")

            self.logger.info(f"Incremental scraping enabled with {backend} cache")
        except Exception as e:
            self.logger.error(f"Failed to initialize cache: {e}")
            self.cache = None

    def execute(self, state):
        """
        Executes the node's logic to fetch HTML content from a specified URL and
        update the state with this content.
        """
        self.logger.info(f"--- Executing {self.node_name} Node ---")

        input_keys = self.get_input_keys(state)
        input_data = [state[key] for key in input_keys]

        source = input_data[0]
        input_type = input_keys[0]

        handlers = {
            "json_dir": self.handle_directory,
            "xml_dir": self.handle_directory,
            "csv_dir": self.handle_directory,
            "pdf_dir": self.handle_directory,
            "md_dir": self.handle_directory,
            "pdf": self.handle_file,
            "csv": self.handle_file,
            "json": self.handle_file,
            "xml": self.handle_file,
            "md": self.handle_file,
        }

        if input_type in handlers:
            return handlers[input_type](state, input_type, source)
        elif input_type == "local_dir":
            return self.handle_local_source(state, source)
        elif input_type == "url":
            return self.handle_web_source(state, source)
        else:
            raise ValueError(f"Invalid input type: {input_type}")

    def handle_directory(self, state, input_type, source):
        """
        Handles the directory by compressing the source document and updating the state.

        Parameters:
        state (dict): The current state of the graph.
        input_type (str): The type of input being processed.
        source (str): The source document to be compressed.

        Returns:
        dict: The updated state with the compressed document.
        """

        compressed_document = [source]
        state.update({self.output[0]: compressed_document})
        return state

    def handle_file(self, state, input_type, source):
        """
        Loads the content of a file based on its input type.

        Parameters:
        state (dict): The current state of the graph.
        input_type (str): The type of the input file (e.g., "pdf", "csv", "json", "xml", "md").
        source (str): The path to the source file.

        Returns:
        dict: The updated state with the compressed document.

        The function supports the following input types:
        - "pdf": Uses PyPDFLoader to load the content of a PDF file.
        - "csv": Reads the content of a CSV file using pandas and converts it to a string.
        - "json": Loads the content of a JSON file.
        - "xml": Reads the content of an XML file as a string.
        - "md": Reads the content of a Markdown file as a string.
        """

        compressed_document = self.load_file_content(source, input_type)

        # return self.update_state(state, compressed_document)
        state.update({self.output[0]: compressed_document})
        return state

    def load_file_content(self, source, input_type):
        """
        Loads the content of a file based on its input type.

        Parameters:
        source (str): The path to the source file.
        input_type (str): The type of the input file (e.g., "pdf", "csv", "json", "xml", "md").

        Returns:
        list: A list containing a Document object with the loaded content and metadata.
        """

        if input_type == "pdf":
            loader = PyPDFLoader(source)
            # PyPDFLoader.load() can be blocking for large PDFs. Run it in a thread and
            # enforce the configured timeout if provided.
            if self.timeout is None:
                return loader.load()
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(loader.load)
                    try:
                        return future.result(timeout=self.timeout)
                    except concurrent.futures.TimeoutError:
                        raise TimeoutError(
                            f"PDF parsing exceeded timeout of {self.timeout} seconds"
                        )
        elif input_type == "csv":
            try:
                import pandas as pd
            except ImportError:
                raise ImportError(
                    "pandas is not installed. Please install it using `pip install pandas`."
                )
            return [
                Document(
                    page_content=str(pd.read_csv(source)), metadata={"source": "csv"}
                )
            ]
        elif input_type == "json":
            with open(source, encoding="utf-8") as f:
                return [
                    Document(
                        page_content=str(json.load(f)), metadata={"source": "json"}
                    )
                ]
        elif input_type == "xml" or input_type == "md":
            with open(source, "r", encoding="utf-8") as f:
                data = f.read()
            return [Document(page_content=data, metadata={"source": input_type})]

    def handle_local_source(self, state, source):
        """
        Handles the local source by fetching HTML content, optionally converting it to Markdown,
        and updating the state.

        Parameters:
        state (dict): The current state of the graph.
        source (str): The HTML content from the local source.

        Returns:
        dict: The updated state with the processed content.

        Raises:
        ValueError: If the source is empty or contains only whitespace.
        """

        self.logger.info(f"--- (Fetching HTML from: {source}) ---")
        if not source.strip():
            raise ValueError("No HTML body content found in the local source.")

        parsed_content = source

        if (
            (
                isinstance(self.llm_model, ChatOpenAI)
                or isinstance(self.llm_model, AzureChatOpenAI)
            )
            and not self.script_creator
            or self.force
            and not self.script_creator
        ):
            parsed_content = convert_to_md(source)
        else:
            parsed_content = source

        compressed_document = [
            Document(page_content=parsed_content, metadata={"source": "local_dir"})
        ]

        # return self.update_state(state, compressed_document)
        state.update({self.output[0]: compressed_document})
        return state

    def handle_web_source(self, state, source):
        """
        Handles the web source by fetching HTML content from a URL,
        optionally converting it to Markdown, and updating the state.

        Enhanced to support incremental scraping with content fingerprinting.

        Parameters:
        state (dict): The current state of the graph.
        source (str): The URL of the web source to fetch HTML content from.

        Returns:
        dict: The updated state with the processed content.

        Raises:
        ValueError: If the fetched HTML content is empty or contains only whitespace.
        """

        self.logger.info(f"--- (Fetching HTML from: {source}) ---")

        # Check if incremental scraping is enabled
        if self.cache is not None:
            return self._handle_web_source_incremental(state, source)

        # Fall back to standard non-incremental fetch
        return self._handle_web_source_full(state, source)

    def _handle_web_source_full(self, state, source):
        """
        Original non-incremental web source handling.

        Parameters:
        state (dict): The current state of the graph.
        source (str): The URL of the web source to fetch HTML content from.

        Returns:
        dict: The updated state with the processed content.
        """
        if self.use_soup:
            # Apply configured timeout to blocking HTTP requests. If timeout is None,
            # don't pass the timeout argument (requests will block until completion).
            if self.timeout is None:
                response = requests.get(source)
            else:
                response = requests.get(source, timeout=self.timeout)
            if response.status_code == 200:
                if not response.text.strip():
                    raise ValueError("No HTML body content found in the response.")

                if not self.cut:
                    parsed_content = cleanup_html(response, source)

                if (
                    isinstance(self.llm_model, (ChatOpenAI, AzureChatOpenAI))
                    and not self.script_creator
                    or (self.force and not self.script_creator)
                ):
                    parsed_content = convert_to_md(source, parsed_content)

                compressed_document = [Document(page_content=parsed_content)]
            else:
                self.logger.warning(
                    f"Failed to retrieve contents from the webpage at url: {source}"
                )
        else:
            loader_kwargs = {}

            if self.node_config:
                loader_kwargs = self.node_config.get("loader_kwargs", {})

            # If a global timeout is configured on the node and no loader-specific timeout
            # was provided, propagate it to ChromiumLoader so it can apply the same limit.
            if "timeout" not in loader_kwargs and self.timeout is not None:
                loader_kwargs["timeout"] = self.timeout

            if self.browser_base:
                try:
                    from ..docloaders.browser_base import browser_base_fetch
                except ImportError:
                    raise ImportError(
                        """The browserbase module is not installed.
                                      Please install it using `pip install browserbase`."""
                    )

                data = browser_base_fetch(
                    self.browser_base.get("api_key"),
                    self.browser_base.get("project_id"),
                    [source],
                )

                document = [
                    Document(page_content=content, metadata={"source": source})
                    for content in data
                ]
            elif self.scrape_do:
                from ..docloaders.scrape_do import scrape_do_fetch

                if (
                    (self.scrape_do.get("use_proxy") is None)
                    or self.scrape_do.get("geoCode") is None
                    or self.scrape_do.get("super_proxy") is None
                ):
                    data = scrape_do_fetch(self.scrape_do.get("api_key"), source)
                else:
                    data = scrape_do_fetch(
                        self.scrape_do.get("api_key"),
                        source,
                        self.scrape_do.get("use_proxy"),
                        self.scrape_do.get("geoCode"),
                        self.scrape_do.get("super_proxy"),
                    )

                document = [Document(page_content=data, metadata={"source": source})]
            else:
                loader = ChromiumLoader(
                    [source],
                    headless=self.headless,
                    storage_state=self.storage_state,
                    **loader_kwargs,
                )
                document = loader.load()

            if not document or not document[0].page_content.strip():
                raise ValueError(
                    """No HTML body content found in
                                 the document fetched by ChromiumLoader."""
                )

            parsed_content = document[0].page_content

            if (
                (
                    isinstance(self.llm_model, ChatOpenAI)
                    or isinstance(self.llm_model, AzureChatOpenAI)
                )
                and not self.script_creator
                or self.force
                and not self.script_creator
                and not self.openai_md_enabled
            ):
                parsed_content = convert_to_md(document[0].page_content, parsed_content)

            compressed_document = [
                Document(page_content=parsed_content, metadata={"source": "html file"})
            ]
        state["doc"] = document
        state.update(
            {
                self.output[0]: compressed_document,
            }
        )
        return state

    def _handle_web_source_incremental(self, state, source):
        """
        Fetch web content with incremental scraping and fingerprinting.

        This method implements content-based change detection using
        cryptographic hashing to determine if content has changed.

        Parameters:
        state (dict): The current state of the graph.
        source (str): The URL of the web source to fetch HTML content from.

        Returns:
        dict: The updated state with the processed content.
        """
        # Step 1: Quick check using HTTP headers (ETag, Last-Modified)
        if self.incremental_config.get("use_http_headers", True):
            if not self._has_server_side_changes(source):
                cached_content = self.cache.get_content(source)
                if cached_content:
                    self.logger.info("--- Using cached content (no HTTP header changes detected) ---")
                    return self._prepare_cached_response(state, source, cached_content)

        # Step 2: Check if cached entry exists and is not expired
        max_age = self.incremental_config.get("max_age", 0)
        if max_age > 0 and self.cache.is_expired(source, max_age):
            self.logger.info(f"--- Cached entry expired (max_age: {max_age}s) ---")
        else:
            # Check if we have a recent check
            cached_entry = self.cache.get(source)
            if cached_entry and self.incremental_config.get("cache_content", True):
                # We have a recent entry, but need to verify content hasn't changed
                # Fetch and compare fingerprints
                pass  # Will fetch and compare below

        # Step 3: Fetch content using standard method
        try:
            document = self._fetch_document(source)
            if not document or not document[0].page_content.strip():
                raise ValueError("No HTML body content found in the document.")

            content = document[0].page_content

            # Step 4: Normalize content for fingerprinting
            normalized_content = self._normalize_content(content)

            # Step 5: Generate fingerprint
            fingerprint = self._generate_fingerprint(normalized_content)

            # Step 6: Compare with cached fingerprint
            cached_entry = self.cache.get(source)
            if cached_entry and cached_entry["fingerprint"] == fingerprint:
                self.logger.info("--- Content unchanged (fingerprint match) ---")
                self.cache.update_last_checked(source)

                # Return cached processed content if available
                if self.incremental_config.get("cache_content", True):
                    cached_content = self.cache.get_content(source)
                    if cached_content:
                        return self._prepare_cached_response(state, source, cached_content)

            # Step 7: Content has changed or is new - process normally
            self.logger.info("--- Content changed or new - processing ---")

            # Process content (convert to markdown if needed)
            parsed_content = self._process_document(document)

            # Step 8: Update cache
            metadata = {
                "size": len(content),
                "content_type": document[0].metadata.get("content_type", "text/html"),
            }

            # Extract ETag from response if available
            if hasattr(document[0], "metadata") and "etag" in document[0].metadata:
                metadata["etag"] = document[0].metadata["etag"]

            self.cache.set(
                url=source,
                fingerprint=fingerprint,
                content=parsed_content if self.incremental_config.get("cache_content", True) else None,
                metadata=metadata
            )

            # Step 9: Return updated state
            compressed_document = [
                Document(page_content=parsed_content, metadata={"source": "html file"})
            ]
            state["doc"] = document
            state.update({self.output[0]: compressed_document})
            return state

        except Exception as e:
            self.logger.error(f"Error in incremental fetch: {e}")
            # Fall back to non-incremental if there's an error
            return self._handle_web_source_full(state, source)

    def _fetch_document(self, source):
        """
        Fetch document from source URL.

        Parameters:
        source (str): The URL to fetch from

        Returns:
        list: List of Document objects
        """
        if self.use_soup:
            if self.timeout is None:
                response = requests.get(source)
            else:
                response = requests.get(source, timeout=self.timeout)

            if response.status_code == 200:
                if not response.text.strip():
                    raise ValueError("No HTML body content found in the response.")

                parsed_content = response.text
                if not self.cut:
                    parsed_content = cleanup_html(response, source)

                return [Document(page_content=parsed_content, metadata={"source": source})]
            else:
                raise ValueError(f"Failed to retrieve contents from the webpage at url: {source}")
        else:
            loader_kwargs = self.node_config.get("loader_kwargs", {}) if self.node_config else {}

            if "timeout" not in loader_kwargs and self.timeout is not None:
                loader_kwargs["timeout"] = self.timeout

            if self.browser_base:
                try:
                    from ..docloaders.browser_base import browser_base_fetch
                except ImportError:
                    raise ImportError(
                        "The browserbase module is not installed. "
                        "Please install it using `pip install browserbase`."
                    )

                data = browser_base_fetch(
                    self.browser_base.get("api_key"),
                    self.browser_base.get("project_id"),
                    [source],
                )

                return [
                    Document(page_content=content, metadata={"source": source})
                    for content in data
                ]
            elif self.scrape_do:
                from ..docloaders.scrape_do import scrape_do_fetch

                if (
                    (self.scrape_do.get("use_proxy") is None)
                    or self.scrape_do.get("geoCode") is None
                    or self.scrape_do.get("super_proxy") is None
                ):
                    data = scrape_do_fetch(self.scrape_do.get("api_key"), source)
                else:
                    data = scrape_do_fetch(
                        self.scrape_do.get("api_key"),
                        source,
                        self.scrape_do.get("use_proxy"),
                        self.scrape_do.get("geoCode"),
                        self.scrape_do.get("super_proxy"),
                    )

                return [Document(page_content=data, metadata={"source": source})]
            else:
                loader = ChromiumLoader(
                    [source],
                    headless=self.headless,
                    storage_state=self.storage_state,
                    **loader_kwargs,
                )
                return loader.load()

    def _process_document(self, document):
        """
        Process document content (convert to markdown if needed).

        Parameters:
        document (list): List of Document objects

        Returns:
        str: Processed content
        """
        parsed_content = document[0].page_content

        if (
            (
                isinstance(self.llm_model, ChatOpenAI)
                or isinstance(self.llm_model, AzureChatOpenAI)
            )
            and not self.script_creator
            or self.force
            and not self.script_creator
            and not self.openai_md_enabled
        ):
            parsed_content = convert_to_md(document[0].page_content, parsed_content)

        return parsed_content

    def _has_server_side_changes(self, url: str) -> bool:
        """
        Quick check using HTTP headers (ETag, Last-Modified).

        This performs a lightweight HEAD request to check if the server
        indicates content has changed, avoiding a full content fetch.

        Parameters:
        url (str): The URL to check

        Returns:
        bool: True if content might have changed, False if unchanged
        """
        try:
            cached_entry = self.cache.get(url)
            if not cached_entry:
                return True

            # HEAD request with timeout
            timeout = self.timeout if self.timeout else 10
            response = requests.head(url, timeout=timeout, allow_redirects=True)

            # Check ETag
            if "ETag" in response.headers:
                cached_etag = cached_entry.get("etag")
                if cached_etag and response.headers["ETag"] == cached_etag:
                    return False

            # Check Last-Modified
            if "Last-Modified" in response.headers:
                from email.utils import parsedate_to_datetime
                from datetime import datetime

                try:
                    last_modified = parsedate_to_datetime(response.headers["Last-Modified"])
                    cached_modified = cached_entry.get("last_modified")

                    if cached_modified:
                        cached_dt = datetime.fromisoformat(cached_modified)
                        if last_modified <= cached_dt:
                            return False
                except Exception:
                    pass

            return True
        except Exception as e:
            self.logger.warning(f"Error checking HTTP headers: {e}")
            return True  # Assume changed if check fails

    def _normalize_content(self, content: str) -> str:
        """
        Normalize content to reduce false positives from non-meaningful changes.

        Parameters:
        content (str): Raw HTML content

        Returns:
        str: Normalized content
        """
        strategy = self.incremental_config.get("normalization", "normalized")

        if strategy == "full":
            return content

        if strategy == "custom":
            normalize_fn = self.incremental_config.get("normalize_fn")
            if normalize_fn:
                return normalize_fn(content)

        # Default normalized strategy
        from ..utils.content_normalizer import normalize_html
        return normalize_html(content, aggressive=False)

    def _generate_fingerprint(self, content: str) -> str:
        """
        Generate cryptographic hash fingerprint of content.

        Parameters:
        content (str): Normalized content

        Returns:
        str: Hexadecimal hash string
        """
        algorithm = self.incremental_config.get("hash_algorithm", "sha256")

        if algorithm == "sha256":
            return hashlib.sha256(content.encode('utf-8')).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(content.encode('utf-8')).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    def _prepare_cached_response(self, state, source, cached_content):
        """
        Prepare response using cached content.

        Parameters:
        state (dict): The current state
        source (str): The source URL
        cached_content (str): Cached content

        Returns:
        dict: Updated state with cached content
        """
        document = [Document(page_content=cached_content, metadata={"source": source, "from_cache": True})]

        compressed_document = [
            Document(page_content=cached_content, metadata={"source": "html file", "from_cache": True})
        ]

        state["doc"] = document
        state["from_cache"] = True
        state.update({self.output[0]: compressed_document})
        return state
