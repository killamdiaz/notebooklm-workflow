"""Utilities for loading configuration values used by the NotebookLM workflow service."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any, Dict


DEFAULT_CONFIG_PATH = pathlib.Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class SelectorConfig:
    """Configuration values for interacting with NotebookLM via Playwright."""

    base_url: str
    upload: Dict[str, str]
    query: Dict[str, str]
    timeouts: Dict[str, int]


def load_config(path: pathlib.Path | str | None = None) -> SelectorConfig:
    """Load configuration for the automation layer.

    Parameters
    ----------
    path:
        Optional path to a JSON configuration file. If not provided the default
        ``config.json`` at the repository root is used.
    """

    config_path = pathlib.Path(path or DEFAULT_CONFIG_PATH)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fp:
        data: Dict[str, Any] = json.load(fp)

    notebooklm_cfg = data.get("notebooklm")
    if not notebooklm_cfg:
        raise KeyError("Missing 'notebooklm' section in configuration file")

    return SelectorConfig(
        base_url=notebooklm_cfg["base_url"],
        upload=notebooklm_cfg.get("upload", {}),
        query=notebooklm_cfg.get("query", {}),
        timeouts=notebooklm_cfg.get("timeouts", {}),
    )


__all__ = ["SelectorConfig", "load_config"]
