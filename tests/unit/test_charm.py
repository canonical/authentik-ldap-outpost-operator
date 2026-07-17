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

        # Assert peer relation has saved the credentials in the merged JSON format
        import json

        peer_rel = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        client_data_str = peer_rel.local_app_data.get(f"client_{ldap_relation.id}")
        assert client_data_str is not None
        client_data = json.loads(client_data_str)
        assert client_data.get("user_id") == "42"
        assert client_data.get("username") == "ldap-client-relation-1"
        assert "password" in client_data

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


class TestProvisionAuthentikResources:
    """Tests for the Authentik resource provisioning and optimization."""

    def test_first_run_provisions_resources(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that resources are provisioned on the first run."""
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

        # Retrieve peer data
        peer_rel = state_out.get_relation(state_out.get_relations("authentik-ldap-peers")[0].id)
        assert peer_rel.local_app_data.get("provider_pk") == "1"
        assert peer_rel.local_app_data.get("outpost_uuid") == "outpost-uuid"
        assert peer_rel.local_app_data.get("outpost_token") == "mock-token-123"
        assert peer_rel.local_app_data.get("last_base_dn") == "dc=ldap,dc=goauthentik,dc=io"

    def test_second_run_skips_provisioning_if_config_unchanged(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that provisioning is skipped on subsequent runs if config is unchanged."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token": "mock-token-123",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "direct",
                "last_bind_mode": "direct",
                "last_mfa_support": "False",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password],
        )

        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.return_value = True

        context.run(context.on.config_changed(), state_in)

        # check_outpost_exists should have been called
        mock_client.check_outpost_exists.assert_called_once_with("outpost-uuid")
        # get_or_create_provider should NOT have been called
        mock_client.get_or_create_provider.assert_not_called()

    def test_reprovisions_if_config_changed(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that provider configuration is updated directly if the configuration changes."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token": "mock-token-123",
                "last_base_dn": "dc=different,dc=dn",  # config changed
                "last_search_mode": "direct",
                "last_bind_mode": "direct",
                "last_mfa_support": "False",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password],
        )

        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.return_value = True

        context.run(context.on.config_changed(), state_in)

        # check_outpost_exists should have been called to verify the outpost still exists
        mock_client.check_outpost_exists.assert_called_once_with("outpost-uuid")
        # update_provider_config should be called to sync new config directly
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
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "provider_pk": "1",
                "outpost_uuid": "outpost-uuid",
                "outpost_token": "mock-token-123",
                "last_base_dn": "dc=ldap,dc=goauthentik,dc=io",
                "last_search_mode": "direct",
                "last_bind_mode": "direct",
                "last_mfa_support": "False",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password],
        )

        mock_client = mocked_api_client.return_value
        mock_client.check_outpost_exists.side_effect = Exception("Not found")

        context.run(context.on.config_changed(), state_in)

        # check_outpost_exists should have been called
        mock_client.check_outpost_exists.assert_called_once_with("outpost-uuid")
        # get_or_create_provider should be called because outpost was not found
        mock_client.get_or_create_provider.assert_called_once()

    def test_leader_elected_cleans_up_orphaned_relations(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that leader_elected cleans up orphaned relations in peer data."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token": "mock-token-123",
                "client_99_user_id": "42",
                "client_99_username": "ldap-client-relation-99",
                "client_99_password": "strongpassword",
            },
        )
        # Note: relation ID 99 is tracked but does NOT exist in active relations list
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password],
        )

        mock_client = mocked_api_client.return_value

        state_out = context.run(context.on.leader_elected(), state_in)

        # Assert deletion API call was made
        mock_client.delete_user.assert_called_once_with(42)

        # Assert peer relation keys are cleanly deleted
        peer_rel_out = state_out.get_relation(peer_relation.id)
        assert "client_99_user_id" not in peer_rel_out.local_app_data
        assert "client_99_username" not in peer_rel_out.local_app_data
        assert "client_99_password" not in peer_rel_out.local_app_data

    def test_update_status_cleans_up_orphaned_relations(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
        mocked_api_client: Any,
    ) -> None:
        """Test that update_status cleans up orphaned relations in peer data."""
        secret_token = testing.Secret(
            {"bootstrap-token": "token123"},
            id="secret:xyz",
        )
        secret_password = testing.Secret(
            {"bootstrap-password": "password123"},
            id="secret:abc",
        )
        peer_relation = testing.PeerRelation(
            endpoint="authentik-ldap-peers",
            interface="authentik_ldap_peers",
            local_app_data={
                "outpost_token": "mock-token-123",
                "client_99_user_id": "42",
                "client_99_username": "ldap-client-relation-99",
                "client_99_password": "strongpassword",
            },
        )
        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, peer_relation],
            secrets=[secret_token, secret_password],
        )

        mock_client = mocked_api_client.return_value

        state_out = context.run(context.on.update_status(), state_in)

        # Assert deletion API call was made
        mock_client.delete_user.assert_called_once_with(42)

        # Assert peer relation keys are cleanly deleted
        peer_rel_out = state_out.get_relation(peer_relation.id)
        assert "client_99_user_id" not in peer_rel_out.local_app_data
        assert "client_99_username" not in peer_rel_out.local_app_data
        assert "client_99_password" not in peer_rel_out.local_app_data


class TestTraefikRouteRelation:
    """Tests for the TraefikRoute relation integration."""

    def test_traefik_route_ready_updates_ldap_relation_to_ldaps(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that having traefik-route ready updates ldap relation data with LDAPS enabled."""
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
                "outpost_token": "mock-token-123",
                f"client_{ldap_relation.id}_user_id": "42",
                f"client_{ldap_relation.id}_username": "ldap-client-relation-1",
                f"client_{ldap_relation.id}_password": "strongpassword",
            },
        )

        state_in = create_state(
            can_connect=True,
            relations=[server_info_relation, ldap_relation, peer_relation, traefik_route_relation],
            secrets=[secret_token, secret_password],
        )

        # Trigger on.ready or relation_changed
        state_out = context.run(context.on.relation_changed(traefik_route_relation), state_in)

        # Assert consumer relation gets ldaps_enabled=true and ldaps_urls pointing to the external host
        consumer_rel = state_out.get_relation(ldap_relation.id)
        assert consumer_rel.local_app_data.get("ldaps_enabled") == "true"
        import json

        ldaps_urls = json.loads(consumer_rel.local_app_data.get("ldaps_urls", "[]"))
        assert ldaps_urls == ["ldaps://external.address.dns:636"]

    def test_traefik_route_broken_disables_ldaps(
        self,
        context: testing.Context,
        server_info_relation: testing.Relation,
    ) -> None:
        """Test that breaking traefik-route updates ldap relation data with LDAPS disabled."""
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
            config={"expose_ldap_ingress": True},
        )

        # Trigger config_changed
        context.run(context.on.config_changed(), state_in)

        # Assert submit_route was called as part of holistic reconciliation
        mock_submit.assert_called()
