# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Authentik REST API client using requests."""

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests
import tenacity

from exceptions import AuthentikAuthorizationError, AuthentikMigrationError, CharmError

logger = logging.getLogger(__name__)


LDAP_SEARCH_PERMISSION = "authentik_providers_ldap.search_full_directory"
LDAP_PROVIDER_MODEL = "authentik_providers_ldap.ldapprovider"
LDAP_PROVIDER_APP_LABEL = "authentik_providers_ldap"


@dataclass(frozen=True)
class AuthentikRole:
    """An Authentik RBAC role."""

    pk: str
    name: str


@dataclass(frozen=True)
class AuthentikProvider:
    """The Authentik LDAP provider fields the charm reads."""

    pk: int
    name: str


@dataclass(frozen=True)
class AuthentikUser:
    """The Authentik user fields the charm reads."""

    pk: int
    username: str
    name: str


@dataclass(frozen=True)
class AssignedPermission:
    """An Authentik permission assigned globally or to one object."""

    codename: str
    model: str
    app_label: str
    object_pk: Optional[str] = None


class AuthentikApiError(CharmError):
    """Base exception for Authentik API errors."""


class AuthentikHttpError(AuthentikApiError):
    """Authentik returned an unsuccessful HTTP response."""

    def __init__(self, message: str, status_code: int):
        """Initialize an HTTP error with its response status."""
        super().__init__(message)
        self.status_code = status_code


class AuthentikNotFoundError(AuthentikHttpError):
    """The requested Authentik resource does not exist."""


class AuthentikConnectionError(AuthentikApiError):
    """The request could not reach Authentik."""


