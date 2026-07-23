## Why

The outpost charm authenticated to the Authentik API with the `bootstrap-token` received over `authentik-server-info`, and required a separate, unused bootstrap password. The server now publishes its Authentik API token under a single canonical `api-token` key (dropping the `bootstrap-token` alias and the bootstrap-password field), so the outpost consumes that key instead.

## What Changes

- Update the vendored `authentik_server_info` charm library to LIBPATCH 4, which resolves the API token from the canonical `api-token` secret key (no bootstrap-token alias, no bootstrap-password field).
- Rename `ServerInfo.bootstrap_token` to `api_token` and drop the bootstrap-password requirement from `ServerInfoIntegration.get_info()` and readiness.
- Authenticate every control-plane `AuthentikApiClient` call in `src/charm.py` with the API token resolved from `api-token`.

## Capabilities

### Modified Capabilities
- `charm-reconcile`: The outpost consumes the API token from the canonical `api-token` server-info key and no longer depends on the bootstrap password.

## Non-goals

- Changing the consumer-facing `ldap` relation, internal HTTP transport, or `AUTHENTIK_INSECURE`.

## Impact

- `lib/charms/authentik_server/v0/authentik_server_info.py`: library sync to LIBPATCH 4.
- `src/integrations.py`: `ServerInfo`/`ServerInfoIntegration` token handling.
- `src/charm.py`: automation-token authentication for all API clients.
