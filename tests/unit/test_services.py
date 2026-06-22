# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


from constants import COMMAND, LDAP_PORT, SERVICE_NAME
from services import AuthentikLdapWorkload, PebbleService


class TestAuthentikLdapWorkload:
    """Tests for AuthentikLdapWorkload."""

    def test_build_layer_returns_correct_structure(self):
        """Test that build_layer returns a valid LayerDict."""
        layer = AuthentikLdapWorkload.build_layer(
            {
                "AUTHENTIK_HOST": "http://server:9000",
                "AUTHENTIK_TOKEN": "token123",
            }
        )

        assert SERVICE_NAME in layer["services"]
        service = layer["services"][SERVICE_NAME]
        assert service["command"] == COMMAND
        assert service["startup"] == "enabled"
        assert service["environment"] == {
            "AUTHENTIK_HOST": "http://server:9000",
            "AUTHENTIK_TOKEN": "token123",
        }
        assert "health" in layer["checks"]
        assert layer["checks"]["health"]["tcp"]["port"] == LDAP_PORT

    def test_build_layer_with_empty_env(self):
        """Test build_layer with empty environment variables."""
        layer = AuthentikLdapWorkload.build_layer({})

        assert layer["services"][SERVICE_NAME]["environment"] == {}

    def test_build_layer_includes_health_check(self):
        """Test that build_layer includes proper health check."""
        layer = AuthentikLdapWorkload.build_layer({})

        health = layer["checks"]["health"]
        assert health["level"] == "alive"
        assert health["tcp"]["port"] == LDAP_PORT


class TestPebbleService:
    """Tests for PebbleService."""

    def test_pebble_service_initializes_with_container(self):
        """Test that PebbleService takes a container in constructor."""

        class MockContainer:
            pass

        container = MockContainer()
        service = PebbleService(container)
        assert service._container is container

    def test_workload_property(self):
        """Test that PebbleService exposes the workload."""

        class MockContainer:
            pass

        container = MockContainer()
        service = PebbleService(container)
        assert hasattr(service, "_workload")
