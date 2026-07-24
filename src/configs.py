# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm configuration."""

import logging

import ops
from ops import ConfigData

from env_vars import EnvVars

logger = logging.getLogger(__name__)


class CharmConfig:
    """Charm configuration helper."""

    def __init__(self, charm: ops.CharmBase, config: ConfigData) -> None:
        self._charm = charm
        self._config = config

    def to_env_vars(self) -> EnvVars:
        """Convert configuration to environment variables.

        Returns:
            Dictionary of environment variables.
        """
        # Trust localhost and private subnets (RFC 1918) to ensure cluster/pod IPs are trusted
        trusted_cidrs = ["127.0.0.1/32", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]

        # Dynamically discover Traefik's IP/subnet
        for rel in self._charm.model.relations.get("traefik-route", []):
            for unit in rel.units:
                if subnet := rel.data[unit].get("egress-subnets"):
                    trusted_cidrs.append(subnet)
                elif private_ip := rel.data[unit].get("private-address"):
                    trusted_cidrs.append(private_ip)

        trusted_cidrs_str = ",".join(trusted_cidrs)

        return {
            "AUTHENTIK_LOG_LEVEL": self._config.get("log_level", "info"),
            "AUTHENTIK_INSECURE": "true" if self.authentik_host_insecure else "false",
            "HTTP_PROXY": self._config.get("http_proxy", ""),
            "HTTPS_PROXY": self._config.get("https_proxy", ""),
            "NO_PROXY": self._config.get("no_proxy", ""),
            "AUTHENTIK_LISTEN__TRUSTED_PROXY_CIDRS": trusted_cidrs_str,
        }

    @property
    def authentik_host_insecure(self) -> bool:
        """Whether the outpost skips TLS verification of the Authentik host.

        Returns:
            True to disable TLS verification, False (the secure default) to enforce it.
        """
        return bool(self._config.get("authentik-host-insecure", False))

    @property
    def ingress_domain(self) -> str:
        """The custom domain name to use for the external ingress route.

        Returns:
            The configured ingress domain, or empty string if not configured.
        """
        return self._config.get("ingress_domain", "")

    @property
    def expose_ldap_ingress(self) -> bool:
        """Whether to expose plain LDAP ingress via Traefik.

        Returns:
            True if plain LDAP ingress should be exposed, False otherwise.
        """
        return bool(self._config.get("expose_ldap_ingress", False))
