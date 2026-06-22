# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Environment variable helpers and protocol."""

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


DEFAULT_CONTAINER_ENV: dict[str, str] = {
    "AUTHENTIK_INSECURE": "true",
}


@runtime_checkable
class EnvVarConvertible(Protocol):
    """Protocol for objects that can provide environment variables."""

    def to_env_vars(self) -> dict[str, str]:
        """Convert to environment variable dict."""
        ...


class EnvVarMerger:
    """Merge multiple EnvVarConvertible sources into a single env dict.

    Precedence: later sources override earlier ones.
    """

    def __init__(self, *sources: EnvVarConvertible):
        self._sources = sources

    def to_env_vars(self) -> dict[str, str]:
        """Merge all source environment variables.

        Returns:
            Merged environment variable dict.
        """
        env: dict[str, str] = dict(DEFAULT_CONTAINER_ENV)
        for source in self._sources:
            if isinstance(source, EnvVarConvertible):
                env.update(source.to_env_vars())
        return env
