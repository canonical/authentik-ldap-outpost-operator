# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the charm lifecycle and event handlers."""

from typing import Any

import ops
from ops import testing
from unit.conftest import create_state


class TestHolisticHandler:
    """Tests for the holistic handler reconciliation logic."""

    def test_when_pebble_not_ready_skips_planning(self, context: testing.Context) -> None:
        """Test that the charm skips Pebble layer planning when container cannot connect."""
        state_in = create_state(can_connect=False)
        state_out = context.run(context.on.config_changed(), state_in)
        container_out = state_out.get_container("authentik-ldap")
        assert not container_out.plan.services

    def test_when_server_info_missing_skips_planning(self, context: testing.Context) -> None:
        """Test that the charm skips Pebble layer planning when server info relation is missing."""
        state_in = create_state(can_connect=True)
        state_out = context.run(context.on.config_changed(), state_in)
        container_out = state_out.get_container("authentik-ldap")
        assert not container_out.plan.services

    def test_when_all_ready_plans_pebble_layer(
        self, context: testing.Context, server_info_relation: testing.Relation
    ) -> None:
        """Test that the charm successfully plans the Pebble layer when all conditions are met."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation],
            secrets=[secret_token, secret_password],
        )
        state_out = context.run(context.on.config_changed(), state_in)
        container_out = state_out.get_container("authentik-ldap")
        assert "authentik-ldap" in container_out.plan.services


class TestCollectStatus:
    """Tests for Juju status collection."""

    def test_when_pebble_not_ready_adds_waiting_status(self, context: testing.Context) -> None:
        """Test that Juju status is WaitingStatus when container cannot connect."""
        state_in = create_state(can_connect=False)
        state_out = context.run(context.on.collect_unit_status(), state_in)
        assert state_out.unit_status == testing.WaitingStatus("waiting for pebble")

    def test_when_server_info_missing_adds_blocked_status(self, context: testing.Context) -> None:
        """Test that Juju status is BlockedStatus when server info relation is missing."""
        state_in = create_state(can_connect=True)
        state_out = context.run(context.on.collect_unit_status(), state_in)
        assert state_out.unit_status == testing.BlockedStatus(
            "missing authentik-server-info relation"
        )

    def test_when_all_ready_adds_active_status(
        self, context: testing.Context, server_info_relation: testing.Relation
    ) -> None:
        """Test that Juju status is ActiveStatus when all conditions are satisfied and service is running."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        import ops.pebble as pebble

        container = testing.Container(
            "authentik-ldap",
            can_connect=True,
            layers={
                "base": pebble.Layer({
                    "services": {
                        "authentik-ldap": {
                            "override": "replace",
                            "summary": "Authentik LDAP outpost",
                            "command": "/ldap",
                            "startup": "disabled",
                        }
                    },
                    "checks": {
                        "ready": {
                            "override": "replace",
                            "level": "ready",
                            "tcp": {
                                "port": 3389,
                            },
                        }
                    },
                })
            },
            service_statuses={"authentik-ldap": pebble.ServiceStatus.ACTIVE},
            check_infos={
                testing.CheckInfo(
                    "ready",
                    level=pebble.CheckLevel.READY,
                    status=pebble.CheckStatus.UP,
                    startup=pebble.CheckStartup.UNSET,
                    threshold=None,
                )
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation],
            secrets=[secret_token, secret_password],
            containers=[container],
        )
        state_out = context.run(context.on.collect_unit_status(), state_in)
        assert state_out.unit_status == testing.ActiveStatus()

    def test_when_service_failing_adds_blocked_status(
        self, context: testing.Context, server_info_relation: testing.Relation, mocker: Any
    ) -> None:
        """Test that collect_unit_status reports BlockedStatus when workload service fails."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )

        class MockWorkloadService:
            def __init__(self, unit: ops.Unit):
                pass

            def is_failing(self) -> bool:
                return True

            def is_running(self) -> bool:
                return False

            @property
            def version(self) -> str:
                return ""

        mocker.patch("charm.WorkloadService", MockWorkloadService)

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation],
            secrets=[secret_token, secret_password],
        )
        state_out = context.run(context.on.collect_unit_status(), state_in)
        assert state_out.unit_status == testing.BlockedStatus(
            "failed to start service, check container logs"
        )


class TestPebbleReadyEvent:
    """Tests for the pebble-ready event handler."""

    def test_open_port_called_on_pebble_ready(self, context: testing.Context, mocker: Any) -> None:
        """Test that open_port is called when Pebble ready event fires."""
        mock_open_port = mocker.Mock()

        class MockWorkloadService:
            def __init__(self, unit: ops.Unit):
                pass

            def open_port(self) -> None:
                mock_open_port()

            def set_version(self) -> None:
                pass

            def is_failing(self) -> bool:
                return False

            def is_running(self) -> bool:
                return True

        mocker.patch("charm.WorkloadService", MockWorkloadService)

        state_in = create_state(can_connect=True)
        container = state_in.get_container("authentik-ldap")
        context.run(context.on.pebble_ready(container), state_in)

        mock_open_port.assert_called_once()

    def test_set_version_called_on_pebble_ready(
        self, context: testing.Context, mocker: Any
    ) -> None:
        """Test that set_version is called on Pebble ready and sets Juju workload version."""
        mock_set_version = mocker.Mock()

        class MockWorkloadService:
            def __init__(self, unit: ops.Unit):
                self.unit = unit

            def open_port(self) -> None:
                pass

            def set_version(self) -> None:
                mock_set_version()
                self.unit.set_workload_version("v1.2.3")

            def is_failing(self) -> bool:
                return False

            def is_running(self) -> bool:
                return True

        mocker.patch("charm.WorkloadService", MockWorkloadService)

        state_in = create_state(can_connect=True)
        container = state_in.get_container("authentik-ldap")
        state_out = context.run(context.on.pebble_ready(container), state_in)

        mock_set_version.assert_called_once()
        assert state_out.workload_version == "v1.2.3"


class TestResourcePatch:
    """Tests for the Kubernetes resource patcher integration."""

    def test_collect_status_includes_resource_patch_status(
        self,
        context: testing.Context,
        mocked_k8s_resource_patch: Any,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that collect_unit_status includes the resource patch status."""
        mocked_k8s_resource_patch.return_value.get_status.return_value = ops.BlockedStatus(
            "resource patch failed"
        )
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        import ops.pebble as pebble

        container = testing.Container(
            "authentik-ldap",
            can_connect=True,
            layers={
                "base": pebble.Layer({
                    "services": {
                        "authentik-ldap": {
                            "override": "replace",
                            "summary": "Authentik LDAP outpost",
                            "command": "/ldap",
                            "startup": "disabled",
                        }
                    },
                    "checks": {
                        "ready": {
                            "override": "replace",
                            "level": "ready",
                            "tcp": {
                                "port": 3389,
                            },
                        }
                    },
                })
            },
            service_statuses={"authentik-ldap": pebble.ServiceStatus.ACTIVE},
            check_infos={
                testing.CheckInfo(
                    "ready",
                    level=pebble.CheckLevel.READY,
                    status=pebble.CheckStatus.UP,
                    startup=pebble.CheckStartup.UNSET,
                    threshold=None,
                )
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation],
            secrets=[secret_token, secret_password],
            containers=[container],
        )
        state_out = context.run(context.on.collect_unit_status(), state_in)
        assert state_out.unit_status == ops.BlockedStatus("resource patch failed")

    def test_on_resource_patch_failed_reconciles(self, mocker: Any) -> None:
        """Test that _on_resource_patch_failed event handler triggers reconciliation."""
        from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
            K8sResourcePatchFailedEvent,
        )
        from ops.testing import Harness

        from charm import AuthentikLdapCharm

        harness = Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        mock_reconcile = mocker.patch.object(charm, "_on_holistic_handler")
        mock_event = mocker.MagicMock(spec=K8sResourcePatchFailedEvent)
        mock_event.message = "k8s api error"

        charm._on_resource_patch_failed(mock_event)
        mock_reconcile.assert_called_once_with(mock_event)


