# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions for the charm."""

from typing import TYPE_CHECKING, Callable

from constants import SERVER_INFO_RELATION, WORKLOAD_CONTAINER

if TYPE_CHECKING:
    from charm import AuthentikLdapCharm

Condition = Callable[["AuthentikLdapCharm"], bool]


def container_connectivity(charm: "AuthentikLdapCharm") -> bool:
    """Check if the workload container can connect.

    Args:
        charm: The charm instance.

    Returns:
        True if container is reachable.
    """
    return charm.unit.get_container(WORKLOAD_CONTAINER).can_connect()


def server_info_integration_exists(charm: "AuthentikLdapCharm") -> bool:
    """Check if the server-info relation is established.

    Args:
        charm: The charm instance.

    Returns:
        True if relation exists.
    """
    return bool(charm.model.get_relation(SERVER_INFO_RELATION))


NOOP_CONDITIONS: tuple[Condition, ...] = (
    container_connectivity,
    server_info_integration_exists,
)
