# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for relation integrations."""

from typing import Any
from unittest.mock import MagicMock, create_autospec

from charms.authentik_server.v0.authentik_server_info import (
    AuthentikServerInfoRequirer,
)

from integrations import ServerInfoIntegration, TracingData, TraefikRouteIntegration


class TestServerInfoIntegration:
    """Tests for the ServerInfoIntegration wrapper."""

    def test_to_env_vars_returns_env_when_ready(self, mocker: Any) -> None:
        """Test that to_env_vars returns expected environment variables when ready."""
        mock_charm = mocker.MagicMock()
        mock_requirer = create_autospec(AuthentikServerInfoRequirer)
        mocker.patch("integrations.AuthentikServerInfoRequirer", return_value=mock_requirer)

        integration = ServerInfoIntegration(mock_charm)
        mock_requirer.is_ready.return_value = True
        mock_requirer.get_authentik_host.return_value = "http://authentik:9000"
        mock_requirer.get_authentik_token.return_value = "token123"
        mock_requirer.get_bootstrap_password.return_value = "password123"

        env = integration.to_env_vars()
        assert env["AUTHENTIK_HOST"] == "http://authentik:9000"
        assert env["AUTHENTIK_TOKEN"] == "token123"

    def test_to_env_vars_empty_when_not_ready(self, mocker: Any) -> None:
        """Test that to_env_vars returns empty dict when requirer is not ready."""
        mock_charm = mocker.MagicMock()
        mock_requirer = create_autospec(AuthentikServerInfoRequirer)
        mocker.patch("integrations.AuthentikServerInfoRequirer", return_value=mock_requirer)

        integration = ServerInfoIntegration(mock_charm)
        mock_requirer.is_ready.return_value = False

        assert integration.to_env_vars() == {}

    def test_is_ready_delegates_to_requirer(self, mocker: Any) -> None:
        """Test that is_ready delegates directly to the underlying requirer."""
        mock_charm = mocker.MagicMock()
        mock_requirer = create_autospec(AuthentikServerInfoRequirer)
        mocker.patch("integrations.AuthentikServerInfoRequirer", return_value=mock_requirer)

        integration = ServerInfoIntegration(mock_charm)

        mock_requirer.is_ready.return_value = True
        assert integration.is_ready() is True

        mock_requirer.is_ready.return_value = False
        assert integration.is_ready() is False


class TestTracingData:
    """Tests for the TracingData class."""

    def test_load_returns_empty_when_not_ready(self) -> None:
        """Test load returns empty TracingData when requirer is not ready."""
        mock_requirer = MagicMock()
        mock_requirer.is_ready.return_value = False

        data = TracingData.load(mock_requirer)
        assert not data.is_ready
        assert data.http_endpoint == ""
        assert data.to_env_vars() == {}

    def test_load_returns_endpoint_when_ready(self) -> None:
        """Test load returns TracingData with endpoint when requirer is ready."""
        mock_requirer = MagicMock()
        mock_requirer.is_ready.return_value = True
        mock_requirer.get_endpoint.return_value = "http://tempo:4318"

        data = TracingData.load(mock_requirer)
        assert data.is_ready
        assert data.http_endpoint == "http://tempo:4318"

    def test_to_env_vars_returns_otlp_endpoint_when_ready(self) -> None:
        """Test to_env_vars returns correct environment variables when ready."""
        data = TracingData(is_ready=True, http_endpoint="http://tempo:4318")
        env = data.to_env_vars()
        assert env == {"AUTHENTIK_OUTPOST__DISCOVER__OTLP_TRACES_ENDPOINT": "http://tempo:4318"}

    def test_to_env_vars_empty_when_not_ready(self) -> None:
        """Test to_env_vars returns empty dict when no endpoint is set."""
        data = TracingData(is_ready=False, http_endpoint="http://tempo:4318")
        assert data.to_env_vars() == {}


