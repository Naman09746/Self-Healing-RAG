import logging
import sys
import structlog
from typing import Any

def setup_logging() -> None:
    """Configure structured logging using structlog."""
    
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if sys.stderr.isatty():
        # Pretty print for local development
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON format for production/containers
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to redirect to structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

def get_logger(name: str) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
