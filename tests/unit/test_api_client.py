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

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_property_mappings_all_exist(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test get_or_create_ldap_property_mappings returns existing mappings without creating."""
        mock_request_all.side_effect = [
            [{"name": "authentik default LDAP Mapping: entryDN", "pk": "uuid-1"}],
            [
                {
                    "name": "authentik default LDAP Mapping: POSIX uidNumber/gidNumber",
                    "pk": "uuid-2",
                }
            ],
            [
                {
                    "name": "authentik default LDAP Mapping: POSIX homeDirectory/loginShell",
                    "pk": "uuid-3",
                }
            ],
            [{"name": "authentik default LDAP Mapping: sshPublicKey", "pk": "uuid-4"}],
        ]

        pks = client.get_or_create_ldap_property_mappings()

        assert pks == ["uuid-1", "uuid-2", "uuid-3", "uuid-4"]
        assert mock_request_all.call_count == 4
        mock_request.assert_not_called()

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_property_mappings_creates_missing(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test get_or_create_ldap_property_mappings creates mapping if missing."""
        mock_request_all.return_value = []  # none exist
        mock_request.side_effect = [
            {"pk": "new-uuid-1"},
            {"pk": "new-uuid-2"},
            {"pk": "new-uuid-3"},
            {"pk": "new-uuid-4"},
        ]

        pks = client.get_or_create_ldap_property_mappings()

        assert pks == ["new-uuid-1", "new-uuid-2", "new-uuid-3", "new-uuid-4"]
        assert mock_request_all.call_count == 4
        assert mock_request.call_count == 4

    @patch.object(AuthentikApiClient, "get_or_create_ldap_property_mappings")
    @patch.object(AuthentikApiClient, "get_or_create_ldap_bind_flow")
    @patch.object(AuthentikApiClient, "resolve_flow_ids")
    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_provider_creates_new(
        self,
        mock_request: MagicMock,
        mock_request_all: MagicMock,
        mock_resolve_flows: MagicMock,
        mock_bind_flow: MagicMock,
        mock_mappings: MagicMock,
        client: AuthentikApiClient,
    ) -> None:
        """Test get_or_create_provider creates new provider when missing and assigns property mappings."""
        mock_request_all.return_value = []  # no existing providers
        mock_resolve_flows.return_value = ("auth-flow-uuid", "inval-flow-uuid")
        mock_bind_flow.return_value = "bind-flow-uuid"
        mock_mappings.return_value = ["uuid-1", "uuid-2", "uuid-3", "uuid-4"]
        mock_request.return_value = {"pk": 42}

        provider_pk = client.get_or_create_provider(
            name="test-provider",
            base_dn="dc=example,dc=com",
            search_mode="direct",
            bind_mode="direct",
            mfa_support=False,
        )

        assert provider_pk == 42
        mock_request_all.assert_called_once_with("/api/v3/providers/ldap/?search=test-provider")
        mock_request.assert_called_once_with(
            "/api/v3/providers/ldap/",
            method="POST",
            data={
                "name": "test-provider",
                "authentication_flow": "bind-flow-uuid",
                "authorization_flow": "bind-flow-uuid",
                "invalidation_flow": "inval-flow-uuid",
                "base_dn": "dc=example,dc=com",
                "search_mode": "direct",
                "bind_mode": "direct",
                "mfa_support": False,
                "property_mappings": ["uuid-1", "uuid-2", "uuid-3", "uuid-4"],
            },
        )

    @patch.object(AuthentikApiClient, "get_or_create_ldap_property_mappings")
    @patch.object(AuthentikApiClient, "get_or_create_ldap_bind_flow")
    @patch.object(AuthentikApiClient, "resolve_flow_ids")
    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_provider_syncs_existing(
        self,
        mock_request: MagicMock,
        mock_request_all: MagicMock,
        mock_resolve_flows: MagicMock,
        mock_bind_flow: MagicMock,
        mock_mappings: MagicMock,
        client: AuthentikApiClient,
    ) -> None:
        """Test get_or_create_provider patches existing provider merging property mappings."""
        mock_request_all.return_value = [{"name": "test-provider", "pk": 42}]
        mock_resolve_flows.return_value = ("auth-flow-uuid", "inval-flow-uuid")
        mock_bind_flow.return_value = "bind-flow-uuid"
        mock_mappings.return_value = ["uuid-1", "uuid-2", "uuid-3", "uuid-4"]

        # side_effect for mock_request:
        # First call is the GET on /api/v3/providers/ldap/42/
        # Second call is the PATCH on /api/v3/providers/ldap/42/
        mock_request.side_effect = [{"property_mappings": ["existing-uuid"]}, {"pk": 42}]

        provider_pk = client.get_or_create_provider(
            name="test-provider",
            base_dn="dc=example,dc=com",
            search_mode="direct",
            bind_mode="direct",
            mfa_support=False,
        )

        assert provider_pk == 42
        mock_request_all.assert_called_once_with("/api/v3/providers/ldap/?search=test-provider")

        mock_request.assert_any_call("/api/v3/providers/ldap/42/")
        mock_request.assert_any_call(
            "/api/v3/providers/ldap/42/",
            method="PATCH",
            data={
                "name": "test-provider",
                "authentication_flow": "bind-flow-uuid",
                "authorization_flow": "bind-flow-uuid",
                "invalidation_flow": "inval-flow-uuid",
                "base_dn": "dc=example,dc=com",
                "search_mode": "direct",
                "bind_mode": "direct",
                "mfa_support": False,
                "property_mappings": ["existing-uuid", "uuid-1", "uuid-2", "uuid-3", "uuid-4"],
            },
        )
