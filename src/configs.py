# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm configuration."""

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)


class CharmConfig:
    """Charm configuration helper."""

    def __init__(self, config: Mapping[str, Any]):
        self._config = config

    @property
    def log_level(self) -> str:
        """Return the log level configuration."""
        return self._config.get("log_level", "info")

    def is_valid(self) -> bool:
        """Validate configuration."""
        return self.log_level in ("debug", "info", "warning", "error")
