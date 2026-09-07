"""
Logging configuration with Rich console output and audit file logging.
"""

import logging
import os
from pathlib import Path
from rich.logging import RichHandler


def setup_logger(name: str = "hw_test_agent", log_dir: str = "reports") -> logging.Logger:
    """Configures and returns a Logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # Console Handler (Rich)
    console_handler = RichHandler(rich_tracebacks=True, show_path=False)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Audit Handler
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    audit_file = os.path.join(log_dir, "audit.log")
    file_handler = logging.FileHandler(audit_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
