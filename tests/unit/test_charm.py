# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the charm lifecycle and event handlers."""

import dataclasses
import json
from typing import Any

import ops
from ops import testing
from unit.conftest import DEPLOYMENT_IDENTITY, create_state

from api_client import AuthentikConnectionError, AuthentikHttpError, AuthentikNotFoundError


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
            {"api-token": "token123"},
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

    def test_authentik_insecure_is_set(
        self, context: testing.Context, server_info_relation: testing.Relation
    ) -> None:
        """AUTHENTIK_INSECURE is set for the internal HTTP connection to the server."""
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation],
            secrets=[
                testing.Secret({"api-token": "token123"}, id="secret:xyz"),
                testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
            ],
        )
        state_out = context.run(context.on.config_changed(), state_in)
        service = state_out.get_container("authentik-ldap").plan.services["authentik-ldap"]
        assert service.environment["AUTHENTIK_INSECURE"] == "true"


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

    def test_when_server_info_present_but_not_ready_adds_waiting_status(
        self, context: testing.Context
    ) -> None:
        """Test that Juju status is WaitingStatus when server info relation exists but is not ready."""
        relation = testing.Relation(
            endpoint="authentik-server-info",
            interface="authentik-server-info",
            remote_app_name="authentik-server",
            remote_app_data={},
        )
        state_in = create_state(can_connect=True, relations=[relation])
        state_out = context.run(context.on.collect_unit_status(), state_in)
        assert state_out.unit_status == testing.WaitingStatus(
            "waiting for authentik-server-info data"
        )

    def test_when_all_ready_adds_active_status(
        self, context: testing.Context, server_info_relation: testing.Relation
    ) -> None:
        """Test that Juju status is ActiveStatus when all conditions are satisfied and service is running."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
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
            {"api-token": "token123"},
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
            {"api-token": "token123"},
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

    def test_on_resource_patch_failed_reconciles(
        self, mocker: Any, context: testing.Context
    ) -> None:
        """Test that _on_resource_patch_failed event handler triggers reconciliation."""
        from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
            KubernetesComputeResourcesPatch,
        )

        mock_reconcile = mocker.MagicMock()

        def mock_handler(self, event: Any) -> None:
            mock_reconcile(event)

        mocker.patch("charm.AuthentikLdapCharm._on_holistic_handler", mock_handler)

        state_in = create_state()
        context.run(
            context.on.custom(
                KubernetesComputeResourcesPatch.on.patch_failed,
                message="k8s api error",
            ),
            state_in,
        )

        mock_reconcile.assert_called_once()
        called_event = mock_reconcile.call_args[0][0]
        assert called_event.message == "k8s api error"


class TestLdapRelation:
    """Tests for the LDAP relation integration."""

    def test_ldap_relation_joined_provisions_service_account(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that joining an LDAP relation provisions a unique service account user."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
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
        )

        state_out = context.run(context.on.relation_joined(ldap_relation), state_in)

        # Peer state tracks identity only; the bind password lives in the library secret.
        peer_rel = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        client_data_str = peer_rel.local_app_data.get(f"client_{ldap_relation.id}")
        assert client_data_str is not None
        client_data = json.loads(client_data_str)
        assert client_data == {
            "user_id": "42",
            "username": "ldap-client-relation-1",
            "last_user": "",
            "last_group": "",
        }

        # Assert consumer relation gets the provisioned details
        consumer_rel = state_out.get_relation(ldap_relation.id)
        assert consumer_rel.local_app_data.get("base_dn") == "dc=ldap,dc=goauthentik,dc=io"
        assert (
            consumer_rel.local_app_data.get("bind_dn")
            == "cn=ldap-client-relation-1,ou=users,dc=ldap,dc=goauthentik,dc=io"
        )
        bind_secret_id = consumer_rel.local_app_data["bind_password_secret"]
        assert state_out.get_secret(id=bind_secret_id).tracked_content.keys() == {"password"}

    def test_ldap_relation_broken_deletes_service_account(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that removing an LDAP relation cleans up the service account and peer data."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
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
                "outpost_token_secret_id": "secret:outpost",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-relation-1",
                }),
            },
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        state_out = context.run(context.on.relation_broken(ldap_relation), state_in)

        # Assert peer relation keys are cleanly deleted
        peer_rel_out = state_out.get_relation(peer_relation.id)
        assert f"client_{ldap_relation.id}" not in peer_rel_out.local_app_data


class TestProvisionAuthentikResources:
    """Tests for the Authentik resource provisioning and optimization."""

    def test_first_run_provisions_resources(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that resources are provisioned on the first run."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
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

        # Peer state contains only a secret reference; the application owns token content.
        peer_rel = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        assert peer_rel.local_app_data.get("provider_pk") == "1"
        assert peer_rel.local_app_data.get("outpost_uuid") == "outpost-uuid"
        assert "outpost_token" not in peer_rel.local_app_data
        secret_id = peer_rel.local_app_data["outpost_token_secret_id"]
        token_secret = state_out.get_secret(id=secret_id)
        assert token_secret.owner == "app"
        assert token_secret.tracked_content == {"token": "mock-token-123"}
        assert peer_rel.local_app_data.get("last_base_dn") == "dc=ldap,dc=goauthentik,dc=io"
        assert peer_rel.local_app_data.get("last_search_mode") == "cached"
        assert peer_rel.local_app_data.get("last_bind_mode") == "cached"

    def test_second_run_skips_provisioning_if_config_unchanged(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that provisioning is skipped on subsequent runs if config is unchanged."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.return_value = True

        context.run(context.on.config_changed(), state_in)

        # check_outpost_exists should have been called
        mock_client.check_outpost_exists.assert_called_once_with("outpost-uuid")
        # get_or_create_provider should NOT have been called
        mock_client.get_or_create_provider.assert_not_called()

    def test_reprovisions_if_modes_pinned_to_direct(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that explicit direct modes replace previously cached provider modes."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
            config={"search_mode": "direct", "bind_mode": "direct"},
        )

        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.return_value = True

        context.run(context.on.config_changed(), state_in)

        # check_outpost_exists should have been called to verify the outpost still exists
        mock_client.check_outpost_exists.assert_called_once_with("outpost-uuid")
        # update_provider_config should be called to apply the explicit direct modes
        mock_client.update_provider_config.assert_called_once_with(
            provider_pk=1,
            base_dn="dc=ldap,dc=goauthentik,dc=io",
            search_mode="direct",
            bind_mode="direct",
            mfa_support=False,
        )
        # get_or_create_provider should NOT be called
        mock_client.get_or_create_provider.assert_not_called()

    def test_reprovisions_if_outpost_does_not_exist(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that resources are re-provisioned if check_outpost_exists raises an error."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "direct",
                "last_bind_mode": "direct",
                "last_mfa_support": "False",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.side_effect = AuthentikNotFoundError("Not found", 404)

        context.run(context.on.config_changed(), state_in)

        # check_outpost_exists should have been called
        mock_client.check_outpost_exists.assert_called_once_with("outpost-uuid")
        # get_or_create_provider should be called because outpost was not found
        mock_client.get_or_create_provider.assert_called_once()

    def test_verification_transient_failure_does_not_reprovision(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """A non-404 API failure is caught, resetting can_plan and skipping planning."""
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "direct",
                "last_bind_mode": "direct",
                "last_mfa_support": "False",
            },
        )
        secrets = [
            testing.Secret({"api-token": "token123"}, id="secret:xyz"),
            testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
            testing.Secret(
                {"token": "mock-token-123"},
                id="secret:outpost",
                owner="app",
                label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
            ),
        ]
        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.side_effect = AuthentikHttpError("unavailable", 503)

        # The transient API failure is caught by the holistic handler: the hook must
        # not crash, must not reprovision, and must leave the Pebble layer unplanned.
        state_out = context.run(
            context.on.config_changed(),
            create_state(relations=[server_info_relation, peer_relation], secrets=secrets),
        )

        mock_client.get_or_create_provider.assert_not_called()
        container_out = state_out.get_container("authentik-ldap")
        assert "authentik-ldap" not in container_out.plan.services

    def test_follower_reads_outpost_token_secret_by_id(
        self, context: testing.Context, server_info_relation: testing.Relation
    ) -> None:
        """A follower configures its workload from the peer secret reference."""
        token_secret = testing.Secret(
            {"token": "secret-backed-token"}, id="secret:outpost", owner="app"
        )
        secrets = [
            token_secret,
            testing.Secret({"api-token": "token123"}, id="secret:xyz"),
            testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
        ]
        peer = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={"outpost_token_secret_id": token_secret.id},
        )

        state_out = context.run(
            context.on.config_changed(),
            create_state(
                leader=False,
                relations=[server_info_relation, peer],
                secrets=secrets,
            ),
        )

        service = state_out.get_container("authentik-ldap").plan.services["authentik-ldap"]
        assert service.environment["AUTHENTIK_TOKEN"] == "secret-backed-token"

    def test_missing_bind_secret_rotates_and_republishes_password(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Identity-only peer state recovers by rotating a missing bind secret."""
        ldap_relation = testing.Relation(
            endpoint="ldap", interface="ldap", remote_app_name="nextcloud"
        )
        peer = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-relation-1",
                }),
            },
        )
        secrets = [
            testing.Secret({"api-token": "token123"}, id="secret:xyz"),
            testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
            testing.Secret(
                {"token": "mock-token-123"},
                id="secret:outpost",
                owner="app",
                label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
            ),
        ]

        state_out = context.run(
            context.on.config_changed(),
            create_state(relations=[server_info_relation, ldap_relation, peer], secrets=secrets),
        )

        mocked_api_client.return_value.set_user_password.assert_called_once()
        relation_out = state_out.get_relation(ldap_relation.id)
        bind_secret_id = relation_out.local_app_data["bind_password_secret"]
        assert state_out.get_secret(id=bind_secret_id).tracked_content.keys() == {"password"}
        peer_out = state_out.get_relation(peer.id)
        assert "password" not in json.loads(peer_out.local_app_data[f"client_{ldap_relation.id}"])

    def test_failed_orphan_deletion_preserves_tracking_for_retry(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """An orphan remains tracked when Authentik deletion does not complete."""
        peer = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                "client_99": json.dumps({"user_id": "42", "username": "orphan"}),
            },
        )
        secrets = [
            testing.Secret({"api-token": "token123"}, id="secret:xyz"),
            testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
            testing.Secret(
                {"token": "mock-token-123"},
                id="secret:outpost",
                owner="app",
                label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
            ),
        ]
        mocked_api_client.return_value.delete_user.side_effect = AuthentikConnectionError(
            "unavailable"
        )

        state_out = context.run(
            context.on.update_status(),
            create_state(relations=[server_info_relation, peer], secrets=secrets),
        )

        peer_out = state_out.get_relation(peer.id)
        assert "client_99" in peer_out.local_app_data

    def test_orphan_not_found_clears_tracking(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """A typed not-found response completes deletion idempotently."""
        peer = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                "client_99": json.dumps({"user_id": "42", "username": "orphan"}),
            },
        )
        mocked_api_client.return_value.delete_user.side_effect = AuthentikNotFoundError(
            "absent", 404
        )
        state_out = context.run(
            context.on.update_status(),
            create_state(
                relations=[server_info_relation, peer],
                secrets=[
                    testing.Secret({"api-token": "token123"}, id="secret:xyz"),
                    testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
                    testing.Secret(
                        {"token": "mock-token-123"},
                        id="secret:outpost",
                        owner="app",
                        label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
                    ),
                ],
            ),
        )

        assert "client_99" not in state_out.get_relation(peer.id).local_app_data

    def test_leader_elected_cleans_up_orphaned_relations(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that leader_elected cleans up orphaned relations in peer data."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                "client_99": json.dumps({"user_id": "42", "username": "ldap-client-relation-99"}),
            },
        )
        # Note: relation ID 99 is tracked but does NOT exist in active relations list
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        mock_client = mocked_api_client.return_value

        state_out = context.run(context.on.leader_elected(), state_in)

        # Assert deletion API call was made
        mock_client.delete_user.assert_called_once_with(42)

        # Assert peer relation keys are cleanly deleted
        peer_rel_out = state_out.get_relation(peer_relation.id)
        assert "client_99" not in peer_rel_out.local_app_data

    def test_update_status_cleans_up_orphaned_relations(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that update_status cleans up orphaned relations in peer data."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                "client_99": json.dumps({"user_id": "42", "username": "ldap-client-relation-99"}),
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        mock_client = mocked_api_client.return_value

        state_out = context.run(context.on.update_status(), state_in)

        # Assert deletion API call was made
        mock_client.delete_user.assert_called_once_with(42)

        # Assert peer relation keys are cleanly deleted
        peer_rel_out = state_out.get_relation(peer_relation.id)
        assert "client_99" not in peer_rel_out.local_app_data


class TestTraefikRouteRelation:
    """Tests for the TraefikRoute relation integration."""

    def test_traefik_route_ready_updates_ldap_relation_to_ldaps(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that having traefik-route ready updates ldap relation data with LDAPS enabled."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )

        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
        )

        traefik_route_relation = testing.Relation(
            endpoint="traefik-route",
            interface="traefik_route",
            remote_app_name="traefik",
            remote_app_data={
                "external_host": "external.address.dns",
                "scheme": "https",
            },
        )

        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-relation-1",
                }),
            },
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation, traefik_route_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        # Trigger on.ready or relation_changed
        state_out = context.run(context.on.relation_changed(traefik_route_relation), state_in)

        # Assert consumer relation gets ldaps_enabled=true and ldaps_urls pointing to the external host
        consumer_rel = state_out.get_relation(ldap_relation.id)
        assert consumer_rel.local_app_data.get("ldaps_enabled") == "true"
        ldaps_urls = json.loads(consumer_rel.local_app_data.get("ldaps_urls", "[]"))
        assert ldaps_urls == ["ldaps://external.address.dns:636"]

    def test_traefik_route_broken_disables_ldaps(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that breaking traefik-route updates ldap relation data with LDAPS disabled."""
        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
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
                "outpost_token_secret_id": "secret:outpost",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-relation-1",
                }),
            },
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
        )

        # Let's say we started with it ready but now it's gone / broken
        # Run standard holistic handler/config changed
        state_out = context.run(context.on.config_changed(), state_in)

        # Assert consumer relation gets ldaps_enabled=false
        consumer_rel = state_out.get_relation(ldap_relation.id)
        assert consumer_rel.local_app_data.get("ldaps_enabled") == "false"

    def test_expose_ldap_ingress_config_change_submits_route(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocker: Any,
    ) -> None:
        """Test that changing expose_ldap_ingress triggers a new Traefik route submission."""
        mock_submit = mocker.patch("integrations.TraefikRouteIntegration.submit_route")

        secret_token = testing.Secret(
            {"api-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
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
                "outpost_token_secret_id": "secret:outpost",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-relation-1",
                }),
            },
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=[secret_token, secret_password, token_secret],
            config={"expose_ldap_ingress": True},
        )

        # Trigger config_changed
        context.run(context.on.config_changed(), state_in)

        # Assert submit_route was called as part of holistic reconciliation
        mock_submit.assert_called()


class TestSearchAuthorization:
    """Tests for RBAC search authorization."""

    def _bootstrap_secrets(self) -> list:
        return [
            testing.Secret({"api-token": "token123"}, id="secret:xyz"),
            testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
        ]

    def test_config_change_reconciles_provider_scoped_search_role(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """A config change assigns full-directory search via a provider-scoped role."""
        ldap_relation = testing.Relation(
            endpoint="ldap", interface="ldap", remote_app_name="nextcloud"
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
                f"client_{ldap_relation.id}": json.dumps({"user_id": "42", "username": "bind"}),
            },
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=self._bootstrap_secrets() + [token_secret],
            config={"base_dn": "dc=changed,dc=io"},
        )

        mock_client = mocked_api_client.return_value

        context.run(context.on.config_changed(), state_in)

        mock_client.get_or_create_role.assert_called_once_with(
            f"ldap-search-{DEPLOYMENT_IDENTITY}"
        )
        mock_client.assign_provider_search_permission.assert_called_once_with("role-uuid", 1)
        mock_client.add_user_to_role.assert_any_call("role-uuid", 42)
        # No legacy group APIs exist on the client any more.
        assert not hasattr(mock_client, "add_user_to_group") or not (
            mock_client.add_user_to_group.called
        )

    def test_search_permission_not_reassigned_when_already_verified(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """A verified provider-scoped grant is not re-assigned on the next config change."""
        ldap_relation = testing.Relation(
            endpoint="ldap", interface="ldap", remote_app_name="nextcloud"
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "search_role_uuid": "role-uuid",
                "search_permission_verified": "1",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
                f"client_{ldap_relation.id}": json.dumps({"user_id": "42", "username": "bind"}),
            },
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=self._bootstrap_secrets() + [token_secret],
            config={"base_dn": "dc=changed,dc=io"},
        )

        mock_client = mocked_api_client.return_value

        context.run(context.on.config_changed(), state_in)

        # Already verified for provider_pk 1 with the same role: skip the redundant grant.
        mock_client.assign_provider_search_permission.assert_not_called()
        # Role membership is still reconciled idempotently.
        mock_client.add_user_to_role.assert_any_call("role-uuid", 42)

    def _membership_state(self, server_info_relation: testing.Relation) -> Any:
        """Build a config-changed-ready state with one tracked bind user."""
        ldap_relation = testing.Relation(
            endpoint="ldap", interface="ldap", remote_app_name="nextcloud"
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token_secret_id": "secret:outpost",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
                f"client_{ldap_relation.id}": json.dumps({"user_id": "42", "username": "bind"}),
            },
        )
        token_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label=f"authentik-ldap-outpost-token-{DEPLOYMENT_IDENTITY}",
        )
        return create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation],
            secrets=self._bootstrap_secrets() + [token_secret],
            config={"base_dn": "dc=changed,dc=io"},
        )

    def test_unchanged_membership_skips_add_user_to_role(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """A second reconcile with unchanged membership makes no add_user_to_role call."""
        mock_client = mocked_api_client.return_value
        state_in = self._membership_state(server_info_relation)

        # First reconcile applies and caches the (user, role) membership.
        state_mid = context.run(context.on.config_changed(), state_in)
        mock_client.add_user_to_role.assert_any_call("role-uuid", 42)

        # A further config change still runs search authorization, but the cached
        # membership for the unchanged role must skip the redundant API call.
        mock_client.add_user_to_role.reset_mock()
        state_next = dataclasses.replace(state_mid, config={"base_dn": "dc=changed-again,dc=io"})
        context.run(context.on.config_changed(), state_next)
        mock_client.add_user_to_role.assert_not_called()

    def test_changed_role_reapplies_membership(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """A changed role UUID invalidates the cache and re-applies membership."""
        from api_client import AuthentikRole

        mock_client = mocked_api_client.return_value
        state_in = self._membership_state(server_info_relation)

        state_mid = context.run(context.on.config_changed(), state_in)
        mock_client.add_user_to_role.assert_any_call("role-uuid", 42)

        # The role is recreated with a new UUID: the prior grant is gone, so the
        # cached membership is invalidated and the user is re-added to the new role.
        mock_client.add_user_to_role.reset_mock()
        mock_client.get_or_create_role.return_value = AuthentikRole(
            pk="new-role-uuid", name="role"
        )
        state_next = dataclasses.replace(state_mid, config={"base_dn": "dc=changed-again,dc=io"})
        context.run(context.on.config_changed(), state_next)
        mock_client.add_user_to_role.assert_any_call("new-role-uuid", 42)


class TestRequirerIdentity:
    """Tests for honoring the requirer-provided ldap user/group."""

    def _secrets(self) -> list:
        return [
            testing.Secret({"api-token": "token123"}, id="secret:xyz"),
            testing.Secret({"bootstrap-password": "password123"}, id="secret:abc"),
        ]

    def test_requested_user_reflected_in_bind_username(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        mocked_api_client.return_value.create_ldap_bind_user.side_effect = lambda name: (42, name)
        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
            remote_app_data={"user": "svc", "group": ""},
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation],
            secrets=self._secrets(),
        )

        state_out = context.run(context.on.relation_joined(ldap_relation), state_in)

        peer = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        rec = json.loads(peer.local_app_data[f"client_{ldap_relation.id}"])
        assert rec["username"].startswith(f"ldap-client-svc-{DEPLOYMENT_IDENTITY}")
        assert rec["last_user"] == "svc"

    def test_requested_group_adopted_when_it_exists(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        client = mocked_api_client.return_value
        client.get_group_by_name.return_value = "grp-uuid"
        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
            remote_app_data={"user": "", "group": "grp"},
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation],
            secrets=self._secrets(),
        )

        state_out = context.run(context.on.relation_joined(ldap_relation), state_in)

        client.add_user_to_group.assert_any_call("grp-uuid", 42)
        peer = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        rec = json.loads(peer.local_app_data[f"client_{ldap_relation.id}"])
        assert rec["last_group"] == "grp"

    def test_requested_group_skipped_when_absent(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        client = mocked_api_client.return_value
        client.get_group_by_name.return_value = None
        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
            remote_app_data={"user": "", "group": "missing"},
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation],
            secrets=self._secrets(),
        )

        context.run(context.on.relation_joined(ldap_relation), state_in)

        client.add_user_to_group.assert_not_called()

    def test_requested_user_change_renames_bind_user(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        client = mocked_api_client.return_value
        client.find_user_by_username.return_value = None
        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
            remote_app_data={"user": "new", "group": ""},
        )
        peer = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "search_role_uuid": "role-uuid",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-old",
                    "last_user": "old",
                    "last_group": "",
                }),
            },
        )
        outpost_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label="authentik-ldap-outpost-token",
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer],
            secrets=self._secrets() + [outpost_secret],
        )

        state_out = context.run(context.on.relation_changed(ldap_relation), state_in)

        target = self._bind_target(ldap_relation.id, "new")
        client.rename_user.assert_any_call(42, target)
        peer_out = state_out.get_relation(peer.id)
        rec = json.loads(peer_out.local_app_data[f"client_{ldap_relation.id}"])
        assert rec["last_user"] == "new"

    def test_requested_user_change_conflict_blocks_rename(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        from api_client import AuthentikUser

        client = mocked_api_client.return_value
        client.find_user_by_username.return_value = AuthentikUser(
            pk=99, username="taken", name="taken"
        )
        ldap_relation = testing.Relation(
            endpoint="ldap",
            interface="ldap",
            remote_app_name="nextcloud",
            remote_app_data={"user": "new", "group": ""},
        )
        peer = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token_secret_id": "secret:outpost",
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "search_role_uuid": "role-uuid",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "cached",
                "last_bind_mode": "cached",
                "last_mfa_support": "False",
                f"client_{ldap_relation.id}": json.dumps({
                    "user_id": "42",
                    "username": "ldap-client-old",
                    "last_user": "old",
                    "last_group": "",
                }),
            },
        )
        outpost_secret = testing.Secret(
            {"token": "mock-token-123"},
            id="secret:outpost",
            owner="app",
            label="authentik-ldap-outpost-token",
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer],
            secrets=self._secrets() + [outpost_secret],
        )

        state_out = context.run(context.on.relation_changed(ldap_relation), state_in)

        client.rename_user.assert_not_called()
        peer_out = state_out.get_relation(peer.id)
        rec = json.loads(peer_out.local_app_data[f"client_{ldap_relation.id}"])
        assert rec["last_user"] == "old"

    @staticmethod
    def _bind_target(relation_id: int, user: str) -> str:
        return f"ldap-client-{user}-{DEPLOYMENT_IDENTITY}-{relation_id}"
