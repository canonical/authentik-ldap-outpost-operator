# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Authentik REST API client."""

import json
import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from api_client import AuthentikApiClient, AuthentikApiError


class TestAuthentikApiClient:
    """Tests for AuthentikApiClient."""

    @pytest.fixture
    def client(self) -> AuthentikApiClient:
        """Fixture for AuthentikApiClient."""
        return AuthentikApiClient(host="http://authentik:9000", token="secret-token")

    @patch("urllib.request.urlopen")
    def test_request_success(self, mock_urlopen: MagicMock, client: AuthentikApiClient) -> None:
        """Test successful GET request."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = client._request("/api/v3/test/")
        assert res == {"status": "ok"}
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_request_delete_success(
        self, mock_urlopen: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test successful DELETE request returns True."""
        mock_response = MagicMock()
        mock_response.status = 204
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = client._request("/api/v3/test/", method="DELETE")
        assert res is True

    @patch("urllib.request.urlopen")
    def test_request_http_error_stores_status_code(
        self, mock_urlopen: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test HTTPError raises AuthentikApiError with status code."""
        # Create an HTTPError with code 404
        fp = BytesIO(b"Not Found")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://authentik:9000/api/v3/test/",
            code=404,
            msg="Not Found",
            hdrs=urllib.request.Request("http://authentik:9000/api/v3/test/").headers,
            fp=fp,
        )

        with pytest.raises(AuthentikApiError) as exc_info:
            client._request("/api/v3/test/")

        assert exc_info.value.status_code == 404
        assert "HTTP Error 404" in str(exc_info.value)

    @patch("urllib.request.urlopen")
    def test_request_all_pagination(
        self, mock_urlopen: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test that _request_all retrieves all pages correctly."""
        mock_response1 = MagicMock()
        mock_response1.read.return_value = json.dumps({
            "results": [{"pk": "1"}],
            "next": "http://authentik:9000/api/v3/test/?page=2",
        }).encode("utf-8")

        mock_response2 = MagicMock()
        mock_response2.read.return_value = json.dumps({
            "results": [{"pk": "2"}],
            "next": None,
        }).encode("utf-8")

        mock_urlopen.side_effect = [
            mock_urlopen.return_value,
            mock_urlopen.return_value,
        ]
        mock_urlopen.return_value.__enter__.side_effect = [mock_response1, mock_response2]

        results = client._request_all("/api/v3/test/")
        assert results == [{"pk": "1"}, {"pk": "2"}]

    @patch.object(AuthentikApiClient, "_request")
    def test_resolve_flow_ids_direct_slug_success(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test that resolve_flow_ids resolves both flows directly by slug successfully."""
        mock_request.side_effect = [
            {"pk": "auth-uuid"},  # auth slug lookup
            {"pk": "inval-uuid"},  # inval slug lookup
        ]

        auth_uuid, inval_uuid = client.resolve_flow_ids()

        assert auth_uuid == "auth-uuid"
        assert inval_uuid == "inval-uuid"
        # Assert that self._request was called for the two slugs directly
        mock_request.assert_any_call(
            "/api/v3/flows/instances/default-provider-authorization-implicit-consent/"
        )
        mock_request.assert_any_call("/api/v3/flows/instances/default-provider-invalidation-flow/")

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_resolve_flow_ids_slug_fallback_to_list(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test that resolve_flow_ids falls back to listing all flows if slug lookup returns 404."""
        # Mock slug lookup raising 404
        mock_request.side_effect = AuthentikApiError("Not Found", status_code=404)

        # Mock list response
        mock_request_all.return_value = [
            {"slug": "default-provider-authorization-implicit-consent", "pk": "auth-uuid"},
            {"slug": "default-provider-invalidation-flow", "pk": "inval-uuid"},
        ]

        auth_uuid, inval_uuid = client.resolve_flow_ids()

        assert auth_uuid == "auth-uuid"
        assert inval_uuid == "inval-uuid"
        mock_request_all.assert_called_with("/api/v3/flows/instances/")

    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_bind_flow_direct_slug_success(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test get_or_create_ldap_bind_flow succeeds on direct slug check."""
        mock_request.return_value = {"pk": "bind-flow-uuid"}

        res = client.get_or_create_ldap_bind_flow()

        assert res == "bind-flow-uuid"
        mock_request.assert_called_once_with("/api/v3/flows/instances/default-ldap-bind-flow/")

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_bind_flow_creates_when_missing(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test get_or_create_ldap_bind_flow creates the flow when direct slug check returns 404."""
        # 1st request (direct check) -> 404
        # 2nd request (POST flows/instances) -> created pk
        # 3rd request (POST flows/bindings) -> bound stage 1
        # 4th request (POST flows/bindings) -> bound stage 2
        # 5th request (POST flows/bindings) -> bound stage 3
        mock_request.side_effect = [
            AuthentikApiError("Not Found", status_code=404),
            {"pk": "new-bind-flow-uuid"},
            {},
            {},
            {},
        ]

        mock_request_all.return_value = [
            {"name": "default-authentication-identification", "pk": "ident-stage-uuid"},
            {"name": "default-authentication-password", "pk": "pass-stage-uuid"},
            {"name": "default-authentication-login", "pk": "login-stage-uuid"},
        ]

        res = client.get_or_create_ldap_bind_flow()

        assert res == "new-bind-flow-uuid"
        # Verify post flow data
        mock_request.assert_any_call(
            "/api/v3/flows/instances/",
            method="POST",
            data={
                "name": "LDAP Bind Flow",
                "slug": "default-ldap-bind-flow",
                "title": "LDAP Bind Flow",
                "designation": "authentication",
                "compatibility_mode": False,
                "layout": "stacked",
                "denied_action": "message_continue",
            },
        )

    @patch.object(AuthentikApiClient, "_request")
    def test_delete_user_ignores_404(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test that delete_user ignores HTTP 404 (already deleted) and logs warning."""
        mock_request.side_effect = AuthentikApiError("Not Found", status_code=404)

        # Should not raise exception
        client.delete_user(42)
        mock_request.assert_called_once_with("/api/v3/core/users/42/", method="DELETE")
