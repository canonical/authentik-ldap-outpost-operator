# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Pebble service helper."""

import logging

import ops
from ops import Unit
from ops.pebble import Layer, LayerDict

from constants import (
    COMMAND,
    LDAP_PORT,
    LDAPS_PORT,
    PEBBLE_READY_CHECK_NAME,
    SERVICE_NAME,
    WORKLOAD_CONTAINER,
)
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible, EnvVars
from exceptions import PebbleError

logger = logging.getLogger(__name__)


class AuthentikLdapWorkload:
    """Workload service definition for Authentik LDAP outpost."""

    @staticmethod
    def build_layer(env: EnvVars) -> LayerDict:
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
                    "startup": "disabled",
                    "environment": env,
                }
            },
            "checks": {
                PEBBLE_READY_CHECK_NAME: {
                    "override": "replace",
                    "level": "ready",
                    "threshold": 10,
                    "tcp": {
                        "port": LDAP_PORT,
                    },
                }
            },
        }


class WorkloadService:
    """Manage the workload service lifecycle."""

    def __init__(self, unit: Unit):
        self._unit = unit
        self._container = unit.get_container(WORKLOAD_CONTAINER)

    @property
    def version(self) -> str:
        """The workload version.

        Returns:
            Version string or empty string on error.
        """
        try:
            process = self._container.exec([COMMAND, "version"])
            stdout, _ = process.wait_output()
            return stdout.strip()
        except Exception:
            return ""

    def set_version(self) -> None:
        """Set the workload version in Juju."""
        try:
            version = self.version
            if version:
                self._unit.set_workload_version(version)
        except Exception as e:
            logger.error("Failed to set workload version: %s", e)

    def open_port(self) -> None:
        """Open workload ports."""
        try:
            self._unit.open_port(protocol="tcp", port=LDAP_PORT)
            self._unit.open_port(protocol="tcp", port=LDAPS_PORT)
        except Exception as e:
            logger.error("Failed to open ports: %s", e)

    def is_running(self) -> bool:
        """Check if the service is running and healthy.

        Returns:
            True if service is running and ready check is UP.
        """
        try:
            service = self._container.get_service(SERVICE_NAME)
            if not service.is_running():
                return False
            check = self._container.get_check(PEBBLE_READY_CHECK_NAME)
            return check.status == ops.pebble.CheckStatus.UP
        except Exception:
            return False

    def is_failing(self) -> bool:
        """Check if the service is running but unhealthy, crashlooping, or failing.

        Returns:
            True if service is failing, crashlooping, or the ready check is DOWN.
        """
        try:
            service = self._container.get_service(SERVICE_NAME)
        except Exception:
            return False

        current_str = (
            service.current.value if hasattr(service.current, "value") else service.current
        )
        if str(current_str).lower() in ("backoff", "error"):
            return True

        if not service.is_running():
            return False

        try:
            check = self._container.get_check(PEBBLE_READY_CHECK_NAME)
            return check.status == ops.pebble.CheckStatus.DOWN
        except Exception:
            return False


class PebbleService:
    """Manage the workload Pebble layer.

    Args:
        unit: The Juju unit owning the workload container.
    """

    def __init__(self, unit: Unit):
        self._unit = unit
        self._container = unit.get_container(WORKLOAD_CONTAINER)

    def render_pebble_layer(self, *env_var_sources: EnvVarConvertible) -> Layer:
        """Render the Pebble layer by merging environment variables.

        Args:
            env_var_sources: Sources of environment variables.

        Returns:
            Layer object.
        """
        env = dict(DEFAULT_CONTAINER_ENV)
        for source in env_var_sources:
            env.update(source.to_env_vars())

        layer_dict = AuthentikLdapWorkload.build_layer(env)
        return Layer(layer_dict)

    def plan(self, layer: Layer) -> None:
        """Apply a pebble layer and replan services.

        Args:
            layer: Pebble layer to apply.

        Raises:
            PebbleError: if planned operation fails.
        """
        try:
            self._container.add_layer(SERVICE_NAME, layer, combine=True)
            try:
                service = self._container.get_service(SERVICE_NAME)
                is_running = service.is_running()
            except Exception:
                is_running = False

            if is_running:
                self._container.replan()
            else:
                self._container.start(SERVICE_NAME)
        except Exception as e:
            raise PebbleError(f"Failed to plan Pebble layer: {e}") from e