class AuthentikApiClient:
    """Client for communicating with the Authentik REST API."""

    def __init__(self, host: str, token: str):
        """Initialize the API client.

        Args:
            host: The Authentik server URL (e.g., "http://authentik-server:9000").
            token: The administrator bootstrap or API token.
        """
        self._host = host.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def _do_request(self, method: str, endpoint: str, data: Optional[Any] = None) -> Any:
        """Execute a single HTTP request.

        Args:
            method: The HTTP method (GET, POST, PATCH, PUT, DELETE).
            endpoint: The API endpoint path.
            data: Optional dictionary or list to send as JSON payload.

        Returns:
            The parsed JSON response, or True for successful empty responses (e.g. DELETE).

        Raises:
            AuthentikApiError: If the request fails.
        """
        url = f"{self._host}{endpoint}"

        try:
            response = self._session.request(
                method=method,
                url=url,
                json=data,
                timeout=15,
            )
            response.raise_for_status()
            if method == "DELETE" or response.status_code == 204:
                return True

            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            response = e.response
            status_code = response.status_code if response is not None else 0
            err_body = response.text if response is not None else "Could not read error body"
            logger.error(
                "Authentik API HTTP Error %s for %s %s: %s",
                status_code,
                method,
                endpoint,
                err_body,
            )
            error_type = AuthentikNotFoundError if status_code == 404 else AuthentikHttpError
            raise error_type(f"HTTP Error {status_code}: {err_body}", status_code) from e
        except ValueError as e:
            raise AuthentikApiError("Authentik API returned invalid JSON") from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error("Failed to connect to Authentik API: %s", e)
            raise AuthentikConnectionError(f"Connection failure: {e}") from e
        except requests.exceptions.RequestException as e:
            raise AuthentikApiError(f"Authentik request failure: {e}") from e

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Any] = None,
    ) -> Any:
        """Make an HTTP request to the Authentik API.

        Args:
            endpoint: The API endpoint path (e.g., "/api/v3/providers/ldap/").
            method: The HTTP method (GET, POST, PATCH, PUT, DELETE).
            data: Optional dictionary or list to send as JSON payload.

        Returns:
            The parsed JSON response, or True for successful empty responses (e.g. DELETE).

        Raises:
            AuthentikApiError: If the request fails.
        """

        def _should_retry(exception: BaseException) -> bool:
            """Retry only failures that can reasonably be transient."""
            return isinstance(exception, AuthentikConnectionError) or (
                isinstance(exception, AuthentikHttpError)
                and (exception.status_code == 429 or exception.status_code >= 500)
            )

        for attempt in tenacity.Retrying(
            stop=tenacity.stop_after_attempt(3),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=4),
            retry=tenacity.retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                return self._do_request(method, endpoint, data)

    def _request_all(self, endpoint: str) -> List[Any]:
        """Fetch all results from a paginated endpoint.

        Args:
            endpoint: The relative endpoint path.

        Returns:
            A combined list of all results across all pages.
        """
        results = []
        max_pages = 500
        for _ in range(max_pages):
            if not endpoint:
                return results
            res = self._request(endpoint)
            results.extend(res.get("results", []))
            next_url = res.get("next")
            if next_url:
                parsed_url = urlparse(next_url)
                endpoint = parsed_url.path
                if parsed_url.query:
                    endpoint += f"?{parsed_url.query}"
            else:
                endpoint = None
        raise AuthentikApiError(
            f"Pagination exceeded {max_pages} pages; aborting to avoid an unbounded loop"
        )

    def resolve_invalidation_flow_id(self) -> str:
        """Resolve the default provider invalidation flow by slug.

        Returns:
            The UUID of the default invalidation flow.

        Raises:
            AuthentikApiError: If the flow is absent or malformed.
        """
        res = self._request("/api/v3/flows/instances/default-provider-invalidation-flow/")
        if flow_pk := res.get("pk"):
            return flow_pk
        raise AuthentikApiError("Could not resolve default invalidation flow")

    def _find_stage(self, stages: List[Any], name: str) -> Optional[str]:
        """Find a stage UUID by its name."""
        for stage in stages:
            if stage.get("name") == name:
                return stage.get("pk")
        return None

    def get_or_create_ldap_bind_flow(self) -> str:
        """Get or create the custom non-interactive LDAP Bind flow.

        Returns:
            The UUID PK of the flow.
        """
        # Try to retrieve the flow directly by slug to avoid paginated listing
        try:
            flow = self._request("/api/v3/flows/instances/default-ldap-bind-flow/")
            if flow_pk := flow.get("pk"):
                return flow_pk
        except AuthentikNotFoundError:
            pass

        logger.info("LDAP Bind Flow not found. Creating a new one.")
        flow_data = {
            "name": "LDAP Bind Flow",
            "slug": "default-ldap-bind-flow",
            "title": "LDAP Bind Flow",
            "designation": "authentication",
            "compatibility_mode": False,
            "layout": "stacked",
            "denied_action": "message_continue",
        }
        res = self._request("/api/v3/flows/instances/", method="POST", data=flow_data)
        flow_pk = res.get("pk")
        if not flow_pk:
            raise AuthentikApiError("Failed to create default-ldap-bind-flow")

        stages = self._request_all("/api/v3/stages/all/")

        ident_stage = self._find_stage(stages, "default-authentication-identification")
        pass_stage = self._find_stage(stages, "default-authentication-password")
        login_stage = self._find_stage(stages, "default-authentication-login")

        if not ident_stage or not pass_stage or not login_stage:
            raise AuthentikApiError(
                f"Could not find all required stages for LDAP Bind Flow: "
                f"ident={ident_stage}, pass={pass_stage}, login={login_stage}"
            )

        bindings = [
            {"stage": ident_stage, "order": 10},
            {"stage": pass_stage, "order": 20},
            {"stage": login_stage, "order": 100},
        ]

        for binding in bindings:
            binding_data = {
                "target": flow_pk,
                "stage": binding["stage"],
                "order": binding["order"],
            }
            self._request("/api/v3/flows/bindings/", method="POST", data=binding_data)

        logger.info("Successfully created LDAP Bind Flow and bound its stages.")
        return flow_pk

    def get_or_create_provider(
        self,
        name: str,
        base_dn: str,
        search_mode: str = "direct",
        bind_mode: str = "direct",
        mfa_support: bool = False,
    ) -> int:
        """Find or create an LDAP Provider, keeping its configuration in sync with Juju.

        Args:
            name: The unique name of the LDAP Provider.
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.

        Returns:
            The integer primary key (ID) of the Provider.
        """
        providers = self._request_all(f"/api/v3/providers/ldap/?search={quote(name)}")
        provider_pk = None

        for prov in providers:
            if prov.get("name") == name:
                provider_pk = prov.get("pk")
                break

        if provider_pk:
            logger.info(
                "Found existing LDAP Provider '%s' (ID: %s). Syncing config.", name, provider_pk
            )
            # PATCH is a partial update: only the managed config fields are sent so an
            # existing provider's flows are left untouched (and flow resolution skipped).
            provider_data = {
                "name": name,
                "base_dn": base_dn,
                "search_mode": search_mode,
                "bind_mode": bind_mode,
                "mfa_support": mfa_support,
            }
            self._request(
                f"/api/v3/providers/ldap/{provider_pk}/", method="PATCH", data=provider_data
            )
        else:
            logger.info("LDAP Provider '%s' not found. Creating a new one.", name)
            inval_flow = self.resolve_invalidation_flow_id()
            bind_flow = self.get_or_create_ldap_bind_flow()
            provider_data = {
                "name": name,
                "authentication_flow": bind_flow,
                "authorization_flow": bind_flow,
                "invalidation_flow": inval_flow,
                "base_dn": base_dn,
                "search_mode": search_mode,
                "bind_mode": bind_mode,
                "mfa_support": mfa_support,
            }
            res = self._request("/api/v3/providers/ldap/", method="POST", data=provider_data)
            provider_pk = res.get("pk")

        if provider_pk is None:
            raise AuthentikApiError(f"Failed to obtain PK for provider {name}")

        return provider_pk

    def update_provider_config(
        self,
        provider_pk: int,
        base_dn: str,
        search_mode: str,
        bind_mode: str,
        mfa_support: bool,
    ) -> None:
        """Update an existing LDAP Provider's configuration directly.

        Args:
            provider_pk: The ID of the LDAP Provider to update.
            base_dn: The Base DN of the directory.
            search_mode: The directory search mode.
            bind_mode: The bind access mode.
            mfa_support: Whether MFA is enabled.
        """
        provider_data = {
            "base_dn": base_dn,
            "search_mode": search_mode,
            "bind_mode": bind_mode,
            "mfa_support": mfa_support,
        }
        logger.info("Updating LDAP Provider '%s' configuration.", provider_pk)
        self._request(f"/api/v3/providers/ldap/{provider_pk}/", method="PATCH", data=provider_data)

    def get_or_create_application(self, name: str, slug: str, provider_pk: int) -> None:
        """Find or create an Application and bind the LDAP Provider to it.

        Args:
            name: The unique name of the Application.
            slug: The slug identifier of the Application.
            provider_pk: The ID of the bound LDAP Provider.
        """
        app_pk = None

        # Try direct lookup by slug (Fast Path)
        try:
            app = self._request(f"/api/v3/core/applications/{slug}/")
            app_pk = app.get("pk")
        except AuthentikNotFoundError:
            pass

        # Fallback to name search only if slug direct lookup 404s (Slow Path / Safety Net)
        if not app_pk:
            encoded_name = quote(name)
            res = self._request(f"/api/v3/core/applications/?name={encoded_name}")
            results = res.get("results", [])
            if results:
                app_pk = results[0].get("pk")

        app_data = {
            "name": name,
            "slug": slug,
            "provider": provider_pk,
        }

        if app_pk:
            logger.info("Found existing Application '%s'. Syncing config.", name)
            self._request(f"/api/v3/core/applications/{slug}/", method="PATCH", data=app_data)
        else:
            logger.info("Application '%s' not found. Creating a new one.", name)
            self._request("/api/v3/core/applications/", method="POST", data=app_data)

    def get_or_create_outpost(self, name: str, provider_pk: int) -> Tuple[str, str]:
        """Find or create an LDAP Outpost, ensuring the provider is bound.

        Args:
            name: The unique name of the Outpost.
            provider_pk: The ID of the bound LDAP Provider.

        Returns:
            A tuple of (outpost_uuid, token_identifier).
        """
        outposts = self._request_all(f"/api/v3/outposts/instances/?search={quote(name)}")
        outpost_pk = None
        token_identifier = None
        existing_providers: List[int] = []

        for op in outposts:
            if op.get("name") == name:
                outpost_pk = op.get("pk")
                token_identifier = op.get("token_identifier")
                existing_providers = op.get("providers", [])
                break

        if outpost_pk:
            logger.info("Found existing LDAP Outpost '%s' (ID: %s).", name, outpost_pk)
            # Ensure provider_pk is bound, keeping other providers untouched (preserve and merge)
            if provider_pk not in existing_providers:
                updated_providers = list(existing_providers) + [provider_pk]
                outpost_data = {
                    "providers": updated_providers,
                }
                self._request(
                    f"/api/v3/outposts/instances/{outpost_pk}/", method="PATCH", data=outpost_data
                )
        else:
            logger.info("LDAP Outpost '%s' not found. Creating a new one.", name)
            outpost_data = {
                "name": name,
                "type": "ldap",
                "providers": [provider_pk],
                "config": {
                    "log_level": "info",
                    "authentik_host": self._host,
                    "authentik_host_insecure": True,
                },
            }
            res = self._request("/api/v3/outposts/instances/", method="POST", data=outpost_data)
            outpost_pk = res.get("pk")
            token_identifier = res.get("token_identifier")

        if not outpost_pk or not token_identifier:
            raise AuthentikApiError(f"Failed to obtain metadata for Outpost {name}")

        return outpost_pk, token_identifier

    @staticmethod
    def _one_exact(
        records: list[dict[str, Any]], field: str, value: Any, resource: str
    ) -> Optional[dict[str, Any]]:
        """Return one exact record and reject an ambiguous API result."""
        matches = [record for record in records if record.get(field) == value]
        if len(matches) > 1:
            raise AuthentikMigrationError(
                f"Authentik returned multiple {resource} records with {field}={value!r}"
            )
        return matches[0] if matches else None

    @staticmethod
    def _parse_provider(record: dict[str, Any]) -> AuthentikProvider:
        """Parse the LDAP provider fields."""
        try:
            return AuthentikProvider(pk=int(record["pk"]), name=str(record["name"]))
        except (KeyError, TypeError, ValueError) as error:
            raise AuthentikMigrationError("Malformed LDAP provider response") from error

    @staticmethod
    def _parse_user(record: dict[str, Any]) -> AuthentikUser:
        """Parse the user fields."""
        try:
            return AuthentikUser(
                pk=int(record["pk"]),
                username=str(record["username"]),
                name=str(record.get("name", record["username"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise AuthentikMigrationError("Malformed Authentik user response") from error

    def get_provider(self, provider_pk: int) -> AuthentikProvider:
        """Get an LDAP provider by its trusted integer primary key."""
        return self._parse_provider(self._request(f"/api/v3/providers/ldap/{provider_pk}/"))

    def find_user_by_username(self, username: str) -> Optional[AuthentikUser]:
        """Find one user by exact username."""
        records = self._request_all(f"/api/v3/core/users/?username={quote(username)}")
        record = self._one_exact(records, "username", username, "user")
        return self._parse_user(record) if record else None

    def rename_user(self, user_pk: int, username: str) -> None:
        """Rename a user selected by trusted integer primary key."""
        self._request(
            f"/api/v3/core/users/{user_pk}/",
            method="PATCH",
            data={"username": username, "name": username},
        )

    def get_role_by_name(self, name: str) -> Optional[AuthentikRole]:
        """Find one Authentik role by exact name."""
        records = self._request_all(f"/api/v3/rbac/roles/?name={quote(name)}")
        record = self._one_exact(records, "name", name, "role")
        if not record:
            return None
        try:
            return AuthentikRole(pk=str(record["pk"]), name=str(record["name"]))
        except (KeyError, TypeError) as error:
            raise AuthentikMigrationError("Malformed Authentik role response") from error

    def create_role(self, name: str) -> AuthentikRole:
        """Create and parse an Authentik role."""
        record = self._request("/api/v3/rbac/roles/", method="POST", data={"name": name})
        try:
            return AuthentikRole(pk=str(record["pk"]), name=str(record["name"]))
        except (KeyError, TypeError) as error:
            raise AuthentikMigrationError("Malformed Authentik role creation response") from error

    def get_or_create_role(self, name: str) -> AuthentikRole:
        """Return the exact role or create it when absent."""
        return self.get_role_by_name(name) or self.create_role(name)

    def add_user_to_role(self, role_uuid: str, user_pk: int) -> None:
        """Idempotently add an integer user primary key to a role."""
        self._request(
            f"/api/v3/rbac/roles/{role_uuid}/add_user/",
            method="POST",
            data={"pk": user_pk},
        )

    def get_group_by_name(self, name: str) -> Optional[str]:
        """Return the UUID of an Authentik group with the exact name, or None."""
        records = self._request_all(f"/api/v3/core/groups/?name={quote(name)}")
        for record in records:
            if record.get("name") == name:
                return record.get("pk")
        return None

    def add_user_to_group(self, group_uuid: str, user_pk: int) -> None:
        """Idempotently add an integer user primary key to a group."""
        self._request(
            f"/api/v3/core/groups/{group_uuid}/add_user/",
            method="POST",
            data={"pk": user_pk},
        )

    def remove_user_from_group(self, group_uuid: str, user_pk: int) -> None:
        """Idempotently remove an integer user primary key from a group."""
        self._request(
            f"/api/v3/core/groups/{group_uuid}/remove_user/",
            method="POST",
            data={"pk": user_pk},
        )

    @staticmethod
    def _permission_payload(provider_pk: int) -> dict[str, Any]:
        """Build the fixed provider-object permission mutation payload."""
        return {
            "permissions": [LDAP_SEARCH_PERMISSION],
            "model": LDAP_PROVIDER_MODEL,
            "object_pk": provider_pk,
        }

    def assign_provider_search_permission(self, role_uuid: str, provider_pk: int) -> None:
        """Assign and then strictly verify the provider-scoped search permission."""
        self.get_provider(provider_pk)
        self._request(
            f"/api/v3/rbac/permissions/assigned_by_roles/{role_uuid}/assign/",
            method="POST",
            data=self._permission_payload(provider_pk),
        )
        self.verify_provider_search_permission(role_uuid, provider_pk)

    @staticmethod
    def _parse_permission(record: dict[str, Any]) -> AssignedPermission:
        """Parse one assigned permission record."""
        try:
            object_pk = record.get("object_pk")
            return AssignedPermission(
                codename=str(record["codename"]),
                model=str(record["model"]),
                app_label=str(record["app_label"]),
                object_pk=str(object_pk) if object_pk is not None else None,
            )
        except (KeyError, TypeError) as error:
            raise AuthentikAuthorizationError("Malformed assigned permission response") from error

    def verify_provider_search_permission(self, role_uuid: str, provider_pk: int) -> None:
        """Require the expected object grant and reject any matching global grant."""
        endpoint = (
            "/api/v3/rbac/permissions/assigned_by_roles/"
            f"?model={LDAP_PROVIDER_MODEL}&object_pk={provider_pk}"
        )
        rows = self._request_all(endpoint)
        role_rows = [row for row in rows if str(row.get("role_pk")) == role_uuid]
        global_permissions = [
            self._parse_permission(permission)
            for row in role_rows
            for permission in row.get("model_permissions", [])
        ]
        if any(
            permission.codename == "search_full_directory"
            and permission.model == "ldapprovider"
            and permission.app_label == LDAP_PROVIDER_APP_LABEL
            for permission in global_permissions
        ):
            raise AuthentikAuthorizationError(
                "LDAP search permission was assigned globally instead of to the provider"
            )

        object_permissions = [
            self._parse_permission(permission)
            for row in role_rows
            for permission in row.get("object_permissions", [])
        ]
        if not any(
            permission.codename == "search_full_directory"
            and permission.model == "ldapprovider"
            and permission.app_label == LDAP_PROVIDER_APP_LABEL
            and permission.object_pk == str(provider_pk)
            for permission in object_permissions
        ):
            raise AuthentikAuthorizationError(
                f"LDAP search permission is not scoped to provider {provider_pk}"
            )

    def get_token_key(self, token_identifier: str) -> str:
        """Retrieve the actual API token key string for an outpost token.

        Args:
            token_identifier: The unique name/identifier of the Token.

        Returns:
            The API token secret string.
        """
        res = self._request(f"/api/v3/core/tokens/{token_identifier}/view_key/")
        key = res.get("key")
        if not key:
            raise AuthentikApiError(f"Could not retrieve token secret key for {token_identifier}")
        return key

    def create_ldap_bind_user(self, name: str) -> Tuple[int, str]:
        """Create a standard user account to act as an LDAP Bind account.

        Args:
            name: Username and name of the LDAP bind user.

        Returns:
            A tuple of (user_pk, username).
        """
        encoded_username = quote(name)
        existing = self._request(f"/api/v3/core/users/?username={encoded_username}")
        results = existing.get("results", [])
        for user in results:
            if user.get("username") == name:
                return user.get("pk"), user.get("username")

        logger.info("Creating standard user for LDAP Bind: %s", name)
        payload = {
            "username": name,
            "name": name,
            "path": "users",
            "is_active": True,
        }
        res = self._request("/api/v3/core/users/", method="POST", data=payload)
        user_pk = res.get("pk")
        username = res.get("username")

        if not user_pk or not username:
            raise AuthentikApiError(f"Failed to create standard user for LDAP Bind {name}")

        return user_pk, username

    def set_user_password(self, user_pk: int, password: str) -> None:
        """Set a password for a service account user.

        Args:
            user_pk: Primary key ID of the user.
            password: The password to apply.
        """
        payload = {"password": password}
        self._request(f"/api/v3/core/users/{user_pk}/set_password/", method="POST", data=payload)

    def delete_user(self, user_pk: int) -> None:
        """Delete a user/service account by ID.

        Args:
            user_pk: The ID of the user to delete.
        """
        logger.info("Deleting user ID: %s", user_pk)
        try:
            self._request(f"/api/v3/core/users/{user_pk}/", method="DELETE")
        except AuthentikNotFoundError:
            logger.warning("User ID %s already deleted.", user_pk)

    def check_outpost_exists(self, outpost_uuid: str) -> bool:
        """Check if an outpost exists by its UUID.

        Args:
            outpost_uuid: The UUID of the outpost.

        Returns:
            True if the outpost exists.

        Raises:
            AuthentikApiError: If the outpost is not found or request fails.
        """
        self._request(f"/api/v3/outposts/instances/{outpost_uuid}/")
        return True
