#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm the Authentik LDAP outpost application."""

import logging
import secrets
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

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
    IngressIntegration,
    LdapProviderIntegration,
    ServerInfoIntegration,
    TracingData,
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
        self._config = CharmConfig(self.model.config)

        self.server_info = ServerInfoIntegration(self)
        self.ldap_provider = LdapProviderIntegration(self)
        self.ingress = IngressIntegration(self)

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
            self.on[PEER_RELATION].relation_joined,
            self.on[PEER_RELATION].relation_changed,
            self.on[LDAP_RELATION].relation_joined,
            self.on[LDAP_RELATION].relation_changed,
            self.server_info.on.info_changed,
            self.server_info.on.info_removed,
            self.ingress.ldap_requirer.on.ready,
            self.ingress.ldaps_requirer.on.ready,
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

        # Create Authentik API Client
        client = AuthentikApiClient(info.host, info.bootstrap_token)

        # Create/Sync Provider
        provider_name = f"ldap-provider-{self.app.name}"
        provider_pk = client.get_or_create_provider(
            name=provider_name,
            base_dn=base_dn,
            search_mode=search_mode,
            bind_mode=bind_mode,
            mfa_support=mfa_support,
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

        logger.info(
            "Successfully provisioned Authentik resources: Provider ID %s, Outpost UUID %s",
            provider_pk,
            outpost_pk,
        )

    def _on_ldap_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Handle the relation broken event for LDAP consumers."""
        if self.unit.is_leader():
            relation_id = event.relation.id
            user_id = self._get_peer_data(f"client_{relation_id}_user_id")
            if user_id:
                info = self.server_info.get_info()
                if info:
                    try:
                        client = AuthentikApiClient(info.host, info.bootstrap_token)
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

                # Clean up peer data
                if peers := self._peers:
                    for suffix in ["user_id", "username", "password"]:
                        key = f"client_{relation_id}_{suffix}"
                        if key in peers.data[self.app]:
                            del peers.data[self.app][key]

        self._on_holistic_handler(event)

    def _on_holistic_handler(self, event: ops.EventBase) -> None:
        """Handle events holistically by setting status and running handler."""
        self.unit.status = ops.MaintenanceStatus("Configuring resources")
        self._holistic_handler(event)

    def _holistic_handler(self, event: ops.EventBase) -> None:
        """Run holistic reconciliation."""
        if not all(condition(self) for condition in NOOP_CONDITIONS):
            return

        if self.unit.is_leader():
            try:
                self._provision_authentik_resources()
                self._api_error = None
            except Exception as e:
                self._api_error = f"API error: {e}"
                logger.error("Error during resource provisioning: %s", e)
                return

        if not self._get_peer_data("outpost_token"):
            logger.info(
                "Outpost token not available in peer data yet; skipping Pebble layer planning"
            )
            return

        self._ensure_pebble_layer()
        self._ensure_ldap_provider()

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

    def _ensure_pebble_layer(self) -> None:
        """Ensure the Pebble layer is applied."""
        info = self.server_info.get_info()
        outpost_token = self._get_peer_data("outpost_token")
        if not info or not outpost_token:
            return

        outpost_env = OutpostEnv(host=info.host, token=outpost_token)
        layer = self._pebble.render_pebble_layer(
            outpost_env,
            self._config,
            TracingData.load(self.tracing_requirer),
        )
        try:
            self._container.add_layer(WORKLOAD_CONTAINER, layer, combine=True)
            relations = self.model.relations.get(LDAP_RELATION, [])
            if relations:
                try:
                    self._pebble.plan(layer)
                except PebbleError as e:
                    logger.error("Failed to plan Pebble layer: %s", e)
            else:
                try:
                    service = self._container.get_service(WORKLOAD_CONTAINER)
                    if service.is_running():
                        self._container.stop(WORKLOAD_CONTAINER)
                except Exception:
                    pass
        except Exception as e:
            logger.error("Failed to add Pebble layer: %s", e)

    def _ensure_ldap_provider(self) -> None:
        """Ensure LDAP provider relation data is updated for all consumers."""
        if not self.server_info.is_ready():
            return

        relations = self.model.relations.get(LDAP_RELATION, [])
        if not relations:
            return

        url = self.ingress.ldap_requirer.url
        if url:
            parsed = urlparse(url)
            address = parsed.hostname or url
        else:
            address = str(self.model.get_binding(LDAP_RELATION).network.bind_address)

        for relation in relations:
            relation_id = relation.id

            if self.unit.is_leader():
                user_id = self._get_peer_data(f"client_{relation_id}_user_id")
                if not user_id:
                    self._provision_service_account(relation_id)
                    if self._api_error:
                        return

            user_id = self._get_peer_data(f"client_{relation_id}_user_id")
            username = self._get_peer_data(f"client_{relation_id}_username")
            password = self._get_peer_data(f"client_{relation_id}_password")

            if not (user_id and username and password):
                logger.info(
                    "Waiting for peer relation to provide credentials for relation %s",
                    relation_id,
                )
                continue

            base_dn = self.model.config.get("base_dn")
            bind_dn = f"cn={username},ou=users,{base_dn}"

            self.ldap_provider.update_relation_data(
                relation_id=relation_id,
                unit_address=address,
                base_dn=base_dn,
                bind_dn=bind_dn,
                password=password,
            )

    def _provision_service_account(self, relation_id: int) -> None:
        """Provision an Authentik Service Account for a given relation ID."""
        info = self.server_info.get_info()
        if not info:
            return

        try:
            client = AuthentikApiClient(info.host, info.bootstrap_token)
            sa_name = f"ldap-client-{self.app.name}-{relation_id}"
            user_pk, username = client.create_service_account(sa_name)

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

            self._set_peer_data(f"client_{relation_id}_user_id", str(user_pk))
            self._set_peer_data(f"client_{relation_id}_username", username)
            self._set_peer_data(f"client_{relation_id}_password", password)
            logger.info(
                "Successfully provisioned Service Account '%s' (ID %s) for relation %s",
                username,
                user_pk,
                relation_id,
            )
            self._api_error = None
        except Exception as e:
            logger.error(
                "Failed to provision Service Account for relation %s: %s",
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
