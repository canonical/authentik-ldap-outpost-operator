# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for relation integrations."""

from typing import Any
from unittest.mock import MagicMock, create_autospec

from charms.authentik_server.v0.authentik_server_info import (
    AuthentikServerInfoRequirer,
)

from integrations import ServerInfoIntegration, TracingData


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
