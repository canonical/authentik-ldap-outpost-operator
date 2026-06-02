# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration helpers for charm relations."""

import logging
from typing import Any, Optional

from constants import (
    AUTHENTIK_INSECURE,
    BASE_DN,
    BIND_DN,
    INGRESS_RELATION,
    LDAP_PORT,
    LDAPS_INGRESS_RELATION,
    LDAPS_PORT,
    SERVER_INFO_RELATION,
)
from ops.charm import CharmBase
from ops.framework import ObjectEvents
from ops.model import Model

logger = logging.getLogger(__name__)

try:
    from charms.authentik_server.v0.authentik_server_info import (
        AuthentikServerInfoRequirer,
    )
    from charms.glauth_k8s.v0.ldap import LdapProvider, LdapProviderData
    from charms.traefik_k8s.v2.ingress import IngressPerUnitRequirer

    HAS_AUTHENTIK_LIB = True
except ImportError:
    HAS_AUTHENTIK_LIB = False
    AuthentikServerInfoRequirer = None
    LdapProvider = None
    LdapProviderData = None
    IngressPerUnitRequirer = None


class ServerInfoIntegration:
    """Integration with authentik-server-info relation."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._server_info = None
        if HAS_AUTHENTIK_LIB and AuthentikServerInfoRequirer:
            self._server_info = AuthentikServerInfoRequirer(
                charm, relation_name=SERVER_INFO_RELATION
            )

    def is_ready(self) -> bool:
        """Check if server info relation is ready."""
        if self._server_info:
            return self._server_info.is_ready()
        relation = self._charm.model.get_relation(SERVER_INFO_RELATION)
        if not relation or not relation.app:
            return False
        data = relation.data[relation.app]
        return bool(data.get("authentik_host"))

    def get_host(self) -> Optional[str]:
        """Get authentik host URL."""
        if self._server_info:
            return self._server_info.get_authentik_host()
        relation = self._charm.model.get_relation(SERVER_INFO_RELATION)
        if not relation or not relation.app:
            return None
        return relation.data[relation.app].get("authentik_host")

    def get_token(self) -> Optional[str]:
        """Get authentik bootstrap token."""
        if self._server_info:
            return self._server_info.get_authentik_token()
        return None

    def get_bootstrap_password(self) -> Optional[str]:
        """Get bootstrap password from secret."""
        if self._server_info:
            return self._server_info.get_bootstrap_password()
        relation = self._charm.model.get_relation(SERVER_INFO_RELATION)
        if not relation or not relation.app:
            return None
        secret_id = relation.data[relation.app].get("bootstrap_password_secret_id")
        if not secret_id:
            return None
        try:
            secret = self._charm.model.get_secret(id=secret_id)
            return secret.get_content().get("bootstrap-password")
        except Exception:
            return None

    def build_env(self) -> dict[str, str]:
        """Build environment variables from server info."""
        if not self.is_ready():
            return {}
        host = self.get_host() or ""
        token = self.get_token() or ""
        return {
            "AUTHENTIK_HOST": host,
            "AUTHENTIK_TOKEN": token,
            "AUTHENTIK_INSECURE": AUTHENTIK_INSECURE,
        }

    @property
    def events(self) -> ObjectEvents | None:
        """Return the server info events if available."""
        if self._server_info:
            return self._server_info.on
        return None


class LdapProviderIntegration:
    """Integration providing LDAP data to consumers."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._provider = LdapProvider(charm) if LdapProvider else None

    @property
    def provider(self) -> Any:
        """Return the LDAP provider instance."""
        return self._provider

    def update_data(self, unit_address: str, bootstrap_password: str) -> None:
        """Update LDAP relation data for consumers.

        Args:
            unit_address: The unit's network address.
            bootstrap_password: The LDAP bind password.
        """
        if not self._provider or not LdapProviderData:
            return
        data = LdapProviderData(
            urls=[f"ldap://{unit_address}:{LDAP_PORT}"],
            ldaps_urls=[f"ldaps://{unit_address}:{LDAPS_PORT}"],
            base_dn=BASE_DN,
            starttls=False,
            bind_dn=BIND_DN,
            bind_password=bootstrap_password,
            auth_method="simple",
        )
        self._provider.update_relations_app_data(data)


class IngressIntegration:
    """Integration with Traefik for ingress."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._ldap_ingress = None
        self._ldaps_ingress = None
        if IngressPerUnitRequirer:
            self._ldap_ingress = IngressPerUnitRequirer(
                charm, relation_name=INGRESS_RELATION, port=LDAP_PORT, mode="tcp"
            )
            self._ldaps_ingress = IngressPerUnitRequirer(
                charm, relation_name=LDAPS_INGRESS_RELATION, port=LDAPS_PORT, mode="tcp"
            )

    @property
    def ldap_events(self) -> Any:
        """Return the LDAP ingress events."""
        return self._ldap_ingress.on if self._ldap_ingress else None

    @property
    def ldaps_events(self) -> Any:
        """Return the LDAPS ingress events."""
        return self._ldaps_ingress.on if self._ldaps_ingress else None


class Integrations:
    """Container for all charm integrations."""

    def __init__(self, charm: CharmBase):
        self.server_info = ServerInfoIntegration(charm)
        self.ldap_provider = LdapProviderIntegration(charm)
        self.ingress = IngressIntegration(charm)

    @staticmethod
    def get_unit_address(model: Model, relation_name: str) -> str:
        """Get the unit's network address.

        Args:
            model: The charm model.
            relation_name: Relation to use for binding.

        Returns:
            String representation of bind address.
        """
        binding = model.get_binding(relation_name)
        return str(binding.network.bind_address)
