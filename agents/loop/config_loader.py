"""Configuration loading for HexClamp agent loop.

Handles YAML config loading and executor enablement checks.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from agents.store import get_workspace_root, read_json

WORKSPACE_ROOT = get_workspace_root()
CONFIG_PATH = WORKSPACE_ROOT / "config.yaml"


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return config


def executor_enabled(executor_name: str) -> bool:
    """Check if a specific executor is enabled in config."""
    config = load_config()
    executors = config.get("executors", {})
    if isinstance(executors, dict):
        executor_config = executors.get(executor_name, {})
        if isinstance(executor_config, dict):
            return executor_config.get("enabled", True)
    return True


def get_executor_config(executor_name: str) -> Dict[str, Any]:
    """Get full configuration for a specific executor."""
    config = load_config()
    executors = config.get("executors", {})
    if isinstance(executors, dict):
        return executors.get(executor_name, {})
    return {}
