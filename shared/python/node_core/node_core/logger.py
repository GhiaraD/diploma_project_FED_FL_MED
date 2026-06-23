"""
Centralized logging for Fed-Med-FL.

Usage:
    from node_core import get_logger

    log = get_logger("node1")
    log.info("Training started")
    log.warning("Dataset is small")
    log.error("Connection failed")
    log.section("FEDERATED LEARNING ROUND 1")  # prints a separator
"""

import logging
import sys
from typing import Optional


class FedLogger:
    """
    Wrapper around Python's standard logger that adds:
    - A node/component prefix on every message: [node1] message
    - Convenience methods for section separators used throughout the codebase
    - Consistent format across all services (worker, API, central, flower)
    """

    SEP_CHAR = "="
    SEP_WIDTH = 70

    def __init__(self, name: str, level: int = logging.INFO):
        self._name = name
        self._logger = logging.getLogger(f"fed_med.{name}")

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._logger.addHandler(handler)
            self._logger.propagate = False

        self._logger.setLevel(level)

    # ------------------------------------------------------------------ #
    # Standard levels                                                      #
    # ------------------------------------------------------------------ #

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(self._prefix(msg), *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(self._prefix(msg), *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(self._prefix(msg), *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(self._prefix(msg), *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log error with full traceback (use inside except blocks)."""
        self._logger.exception(self._prefix(msg), *args, **kwargs)

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #

    def section(self, title: str) -> None:
        """Print a full-width separator with a title — replaces print('='*70)."""
        sep = self.SEP_CHAR * self.SEP_WIDTH
        self._logger.info(sep)
        self._logger.info(self._prefix(title))
        self._logger.info(sep)

    def separator(self) -> None:
        """Print a plain separator line."""
        self._logger.info(self.SEP_CHAR * self.SEP_WIDTH)

    def step(self, msg: str) -> None:
        """Log a sub-step with a dash prefix — replaces print('  • ...')."""
        self._logger.info(self._prefix(f"  • {msg}"))

    def ok(self, msg: str) -> None:
        """Log a success message — replaces print('✓ ...')."""
        self._logger.info(self._prefix(f"✓ {msg}"))

    def warn(self, msg: str) -> None:
        """Alias for warning — replaces print('⚠️ ...')."""
        self._logger.warning(self._prefix(f"⚠  {msg}"))

    def fail(self, msg: str) -> None:
        """Log a failure — replaces print('✗ ...')."""
        self._logger.error(self._prefix(f"✗ {msg}"))

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _prefix(self, msg: str) -> str:
        return f"[{self._name}] {msg}"

    def set_level(self, level: int) -> None:
        self._logger.setLevel(level)

    @property
    def name(self) -> str:
        return self._name


# ------------------------------------------------------------------ #
# Module-level cache — one logger per name                            #
# ------------------------------------------------------------------ #

_loggers: dict[str, FedLogger] = {}


def get_logger(name: str, level: int = logging.INFO) -> FedLogger:
    """
    Get or create a FedLogger for the given name.

    Args:
        name: Component name used as prefix, e.g. "node1", "central", "worker"
        level: Logging level (default INFO)

    Returns:
        FedLogger instance
    """
    if name not in _loggers:
        _loggers[name] = FedLogger(name, level)
    return _loggers[name]
