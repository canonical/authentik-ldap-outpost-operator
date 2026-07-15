#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm the Authentik LDAP outpost application."""

import json
import logging
import secrets
from dataclasses import dataclass
from typing import Optional

import ops
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v1.loki_push_api import LogForwarder
from charms.observability_libs.v0.kubernetes_compute_resources_patch import (
    K8sResourcePatchFailedEvent,
    KubernetesComputeResourcesPatch,
    ResourceRequirements,
    adjust_resource_requirements,
)
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer

from api_client import AuthentikApiClient
from configs import CharmConfig
from constants import (
    GRAFANA_DASHBOARD_RELATION,
    LDAP_RELATION,
    LOGGING_RELATION,
    METRICS_ENDPOINT_RELATION,
    METRICS_PORT,
    PEBBLE_READY_CHECK_NAME,
    PEER_RELATION,
    TRACING_RELATION,
    WORKLOAD_CONTAINER,
)
from env_vars import EnvVars
from exceptions import PebbleError
from integrations import (
    LdapProviderIntegration,
    ServerInfoIntegration,
    TracingData,
    TraefikRouteIntegration,
)
from services import PebbleService, WorkloadService
from utils import NOOP_CONDITIONS

logger = logging.getLogger(__name__)


@dataclass
class OutpostEnv:
    """Environment variables for the Authentik outpost."""

    host: str
    token: str

    def to_env_vars(self) -> EnvVars:
        """Convert to environment variable dictionary."""
        return {
            "AUTHENTIK_HOST": self.host,
            "AUTHENTIK_TOKEN": self.token,
            "AUTHENTIK_INSECURE": "true",
        }


