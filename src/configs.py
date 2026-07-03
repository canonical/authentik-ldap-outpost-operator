# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm configuration."""

import logging

from ops import ConfigData

from env_vars import EnvVars

logger = logging.getLogger(__name__)


class CharmConfig:
    """Charm configuration helper."""

    def __init__(self, config: ConfigData) -> None:
        self._config = config

    def to_env_vars(self) -> EnvVars:
        """Convert configuration to environment variables.

        Returns:
            Dictionary of environment variables.
        """
        return {
            "AUTHENTIK_LOG_LEVEL": self._config.get("log_level", "info"),
            "HTTP_PROXY": self._config.get("http_proxy", ""),
            "HTTPS_PROXY": self._config.get("https_proxy", ""),
            "NO_PROXY": self._config.get("no_proxy", ""),
        }
