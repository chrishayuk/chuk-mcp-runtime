from chuk_mcp_runtime.server.logging_config import configure_logging, get_logger


def test_configure_logging(monkeypatch):
    # Create a dummy logging configuration
    config = {
        "logging": {
            "level": "DEBUG",
            "reset_handlers": True,
            "format": "%(levelname)s - %(message)s",
        }
    }

    configure_logging(config)
    logger = get_logger("test_logger")

    # Log a test message to ensure the logger has handlers attached
    logger.debug("Test debug message")
    assert logger.hasHandlers()
