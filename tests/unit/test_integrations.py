# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from charm import AuthentikLdapCharm
from constants import (
    LDAP_RELATION,
    WORKLOAD_CONTAINER,
)
from integrations import (
    IngressIntegration,
    Integrations,
    LdapProviderIntegration,
    ServerInfoIntegration,
)
from ops import testing


class TestServerInfoIntegration:
    """Tests for ServerInfoIntegration."""

    def test_is_ready_returns_false_without_relation(self):
        """Test is_ready returns False when no relation exists."""
        ctx = testing.Context(AuthentikLdapCharm)
        container = testing.Container(WORKLOAD_CONTAINER, can_connect=True)
        state = testing.State(containers={container})
        ctx.run(ctx.on.pebble_ready(container), state)

        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = ServerInfoIntegration(charm)
        assert not integration.is_ready()

    def test_build_env_returns_empty_when_not_ready(self):
        """Test build_env returns empty dict when relation not ready."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = ServerInfoIntegration(charm)
        env = integration.build_env()

        assert env == {}

    def test_get_host_returns_none_without_relation(self):
        """Test get_host returns None when no relation."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = ServerInfoIntegration(charm)
        assert integration.get_host() is None

    def test_get_token_returns_none_without_relation(self):
        """Test get_token returns None when no relation."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = ServerInfoIntegration(charm)
        assert integration.get_token() is None

    def test_get_bootstrap_password_returns_none_without_relation(self):
        """Test get_bootstrap_password returns None when no relation."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = ServerInfoIntegration(charm)
        assert integration.get_bootstrap_password() is None

    def test_events_property_returns_none(self):
        """Test events property returns None when lib not available."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = ServerInfoIntegration(charm)
        assert integration.events is None


class TestLdapProviderIntegration:
    """Tests for LdapProviderIntegration."""

    def test_provider_property_returns_none_when_lib_not_available(self):
        """Test provider returns None when glauth lib not available."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = LdapProviderIntegration(charm)
        assert integration.provider is None

    def test_update_data_does_nothing_without_provider(self):
        """Test update_data does nothing when provider lib not available."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = LdapProviderIntegration(charm)
        integration.update_data("127.0.0.1", "password123")


class TestIngressIntegration:
    """Tests for IngressIntegration."""

    def test_ldap_events_property_returns_none(self):
        """Test ldap_events returns None when traefik lib not available."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = IngressIntegration(charm)
        assert integration.ldap_events is None

    def test_ldaps_events_property_returns_none(self):
        """Test ldaps_events returns None when traefik lib not available."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integration = IngressIntegration(charm)
        assert integration.ldaps_events is None


class TestIntegrations:
    """Tests for Integrations container."""

    def test_integrations_contain_all_integrations(self):
        """Test Integrations container has all integration objects."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        integrations = Integrations(charm)

        assert isinstance(integrations.server_info, ServerInfoIntegration)
        assert isinstance(integrations.ldap_provider, LdapProviderIntegration)
        assert isinstance(integrations.ingress, IngressIntegration)

    def test_get_unit_address_raises_without_relation(self):
        """Test get_unit_address raises when relation doesn't exist."""
        harness = testing.Harness(AuthentikLdapCharm)
        harness.begin()
        charm = harness.charm

        with pytest.raises(Exception):
            Integrations.get_unit_address(charm.model, LDAP_RELATION)
