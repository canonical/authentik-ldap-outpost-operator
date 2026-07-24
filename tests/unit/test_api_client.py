# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for Authentik REST API client."""

from unittest.mock import MagicMock, patch

import pytest
import responses

from api_client import (
    AuthentikApiClient,
    AuthentikApiError,
    AuthentikConnectionError,
    AuthentikHttpError,
    AuthentikNotFoundError,
)


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
        """A 404 is exposed as a typed not-found error."""
        with pytest.raises(AuthentikNotFoundError) as exc_info:
            client._request("/api/v3/test/")

        assert exc_info.value.status_code == 404
        assert len(responses.calls) == 1

    @responses.activate
    def test_request_all_pagination(
        self, client: AuthentikApiClient, mock_request_all_pagination: None
    ) -> None:
        """Test that _request_all retrieves all pages correctly."""
        results = client._request_all("/api/v3/test/")
        assert results == [{"pk": "1"}, {"pk": "2"}]

    @patch.object(AuthentikApiClient, "_request")
    def test_request_all_guards_against_unbounded_pagination(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """_request_all raises rather than looping forever on a self-referential 'next'."""
        mock_request.return_value = {
            "results": [{"pk": "1"}],
            "next": "http://authentik:9000/api/v3/test/?page=next",
        }
        with pytest.raises(AuthentikApiError, match="Pagination exceeded"):
            client._request_all("/api/v3/test/")
        assert mock_request.call_count == 500

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_outpost_marks_host_insecure(
        self, mock_request: MagicMock, mock_request_all: MagicMock
    ) -> None:
        """The created outpost is marked authentik_host_insecure (internal HTTP host)."""
        client = AuthentikApiClient(host="http://authentik:9000", token="secret-token")
        mock_request_all.return_value = []
        mock_request.return_value = {"pk": "outpost-uuid", "token_identifier": "tok"}

        client.get_or_create_outpost(name="outpost", provider_pk=1)

        _, kwargs = mock_request.call_args
        assert kwargs["data"]["config"]["authentik_host_insecure"] is True

    def test_client_reuses_one_authenticated_session(self, client: AuthentikApiClient) -> None:
        """All client requests use the session created during initialization."""
        response = MagicMock(status_code=200, text="")
        client._session.request = MagicMock(return_value=response)

        client._request("/api/v3/one/")
        client._request("/api/v3/two/")

        assert client._session.request.call_count == 2
        assert client._session.headers["Authorization"] == "Bearer secret-token"

    @pytest.mark.parametrize("status_code", [429, 500, 503])
    def test_request_retries_transient_http_errors(
        self, client: AuthentikApiClient, status_code: int
    ) -> None:
        """Throttling and server failures are retried within the attempt bound."""
        client._do_request = MagicMock(
            side_effect=[
                AuthentikHttpError("transient", status_code),
                {"status": "ok"},
            ]
        )

        assert client._request("/api/v3/test/") == {"status": "ok"}
        assert client._do_request.call_count == 2

    def test_request_retries_connection_errors_at_most_three_times(
        self, client: AuthentikApiClient
    ) -> None:
        """Connection retries retain their type and stop after three attempts."""
        client._do_request = MagicMock(side_effect=AuthentikConnectionError("unavailable"))

        with pytest.raises(AuthentikConnectionError):
            client._request("/api/v3/test/")

        assert client._do_request.call_count == 3

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404])
    def test_request_does_not_retry_permanent_http_errors(
        self, client: AuthentikApiClient, status_code: int
    ) -> None:
        """Permanent client errors fail on their first attempt."""
        error = AuthentikHttpError("permanent", status_code)
        client._do_request = MagicMock(side_effect=error)

        with pytest.raises(AuthentikHttpError):
            client._request("/api/v3/test/")

        client._do_request.assert_called_once()

    @patch.object(AuthentikApiClient, "_request")
    def test_resolve_invalidation_flow_requests_only_required_slug(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Flow resolution never requests the unused authorization flow."""
        mock_request.return_value = {"pk": "inval-uuid"}

        assert client.resolve_invalidation_flow_id() == "inval-uuid"
        mock_request.assert_called_once_with(
            "/api/v3/flows/instances/default-provider-invalidation-flow/"
        )

    @patch.object(AuthentikApiClient, "_request")
    def test_resolve_invalidation_flow_rejects_missing_pk(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """A malformed invalidation-flow response is rejected without blind retry."""
        mock_request.return_value = {}

        with pytest.raises(AuthentikApiError, match="Could not resolve default invalidation flow"):
            client.resolve_invalidation_flow_id()

        mock_request.assert_called_once()

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_bind_flow_existing_all_bound_is_noop(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """An existing flow with all stage bindings present creates nothing."""
        mock_request_all.side_effect = [
            [
                {"name": "default-authentication-identification", "pk": "ident"},
                {"name": "default-authentication-password", "pk": "pass"},
                {"name": "default-authentication-login", "pk": "login"},
            ],
            [{"stage": "ident"}, {"stage": "pass"}, {"stage": "login"}],
        ]
        mock_request.return_value = {"pk": "bind-flow-uuid"}

        res = client.get_or_create_ldap_bind_flow()

        assert res == "bind-flow-uuid"
        # Only the flow slug GET is issued; no flow or binding is created.
        mock_request.assert_called_once_with("/api/v3/flows/instances/default-ldap-bind-flow/")

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_bind_flow_repairs_missing_bindings(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """An existing flow left without bindings is repaired (idempotent)."""
        mock_request_all.side_effect = [
            [
                {"name": "default-authentication-identification", "pk": "ident"},
                {"name": "default-authentication-password", "pk": "pass"},
                {"name": "default-authentication-login", "pk": "login"},
            ],
            [],  # flow exists but has no stage bindings
        ]
        mock_request.side_effect = [
            {"pk": "bind-flow-uuid"},  # flow slug GET
            {},  # POST binding ident
            {},  # POST binding pass
            {},  # POST binding login
        ]

        res = client.get_or_create_ldap_bind_flow()

        assert res == "bind-flow-uuid"
        for stage, order in [("ident", 10), ("pass", 20), ("login", 100)]:
            mock_request.assert_any_call(
                "/api/v3/flows/bindings/",
                method="POST",
                data={"target": "bind-flow-uuid", "stage": stage, "order": order},
            )

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_bind_flow_creates_when_missing(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """When the flow is absent it is created and all stage bindings are added."""
        mock_request_all.side_effect = [
            [
                {"name": "default-authentication-identification", "pk": "ident"},
                {"name": "default-authentication-password", "pk": "pass"},
                {"name": "default-authentication-login", "pk": "login"},
            ],
            [],  # no bindings on the freshly created flow
        ]
        mock_request.side_effect = [
            AuthentikNotFoundError("Not Found", 404),  # flow slug GET
            {"pk": "new-bind-flow-uuid"},  # POST flow
            {},  # POST binding ident
            {},  # POST binding pass
            {},  # POST binding login
        ]

        res = client.get_or_create_ldap_bind_flow()

        assert res == "new-bind-flow-uuid"
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

    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_ldap_bind_flow_raises_when_stages_absent(
        self, mock_request: MagicMock, mock_request_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        """If the default stages are not applied yet, raise without creating a flow."""
        mock_request_all.return_value = []  # stages not present yet

        with pytest.raises(AuthentikApiError, match="stages not ready"):
            client.get_or_create_ldap_bind_flow()

        # No flow or binding is created; the reconcile simply retries later.
        mock_request.assert_not_called()

    @patch.object(AuthentikApiClient, "_request")
    def test_delete_user_ignores_404(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        """Test that delete_user ignores HTTP 404 (already deleted) and logs warning."""
        mock_request.side_effect = AuthentikNotFoundError("Not Found", 404)

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
            AuthentikNotFoundError("Not Found", 404),  # direct slug check 404
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

    @patch.object(AuthentikApiClient, "get_or_create_ldap_bind_flow")
    @patch.object(AuthentikApiClient, "resolve_invalidation_flow_id")
    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_provider_creates_new(
        self,
        mock_request: MagicMock,
        mock_request_all: MagicMock,
        mock_resolve_invalidation: MagicMock,
        mock_bind_flow: MagicMock,
        client: AuthentikApiClient,
    ) -> None:
        """Test get_or_create_provider creates a new provider when missing."""
        mock_request_all.return_value = []
        mock_resolve_invalidation.return_value = "inval-flow-uuid"
        mock_bind_flow.return_value = "bind-flow-uuid"
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
            },
        )

    @patch.object(AuthentikApiClient, "get_or_create_ldap_bind_flow")
    @patch.object(AuthentikApiClient, "resolve_invalidation_flow_id")
    @patch.object(AuthentikApiClient, "_request_all")
    @patch.object(AuthentikApiClient, "_request")
    def test_get_or_create_provider_syncs_existing(
        self,
        mock_request: MagicMock,
        mock_request_all: MagicMock,
        mock_resolve_invalidation: MagicMock,
        mock_bind_flow: MagicMock,
        client: AuthentikApiClient,
    ) -> None:
        """Test get_or_create_provider patches an existing provider's config without flows."""
        mock_request_all.return_value = [{"name": "test-provider", "pk": 42}]
        mock_resolve_invalidation.return_value = "inval-flow-uuid"
        mock_bind_flow.return_value = "bind-flow-uuid"
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
        # PATCH is a partial update: only managed config fields, no flow fields.
        mock_request.assert_called_once_with(
            "/api/v3/providers/ldap/42/",
            method="PATCH",
            data={
                "name": "test-provider",
                "base_dn": "dc=example,dc=com",
                "search_mode": "direct",
                "bind_mode": "direct",
                "mfa_support": False,
            },
        )
        # Flow resolution must be skipped entirely on the PATCH path.
        mock_resolve_invalidation.assert_not_called()
        mock_bind_flow.assert_not_called()


class TestGroupMembership:
    """Tests for Authentik group lookup and membership methods."""

    @pytest.fixture
    def client(self) -> AuthentikApiClient:
        return AuthentikApiClient(host="http://authentik:9000", token="secret-token")

    @patch.object(AuthentikApiClient, "_request_all")
    def test_get_group_by_name_exact_match(
        self, mock_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        mock_all.return_value = [
            {"pk": "other-uuid", "name": "authentik Admins"},
            {"pk": "grp-uuid", "name": "grp"},
        ]
        assert client.get_group_by_name("grp") == "grp-uuid"

    @patch.object(AuthentikApiClient, "_request_all")
    def test_get_group_by_name_absent(
        self, mock_all: MagicMock, client: AuthentikApiClient
    ) -> None:
        mock_all.return_value = [{"pk": "x", "name": "authentik Admins"}]
        assert client.get_group_by_name("grp") is None

    @patch.object(AuthentikApiClient, "_request")
    def test_add_user_to_group_payload(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        client.add_user_to_group("grp-uuid", 42)
        mock_request.assert_called_once_with(
            "/api/v3/core/groups/grp-uuid/add_user/", method="POST", data={"pk": 42}
        )

    @patch.object(AuthentikApiClient, "_request")
    def test_remove_user_from_group_payload(
        self, mock_request: MagicMock, client: AuthentikApiClient
    ) -> None:
        client.remove_user_from_group("grp-uuid", 42)
        mock_request.assert_called_once_with(
            "/api/v3/core/groups/grp-uuid/remove_user/", method="POST", data={"pk": 42}
        )
