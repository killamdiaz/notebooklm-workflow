"""FastAPI service exposing the NotebookLM automation workflow."""

from __future__ import annotations

import logging
import os
import pathlib
import tempfile
from typing import Any, Awaitable, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, BaseSettings

from .config import SelectorConfig, load_config
from .notebooklm_client import NotebookLMClient, NotebookLMError

LOGGER = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings configurable via environment variables."""

    config_path: pathlib.Path | None = None
    cookies_path: pathlib.Path = pathlib.Path("cookies.json")
    headless: bool = True

    class Config:
        env_prefix = "NOTEBOOKLM_"
        case_sensitive = False


settings = Settings()
app = FastAPI(title="NotebookLM Workflow Service", version="0.1.0")


@app.on_event("startup")
async def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)


def _load_selector_config() -> SelectorConfig:
    config_path = settings.config_path
    return load_config(config_path) if config_path else load_config()


class QueryPayload(BaseModel):
    query: str


async def _run_notebooklm_action(
    action: str,
    coroutine: Awaitable[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        return await coroutine
    except NotebookLMError as exc:
        LOGGER.exception("NotebookLM workflow failed during %s", action)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a document to NotebookLM using the automation client."""

    selector_config = _load_selector_config()
    cookies_path = settings.cookies_path

    suffix = pathlib.Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = pathlib.Path(tmp.name)

    try:
        async with NotebookLMClient(selector_config, cookies_path, headless=settings.headless) as client:
            result = await _run_notebooklm_action(
                "upload",
                client.upload_document(tmp_path),
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            LOGGER.warning("Unable to remove temporary file %s", tmp_path)

    return {"status": "success", "details": result}


@app.post("/query")
async def query_notebooklm(payload: QueryPayload) -> Dict[str, Any]:
    """Submit a query to NotebookLM and return the AI response."""

    selector_config = _load_selector_config()
    cookies_path = settings.cookies_path

    try:
        async with NotebookLMClient(selector_config, cookies_path, headless=settings.headless) as client:
            response = await _run_notebooklm_action(
                "query",
                client.query(payload.query),
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return response


__all__ = ["app"]
