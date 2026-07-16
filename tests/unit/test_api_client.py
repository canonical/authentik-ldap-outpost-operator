# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Authentik REST API client."""

from unittest.mock import MagicMock, patch

import pytest
import responses

from api_client import AuthentikApiClient, AuthentikApiError


class TestAuthentikApiClient:
    """Tests for AuthentikApiClient."""

    @pytest.fixture(autouse=True)
    def fast_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock time.sleep, time.time, and time.monotonic to make tenacity retries instantaneous and correct."""
        current_time = [0.0]

        def mock_sleep(seconds: float) -> None:
            current_time[0] += seconds

        def mock_time() -> float:
            return current_time[0]

        monkeypatch.setattr("time.sleep", mock_sleep)
        monkeypatch.setattr("time.time", mock_time)
        monkeypatch.setattr("time.monotonic", mock_time)

    @pytest.fixture
    def client(self) -> AuthentikApiClient:
        """Fixture for AuthentikApiClient."""
        return AuthentikApiClient(host="http://authentik:9000", token="secret-token")

    @pytest.fixture
    def mock_request_success(self) -> None:
        """Fixture to mock successful GET request."""
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/test/",
            json={"status": "ok"},
            status=200,
        )

    @pytest.fixture
    def mock_request_delete_success(self) -> None:
        """Fixture to mock successful DELETE request."""
        responses.add(
            responses.DELETE,
            "http://authentik:9000/api/v3/test/",
            status=204,
        )

    @pytest.fixture
    def mock_request_http_error(self) -> None:
        """Fixture to mock HTTP 404 Not Found error."""
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/test/",
            body="Not Found",
            status=404,
        )

    @pytest.fixture
    def mock_request_all_pagination(self) -> None:
        """Fixture to mock paginated GET requests."""
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/test/",
            json={
                "results": [{"pk": "1"}],
                "next": "http://authentik:9000/api/v3/test/?page=2",
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/test/?page=2",
            json={
                "results": [{"pk": "2"}],
                "next": None,
            },
            status=200,
        )

    @pytest.fixture
    def mock_flow_resolution_failure(self) -> None:
        """Fixture to mock flow resolution failure with 404s and empty flow list."""
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/flows/instances/default-provider-authorization-implicit-consent/",
            status=404,
        )
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/flows/instances/default-provider-invalidation-flow/",
            status=404,
        )
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/flows/instances/",
            json={"results": []},
            status=200,
        )

    @pytest.fixture
    def mock_flow_resolution_success(self) -> None:
        """Fixture to mock successful flow resolution."""
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/flows/instances/default-provider-authorization-implicit-consent/",
            json={"pk": "auth-uuid"},
            status=200,
        )
        responses.add(
            responses.GET,
            "http://authentik:9000/api/v3/flows/instances/default-provider-invalidation-flow/",
            json={"pk": "inval-uuid"},
            status=200,
        )

    @responses.activate
    def test_request_success(self, client: AuthentikApiClient, mock_request_success: None) -> None:
        """Test successful GET request."""
        res = client._request("/api/v3/test/")
        assert res == {"status": "ok"}

    @responses.activate
    def test_request_delete_success(
        self, client: AuthentikApiClient, mock_request_delete_success: None
    ) -> None:
        """Test successful DELETE request returns True."""
        res = client._request("/api/v3/test/", method="DELETE")
        assert res is True

    @responses.activate
    def test_request_http_error_stores_status_code(
        self, client: AuthentikApiClient, mock_request_http_error: None
    ) -> None:
        """Test HTTPError raises AuthentikApiError with status code."""
        with pytest.raises(AuthentikApiError) as exc_info:
            client._request("/api/v3/test/")

        assert exc_info.value.status_code == 404
        assert "HTTP Error 404" in str(exc_info.value)

    @responses.activate
    def test_request_all_pagination(
        self, client: AuthentikApiClient, mock_request_all_pagination: None
    ) -> None:
        """Test that _request_all retrieves all pages correctly."""
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

    @patch.object(AuthentikApiClient, "_request")
    def test_resolve_flow_ids_slug_failure_raises_error(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test that resolve_flow_ids raises AuthentikApiError if direct slug lookup fails."""
        # Mock slug lookup raising 404
        mock_request.side_effect = AuthentikApiError("Not Found", status_code=404)

        with pytest.raises(AuthentikApiError) as exc_info:
            client.resolve_flow_ids()

        assert "Could not resolve default authorization or invalidation flows" in str(
            exc_info.value
        )

    @responses.activate
    def test_resolve_flow_ids_retries_on_404(
        self,
        client: AuthentikApiClient,
        mock_flow_resolution_failure: None,
        mock_flow_resolution_success: None,
    ) -> None:
        """Test that resolve_flow_ids retries on 404 errors and eventually succeeds."""
        auth_uuid, inval_uuid = client.resolve_flow_ids()

        assert auth_uuid == "auth-uuid"
        assert inval_uuid == "inval-uuid"

    @responses.activate
    def test_resolve_flow_ids_times_out(
        self, client: AuthentikApiClient, mock_flow_resolution_failure: None
    ) -> None:
        """Test that resolve_flow_ids eventually times out and raises AuthentikApiError on persistent 404."""
        with pytest.raises(AuthentikApiError) as exc_info:
            client.resolve_flow_ids()

        assert "Could not resolve default authorization or invalidation flows" in str(
            exc_info.value
        )

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

    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_application_exists_patches(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test get_or_create_application updates existing application."""
        mock_request.side_effect = [
            {"name": "test-app", "slug": "test-app-slug", "pk": 10},  # direct slug lookup success
            {},  # PATCH success
        ]

        client.get_or_create_application("test-app", "test-app-slug", 5)

        mock_request.assert_any_call("/api/v3/core/applications/test-app-slug/")
        mock_request.assert_any_call(
            "/api/v3/core/applications/test-app-slug/",
            method="PATCH",
            data={"name": "test-app", "slug": "test-app-slug", "provider": 5},
        )

    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_application_new_posts(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test get_or_create_application creates new application if missing."""
        mock_request.side_effect = [
            AuthentikApiError("Not Found", status_code=404),  # direct slug check 404
            {"results": []},  # fallback name filter query
            {},  # POST success
        ]

        client.get_or_create_application("test-app", "test-app-slug", 5)

        mock_request.assert_any_call("/api/v3/core/applications/test-app-slug/")
        mock_request.assert_any_call("/api/v3/core/applications/?name=test-app")
        mock_request.assert_any_call(
            "/api/v3/core/applications/",
            method="POST",
            data={"name": "test-app", "slug": "test-app-slug", "provider": 5},
        )
