# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Authentik REST API client using requests."""

import logging
from typing import Any, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests
import tenacity

logger = logging.getLogger(__name__)


class AuthentikApiError(Exception):
    """Base exception for Authentik API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        """Initialize the API error with optional status code.

        Args:
            message: Exception message.
            status_code: Optional HTTP status code.
        """
        super().__init__(message)
        self.status_code = status_code


class AuthentikApiClient:
    """Client for communicating with the Authentik REST API."""

    def __init__(self, host: str, token: str):
        """Initialize the API client.

        Args:
            host: The Authentik server URL (e.g., "http://authentik-server:9000").
            token: The administrator bootstrap or API token.
        """
        self._host = host.rstrip("/")
        self._token = token

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
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=15,
            )
            response.raise_for_status()
            if method == "DELETE" or response.status_code == 204:
                return True

            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            try:
                err_body = e.response.text
            except Exception:
                err_body = "Could not read error body"
            status_code = e.response.status_code if e.response is not None else None
            logger.error(
                "Authentik API HTTP Error %s for %s %s: %s",
                status_code,
                method,
                endpoint,
                err_body,
            )
            raise AuthentikApiError(
                f"HTTP Error {status_code}: {err_body}", status_code=status_code
            ) from e
        except Exception as e:
            logger.error("Failed to connect to Authentik API: %s", e)
            raise AuthentikApiError(f"Connection failure: {e}") from e

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

        def _should_retry(exception: Exception) -> bool:
            """Determine if we should retry the API request."""
            if isinstance(exception, AuthentikApiError):
                if exception.status_code == 503:
                    return True
                if "Connection failure" in str(exception):
                    return True
            return False

        try:
            for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_delay(180),
                wait=tenacity.wait_exponential(multiplier=1, min=5, max=15),
                retry=tenacity.retry_if_exception(_should_retry),
                reraise=True,
            ):
                with attempt:
                    return self._do_request(method, endpoint, data)
        except tenacity.RetryError as e:
            raise AuthentikApiError(f"API request timed out: {e}") from e

    def _request_all(self, endpoint: str) -> List[Any]:
        """Fetch all results from a paginated endpoint.

        Args:
            endpoint: The relative endpoint path.

        Returns:
            A combined list of all results across all pages.
        """
        results = []
        while endpoint:
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
        return results

    def _resolve_flow_ids_once(self) -> Tuple[str, str]:
        """Attempt to resolve standard flow IDs once.

        Returns:
            A tuple of (authorization_flow_uuid, invalidation_flow_uuid).

        Raises:
            AuthentikApiError: If standard flows cannot be found.
        """
        auth_flow = None
        inval_flow = None

        # Try to resolve authorization flow directly by slug
        try:
            res = self._request(
                "/api/v3/flows/instances/default-provider-authorization-implicit-consent/"
            )
            auth_flow = res.get("pk")
        except AuthentikApiError as e:
            if e.status_code != 404:
                raise e

        # Try to resolve invalidation flow directly by slug
        try:
            res = self._request("/api/v3/flows/instances/default-provider-invalidation-flow/")
            inval_flow = res.get("pk")
        except AuthentikApiError as e:
            if e.status_code != 404:
                raise e

        if not auth_flow or not inval_flow:
            raise AuthentikApiError(
                "Could not resolve default authorization or invalidation flows",
                status_code=404,
            )

        return auth_flow, inval_flow

    def resolve_flow_ids(self) -> Tuple[str, str]:
        """Dynamically find default authorization and invalidation flow UUIDs with retry.

        Returns:
            A tuple of (authorization_flow_uuid, invalidation_flow_uuid).

        Raises:
            AuthentikApiError: If standard flows cannot be found after retries.
        """

        def _should_retry(exception: Exception) -> bool:
            """Determine if we should retry flow resolution."""
            return isinstance(exception, AuthentikApiError) and exception.status_code == 404

        def _before_sleep(retry_state: Any) -> None:
            """Log a warning before sleeping between retries."""
            logger.warning(
                "Default Authentik flows not ready yet (attempt %d); retrying...",
                retry_state.attempt_number,
            )

        try:
            for attempt in tenacity.Retrying(
                stop=tenacity.stop_after_delay(120),
                wait=tenacity.wait_exponential(multiplier=1, min=5, max=15),
                retry=tenacity.retry_if_exception(_should_retry),
                before_sleep=_before_sleep,
                reraise=True,
            ):
                with attempt:
                    return self._resolve_flow_ids_once()
        except tenacity.RetryError as e:
            raise AuthentikApiError(
                "Could not resolve default authorization or invalidation flows after retries"
            ) from e

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
        except AuthentikApiError as e:
            if e.status_code != 404:
                raise e

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

        auth_flow, inval_flow = self.resolve_flow_ids()
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

        if provider_pk:
            logger.info(
                "Found existing LDAP Provider '%s' (ID: %s). Syncing config.", name, provider_pk
            )
            self._request(
                f"/api/v3/providers/ldap/{provider_pk}/", method="PATCH", data=provider_data
            )
        else:
            logger.info("LDAP Provider '%s' not found. Creating a new one.", name)
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
        except AuthentikApiError as e:
            if e.status_code != 404:
                raise e

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

    def get_group_by_name(self, name: str) -> Optional[str]:
        """Search for an Authentik User Group by its name.

        Args:
            name: The name of the group to search for.

        Returns:
            The UUID PK of the group if found, otherwise None.
        """
        # Encode name parameter
        encoded_name = quote(name)
        res = self._request(f"/api/v3/core/groups/?name={encoded_name}")
        results = res.get("results", [])
        if results:
            return results[0].get("pk")
        return None

    def create_service_account(self, name: str) -> Tuple[int, str]:
        """Create a dedicated service account user.

        Args:
            name: Name of the service account.

        Returns:
            A tuple of (user_pk, username).
        """
        # First check if the service account user already exists
        encoded_name = quote(name)
        existing = self._request(f"/api/v3/core/users/?name={encoded_name}")
        results = existing.get("results", [])
        for user in results:
            # Service accounts usernames usually have a prefix of 'service-account-'
            if user.get("name") == name:
                return user.get("pk"), user.get("username")

        logger.info("Creating Service Account user: %s", name)
        payload = {
            "name": name,
            "create_token": False,
        }
        res = self._request("/api/v3/core/users/service_account/", method="POST", data=payload)
        user_pk = res.get("user", {}).get("pk")
        username = res.get("user", {}).get("username")

        if not user_pk or not username:
            raise AuthentikApiError(f"Failed to create service account {name}")

        return user_pk, username

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

    def add_user_to_group(self, group_uuid: str, user_pk: int) -> None:
        """Add a user/service account to a search group.

        Args:
            group_uuid: The UUID of the group.
            user_pk: The ID of the user to add.
        """
        payload = {"pk": user_pk}
        self._request(f"/api/v3/core/groups/{group_uuid}/add_user/", method="POST", data=payload)

    def delete_user(self, user_pk: int) -> None:
        """Delete a user/service account by ID.

        Args:
            user_pk: The ID of the user to delete.
        """
        logger.info("Deleting user ID: %s", user_pk)
        try:
            self._request(f"/api/v3/core/users/{user_pk}/", method="DELETE")
        except AuthentikApiError as e:
            # If already deleted, ignore
            if e.status_code == 404:
                logger.warning("User ID %s already deleted.", user_pk)
            else:
                raise e

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