class TestLdapRelation:
    """Tests for the LDAP relation integration."""

    def test_ldap_relation_joined_provisions_service_account(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that joining an LDAP relation provisions a unique service account user."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )

        # Define the LDAP relation with a consumer
        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation],
            secrets=[secret_token, secret_password],
            peer_data={"outpost_token": "mock-token-123"},
        )

        state_out = context.run(context.on.relation_joined(ldap_relation), state_in)

        # Assert peer relation has saved the credentials
        peer_rel = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        assert peer_rel.local_app_data.get(f"client_{ldap_relation.id}_user_id") == "42"
        assert (
            peer_rel.local_app_data.get(f"client_{ldap_relation.id}_username")
            == "ldap-client-relation-1"
        )
        assert f"client_{ldap_relation.id}_password" in peer_rel.local_app_data

        # Assert consumer relation gets the provisioned details
        consumer_rel = state_out.get_relation(ldap_relation.id)
        assert consumer_rel.local_app_data.get("base_dn") == "dc=ldap,dc=goauthentik,dc=io"
        assert (
            consumer_rel.local_app_data.get("bind_dn")
            == "cn=ldap-client-relation-1,ou=users,dc=ldap,dc=goauthentik,dc=io"
        )
        assert "bind_password_secret" in consumer_rel.local_app_data

    def test_ldap_relation_broken_deletes_service_account(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that removing an LDAP relation cleans up the service account and peer data."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )

        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
        )

        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token": "mock-token-123",
                f"client_{ldap_relation.id}_user_id": "42",
                f"client_{ldap_relation.id}_username": "ldap-client-relation-1",
                f"client_{ldap_relation.id}_password": "strongpassword",
            },
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=[secret_token, secret_password],
        )

        state_out = context.run(context.on.relation_broken(ldap_relation), state_in)

        # Assert peer relation keys are cleanly deleted
        peer_rel_out = state_out.get_relation(peer_relation.id)
        assert f"client_{ldap_relation.id}_user_id" not in peer_rel_out.local_app_data
        assert f"client_{ldap_relation.id}_username" not in peer_rel_out.local_app_data
        assert f"client_{ldap_relation.id}_password" not in peer_rel_out.local_app_data
