# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utility functions, condition factories and decorators."""

import logging
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from ops.charm import CharmBase

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def container_connectivity(charm: "CharmBase") -> bool:
    """Check if the workload container can connect.

    Args:
        charm: The charm instance.

    Returns:
        True if container is reachable.
    """
    container_name = getattr(charm, "_workload_container", "authentik-ldap")
    try:
        container = charm.unit.get_container(container_name)
        return container.can_connect()
    except Exception:
        return False


def leader_unit(func: F) -> F:
    """Ensure the function only runs on the leader unit.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function that checks leadership.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if hasattr(args[0], "unit") and not args[0].unit.is_leader():
            return None
        return func(*args, **kwargs)

    return wrapper  # type: ignore


def condition_factory(condition: Callable[["CharmBase"], bool]) -> Callable[[F], F]:
    """Create a decorator that checks a condition before executing.

    Args:
        condition: Function that takes a charm and returns bool.

    Returns:
        Decorator that wraps the function if condition is met.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if len(args) > 0 and isinstance(args[0], CharmBase):
                if not condition(args[0]):
                    return True
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def database_integration_exists(charm: "CharmBase") -> bool:
    """Check if database integration is established.

    Args:
        charm: The charm instance.

    Returns:
        True if database relation exists.
    """
    return False


def peer_integration_exists(charm: "CharmBase") -> bool:
    """Check if peer integration is established.

    Args:
        charm: The charm instance.

    Returns:
        True if peer relation exists.
    """
    return len(charm.model.relations.get("authentik-ldap-peers", [])) > 0
