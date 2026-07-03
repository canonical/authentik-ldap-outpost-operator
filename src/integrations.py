# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration helpers for charm relations."""

import logging
from dataclasses import dataclass
from typing import Optional

from charms.authentik_server.v0.authentik_server_info import (
    AuthentikServerInfoRequirer,
)
from charms.glauth_k8s.v0.ldap import LdapProvider, LdapProviderData
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops.charm import CharmBase

from constants import (
    AUTHENTIK_INSECURE,
    INGRESS_RELATION,
    LDAP_PORT,
    LDAPS_INGRESS_RELATION,
    LDAPS_PORT,
    SERVER_INFO_RELATION,
)
from env_vars import EnvVarConvertible, EnvVars

logger = logging.getLogger(__name__)


@dataclass
class ServerInfo:
    """Server info retrieved from the relation."""

    host: str
    bootstrap_token: str
    bootstrap_password: str


class IngressPerUnitRequirer(IngressPerAppRequirer):
    """Shim for IngressPerUnitRequirer using IngressPerAppRequirer."""

    def __init__(self, *args, **kwargs):
        kwargs.pop("mode", None)
        super().__init__(*args, **kwargs)


class ServerInfoIntegration(EnvVarConvertible):
    """Integration with authentik-server-info relation."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._server_info = AuthentikServerInfoRequirer(charm, relation_name=SERVER_INFO_RELATION)

    @property
    def on(self):
        """The ServerInfoRequirer events."""
        return self._server_info.on

    def is_ready(self) -> bool:
        """Check if server info relation is ready."""
        return self._server_info.is_ready()

    def get_info(self) -> Optional[ServerInfo]:
        """Get the ServerInfo object."""
        if not self.is_ready():
            return None
        host = self._server_info.get_authentik_host()
        token = self._server_info.get_authentik_token()
        password = self._server_info.get_bootstrap_password()
        if not (host and token and password):
            return None
        return ServerInfo(host=host, bootstrap_token=token, bootstrap_password=password)

    def to_env_vars(self) -> EnvVars:
        """Build environment variables from server info."""
        info = self.get_info()
        if not info:
            return {}
        return {
            "AUTHENTIK_HOST": info.host,
            "AUTHENTIK_TOKEN": info.bootstrap_token,
            "AUTHENTIK_INSECURE": AUTHENTIK_INSECURE,
        }


class LdapProviderIntegration:
    """Integration providing LDAP data to consumers."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._provider = LdapProvider(charm)

    @property
    def provider(self) -> LdapProvider:
        """The LDAP provider instance."""
        return self._provider

    def update_relation_data(
        self,
        relation_id: int,
        unit_address: str,
        base_dn: str,
        bind_dn: str,
        password: str,
    ) -> None:
        """Update specific LDAP relation data for a consumer.

        Args:
            relation_id: The ID of the relation to update.
            unit_address: The unit's network address.
            base_dn: The Base DN of the directory.
            bind_dn: The Bind DN for the service account.
            password: The password for the service account.
        """
        data = LdapProviderData(
            urls=[f"ldap://{unit_address}:{LDAP_PORT}"],
            ldaps_urls=[f"ldaps://{unit_address}:{LDAPS_PORT}"],
            base_dn=base_dn,
            starttls=False,
            bind_dn=bind_dn,
            bind_password=password,
            auth_method="simple",
        )
        self._provider.update_relations_app_data(data, relation_id=relation_id)


class IngressIntegration:
    """Integration with Traefik for ingress."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._ldap_ingress = IngressPerUnitRequirer(
            charm, relation_name=INGRESS_RELATION, port=LDAP_PORT, mode="tcp"
        )
        self._ldaps_ingress = IngressPerUnitRequirer(
            charm, relation_name=LDAPS_INGRESS_RELATION, port=LDAPS_PORT, mode="tcp"
        )

    @property
    def ldap_requirer(self) -> IngressPerUnitRequirer:
        """The LDAP ingress requirer."""
        return self._ldap_ingress

    @property
    def ldaps_requirer(self) -> IngressPerUnitRequirer:
        """The LDAPS ingress requirer."""
        return self._ldaps_ingress


@dataclass(frozen=True)
class TracingData(EnvVarConvertible):
    """Tracing integration data model."""

    is_ready: bool = False
    http_endpoint: str = ""

    def to_env_vars(self) -> EnvVars:
        """Convert to environment variable mapping."""
        if not self.is_ready or not self.http_endpoint:
            return {}
        return {"AUTHENTIK_OUTPOST__DISCOVER__OTLP_TRACES_ENDPOINT": self.http_endpoint}

    @classmethod
    def load(cls, requirer: TracingEndpointRequirer) -> "TracingData":
        """Load TracingData from the TracingEndpointRequirer."""
        if not requirer.is_ready():
            return cls()
        endpoint = requirer.get_endpoint("otlp_http")
        if not endpoint:
            return cls()
        return cls(is_ready=True, http_endpoint=endpoint)
