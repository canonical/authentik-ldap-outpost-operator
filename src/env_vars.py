# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Environment variable helpers and protocol."""

import logging
from typing import Mapping, Protocol, TypeAlias, Union, runtime_checkable

logger = logging.getLogger(__name__)

EnvVars: TypeAlias = Mapping[str, Union[str, bool]]

DEFAULT_CONTAINER_ENV: EnvVars = {
    "AUTHENTIK_HOST": "",
    "AUTHENTIK_TOKEN": "",
    "AUTHENTIK_INSECURE": "true",
    "AUTHENTIK_LOG_LEVEL": "info",
    "GOFIPS": "1",
}


@runtime_checkable
class EnvVarConvertible(Protocol):
    """Protocol for objects that can provide environment variables."""

    def to_env_vars(self) -> EnvVars:
        """Convert to environment variable dict."""
        ...
