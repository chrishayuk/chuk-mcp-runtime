import os

import yaml
from chuk_mcp_runtime.server.config_loader import (
    find_project_root,
    get_config_value,
    load_config,
)


def test_load_config_default(tmp_path):
    # Create a temporary config file
    config_content = {
        "host": {"name": "test-server", "log_level": "DEBUG"},
        "mcp_servers": {},
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    # Change working directory to tmp_path
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        config = load_config()
        assert config.host.name == "test-server"
    finally:
        os.chdir(original_cwd)


def test_find_project_root(tmp_path):
    # Create a temporary project structure with a marker file (config.yaml)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    marker_file = project_dir / "config.yaml"
    marker_file.write_text("host: {name: test}")

    # Create a subdirectory inside the project
    sub_dir = project_dir / "subdir"
    sub_dir.mkdir()

    project_root = find_project_root(str(sub_dir))
    assert project_root == str(project_dir)


def test_get_config_value():
    from chuk_mcp_runtime.types import RuntimeConfig

    config = RuntimeConfig()
    # Test accessing existing values
    value = get_config_value(config, "host.name")
    assert value == "generic-mcp-server"

    # Verify that a missing key returns the default value
    assert get_config_value(config, "nonexistent.path", default="not found") == "not found"
