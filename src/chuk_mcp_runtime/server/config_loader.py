# chuk_mcp_runtime/server/config_loader.py
"""
Configuration Loader Module

Pydantic-based configuration loading for type safety and validation.
Supports YAML files and dict-based configuration.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from pydantic import ValidationError

from chuk_mcp_runtime.types import RuntimeConfig

# Configure logger to log to stderr
logger = logging.getLogger("chuk_mcp_runtime.config")

# Create a StreamHandler that logs to stderr
stderr_handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)


def load_config(
    config_paths: Optional[list[Union[str, Path]]] = None,
    default_config: Optional[RuntimeConfig] = None,
) -> RuntimeConfig:
    """
    Load configuration from YAML files.

    Args:
        config_paths: List of paths to search for config files
        default_config: Default configuration (RuntimeConfig)

    Returns:
        RuntimeConfig: Validated Pydantic model

    Raises:
        ValidationError: If configuration is invalid
    """
    # Create default config if not provided
    if default_config is None:
        default_config = RuntimeConfig()

    # If no explicit config_paths provided, look in common locations
    if config_paths is None:
        config_paths = [
            Path.cwd() / "config.yaml",
            Path.cwd() / "config.yml",
            Path(os.environ.get("CHUK_MCP_CONFIG_PATH", "")),
        ]
        package_dir = Path(__file__).parent.parent
        config_paths.append(package_dir / "config.yaml")

    # Filter out empty paths
    config_paths = [Path(p) for p in config_paths if p]

    # Try loading from each path
    for path_item in config_paths:
        path = Path(path_item)
        if not path.exists():
            continue

        try:
            with open(path, "r") as f:
                file_config = yaml.safe_load(f) or {}

            # Merge file config with defaults
            merged_dict = default_config.to_dict()
            _deep_merge(merged_dict, file_config)

            # Validate and return
            config = RuntimeConfig.from_dict(merged_dict)
            logger.debug(f"Loaded configuration from {path}")
            return config

        except ValidationError as e:
            logger.error(f"Invalid configuration in {path}: {e}")
            raise
        except Exception as e:
            logger.warning(f"Error loading config from {path}: {e}")
            continue

    # No file loaded, return default
    logger.debug("Using default configuration")
    return default_config


def _deep_merge(base: dict, override: dict) -> None:
    """
    Deep merge override dict into base dict (in-place).

    Args:
        base: Base dictionary to merge into
        override: Dictionary with values to override
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


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


def get_config_value(config: RuntimeConfig, path: str, default: Any = None) -> Any:
    """
    Get a value from configuration using a dot-separated path.

    Args:
        config: Configuration (RuntimeConfig)
        path: Dot-separated path to the value (e.g., "host.name")
        default: Default value to return if the path is not found

    Returns:
        The value at the specified path, or the default value if not found

    Examples:
        >>> config = RuntimeConfig()
        >>> get_config_value(config, "host.name")
        'generic-mcp-server'
        >>> get_config_value(config, "server.type")
        <ServerType.STDIO: 'stdio'>
    """
    # Navigate through the Pydantic model using getattr
    keys = path.split(".")
    result: Any = config

    for key in keys:
        try:
            result = getattr(result, key)
        except AttributeError:
            return default

    return result
