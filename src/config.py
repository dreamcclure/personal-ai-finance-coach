"""Central configuration loader.

Reads settings from config.yaml and secrets from .env so that paths, seeds, the
target user, and API credentials live in one place — never hard-coded in logic.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Project root = the folder that contains this src/ directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_config(config_path: str | Path | None = None) -> dict:
    """Load config.yaml + .env into one dict with absolute paths resolved."""
    cfg_path = Path(config_path) if config_path else PROJECT_ROOT / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Resolve every path relative to the project root -> absolute.
    cfg["paths"] = {k: PROJECT_ROOT / v for k, v in cfg["paths"].items()}
    cfg["buckets_file"] = PROJECT_ROOT / cfg["buckets_file"]

    # Load secrets from .env (if present) into a tidy sub-dict.
    load_dotenv(PROJECT_ROOT / ".env")
    cfg["llm"] = {
        "provider": os.getenv("LLM_PROVIDER"),
        "api_key": os.getenv("LLM_API_KEY"),
        "model": os.getenv("LLM_MODEL"),
        "base_url": os.getenv("LLM_BASE_URL"),  # gateway endpoint (e.g. Great Learning proxy)
    }
    return cfg
