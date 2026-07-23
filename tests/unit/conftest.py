# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit test fixtures and shared utilities."""

import hashlib
import sys
import types
from typing import Any, Mapping, Optional, Sequence

import ops
import pytest
from ops import testing
from ops.framework import EventBase, EventSource, Object, ObjectEvents

MODEL_UUID = "12345678-1234-4234-8234-123456789abc"
APP_NAME = "authentik-ldap-outpost"
DEPLOYMENT_IDENTITY = f"{APP_NAME}-{hashlib.sha256(MODEL_UUID.encode()).hexdigest()[:12]}"

# Create mock module for charms.observability_libs.v0.kubernetes_compute_resources_patch
module_name = "charms.observability_libs.v0.kubernetes_compute_resources_patch"
mock_module = types.ModuleType(module_name)


class MockResourcePatcher:
    """Mock ResourcePatcher class."""

    pass


class K8sResourcePatchFailedEvent(EventBase):
    """Mock K8sResourcePatchFailedEvent."""

    def __init__(self, handle, message=""):
        super().__init__(handle)
        self.message = message

    def snapshot(self) -> dict:
        return {"message": self.message}

    def restore(self, snapshot):
        self.message = snapshot["message"]


class K8sResourcePatchEvents(ObjectEvents):
    """Mock K8sResourcePatchEvents."""

    patch_failed = EventSource(K8sResourcePatchFailedEvent)


class MockKubernetesComputeResourcesPatch(Object):
    """Mock KubernetesComputeResourcesPatch class."""

    on = K8sResourcePatchEvents()

    def __init__(self, charm: ops.CharmBase, *args: Any, **kwargs: Any):
        super().__init__(charm, "mock_kubernetes_compute_resources_patch")

    def get_status(self) -> Any:
        """Get the status of the resource patch."""
        return None


class ResourceRequirements:
    """Mock ResourceRequirements."""

    def __init__(self, limits=None, requests=None, claims=None):
        self.limits = limits or {}
        self.requests = requests or {}
        self.claims = claims


def adjust_resource_requirements(limits, requests, adhere_to_requests=True):
    """Mock adjust_resource_requirements."""
    return ResourceRequirements(limits=limits, requests=requests)


mock_module.ResourcePatcher = MockResourcePatcher
mock_module.KubernetesComputeResourcesPatch = MockKubernetesComputeResourcesPatch
mock_module.ResourceRequirements = ResourceRequirements
mock_module.K8sResourcePatchFailedEvent = K8sResourcePatchFailedEvent
mock_module.adjust_resource_requirements = adjust_resource_requirements

# Populate sys.modules so imports of this missing charm library succeed
sys.modules["charms.observability_libs"] = types.ModuleType("charms.observability_libs")
sys.modules["charms.observability_libs.v0"] = types.ModuleType("charms.observability_libs.v0")
sys.modules[module_name] = mock_module


def create_state(
    leader: bool = True,
    secrets: Optional[Sequence[Any]] = None,
    relations: Optional[Sequence[Any]] = None,
    containers: Optional[Sequence[Any]] = None,
    config: Optional[Mapping[str, Any]] = None,
    can_connect: bool = True,
    peer_data: Optional[Mapping[str, str]] = None,
) -> testing.State:
    """Create a Scenario State with sensible defaults."""
    secrets = list(secrets or [])
    if relations is None:
        relations = []
    else:
        relations = list(relations)
    if config is None:
        config = {}
    if containers is None:
        containers = [testing.Container("authentik-ldap", can_connect=can_connect)]

    # Always ensure a peer relation is present
    peer_rel_exists = any(r.endpoint == "authentik-ldap-peers" for r in relations)
    if not peer_rel_exists:
        if peer_data is None:
            outpost_secret = testing.Secret(
                {"token": "mock-token-123"},
                id="secret:outpost-token",
                owner="app",
                label="authentik-ldap-outpost-token",
            )
            secrets.append(outpost_secret)
            peer_data = {
                "outpost_token_secret_id": outpost_secret.id,
            }
        peer_rel = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data=peer_data,
        )
        relations.append(peer_rel)

    return testing.State(
        leader=leader,
        model=testing.Model(name="ldap-model", uuid=MODEL_UUID),
        secrets=set(secrets),
        relations=set(relations),
        containers=set(containers),
        config=config,
    )


@pytest.fixture
def mocked_resource_patch(mocker: Any) -> Any:
    """Fixture to patch ResourcePatcher."""
    return mocker.patch(
        "charms.observability_libs.v0.kubernetes_compute_resources_patch.ResourcePatcher",
        autospec=True,
    )


@pytest.fixture(autouse=True)
def mocked_k8s_resource_patch(mocker: Any) -> Any:
    """Fixture to patch KubernetesComputeResourcesPatch on the charm module."""
    import charm

    mock_get_status = mocker.patch.object(
        charm.KubernetesComputeResourcesPatch, "get_status", return_value=None
    )
    mock_class = mocker.MagicMock()
    mock_class.return_value.get_status = mock_get_status
    return mock_class


@pytest.fixture
def context() -> testing.Context:
    """Fixture to get testing context."""
    from charm import AuthentikLdapCharm

    return testing.Context(AuthentikLdapCharm)


@pytest.fixture
def container() -> testing.Container:
    """Fixture to get a connected container."""
    return testing.Container("authentik-ldap", can_connect=True)


@pytest.fixture
def server_info_relation() -> testing.Relation:
    """Fixture to get server info relation."""
    return testing.Relation(
        endpoint="authentik-server-info",
        interface="authentik-server-info",
        remote_app_name="authentik-server",
        remote_app_data={
            "authentik_host": "http://authentik:9000",
            "bootstrap_token_secret_id": "secret:xyz",
            "authentik_token_secret_id": "secret:xyz",
            "bootstrap_password_secret_id": "secret:abc",
        },
    )


@pytest.fixture(autouse=True)
def mocked_api_client(mocker: Any) -> Any:
    """Fixture to mock AuthentikApiClient to avoid real HTTP requests."""
    from api_client import AuthentikRole

    mock_class = mocker.patch("charm.AuthentikApiClient", autospec=True)
    mock_instance = mock_class.return_value
    mock_instance.get_or_create_provider.return_value = 1
    mock_instance.get_or_create_outpost.return_value = ("outpost-uuid", "token-ident")
    mock_instance.get_token_key.return_value = "mock-token-123"
    mock_instance.create_service_account.return_value = (42, "ldap-client-relation-1")
    mock_instance.create_ldap_bind_user.return_value = (42, "ldap-client-relation-1")
    mock_instance.check_outpost_exists.return_value = True
    # RBAC search-authorization defaults (idempotent, verified by the client).
    mock_instance.get_or_create_role.return_value = AuthentikRole(pk="role-uuid", name="role")
    mock_instance.assign_provider_search_permission.return_value = None
    mock_instance.add_user_to_role.return_value = None
    return mock_class