class TestTraefikRouteIntegration:
    """Tests for the TraefikRouteIntegration wrapper."""

    def test_is_ready_delegates_to_requirer(self, mocker: Any) -> None:
        """Test is_ready checks requirer readiness and external host."""
        mock_charm = mocker.MagicMock()
        mock_requirer = MagicMock()
        mocker.patch("integrations.TraefikRouteRequirer", return_value=mock_requirer)

        integration = TraefikRouteIntegration(mock_charm)

        mock_requirer.is_ready.return_value = True
        mock_requirer.external_host = "external.host"
        assert integration.is_ready() is True

        mock_requirer.is_ready.return_value = False
        assert integration.is_ready() is False

        mock_requirer.is_ready.return_value = True
        mock_requirer.external_host = ""
        assert integration.is_ready() is False

    def test_submit_route_submits_config_with_default_wildcard(self, mocker: Any) -> None:
        """Test submit_route fallback to wildcard rule when ingress_domain is unset."""
        mock_charm = mocker.MagicMock()
        mock_charm.model.name = "my-model"
        mock_charm.app.name = "my-app"
        mock_charm.unit.is_leader.return_value = True
        mock_charm._config.ingress_domain = ""
        mock_charm._config.expose_ldap_ingress = False

        mock_requirer = MagicMock()
        mocker.patch("integrations.TraefikRouteRequirer", return_value=mock_requirer)

        # Mock open to return template content with {{ rule }} and {{ ldap_port }}
        template_content = '{"tcp": {"routers": {"juju-{{ identifier }}-tcp-router": {"rule": "{{ rule }}"}, "juju-{{ identifier }}-tcp-router-plain": {"entryPoints": ["ldap"], "rule": "HostSNI(`*`)"}}, "services": {"juju-{{ identifier }}-tcp-service": {"loadBalancer": {"servers": [{"address": "my-app.my-model.svc.cluster.local:{{ ldap_port }}"}]}}}}}'
        mock_open = mocker.mock_open(read_data=template_content)
        mocker.patch("builtins.open", mock_open)

        integration = TraefikRouteIntegration(mock_charm)
        integration.submit_route()

        mock_requirer.submit_to_traefik.assert_called_once_with(
            config={
                "tcp": {
                    "routers": {
                        "juju-my-model-my-app-tcp-router": {"rule": "HostSNI(`*`)"},
                        "juju-my-model-my-app-tcp-router-plain": {
                            "entryPoints": ["ldap"],
                            "rule": "HostSNI(`*`)",
                        },
                    },
                    "services": {
                        "juju-my-model-my-app-tcp-service": {
                            "loadBalancer": {
                                "servers": [{"address": "my-app.my-model.svc.cluster.local:3389"}]
                            }
                        }
                    },
                }
            },
            static={
                "entryPoints": {
                    "ldaps": {"address": ":636", "proxyProtocol": {"insecure": True}},
                    "ldap": {"address": ":3389", "proxyProtocol": {"insecure": True}},
                }
            },
        )

    def test_submit_route_submits_config_with_custom_domain(self, mocker: Any) -> None:
        """Test submit_route renders specific HostSNI rule when ingress_domain is set."""
        mock_charm = mocker.MagicMock()
        mock_charm.model.name = "my-model"
        mock_charm.app.name = "my-app"
        mock_charm.unit.is_leader.return_value = True
        mock_charm._config.ingress_domain = "outpost.example.com"
        mock_charm._config.expose_ldap_ingress = False

        mock_requirer = MagicMock()
        mocker.patch("integrations.TraefikRouteRequirer", return_value=mock_requirer)

        # Mock open to return template content with {{ rule }} and {{ ldap_port }}
        template_content = '{"tcp": {"routers": {"juju-{{ identifier }}-tcp-router": {"rule": "{{ rule }}"}, "juju-{{ identifier }}-tcp-router-plain": {"entryPoints": ["ldap"], "rule": "HostSNI(`*`)"}}, "services": {"juju-{{ identifier }}-tcp-service": {"loadBalancer": {"servers": [{"address": "my-app.my-model.svc.cluster.local:{{ ldap_port }}"}]}}}}}'
        mock_open = mocker.mock_open(read_data=template_content)
        mocker.patch("builtins.open", mock_open)

        integration = TraefikRouteIntegration(mock_charm)
        integration.submit_route()

        mock_requirer.submit_to_traefik.assert_called_once_with(
            config={
                "tcp": {
                    "routers": {
                        "juju-my-model-my-app-tcp-router": {
                            "rule": "HostSNI(`outpost.example.com`)"
                        },
                        "juju-my-model-my-app-tcp-router-plain": {
                            "entryPoints": ["ldap"],
                            "rule": "HostSNI(`*`)",
                        },
                    },
                    "services": {
                        "juju-my-model-my-app-tcp-service": {
                            "loadBalancer": {
                                "servers": [{"address": "my-app.my-model.svc.cluster.local:3389"}]
                            }
                        }
                    },
                }
            },
            static={
                "entryPoints": {
                    "ldaps": {"address": ":636", "proxyProtocol": {"insecure": True}},
                    "ldap": {"address": ":3389", "proxyProtocol": {"insecure": True}},
                }
            },
        )

    def test_submit_route_with_plain_ldap_ingress_enabled(self, mocker: Any) -> None:
        """Test submit_route adds the plain LDAP entrypoint and router when enabled."""
        mock_charm = mocker.MagicMock()
        mock_charm.model.name = "my-model"
        mock_charm.app.name = "my-app"
        mock_charm.unit.is_leader.return_value = True
        mock_charm._config.ingress_domain = ""
        mock_charm._config.expose_ldap_ingress = True

        mock_requirer = MagicMock()
        mocker.patch("integrations.TraefikRouteRequirer", return_value=mock_requirer)

        # Mock open to return template content that has conditional check
        template_content = (
            '{"tcp": {"routers": {'
            '"juju-{{ identifier }}-tcp-router": {"rule": "{{ rule }}"}'
            "{% if expose_ldap_ingress %},"
            '"juju-{{ identifier }}-ldap-tcp-router": {"rule": "HostSNI(`*`)"}'
            "{% endif %}"
            '}, "services": {'
            '"juju-{{ identifier }}-tcp-service": {"loadBalancer": {"servers": [{"address": "my-app.my-model.svc.cluster.local:{{ ldap_port }}"}]}}'
            "}}}"
        )
        mock_open = mocker.mock_open(read_data=template_content)
        mocker.patch("builtins.open", mock_open)

        integration = TraefikRouteIntegration(mock_charm)
        integration.submit_route()

        mock_requirer.submit_to_traefik.assert_called_once_with(
            config={
                "tcp": {
                    "routers": {
                        "juju-my-model-my-app-tcp-router": {"rule": "HostSNI(`*`)"},
                        "juju-my-model-my-app-ldap-tcp-router": {"rule": "HostSNI(`*`)"},
                    },
                    "services": {
                        "juju-my-model-my-app-tcp-service": {
                            "loadBalancer": {
                                "servers": [{"address": "my-app.my-model.svc.cluster.local:3389"}]
                            }
                        }
                    },
                }
            },
            static={
                "entryPoints": {
                    "ldaps": {"address": ":636"},
                    "ldap": {"address": ":389"},
                }
            },
        )

    def test_ldaps_enabled(self, mocker: Any) -> None:
        """Test that ldaps_enabled checks the scheme on the requirer."""
        mock_charm = mocker.MagicMock()
        mock_requirer = MagicMock()
        mocker.patch("integrations.TraefikRouteRequirer", return_value=mock_requirer)

        integration = TraefikRouteIntegration(mock_charm)

        mock_requirer.scheme = "https"
        assert integration.ldaps_enabled is True

        mock_requirer.scheme = "http"
        assert integration.ldaps_enabled is False

        mock_requirer.scheme = ""
        assert integration.ldaps_enabled is False
