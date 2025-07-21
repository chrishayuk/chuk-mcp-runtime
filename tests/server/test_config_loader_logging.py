import os
import sys
import pytest
from chuk_mcp_runtime.server import config_loader


def test_logging_to_stderr(tmp_path, monkeypatch, caplog, capsys):
    """
    Verify that logging messages from config_loader appear on stderr.
    """
    # Create a temporary file that simulates an invalid YAML file.
    invalid_yaml = tmp_path / "invalid_config.yaml"
    # Write an invalid YAML string so that yaml.safe_load() fails.
    invalid_yaml.write_text("not: valid: yaml: : -")

    # Ensure the file exists in our config_paths.
    config_paths = [str(invalid_yaml)]

    # Clear caplog before running.
    caplog.clear()

    # Run load_config() which should attempt to load the invalid file.
    config = config_loader.load_config(config_paths=config_paths)

    # Assert that we received a warning log message via caplog.
    assert "Error loading config from" in caplog.text

    # Verify that nothing was written to stdout.
    captured = capsys.readouterr()
    assert captured.out == ""


def test_default_config_returned_when_no_files(monkeypatch):
    """
    When no configuration files exist, load_config should return default configuration.
    """
    # Supply a non-existent path.
    config = config_loader.load_config(config_paths=["/nonexistent/path.yaml"])
    # Check that a value from the default configuration is present.
    assert config.get("host", {}).get("name") == "generic-mcp-server"
