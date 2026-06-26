# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# The integration tests use the Jubilant library. See https://documentation.ubuntu.com/jubilant/
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import logging
import os
import pathlib
import sys
import time

import jubilant
import pytest

from tests.integration.constants import APP_NAME, DB_APP, SERVER_APP, WORKER_APP

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Create a temporary Juju model for running tests."""
    with jubilant.temp_model() as juju:
        yield juju

        if request.session.testsfailed:
            logger.info("Collecting Juju logs...")
            time.sleep(0.5)  # Wait for Juju to process logs.
            log = juju.debug_log(limit=1000)
            print(log, end="", file=sys.stderr)


@pytest.fixture(scope="session")
def charm():
    """Return the path of the charm under test."""
    if "CHARM_PATH" in os.environ:
        charm_path = pathlib.Path(os.environ["CHARM_PATH"])
        if not charm_path.exists():
            raise FileNotFoundError(f"Charm does not exist: {charm_path}")
        return charm_path
    # Modify below if you're building for multiple bases or architectures.
    charm_paths = list(pathlib.Path(".").glob("*.charm"))
    if not charm_paths:
        raise FileNotFoundError("No .charm file in current directory")
    if len(charm_paths) > 1:
        path_list = ", ".join(str(path) for path in charm_paths)
        raise ValueError(f"More than one .charm file in current directory: {path_list}")
    return charm_paths[0]


def integrate_dependencies(juju: jubilant.Juju) -> None:
    """Integrate the charm with all required dependencies."""
    juju.integrate(DB_APP, SERVER_APP)
    juju.integrate(DB_APP, WORKER_APP)
    juju.integrate(f"{SERVER_APP}:authentik-cluster", WORKER_APP)
    juju.integrate(f"{SERVER_APP}:authentik-server-info", APP_NAME)
