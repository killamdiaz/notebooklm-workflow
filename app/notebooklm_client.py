"""Async client for automating Google NotebookLM via Playwright."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Error, Page, async_playwright

from .config import SelectorConfig

LOGGER = logging.getLogger(__name__)


class NotebookLMError(RuntimeError):
    """Raised when the automation workflow cannot complete successfully."""


class NotebookLMClient:
    """High-level automation wrapper around the NotebookLM web UI."""

    def __init__(
        self,
        config: SelectorConfig,
        cookies_path: str | pathlib.Path,
        headless: bool = True,
        navigation_timeout: Optional[int] = None,
    ) -> None:
        self._config = config
        self._cookies_path = pathlib.Path(cookies_path)
        self._headless = headless
        self._navigation_timeout = navigation_timeout or config.timeouts.get("page_load", 30000)
        self._playwright_cm = async_playwright()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "NotebookLMClient":
        self._playwright = await self._playwright_cm.__aenter__()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context()
        await self._load_cookies()
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self._navigation_timeout)
        await self._page.goto(self._config.base_url)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self._cleanup()

    async def _cleanup(self) -> None:
        try:
            if self._context:
                await self._context.close()
        finally:
            if self._browser:
                await self._browser.close()
            await self._playwright_cm.__aexit__(None, None, None)

    async def _load_cookies(self) -> None:
        if not self._cookies_path.exists():
            raise FileNotFoundError(
                f"Cookie file not found at {self._cookies_path}. Run the save_cookies script first."
            )

        with self._cookies_path.open("r", encoding="utf-8") as fh:
            cookies = json.load(fh)

        if not isinstance(cookies, list):
            raise NotebookLMError("Cookies file must contain a list of serialized cookies")

        if not self._context:
            raise NotebookLMError("Browser context is not initialized")

        await self._context.add_cookies(cookies)

    # ------------------------------------------------------------------
    # Upload flow
    # ------------------------------------------------------------------
    async def upload_document(self, file_path: str | pathlib.Path) -> Dict[str, Any]:
        """Upload a document and wait until NotebookLM finishes processing it."""

        if not self._page:
            raise NotebookLMError("Client is not initialized. Use as an async context manager.")

        file_path = str(pathlib.Path(file_path).resolve())
        upload_cfg = self._config.upload
        add_button_selector = upload_cfg.get("add_source_button")
        file_input_selector = upload_cfg.get("file_input")

        if not add_button_selector or not file_input_selector:
            raise NotebookLMError("Upload selectors are missing from the configuration file.")

        LOGGER.debug("Navigating to NotebookLM base URL: %s", self._config.base_url)
        await self._page.goto(self._config.base_url)

        LOGGER.debug("Clicking the add source button (%s)", add_button_selector)
        await self._page.click(add_button_selector)

        file_input = self._page.locator(file_input_selector)
        if not await file_input.is_visible():
            LOGGER.debug("File input not visible, forcing state by setting input")

        LOGGER.info("Uploading file %s", file_path)
        await file_input.set_input_files(file_path)

        processed_selector = upload_cfg.get("processed_marker")
        processing_indicator = upload_cfg.get("processing_indicator")
        processing_timeout = self._config.timeouts.get("processing", 180000)

        if processed_selector:
            LOGGER.debug("Waiting for processed marker (%s)", processed_selector)
            await self._page.wait_for_selector(
                processed_selector,
                state="visible",
                timeout=processing_timeout,
            )
        elif processing_indicator:
            LOGGER.debug("Waiting for processing indicator (%s) to disappear", processing_indicator)
            await self._page.wait_for_selector(
                processing_indicator,
                state="hidden",
                timeout=processing_timeout,
            )
        else:
            LOGGER.warning(
                "No processing selector configured; applying fixed delay as a fallback."
            )
            await asyncio.sleep(processing_timeout / 1000)

        return {"file_path": file_path, "status": "processed"}

    # ------------------------------------------------------------------
    # Query flow
    # ------------------------------------------------------------------
    async def query(self, query: str) -> Dict[str, Any]:
        """Submit a query and return the structured response."""

        if not self._page:
            raise NotebookLMError("Client is not initialized. Use as an async context manager.")

        query_cfg = self._config.query
        prompt_selector = query_cfg.get("prompt_input")
        submit_selector = query_cfg.get("submit_button")
        response_selector = query_cfg.get("response_container")

        if not prompt_selector or not response_selector:
            raise NotebookLMError("Query selectors are missing from the configuration file.")

        LOGGER.debug("Focusing prompt input (%s)", prompt_selector)
        prompt_input = self._page.locator(prompt_selector)
        await prompt_input.click()
        await prompt_input.fill(query)

        if submit_selector:
            LOGGER.debug("Submitting prompt via button (%s)", submit_selector)
            await self._page.click(submit_selector)
        else:
            LOGGER.debug("Submitting prompt via Enter key")
            await prompt_input.press("Enter")

        response_timeout = self._config.timeouts.get("response", 120000)
        LOGGER.debug("Waiting for response container (%s)", response_selector)
        await self._page.wait_for_selector(response_selector, state="visible", timeout=response_timeout)

        response_locator = self._page.locator(response_selector).first
        answer_text = (await response_locator.inner_text()).strip()

        citations: List[str] = []
        citation_selector = query_cfg.get("citation_selector")
        if citation_selector:
            LOGGER.debug("Collecting citations using selector %s", citation_selector)
            try:
                citation_locators = self._page.locator(citation_selector)
                count = await citation_locators.count()
                for idx in range(count):
                    text = await citation_locators.nth(idx).inner_text()
                    text = text.strip()
                    if text:
                        citations.append(text)
            except Error as exc:  # pragma: no cover - depends on runtime DOM structure
                LOGGER.warning("Failed to extract citations: %s", exc)

        return {"query": query, "answer": answer_text, "citations": citations}


@asynccontextmanager
async def notebooklm_client(
    config: SelectorConfig,
    cookies_path: str | pathlib.Path,
    headless: bool = True,
    navigation_timeout: Optional[int] = None,
):
    """Context manager yielding a :class:`NotebookLMClient`."""

    client = NotebookLMClient(config, cookies_path, headless=headless, navigation_timeout=navigation_timeout)
    try:
        await client.__aenter__()
        yield client
    finally:
        await client.__aexit__(None, None, None)


__all__ = [
    "NotebookLMClient",
    "NotebookLMError",
    "notebooklm_client",
]
