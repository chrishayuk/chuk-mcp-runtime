# chuk_mcp_runtime/server/config_loader.py
"""
Configuration Loader Module

This module provides functionality to load and manage
configuration files for CHUK MCP servers from multiple potential locations.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

import yaml

# Configure logger to log to stderr
logger = logging.getLogger("chuk_mcp_runtime.config")

# Create a StreamHandler that logs to stderr
stderr_handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)


def load_config(config_paths=None, default_config=None):
    if default_config is None:
        default_config = {
            "host": {"name": "generic-mcp-server", "log_level": "INFO"},
            "server": {"type": "stdio"},
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "reset_handlers": True,
                "quiet_libraries": True,
            },
            "tools": {
                "registry_module": "chuk_mcp_runtime.common.mcp_tool_decorator",
                "registry_attr": "TOOLS_REGISTRY",
            },
            "proxy": {
                "enabled": False,
                "namespace": "proxy",
                "keep_root_aliases": False,
                "openai_compatible": False,
                "only_openai_tools": False,
            },
            "mcp_servers": {},
        }

    # If no explicit config_paths provided, look in common locations.
    if config_paths is None:
        config_paths = [
            os.path.join(os.getcwd(), "config.yaml"),
            os.path.join(os.getcwd(), "config.yml"),
            os.environ.get("CHUK_MCP_CONFIG_PATH", ""),
        ]
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_paths.append(os.path.join(package_dir, "config.yaml"))

    config_paths = [p for p in config_paths if p]

    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    file_config = yaml.safe_load(f) or {}

                    # Deep merge of proxy section (if it exists in both)
                    if "proxy" in file_config and "proxy" in default_config:
                        for key, value in file_config["proxy"].items():
                            default_config["proxy"][key] = value
                        # Remove from file_config to avoid duplication
                        del file_config["proxy"]

                    # Now do the regular update for the rest of the config
                    default_config.update(file_config)

                    # Ensure only_openai_tools is false if openai_compatible is false
                    if not default_config.get("proxy", {}).get("openai_compatible", False):
                        default_config["proxy"]["only_openai_tools"] = False

                    return default_config
            except Exception as e:
                # Log warning but continue trying
                logger.warning(f"Error loading config from {path}: {e}")

    return default_config


def find_project_root(start_dir: Optional[str] = None) -> str:
    """
    Find the project root directory by looking for markers like config.yaml,
    pyproject.toml, etc.

    Args:
        start_dir: Directory to start the search from. If None, uses current directory.

    Returns:
        Absolute path to the project root directory.
    """
    if start_dir is None:
        start_dir = os.getcwd()

    current_dir = os.path.abspath(start_dir)

    # Markers that indicate a project root
    markers = ["config.yaml", "config.yml", "pyproject.toml", "setup.py"]

    # Maximum depth to search up
    max_depth = 10
    depth = 0

    while depth < max_depth:
        # Check if any markers exist in current directory
        if any(os.path.exists(os.path.join(current_dir, marker)) for marker in markers):
            return current_dir

        # Go up one directory
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # Reached the filesystem root
            break

        current_dir = parent_dir
        depth += 1

    # If no project root found, log a warning and return the starting directory
    logger.warning(f"No project root markers found, using {start_dir} as project root")
    return os.path.abspath(start_dir)


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Get a value from a nested configuration dictionary using a dot-separated path.

    Args:
        config: Configuration dictionary.
        path: Dot-separated path to the value (e.g., "host.name").
        default: Default value to return if the path is not found.

    Returns:
        The value at the specified path, or the default value if not found.
    """
    keys = path.split(".")
    result = config

    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default

    return result
