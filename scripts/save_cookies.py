"""Manual login helper script for capturing NotebookLM authentication cookies."""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
from typing import Optional

from playwright.async_api import async_playwright

from app.config import load_config


async def capture_cookies(output_path: pathlib.Path, config_path: Optional[str] = None, slow_mo: int = 0) -> None:
    config = load_config(config_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=slow_mo)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(config.base_url)

        print(
            "\nPlease complete the NotebookLM login flow in the opened browser window."
            "\nWhen the application has fully loaded, return to this terminal and press ENTER."
        )
        input("Press ENTER once you are logged in...")

        cookies = await context.cookies()

        output_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        print(f"Saved {len(cookies)} cookies to {output_path}")

        await context.close()
        await browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save NotebookLM auth cookies to disk")
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("cookies.json"),
        help="Destination file for serialized cookies (default: cookies.json)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional path to config.json with selectors and base URL.",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=0,
        help="Optional slow motion delay in milliseconds for Playwright (useful for debugging).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(capture_cookies(args.output, args.config, args.slow_mo))


if __name__ == "__main__":
    main()