class AuthentikLdapCharm(ops.CharmBase):
    """Authentik LDAP Outpost Operator."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self._container = self.unit.get_container(WORKLOAD_CONTAINER)
        self._pebble = PebbleService(self.unit)
        self._workload_service = WorkloadService(self.unit)
        self._config = CharmConfig(self, self.model.config)

        self.server_info = ServerInfoIntegration(self)
        self.ldap_provider = LdapProviderIntegration(self)
        self.traefik_route = TraefikRouteIntegration(self)

        self.metrics_endpoint = MetricsEndpointProvider(
            self,
            relation_name=METRICS_ENDPOINT_RELATION,
            jobs=[{"static_configs": [{"targets": [f"*:{METRICS_PORT}"]}]}],
        )
        self.log_forwarder = LogForwarder(self, relation_name=LOGGING_RELATION)
        self.grafana_dashboard = GrafanaDashboardProvider(
            self, relation_name=GRAFANA_DASHBOARD_RELATION
        )
        self.tracing_requirer = TracingEndpointRequirer(
            self, relation_name=TRACING_RELATION, protocols=["otlp_http"]
        )
        self.resources_patch = KubernetesComputeResourcesPatch(
            self, WORKLOAD_CONTAINER, resource_reqs_func=self._resource_reqs_from_config
        )
        self._api_error = None

        # Observe events that trigger the holistic handler
        for event in [
            self.on.install,
            self.on.config_changed,
            self.on.leader_elected,
            self.on.update_status,
            self.on[PEER_RELATION].relation_joined,
            self.on[PEER_RELATION].relation_changed,
            self.on[LDAP_RELATION].relation_joined,
            self.on[LDAP_RELATION].relation_changed,
            self.server_info.on.info_changed,
            self.server_info.on.info_removed,
            self.traefik_route.requirer.on.ready,
            self.tracing_requirer.on.endpoint_changed,
            self.tracing_requirer.on.endpoint_removed,
        ]:
            self.framework.observe(event, self._on_holistic_handler)

        self.framework.observe(
            self.on[LDAP_RELATION].relation_broken, self._on_ldap_relation_broken
        )
        self.framework.observe(self.on.authentik_ldap_pebble_ready, self._on_pebble_ready)
        self.framework.observe(
            self.on.authentik_ldap_pebble_check_failed,
            self._on_pebble_check_failed,
        )
        self.framework.observe(
            self.on.authentik_ldap_pebble_check_recovered,
            self._on_pebble_check_recovered,
        )
        self.framework.observe(
            self.resources_patch.on.patch_failed, self._on_resource_patch_failed
        )

        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

    def _on_pebble_ready(self, event: ops.PebbleReadyEvent) -> None:
        """Handle pebble-ready event."""
        self._workload_service.open_port()
        self._on_holistic_handler(event)
        self._workload_service.set_version()

    def _on_pebble_check_failed(self, event: ops.PebbleCheckFailedEvent) -> None:
        """Handle Pebble health check failures."""
        if event.info.name == PEBBLE_READY_CHECK_NAME:
            logger.warning("Pebble ready check failed: %s", event.info.name)

    def _on_pebble_check_recovered(self, event: ops.PebbleCheckRecoveredEvent) -> None:
        """Handle Pebble health check recovery."""
        if event.info.name == PEBBLE_READY_CHECK_NAME:
            logger.info("Pebble ready check recovered")

    @property
    def _peers(self) -> Optional[ops.Relation]:
        """The peer relation."""
        return self.model.get_relation(PEER_RELATION)

    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """Build the pebble layer from all env var sources."""
        info = self.server_info.get_info()
        outpost_token = self._get_peer_data("outpost_token")
        if not info or not outpost_token:
            outpost_env = OutpostEnv(host="", token="")
        else:
            outpost_env = OutpostEnv(host=info.host, token=outpost_token)

        return self._pebble.render_pebble_layer(
            outpost_env,
            self._config,
            TracingData.load(self.tracing_requirer),
        )

    def _set_peer_data(self, key: str, value: str) -> None:
        """Set a value in the peer relation application databag."""
        if not self.unit.is_leader():
            return
        if peers := self._peers:
            peers.data[self.app][key] = value

    def _get_peer_data(self, key: str) -> Optional[str]:
        """Get a value from the peer relation application databag."""
        if peers := self._peers:
            return peers.data[self.app].get(key)
        return None

    def _set_peer_config_metadata(
        self,
        base_dn: Optional[str],
        search_mode: str,
        bind_mode: str,
        mfa_support: bool,
    ) -> None:
        """Store config values in peer relation to track changes.

        Args:
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.
        """
        self._set_peer_data("last_base_dn", base_dn or "")
        self._set_peer_data("last_search_mode", search_mode or "")
        self._set_peer_data("last_bind_mode", bind_mode or "")
        self._set_peer_data("last_mfa_support", str(mfa_support))

    def _verify_and_update_existing_resources(
        self,
        client: AuthentikApiClient,
        provider_pk_peer: Optional[str],
        outpost_uuid_peer: Optional[str],
        outpost_token_peer: Optional[str],
        base_dn: Optional[str],
        search_mode: str,
        bind_mode: str,
        mfa_support: bool,
        config_unchanged: bool,
    ) -> bool:
        """Verify the existing outpost resources and update provider config if changed.

        Args:
            client: The AuthentikApiClient instance.
            provider_pk_peer: Cached provider primary key.
            outpost_uuid_peer: Cached outpost UUID.
            outpost_token_peer: Cached outpost token.
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.
            config_unchanged: True if configuration matches cached values.

        Returns:
            bool: True if resources are successfully verified/updated and up to date.
                  False if validation failed or re-provisioning is required.
        """
        if not (provider_pk_peer and outpost_uuid_peer and outpost_token_peer):
            return False

        try:
            client.check_outpost_exists(outpost_uuid_peer)
            if config_unchanged:
                logger.debug(
                    "Authentik resources are already provisioned and configuration is up to date."
                )
                return True

            # If config has changed, we only need to update the Provider directly
            logger.info("Configuration changed. Updating existing LDAP Provider config.")
            client.update_provider_config(
                provider_pk=int(provider_pk_peer),
                base_dn=base_dn or "",
                search_mode=search_mode,
                bind_mode=bind_mode,
                mfa_support=mfa_support,
            )

            # Store config values in peer relation to track changes
            self._set_peer_config_metadata(base_dn, search_mode, bind_mode, mfa_support)

            logger.info("Successfully updated Authentik LDAP Provider configuration.")
            return True
        except Exception as e:
            logger.warning("Failed to verify or update existing resources, re-provisioning: %s", e)
            return False

    def _provision_fresh_resources(
        self,
        client: AuthentikApiClient,
        base_dn: Optional[str],
        search_mode: str,
        bind_mode: str,
        mfa_support: bool,
    ) -> None:
        """Create and sync fresh Provider, Application, and Outpost resources on Authentik.

        Args:
            client: The AuthentikApiClient instance.
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.
        """
        # Create/Sync Provider
        provider_name = f"ldap-provider-{self.app.name}"
        provider_pk = client.get_or_create_provider(
            name=provider_name,
            base_dn=base_dn or "",
            search_mode=search_mode,
            bind_mode=bind_mode,
            mfa_support=mfa_support,
        )

        # Create/Sync Application to bind Provider
        app_name = f"ldap-app-{self.app.name}"
        app_slug = f"ldap-app-{self.app.name}"
        client.get_or_create_application(
            name=app_name,
            slug=app_slug,
            provider_pk=provider_pk,
        )

        # Create/Sync Outpost
        outpost_name = f"ldap-outpost-{self.app.name}"
        outpost_pk, token_identifier = client.get_or_create_outpost(
            name=outpost_name,
            provider_pk=provider_pk,
        )

        # Retrieve Outpost Token Key
        outpost_token = client.get_token_key(token_identifier)

        # Store in peer relation
        self._set_peer_data("provider_pk", str(provider_pk))
        self._set_peer_data("outpost_uuid", outpost_pk)
        self._set_peer_data("outpost_token", outpost_token)

        # Store config values in peer relation to track changes
        self._set_peer_config_metadata(base_dn, search_mode, bind_mode, mfa_support)

        logger.info(
            "Successfully provisioned Authentik resources: Provider ID %s, Outpost UUID %s",
            provider_pk,
            outpost_pk,
        )

    def _provision_authentik_resources(self) -> None:
        """Provision the Upstream Provider and Outpost on Authentik."""
        if not self.unit.is_leader():
            return

        info = self.server_info.get_info()
        if not info:
            logger.info("Server info not ready yet; skipping provisioning")
            return

        base_dn = self.model.config.get("base_dn")
        search_mode = self.model.config.get("search_mode", "direct")
        bind_mode = self.model.config.get("bind_mode", "direct")
        mfa_support = bool(self.model.config.get("mfa_support", False))

        provider_pk_peer = self._get_peer_data("provider_pk")
        outpost_uuid_peer = self._get_peer_data("outpost_uuid")
        outpost_token_peer = self._get_peer_data("outpost_token")

        last_base_dn = self._get_peer_data("last_base_dn")
        last_search_mode = self._get_peer_data("last_search_mode")
        last_bind_mode = self._get_peer_data("last_bind_mode")
        last_mfa_support = self._get_peer_data("last_mfa_support")

        config_unchanged = (
            last_base_dn == base_dn
            and last_search_mode == search_mode
            and last_bind_mode == bind_mode
            and last_mfa_support == str(mfa_support)
        )

        client = AuthentikApiClient(info.host, info.bootstrap_token)

        if self._verify_and_update_existing_resources(
            client=client,
            provider_pk_peer=provider_pk_peer,
            outpost_uuid_peer=outpost_uuid_peer,
            outpost_token_peer=outpost_token_peer,
            base_dn=base_dn,
            search_mode=search_mode,
            bind_mode=bind_mode,
            mfa_support=mfa_support,
            config_unchanged=config_unchanged,
        ):
            return

        self._provision_fresh_resources(
            client=client,
            base_dn=base_dn,
            search_mode=search_mode,
            bind_mode=bind_mode,
            mfa_support=mfa_support,
        )

    def _get_tracked_relation_ids(self) -> set[int]:
        """Get relation IDs tracked in the peer relation.

        Returns:
            set[int]: Set of tracked relation IDs.
        """
        peers = self._peers
        if not peers:
            return set()

        tracked = set()
        for key in peers.data[self.app]:
            if key.startswith("client_"):
                try:
                    parts = key.split("_")
                    if len(parts) == 2:
                        tracked.add(int(parts[1]))
                    elif key.endswith("_user_id"):
                        tracked.add(int(parts[1]))
                except ValueError:
                    continue
        return tracked

    def _get_relation_credentials(self, relation_id: int) -> dict[str, str]:
        """Get the credentials for a given relation ID from peer data.

        Handles both new JSON format and legacy separate keys.

        Returns:
            dict[str, str]: Dictionary containing user_id, username, password.
        """
        data_str = self._get_peer_data(f"client_{relation_id}")
        if data_str:
            try:
                return json.loads(data_str)
            except Exception:
                pass

        return {
            "user_id": self._get_peer_data(f"client_{relation_id}_user_id") or "",
            "username": self._get_peer_data(f"client_{relation_id}_username") or "",
            "password": self._get_peer_data(f"client_{relation_id}_password") or "",
        }

    def _delete_orphaned_relation(self, client: AuthentikApiClient, relation_id: int) -> None:
        """Delete an orphaned relation's service account and clear peer data."""
        creds = self._get_relation_credentials(relation_id)
        user_id = creds.get("user_id")
        if user_id:
            try:
                client.delete_user(int(user_id))
                logger.info(
                    "Successfully deleted Authentik service account user ID %s for relation %s",
                    user_id,
                    relation_id,
                )
            except Exception as e:
                logger.error(
                    "Failed to delete Service Account for relation %s: %s",
                    relation_id,
                    e,
                )

        peers = self._peers
        if peers:
            key = f"client_{relation_id}"
            if key in peers.data[self.app]:
                del peers.data[self.app][key]
            for suffix in ["user_id", "username", "password"]:
                legacy_key = f"client_{relation_id}_{suffix}"
                if legacy_key in peers.data[self.app]:
                    del peers.data[self.app][legacy_key]

    def _cleanup_orphaned_relations(self) -> None:
        """Identify and clean up Authentik service accounts for broken LDAP relations."""
        if not self.unit.is_leader():
            return

        # Find active relation IDs
        active_relations = self.model.relations.get(LDAP_RELATION, [])
        active_relation_ids = {rel.id for rel in active_relations}

        tracked_relation_ids = self._get_tracked_relation_ids()
        orphaned_ids = tracked_relation_ids - active_relation_ids
        if not orphaned_ids:
            return

        info = self.server_info.get_info()
        if not info:
            return

        client = AuthentikApiClient(info.host, info.bootstrap_token)
        for relation_id in orphaned_ids:
            self._delete_orphaned_relation(client, relation_id)

    def _on_ldap_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle the relation broken event for LDAP consumers."""
        self._on_holistic_handler(event)

    def _on_holistic_handler(self, event: ops.EventBase) -> None:
        """Handle events holistically by setting status and running handler."""
        self.unit.status = ops.MaintenanceStatus("Configuring resources")
        self._holistic_handler(event)

    def _ensure_traefik_route(self) -> bool:
        """Ensure Traefik Route is submitted to Traefik if leader.

        Returns:
            bool: True.
        """
        if self.unit.is_leader():
            self.traefik_route.submit_route()
        return True

    def _holistic_handler(self, event: ops.EventBase) -> None:
        """Centralized reconciliation handler."""
        if not all(condition(self) for condition in NOOP_CONDITIONS):
            return

        can_plan = True
        for f in [
            self._ensure_traefik_route,
            self._ensure_authentik_resources,
            self._ensure_ldap_provider,
        ]:
            try:
                can_plan = can_plan and f()
            except Exception as e:
                logger.exception("Error in %s: %s", f.__name__, e)
                can_plan = False

        if not can_plan:
            return

        try:
            self._pebble.plan(self._pebble_layer)
        except PebbleError as e:
            logger.error("Failed to plan Pebble layer: %s", e)

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Collect unit status."""
        if not self._container.can_connect():
            event.add_status(ops.WaitingStatus("waiting for pebble"))
            return

        if not self.server_info.is_ready():
            event.add_status(ops.BlockedStatus("missing authentik-server-info relation"))
            return

        if getattr(self, "_api_error", None):
            event.add_status(ops.WaitingStatus(self._api_error))
            return

        if not self._get_peer_data("outpost_token"):
            event.add_status(ops.WaitingStatus("waiting for outpost token from peer relation"))
            return

        if self._workload_service.is_failing():
            event.add_status(ops.BlockedStatus("failed to start service, check container logs"))
        elif not self._workload_service.is_running():
            relations = self.model.relations.get(LDAP_RELATION, [])
            if not relations:
                event.add_status(ops.BlockedStatus("missing ldap integration"))
            else:
                event.add_status(ops.WaitingStatus("waiting for service to start"))

        if patch_status := self.resources_patch.get_status():
            event.add_status(patch_status)

        event.add_status(ops.ActiveStatus())

    def _ensure_authentik_resources(self) -> bool:
        """Ensure the Upstream Provider and Outpost on Authentik are provisioned.

        Returns:
            bool: True if provisioning succeeded and we have the token.
        """
        if self.unit.is_leader():
            try:
                self._provision_authentik_resources()
                self._api_error = None
            except Exception as e:
                self._api_error = f"API error: {e}"
                logger.error("Error during resource provisioning: %s", e)
                return False

        return bool(self._get_peer_data("outpost_token"))

    @property
    def _ldap_host(self) -> str:
        """The hostname/IP address for LDAP and LDAPS clients to connect to."""
        if self.traefik_route.ldaps_enabled and self.traefik_route.external_host:
            return self.traefik_route.external_host
        return f"{self.app.name}.{self.model.name}.svc.cluster.local"

    def _update_ldap_relation(self, relation: ops.Relation, address: str) -> bool:
        """Update a single LDAP relation's credentials and data.

        Returns:
            bool: True if relation was successfully updated, False if waiting or errored.
        """
        relation_id = relation.id

        creds = self._get_relation_credentials(relation_id)
        user_id = creds.get("user_id")

        if self.unit.is_leader() and not user_id:
            self._provision_service_account(relation_id)
            if self._api_error:
                return False
            creds = self._get_relation_credentials(relation_id)
            user_id = creds.get("user_id")

        username = creds.get("username")
        password = creds.get("password")

        if not (user_id and username and password):
            logger.info(
                "Waiting for peer relation to provide credentials for relation %s",
                relation_id,
            )
            return False

        base_dn = self.model.config.get("base_dn")
        bind_dn = f"cn={username},ou=users,{base_dn}"

        ldaps_enabled = self.traefik_route.ldaps_enabled
        external_host = self.traefik_route.external_host if ldaps_enabled else None

        self.ldap_provider.update_relation_data(
            relation_id=relation_id,
            unit_address=address,
            base_dn=base_dn,
            bind_dn=bind_dn,
            password=password,
            ldaps_enabled=ldaps_enabled,
            external_host=external_host,
        )
        return True

    def _ensure_ldap_provider(self) -> bool:
        """Ensure LDAP provider relation data is updated for all consumers.

        Returns:
            bool: True if the provider is fully configured.
        """
        if not self.server_info.is_ready():
            return False

        # Clean up any orphaned relations
        if self.unit.is_leader():
            try:
                self._cleanup_orphaned_relations()
            except Exception as e:
                logger.error("Failed to clean up orphaned relations: %s", e)

        relations = self.model.relations.get(LDAP_RELATION, [])
        if not relations:
            return True

        success = True
        for relation in relations:
            success &= self._update_ldap_relation(relation, self._ldap_host)

        return success

    def _provision_service_account(self, relation_id: int) -> None:
        """Provision an Authentik User account for a given relation ID to act as LDAP Bind."""
        info = self.server_info.get_info()
        if not info:
            return

        try:
            client = AuthentikApiClient(info.host, info.bootstrap_token)
            sa_name = f"ldap-client-{self.app.name}-{relation_id}"
            user_pk, username = client.create_ldap_bind_user(sa_name)

            password = secrets.token_urlsafe(16)
            client.set_user_password(user_pk, password)

            search_group_name = self.model.config.get("search_group")
            if search_group_name:
                group_uuid = client.get_group_by_name(search_group_name)
                if group_uuid:
                    client.add_user_to_group(group_uuid, user_pk)
                else:
                    logger.warning(
                        "LDAP search group '%s' not found on Authentik Server. User may not be able to perform searches.",
                        search_group_name,
                    )

            payload = json.dumps({
                "user_id": str(user_pk),
                "username": username,
                "password": password,
            })
            self._set_peer_data(f"client_{relation_id}", payload)
            logger.info(
                "Successfully provisioned LDAP Bind User '%s' (ID %s) for relation %s",
                username,
                user_pk,
                relation_id,
            )
            self._api_error = None
        except Exception as e:
            logger.error(
                "Failed to provision LDAP Bind User for relation %s: %s",
                relation_id,
                e,
            )
            self._api_error = f"API error: {e}"

    def _resource_reqs_from_config(self) -> ResourceRequirements:
        """Get resource requirements from charm config.

        Returns:
            ResourceRequirements object.
        """
        limits = {}
        if cpu := self.model.config.get("cpu"):
            limits["cpu"] = cpu
        if memory := self.model.config.get("memory"):
            limits["memory"] = memory
        return adjust_resource_requirements(
            limits,
            {"cpu": "100m", "memory": "200Mi"},
            adhere_to_requests=True,
        )

    def _on_resource_patch_failed(self, event: K8sResourcePatchFailedEvent) -> None:
        """Handle resource patch failed event.

        Args:
            event: K8sResourcePatchFailedEvent event object.
        """
        logger.error("Kubernetes resource patch failed: %s", event.message)
        self._on_holistic_handler(event)


if __name__ == "__main__":
    ops.main(AuthentikLdapCharm)
