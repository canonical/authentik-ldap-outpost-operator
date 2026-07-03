# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# The integration tests use the Jubilant library. See https://documentation.ubuntu.com/jubilant/
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import logging
import os
import pathlib
import subprocess

import jubilant
import pytest
from integration.constants import APP_NAME, DB_APP, SERVER_APP, WORKER_APP

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def charm() -> pathlib.Path:
    """Return the path of the charm under test."""
    if "CHARM_PATH" in os.environ:
        charm_path = pathlib.Path(os.environ["CHARM_PATH"])
        if not charm_path.exists():
            raise FileNotFoundError(f"Charm does not exist: {charm_path}")
        return charm_path
    subprocess.run(["charmcraft", "pack"], check=True)
    if not (charms := list(pathlib.Path(".").glob("*.charm"))):
        raise RuntimeError("Charm not found and build failed")
    return charms[0].absolute()


def integrate_dependencies(juju: jubilant.Juju) -> None:
    """Integrate the charm with all required dependencies."""
    juju.integrate(DB_APP, SERVER_APP)
    juju.integrate(f"{SERVER_APP}:authentik-cluster", WORKER_APP)
    juju.integrate(f"{SERVER_APP}:authentik-server-info", APP_NAME)
