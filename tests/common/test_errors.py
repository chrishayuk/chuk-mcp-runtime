import pytest
from chuk_mcp_runtime.common.errors import (
    ChukMcpRuntimeError,
    ConfigurationError,
    ImportError as ChukImportError,
    ToolExecutionError,
    ServerError,
    ValidationError,
)


def test_chuk_mcp_runtime_error_message():
    msg = "Test error message"
    error = ChukMcpRuntimeError(msg)
    assert error.message == msg


def test_configuration_error():
    with pytest.raises(ConfigurationError):
        raise ConfigurationError("Config error")
