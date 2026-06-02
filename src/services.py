# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pebble service helper."""

import logging

from constants import (
    AUTHENTIK_INSECURE,
    COMMAND,
    LDAP_PORT,
    SERVICE_NAME,
)
from ops import Container
from ops.pebble import Layer, LayerDict

logger = logging.getLogger(__name__)


class AuthentikLdapWorkload:
    """Workload service definition for Authentik LDAP outpost."""

    @staticmethod
    def build_layer(env: dict[str, str]) -> LayerDict:
        """Build the pebble layer configuration.

        Args:
            env: Environment variables for the workload.

        Returns:
            LayerDict for Pebble.
        """
        return {
            "services": {
                SERVICE_NAME: {
                    "override": "replace",
                    "summary": "Authentik LDAP outpost",
                    "command": COMMAND,
                    "startup": "enabled",
                    "environment": env,
                }
            },
            "checks": {
                "health": {
                    "override": "replace",
                    "level": "alive",
                    "tcp": {
                        "port": LDAP_PORT,
                    },
                }
            },
        }

    @staticmethod
    def build_layer_with_defaults(env: dict[str, str]) -> LayerDict:
        """Build layer with default AUTHENTIK_INSECURE env var.

        Args:
            env: Additional environment variables.

        Returns:
            LayerDict for Pebble.
        """
        full_env = {**env, "AUTHENTIK_INSECURE": AUTHENTIK_INSECURE}
        return AuthentikLdapWorkload.build_layer(full_env)


class PebbleService:
    """Manage the workload Pebble layer."""

    def __init__(self, container: Container):
        self._container = container
        self._workload = AuthentikLdapWorkload()

    def plan(self, layer: Layer | dict | LayerDict) -> None:
        """Apply a pebble layer and replan services."""
        self._container.add_layer("authentik", layer, combine=True)
        self._container.replan()
