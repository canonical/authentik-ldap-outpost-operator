# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from charm import AuthentikLdapCharm
from constants import SERVICE_NAME, WORKLOAD_CONTAINER
from ops import pebble, testing

layer = pebble.Layer(
    {
        "services": {
            SERVICE_NAME: {
                "override": "replace",
                "command": "/ldap",
                "startup": "enabled",
            }
        },
    }
)


def test_waiting_when_container_not_ready():
    """Test that the charm is waiting when container cannot connect."""
    ctx = testing.Context(AuthentikLdapCharm)
    container_in = testing.Container(
        WORKLOAD_CONTAINER,
        can_connect=False,
    )
    state_in = testing.State(containers={container_in})

    state_out = ctx.run(ctx.on.pebble_ready(container_in), state_in)

    assert state_out.unit_status == testing.WaitingStatus("waiting for pebble")


def test_blocked_without_server_info():
    """Test that the charm is blocked without server info relation."""
    ctx = testing.Context(AuthentikLdapCharm)
    container_in = testing.Container(
        WORKLOAD_CONTAINER,
        can_connect=True,
        layers={"authentik": layer},
        service_statuses={SERVICE_NAME: pebble.ServiceStatus.ACTIVE},
    )
    state_in = testing.State(containers={container_in})

    state_out = ctx.run(ctx.on.pebble_ready(container_in), state_in)

    assert state_out.unit_status == testing.BlockedStatus("missing authentik-server-info relation")
