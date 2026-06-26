# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Authentik REST API client using standard libraries."""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AuthentikApiError(Exception):
    """Base exception for Authentik API errors."""


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
        url = f"{self._host}{endpoint}"
        req_data = json.dumps(data).encode("utf-8") if data is not None else None

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if req_data:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, headers=headers, method=method, data=req_data)

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if method == "DELETE" or response.status == 204:
                    return True
                res_content = response.read().decode("utf-8")
                return json.loads(res_content) if res_content else {}
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = "Could not read error body"
            logger.error(
                "Authentik API HTTP Error %s for %s %s: %s",
                e.code,
                method,
                endpoint,
                err_body,
            )
            raise AuthentikApiError(f"HTTP Error {e.code}: {err_body}") from e
        except Exception as e:
            logger.error("Failed to connect to Authentik API: %s", e)
            raise AuthentikApiError(f"Connection failure: {e}") from e

    def _find_flow(self, flows: List[Any], slug: str, designation: str) -> Optional[str]:
        """Find a flow matching the slug or falling back to designation."""
        for flow in flows:
            if flow.get("slug") == slug:
                return flow.get("pk")
        for flow in flows:
            if flow.get("designation") == designation:
                return flow.get("pk")
        return None

    def resolve_flow_ids(self) -> Tuple[str, str]:
        """Dynamically find default authorization and invalidation flow UUIDs.

        Returns:
            A tuple of (authorization_flow_uuid, invalidation_flow_uuid).

        Raises:
            AuthentikApiError: If standard flows cannot be found.
        """
        res = self._request("/api/v3/flows/instances/")
        results = res.get("results", [])

        auth_flow = self._find_flow(
            results,
            "default-provider-authorization-implicit-consent",
            "authorization",
        )
        inval_flow = self._find_flow(
            results,
            "default-provider-invalidation-flow",
            "invalidation",
        )

        if not auth_flow or not inval_flow:
            raise AuthentikApiError(
                "Could not resolve default authorization or invalidation flows"
            )

        return auth_flow, inval_flow

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
        flows_res = self._request("/api/v3/flows/instances/")
        for flow in flows_res.get("results", []):
            if flow.get("slug") == "default-ldap-bind-flow":
                return flow.get("pk")

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

        stages_res = self._request("/api/v3/stages/all/")
        stages = stages_res.get("results", [])

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
        providers_res = self._request("/api/v3/providers/ldap/")
        provider_pk = None

        for prov in providers_res.get("results", []):
            if prov.get("name") == name:
                provider_pk = prov.get("pk")
                break

        auth_flow, inval_flow = self.resolve_flow_ids()
        bind_flow = self.get_or_create_ldap_bind_flow()

        provider_data = {
            "name": name,
            "authentication_flow": bind_flow,
            "authorization_flow": auth_flow,
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

    def get_or_create_outpost(self, name: str, provider_pk: int) -> Tuple[str, str]:
        """Find or create an LDAP Outpost, ensuring the provider is bound.

        Args:
            name: The unique name of the Outpost.
            provider_pk: The ID of the bound LDAP Provider.

        Returns:
            A tuple of (outpost_uuid, token_identifier).
        """
        outposts_res = self._request("/api/v3/outposts/instances/")
        outpost_pk = None
        token_identifier = None
        existing_providers: List[int] = []

        for op in outposts_res.get("results", []):
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
        encoded_name = urllib.parse.quote(name)
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
        encoded_name = urllib.parse.quote(name)
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
            if "404" in str(e):
                logger.warning("User ID %s already deleted.", user_pk)
            else:
                raise e
