import os

import pytest

from chuk_mcp_runtime.server.server_registry import ServerRegistry


@pytest.fixture
def dummy_config(tmp_path):
    # Create a dummy configuration with core and mcp_servers entries
    config = {
        "core": {"core_path": "core_dir"},
        "mcp_servers": {
            "server1": {
                "enabled": True,
                "location": "server1_dir",
                "tools": {"enabled": True, "module": "server1.tools"},
                "resources": {},
                "prompts": {},
            }
        },
        "auto_discover": False,
    }
    # Create dummy directories for core and server
    project_root = str(tmp_path)
    os.mkdir(os.path.join(project_root, "core_dir"))
    os.mkdir(os.path.join(project_root, "server1_dir"))

    return project_root, config


def test_server_registry_setup(dummy_config):
    project_root, config = dummy_config
    registry = ServerRegistry(project_root, config)

    # Check that both the core and server paths are in the registry
    assert "core_path" in registry.server_paths
    assert "server1" in registry.server_paths

    # Verify that components for server1 include at least the tools component
    assert "server1" in registry.components
    server1_components = registry.components["server1"]
    assert any(comp["type"] == "tools" for comp in server1_components)
