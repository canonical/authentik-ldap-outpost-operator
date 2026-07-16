# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the Authentik LDAP Outpost charm."""

import logging
import platform
from pathlib import Path
from typing import Callable

import jubilant
import pytest
from integration.conftest import integrate_dependencies
from integration.constants import (
    APP_IMAGE,
    APP_NAME,
    CA_APP,
    CA_CHANNEL,
    DB_APP,
    DB_CHANNEL,
    EXTERNAL_HOSTNAME,
    SERVER_APP,
    SERVER_CHANNEL,
    TRAEFIK_APP,
    TRAEFIK_CHANNEL,
    WORKER_APP,
    WORKER_CHANNEL,
)
from integration.utils import (
    StatusPredicate,
    all_active,
    and_,
    any_error,
    is_blocked,
    remove_integration,
    unit_number,
)

logger = logging.getLogger(__name__)


@pytest.mark.juju_setup
def test_build_and_deploy(juju: jubilant.Juju, charm: Path) -> None:
    """Build and deploy the charm-under-test together with related charms."""
    # Set model constraints dynamically based on native host architecture
    arch_map = {
        "aarch64": "arm64",
        "arm64": "arm64",
        "x86_64": "amd64",
        "amd64": "amd64",
    }
    host_arch = arch_map.get(platform.machine().lower(), "amd64")
    juju.cli("set-model-constraints", f"arch={host_arch}")

    juju.deploy(
        DB_APP,
        channel=DB_CHANNEL,
        trust=True,
    )

    juju.deploy(
        WORKER_APP,
        channel=WORKER_CHANNEL,
        trust=True,
    )

    juju.deploy(
        SERVER_APP,
        channel=SERVER_CHANNEL,
        trust=True,
    )

    juju.deploy(
        TRAEFIK_APP,
        channel=TRAEFIK_CHANNEL,
        config={"external_hostname": EXTERNAL_HOSTNAME},
        trust=True,
    )

    juju.deploy(
        CA_APP,
        channel=CA_CHANNEL,
        trust=True,
    )

    juju.deploy(
        str(charm),
        app=APP_NAME,
        resources={"oci-image": APP_IMAGE},
        trust=True,
    )

    integrate_dependencies(juju)

    juju.wait(
        ready=all_active(APP_NAME, SERVER_APP, DB_APP, WORKER_APP, TRAEFIK_APP, CA_APP),
        error=any_error(APP_NAME, SERVER_APP, DB_APP, WORKER_APP, TRAEFIK_APP, CA_APP),
        timeout=15 * 60,
    )


def test_scale_up(juju: jubilant.Juju) -> None:
    """Test scaling up to verify HA and leader election."""
    target_unit_number = 2
    juju.cli("scale-application", APP_NAME, str(target_unit_number))

    juju.wait(
        ready=and_(
            all_active(APP_NAME),
            unit_number(APP_NAME, target_unit_number),
        ),
        error=any_error(APP_NAME),
        timeout=5 * 60,
    )


@pytest.mark.parametrize(
    "remote_app_name,integration_name,is_status",
    [
        (SERVER_APP, "authentik-server-info", is_blocked),
        (TRAEFIK_APP, "traefik-route", all_active),
    ],
)
def test_remove_integration(
    juju: jubilant.Juju,
    remote_app_name: str,
    integration_name: str,
    is_status: Callable[[str], StatusPredicate],
) -> None:
    """Test removing and re-adding integrations."""
    with remove_integration(juju, remote_app_name, integration_name):
        juju.wait(
            ready=is_status(APP_NAME)
            if is_status == is_blocked
            else is_status(APP_NAME, remote_app_name),
            error=any_error(APP_NAME, remote_app_name),
            timeout=10 * 60,
        )
    juju.wait(
        ready=all_active(APP_NAME, remote_app_name),
        error=any_error(APP_NAME, remote_app_name),
        timeout=10 * 60,
    )


def test_scale_down(juju: jubilant.Juju) -> None:
    """Test scaling down to verify cluster stability."""
    target_unit_num = 1
    juju.cli("scale-application", APP_NAME, str(target_unit_num))

    juju.wait(
        ready=and_(
            all_active(APP_NAME),
            unit_number(APP_NAME, target_unit_num),
        ),
        error=any_error(APP_NAME),
        timeout=5 * 60,
    )


@pytest.mark.juju_teardown
def test_remove_application(juju: jubilant.Juju) -> None:
    """Test removing the application."""
    juju.remove_application(APP_NAME, destroy_storage=True)
    juju.wait(lambda s: APP_NAME not in s.apps, timeout=5 * 60)
