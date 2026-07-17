# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration helpers for charm relations."""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from charm import AuthentikLdapCharm


from charms.authentik_server.v0.authentik_server_info import (
    AuthentikServerInfoRequirer,
)
from charms.glauth_k8s.v0.ldap import LdapProvider, LdapProviderData
from charms.tempo_coordinator_k8s.v0.tracing import TracingEndpointRequirer
from charms.traefik_k8s.v0.traefik_route import TraefikRouteRequirer
from jinja2 import Template
from ops.charm import CharmBase

from constants import (
    AUTHENTIK_INSECURE,
    EXTERNAL_LDAP_PORT,
    LDAP_PORT,
    LDAP_RELATION,
    LDAPS_PORT,
    SERVER_INFO_RELATION,
    TRAEFIK_ROUTE_RELATION,
)
from env_vars import EnvVarConvertible, EnvVars

logger = logging.getLogger(__name__)


@dataclass
class ServerInfo:
    """Server info retrieved from the relation."""

    host: str
    bootstrap_token: str
    bootstrap_password: str


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
        ldaps_enabled: bool = False,
        external_host: Optional[str] = None,
    ) -> None:
        """Update specific LDAP relation data for a consumer.

        Args:
            relation_id: The ID of the relation to update.
            unit_address: The unit's network address.
            base_dn: The Base DN of the directory.
            bind_dn: The Bind DN for the service account.
            password: The password for the service account.
            ldaps_enabled: Whether secure LDAPS is enabled.
            external_host: Optional external host from Traefik.
        """
        ldaps_urls = (
            [f"ldaps://{external_host}:{LDAPS_PORT}"]
            if ldaps_enabled and external_host
            else [f"ldaps://{unit_address}:{LDAPS_PORT}"]
        )
        data = LdapProviderData(
            urls=[f"ldap://{unit_address}:{LDAP_PORT}"],
            ldaps_urls=ldaps_urls,
            base_dn=base_dn,
            starttls=False,
            bind_dn=bind_dn,
            bind_password=password,
            auth_method="simple",
        )
        self._provider.update_relations_app_data(data, relation_id=relation_id)

        # Write ldaps_enabled=true/false directly to the app databag
        relation = self._charm.model.get_relation(LDAP_RELATION, relation_id)
        if relation and self._charm.unit.is_leader():
            relation.data[self._charm.app]["ldaps_enabled"] = str(ldaps_enabled).lower()


class TraefikRouteIntegration:
    """Integration with Traefik for L4 route configuration."""

    def __init__(self, charm: "AuthentikLdapCharm"):
        self._charm = charm
        self._requirer = TraefikRouteRequirer(
            charm,
            charm.model.get_relation(TRAEFIK_ROUTE_RELATION),
            relation_name=TRAEFIK_ROUTE_RELATION,
        )

    @property
    def requirer(self) -> TraefikRouteRequirer:
        """The TraefikRouteRequirer instance."""
        return self._requirer

    @property
    def ldaps_enabled(self) -> bool:
        """Check if Traefik route has LDAPS enabled by inspecting the scheme.

        The assumption is that if Traefik reports its scheme as "https", it possesses
        a valid TLS certificate. This implies Traefik can also perform TLS termination
        for TCP traffic (LDAPS) using that same certificate.
        """
        return self.is_ready() and self._requirer.scheme == "https"

    def is_ready(self) -> bool:
        """Check if Traefik route is ready with a valid external host."""
        return bool(self._requirer.is_ready() and self._requirer.external_host)

    @property
    def external_host(self) -> str:
        """The external host from Traefik."""
        return self._requirer.external_host

    def submit_route(self) -> None:
        """Render and submit static and dynamic route configuration to Traefik."""
        relation = self._charm.model.get_relation(TRAEFIK_ROUTE_RELATION)
        if not relation or not self._charm.unit.is_leader():
            return

        # Renders templates/traefik-route.json.j2
        with open("templates/traefik-route.json.j2", "r") as f:
            template_content = f.read()

        model_name = self._charm.model.name
        app_name = self._charm.app.name
        identifier = f"{model_name}-{app_name}"

        template = Template(template_content)
        ingress_domain = self._charm._config.ingress_domain
        rule = f"HostSNI(`{ingress_domain}`)" if ingress_domain else "HostSNI(`*`)"
        expose_ldap_ingress = self._charm._config.expose_ldap_ingress

        rendered_json = template.render(
            identifier=identifier,
            app=app_name,
            model=model_name,
            rule=rule,
            ldap_port=LDAP_PORT,
            expose_ldap_ingress=expose_ldap_ingress,
        )

        dynamic_config = json.loads(rendered_json)

        static_config = {
            "entryPoints": {
                "ldaps": {
                    "address": f":{LDAPS_PORT}",
                    "proxyProtocol": {"insecure": True},
                }
            }
        }
        if expose_ldap_ingress:
            static_config["entryPoints"]["ldap"] = {
                "address": f":{EXTERNAL_LDAP_PORT}",
                "proxyProtocol": {"insecure": True},
            }

        self._requirer.submit_to_traefik(config=dynamic_config, static=static_config)


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
