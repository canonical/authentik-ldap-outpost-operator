#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm the Authentik LDAP outpost application."""

import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from functools import cached_property
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

from api_client import AuthentikApiClient, AuthentikApiError, AuthentikNotFoundError
from configs import CharmConfig
from constants import (
    GRAFANA_DASHBOARD_RELATION,
    LDAP_RELATION,
    LOGGING_RELATION,
    METRICS_ENDPOINT_RELATION,
    METRICS_PORT,
    PEBBLE_READY_CHECK_NAME,
    PEER_RELATION,
    SERVER_INFO_RELATION,
    TRACING_RELATION,
    WORKLOAD_CONTAINER,
)
from env_vars import EnvVars
from exceptions import AuthentikMigrationError, CharmError, PebbleError
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
    def _deployment_identity(self) -> str:
        """A stable, slug-safe identity unique to this deployment.

        Combines a sanitized application name with a 48-bit hash of the immutable
        Juju model UUID so separate deployments never collide on shared Authentik
        resource names, even when they reuse the same application name.
        """
        slug = re.sub(r"[^a-z0-9-]", "-", self.app.name.lower()).strip("-") or "ldap"
        digest = hashlib.sha256(self.model.uuid.encode("utf-8")).hexdigest()[:12]
        return f"{slug}-{digest}"

    @property
    def _provider_name(self) -> str:
        """The managed LDAP provider name for this deployment."""
        return f"ldap-provider-{self._deployment_identity}"

    @property
    def _application_name(self) -> str:
        """The managed application name and slug for this deployment."""
        return f"ldap-app-{self._deployment_identity}"

    @property
    def _outpost_name(self) -> str:
        """The managed outpost name for this deployment."""
        return f"ldap-outpost-{self._deployment_identity}"

    @property
    def _search_role_name(self) -> str:
        """The managed RBAC role name granting full-directory search."""
        return f"ldap-search-{self._deployment_identity}"

    @property
    def _outpost_token_label(self) -> str:
        """The Juju secret label holding the outpost API token."""
        return f"authentik-ldap-outpost-token-{self._deployment_identity}"

    def _bind_user_name(self, relation_id: int, requested_user: Optional[str] = None) -> str:
        """The managed LDAP bind username for a consumer relation.

        Incorporates the requirer-requested ``user`` (sanitized) for traceability
        while keeping the deployment identity and relation id so the username stays
        globally unique. Falls back to the deployment-unique name when no user is
        requested.
        """
        base = f"ldap-client-{self._deployment_identity}-{relation_id}"
        if not requested_user:
            return base
        slug = re.sub(r"[^a-z0-9-]", "-", requested_user.lower()).strip("-")
        if not slug:
            return base
        return f"ldap-client-{slug}-{self._deployment_identity}-{relation_id}"

    def _requested_ldap_identity(self, relation_id: int) -> tuple[Optional[str], Optional[str]]:
        """Read the requirer-provided ``user``/``group`` from the ldap relation."""
        relation = self.model.get_relation(LDAP_RELATION, relation_id)
        if not relation or not relation.app:
            return None, None
        data = relation.data[relation.app]
        return data.get("user"), data.get("group")

    def _apply_group_membership(
        self,
        user_pk: int,
        old_group: Optional[str],
        new_group: Optional[str],
    ) -> None:
        """Adopt-only group membership: move the bind user between existing groups.

        Groups are never created. A requested group that does not exist is skipped
        with a log; full-directory search remains granted via the RBAC role.
        """
        if (old_group or "") == (new_group or ""):
            return
        if old_group:
            if old_uuid := self._api_client.get_group_by_name(old_group):
                self._api_client.remove_user_from_group(old_uuid, user_pk)
        if new_group:
            if new_uuid := self._api_client.get_group_by_name(new_group):
                self._api_client.add_user_to_group(new_uuid, user_pk)
            else:
                logger.info(
                    "Requested LDAP group '%s' not found on Authentik; skipping membership",
                    new_group,
                )

    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """Build the pebble layer from all env var sources."""
        info = self.server_info.get_info()
        outpost_token = self._get_outpost_token()
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

    def _remove_peer_data(self, key: str) -> None:
        """Remove a value from the peer application databag as leader."""
        if self.unit.is_leader() and (peers := self._peers):
            peers.data[self.app].pop(key, None)

    def _read_outpost_token_secret(self, secret_id: str) -> Optional[str]:
        """Read an outpost token from an application-owned secret."""
        try:
            return self.model.get_secret(id=secret_id).get_content().get("token")
        except (ops.SecretNotFoundError, ops.ModelError):
            logger.warning("Outpost token secret %s is not readable", secret_id)
            return None

    def _store_outpost_token(self, token: str) -> str:
        """Store and verify the outpost token, returning its secret ID."""
        secret_id = self._get_peer_data("outpost_token_secret_id")
        if secret_id:
            secret = self.model.get_secret(id=secret_id)
            secret.set_content({"token": token})
        else:
            try:
                secret = self.model.get_secret(label=self._outpost_token_label)
                secret.set_content({"token": token})
            except ops.SecretNotFoundError:
                secret = self.app.add_secret({"token": token}, label=self._outpost_token_label)
            secret_id = secret.id

        if self._read_outpost_token_secret(secret_id) != token:
            raise RuntimeError("Failed to verify outpost token secret")

        self._set_peer_data("outpost_token_secret_id", secret_id)
        return secret_id

    def _get_outpost_token(self) -> Optional[str]:
        """Resolve the outpost token from its application-owned secret."""
        if secret_id := self._get_peer_data("outpost_token_secret_id"):
            return self._read_outpost_token_secret(secret_id)
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

    def _ensure_search_authorization(self, provider_pk: int) -> None:
        """Grant full-directory search to all bind users via a provider-scoped role.

        Creates (or adopts) a deployment-owned role, assigns the
        ``search_full_directory`` permission scoped to exactly this LDAP provider,
        strictly verifies the grant is object-scoped, then adds every tracked bind
        user to the role. Role membership is idempotent on Authentik.

        Args:
            provider_pk: The primary key of this deployment's LDAP provider.
        """
        prev_role_uuid = self._get_peer_data("search_role_uuid")
        role = self._api_client.get_or_create_role(self._search_role_name)
        verified_pk = self._get_peer_data("search_permission_verified")
        # Re-assign and re-verify only when the provider changed or the role was
        # recreated (a new UUID means the prior grant is gone); otherwise skip the
        # redundant assign+verify round-trip on every config change.
        already_verified = verified_pk == str(provider_pk) and prev_role_uuid == role.pk
        if not already_verified:
            self._api_client.assign_provider_search_permission(role.pk, provider_pk)
            self._set_peer_data("search_permission_verified", str(provider_pk))
        self._set_peer_data("search_role_uuid", role.pk)

        for relation in self.model.relations.get(LDAP_RELATION, []):
            creds = self._get_relation_credentials(relation.id)
            if user_id := creds.get("user_id"):
                self._api_client.add_user_to_role(role.pk, int(user_id))

    def _verify_and_update_existing_resources(
        self,
        provider_pk_peer: Optional[str],
        outpost_uuid_peer: Optional[str],
        outpost_token_peer: Optional[str],
        base_dn: Optional[str],
        search_mode: str,
        bind_mode: str,
        mfa_support: bool,
        config_unchanged: bool,
    ) -> bool:
        """Verify existing outpost resources and reconcile configuration.

        Args:
            provider_pk_peer: Cached provider primary key.
            outpost_uuid_peer: Cached outpost UUID.
            outpost_token_peer: Cached outpost token.
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.
            config_unchanged: True if configuration matches cached values.

        Returns:
            bool: True if resources are verified and configuration reconciled.
                  False if the cached outpost is gone and re-provisioning is required.
        """
        if not (provider_pk_peer and outpost_uuid_peer and outpost_token_peer):
            return False

        try:
            self._api_client.check_outpost_exists(outpost_uuid_peer)
            provider_pk = int(provider_pk_peer)

            if not config_unchanged:
                logger.info("Configuration changed. Updating existing LDAP Provider config.")
                self._api_client.update_provider_config(
                    provider_pk=provider_pk,
                    base_dn=base_dn or "",
                    search_mode=search_mode,
                    bind_mode=bind_mode,
                    mfa_support=mfa_support,
                )
                self._set_peer_config_metadata(base_dn, search_mode, bind_mode, mfa_support)
                self._ensure_search_authorization(provider_pk)
            return True
        except AuthentikNotFoundError:
            logger.info("Stored Authentik outpost no longer exists; reprovisioning")
            return False

    def _provision_fresh_resources(
        self,
        base_dn: Optional[str],
        search_mode: str,
        bind_mode: str,
        mfa_support: bool,
    ) -> None:
        """Create and sync fresh Provider, Application, and Outpost resources.

        Args:
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.
        """
        provider_pk = self._api_client.get_or_create_provider(
            name=self._provider_name,
            base_dn=base_dn or "",
            search_mode=search_mode,
            bind_mode=bind_mode,
            mfa_support=mfa_support,
        )

        self._api_client.get_or_create_application(
            name=self._application_name,
            slug=self._application_name,
            provider_pk=provider_pk,
        )

        outpost_pk, token_identifier = self._api_client.get_or_create_outpost(
            name=self._outpost_name,
            provider_pk=provider_pk,
        )

        outpost_token = self._api_client.get_token_key(token_identifier)

        # Store identifiers in peer relation and keep the token in an application secret.
        self._set_peer_data("provider_pk", str(provider_pk))
        self._set_peer_data("outpost_uuid", outpost_pk)
        self._store_outpost_token(outpost_token)
        self._set_peer_config_metadata(base_dn, search_mode, bind_mode, mfa_support)

        # Grant full-directory search to bind users through a provider-scoped role.
        self._ensure_search_authorization(provider_pk)

        logger.info(
            "Successfully provisioned Authentik resources: Provider ID %s, Outpost UUID %s",
            provider_pk,
            outpost_pk,
        )

    @cached_property
    def _api_client(self) -> Optional[AuthentikApiClient]:
        """Build the Authentik API client once per charm instance (per event).

        Returns:
            An API client when server info is ready, otherwise None.
        """
        info = self.server_info.get_info()
        if not info:
            return None
        return AuthentikApiClient(
            info.host, info.api_token, insecure=self._config.authentik_host_insecure
        )

    def _provision_authentik_resources(self) -> None:
        """Provision the Upstream Provider and Outpost on Authentik."""
        if not self.unit.is_leader():
            return

        base_dn = self.model.config.get("base_dn")
        search_mode = self.model.config.get("search_mode", "cached")
        bind_mode = self.model.config.get("bind_mode", "cached")
        mfa_support = bool(self.model.config.get("mfa_support", False))

        provider_pk_peer = self._get_peer_data("provider_pk")
        outpost_uuid_peer = self._get_peer_data("outpost_uuid")
        outpost_token_peer = self._get_outpost_token()

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

        if self._verify_and_update_existing_resources(
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
            parts = key.split("_")
            if len(parts) == 2 and parts[0] == "client":
                try:
                    tracked.add(int(parts[1]))
                except ValueError:
                    continue
        return tracked

    def _get_relation_credentials(self, relation_id: int) -> dict[str, str]:
        """Get a relation's tracked identity from peer data."""
        data_str = self._get_peer_data(f"client_{relation_id}")
        if data_str:
            try:
                return json.loads(data_str)
            except (TypeError, json.JSONDecodeError):
                pass
        return {}

    def _clear_relation_credentials(self, relation_id: int) -> None:
        """Remove peer tracking for a relation."""
        self._remove_peer_data(f"client_{relation_id}")

    def _delete_orphaned_relation(self, relation_id: int) -> None:
        """Delete an orphaned relation's service account and then clear peer data."""
        creds = self._get_relation_credentials(relation_id)
        if user_id := creds.get("user_id"):
            try:
                self._api_client.delete_user(int(user_id))
                logger.info(
                    "Successfully deleted Authentik service account user ID %s for relation %s",
                    user_id,
                    relation_id,
                )
            except AuthentikNotFoundError:
                logger.info("Authentik service account %s was already absent", user_id)
        self._clear_relation_credentials(relation_id)

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

        for relation_id in orphaned_ids:
            self._delete_orphaned_relation(relation_id)

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
        for step in [
            self._ensure_traefik_route,
            self._ensure_authentik_resources,
            self._ensure_ldap_provider,
        ]:
            try:
                can_plan = can_plan and step()
            except CharmError as e:
                can_plan = False
                logger.exception("Error in %s: %s", step.__name__, e)

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

        if not self.model.relations.get(SERVER_INFO_RELATION):
            event.add_status(ops.BlockedStatus("missing authentik-server-info relation"))
            return

        if not self.server_info.is_ready():
            event.add_status(ops.WaitingStatus("waiting for authentik-server-info data"))
            return

        if not self._get_outpost_token():
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
        if self.unit.is_leader() and self._api_client is not None:
            self._provision_authentik_resources()

        return bool(self._get_outpost_token())

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
        requested_user, requested_group = self._requested_ldap_identity(relation_id)

        creds = self._get_relation_credentials(relation_id)
        user_id = creds.get("user_id")
        password = self.ldap_provider.get_bind_password(relation_id)

        if self.unit.is_leader() and not user_id:
            password = self._provision_service_account(
                relation_id, requested_user, requested_group
            )
            creds = self._get_relation_credentials(relation_id)
            user_id = creds.get("user_id")

        username = creds.get("username")
        if self.unit.is_leader() and user_id and username and not password:
            password = self._rotate_bind_password(int(user_id))

        # Reconcile requirer-requested identity changes (rename / group move).
        if self.unit.is_leader() and user_id and username:
            username = self._reconcile_requested_identity(
                relation_id, int(user_id), username, requested_user, requested_group
            )

        if not (user_id and username and password):
            logger.info("Waiting for peer relation and bind secret for relation %s", relation_id)
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
        if not self.server_info.is_ready() or self._api_client is None:
            return False

        # Clean up any orphaned relations
        if self.unit.is_leader():
            try:
                self._cleanup_orphaned_relations()
            except AuthentikApiError as e:
                # Retain peer-data tracking on a transient failure so the next
                # reconcile retries; let programming errors propagate.
                logger.error("Failed to clean up orphaned relations: %s", e)

        relations = self.model.relations.get(LDAP_RELATION, [])
        if not relations:
            return True

        success = True
        for relation in relations:
            success &= self._update_ldap_relation(relation, self._ldap_host)

        return success

    def _rotate_bind_password(self, user_pk: int) -> str:
        """Rotate and return the password for an existing LDAP bind user."""
        password = secrets.token_urlsafe(16)
        self._api_client.set_user_password(user_pk, password)
        return password

    def _provision_service_account(
        self,
        relation_id: int,
        requested_user: Optional[str] = None,
        requested_group: Optional[str] = None,
    ) -> str:
        """Provision an Authentik user account for an LDAP bind relation."""
        user_pk, username = self._api_client.create_ldap_bind_user(
            self._bind_user_name(relation_id, requested_user)
        )

        password = secrets.token_urlsafe(16)
        self._api_client.set_user_password(user_pk, password)

        # Grant full-directory search by adding the user to the provider-scoped role.
        role_uuid = self._get_peer_data("search_role_uuid")
        provider_pk_peer = self._get_peer_data("provider_pk")
        if not role_uuid and provider_pk_peer:
            role = self._api_client.get_or_create_role(self._search_role_name)
            self._api_client.assign_provider_search_permission(role.pk, int(provider_pk_peer))
            role_uuid = role.pk
            self._set_peer_data("search_role_uuid", role_uuid)
            self._set_peer_data("search_permission_verified", provider_pk_peer)
        if role_uuid:
            self._api_client.add_user_to_role(role_uuid, user_pk)
        else:
            logger.warning(
                "Search role is not ready; bind user %s cannot search until provisioning completes",
                username,
            )

        # Adopt the requirer-requested group if it already exists.
        self._apply_group_membership(user_pk, None, requested_group)

        self._set_peer_data(
            f"client_{relation_id}",
            json.dumps({
                "user_id": str(user_pk),
                "username": username,
                "last_user": requested_user or "",
                "last_group": requested_group or "",
            }),
        )
        logger.info(
            "Successfully provisioned LDAP Bind User '%s' (ID %s) for relation %s",
            username,
            user_pk,
            relation_id,
        )
        return password

    def _reconcile_requested_identity(
        self,
        relation_id: int,
        user_pk: int,
        current_username: str,
        requested_user: Optional[str],
        requested_group: Optional[str],
    ) -> str:
        """Reconcile requirer ``user``/``group`` changes for an existing bind user.

        Renames the bind user when the requested name changes (refusing to steal an
        occupied username) and moves adopt-only group membership. Returns the
        effective username.
        """
        creds = self._get_relation_credentials(relation_id)
        last_user = creds.get("last_user", "")
        last_group = creds.get("last_group", "")
        req_user = requested_user or ""
        req_group = requested_group or ""
        # Only act on genuine requirer changes (tracked user/group differs).
        if req_user == last_user and req_group == last_group:
            return current_username

        username = current_username
        if req_user != last_user:
            target = self._bind_user_name(relation_id, requested_user)
            if target != username:
                conflict = self._api_client.find_user_by_username(target)
                if conflict and conflict.pk != user_pk:
                    raise AuthentikMigrationError(
                        f"Target bind username {target!r} is owned by another user"
                    )
                self._api_client.rename_user(user_pk, target)
                username = target

        if req_group != last_group:
            self._apply_group_membership(user_pk, last_group, req_group)

        self._set_peer_data(
            f"client_{relation_id}",
            json.dumps({
                "user_id": str(user_pk),
                "username": username,
                "last_user": requested_user or "",
                "last_group": req_group,
            }),
        )
        return username

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
