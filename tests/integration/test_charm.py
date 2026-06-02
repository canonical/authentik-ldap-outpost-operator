# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import pathlib

import jubilant
import yaml

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(pathlib.Path("charmcraft.yaml").read_text())


def test_deploy(charm: pathlib.Path, juju: jubilant.Juju):
    """Deploy the charm under test."""
    resources = {"oci-image": METADATA["resources"]["oci-image"]["upstream-source"]}
    juju.deploy(charm.resolve(), app="authentik-ldap-outpost", resources=resources)
    juju.wait(jubilant.all_active)
