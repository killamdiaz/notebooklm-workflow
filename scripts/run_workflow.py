"""Script demonstrating how to automate NotebookLM using saved cookies."""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
from typing import Any, Dict, Optional

from app.config import load_config
from app.notebooklm_client import NotebookLMClient


async def run_workflow(
    cookies_path: pathlib.Path,
    config_path: Optional[str],
    upload_path: Optional[pathlib.Path],
    query_text: Optional[str],
    headless: bool,
) -> Dict[str, Any]:
    config = load_config(config_path)
    results: Dict[str, Any] = {}

    async with NotebookLMClient(config, cookies_path, headless=headless) as client:
        if upload_path:
            results["upload"] = await client.upload_document(upload_path)
        if query_text:
            results["query"] = await client.query(query_text)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NotebookLM automation using stored cookies")
    parser.add_argument(
        "--cookies",
        type=pathlib.Path,
        default=pathlib.Path("cookies.json"),
        help="Path to cookies.json captured via scripts/save_cookies.py",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to config.json",
    )
    parser.add_argument(
        "--upload",
        type=pathlib.Path,
        default=None,
        help="Optional path to a document that should be uploaded",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional query to submit after the upload step",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Playwright in headless mode (default: headed)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = asyncio.run(
        run_workflow(args.cookies, args.config, args.upload, args.query, args.headless)
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
