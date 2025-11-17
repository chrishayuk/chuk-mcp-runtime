# tests/server/test_config_loader_coverage.py
"""
Additional tests to improve config_loader coverage.
"""

import tempfile
from pathlib import Path

import yaml
from chuk_mcp_runtime.server.config_loader import load_config


def test_load_config_with_proxy_merge():
    """Test loading config with proxy section that needs merging."""
    # Create a temporary config file with proxy settings
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"proxy": {"enabled": True, "namespace": "custom"}, "server": {"type": "stdio"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        # Load the config - this should trigger the proxy merge logic
        loaded = load_config([config_path])

        # Verify proxy section is present and merged
        assert hasattr(loaded, "proxy")
        assert loaded.proxy.enabled is True
        assert loaded.proxy.namespace == "custom"

    finally:
        Path(config_path).unlink()


def test_load_config_with_openai_compatible_false():
    """Test config loading when openai_compatible is false."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"proxy": {"enabled": True, "openai_compatible": False}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        loaded = load_config([config_path])

        # Should set only_openai_tools to False when openai_compatible is False
        assert loaded.proxy.only_openai_tools is False

    finally:
        Path(config_path).unlink()


def test_load_config_deep_proxy_merge():
    """Test deep merging of proxy configuration."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {
            "proxy": {
                "enabled": True,
                "namespace": "proxy",
                "openai_compatible": True,
            },
            "server": {"type": "stdio"},
        }
        yaml.dump(config, f)
        config_path = f.name

    try:
        loaded = load_config([config_path])

        # All proxy settings should be merged
        assert loaded.proxy.enabled is True
        assert loaded.proxy.namespace == "proxy"
        assert loaded.proxy.openai_compatible is True
        # Note: custom_setting would be in extra fields if we allowed them
        # For now, extra fields are ignored in the Pydantic model

    finally:
        Path(config_path).unlink()


def test_load_config_no_proxy_section():
    """Test loading config without proxy section."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"server": {"type": "stdio"}, "tools": {}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        loaded = load_config([config_path])

        # Should still load successfully
        assert hasattr(loaded, "server")
        assert loaded.server.type.value == "stdio"

    finally:
        Path(config_path).unlink()
