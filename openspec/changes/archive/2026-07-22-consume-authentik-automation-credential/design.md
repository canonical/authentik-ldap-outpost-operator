## Context

The server publishes a dedicated LDAP automation token through `authentik-server-info` under the canonical `api-token` secret key. The outpost must consume that token, without depending on any bootstrap password and without changing the consumer-facing LDAP relation. The charm is pre-release, so this is a clean cutover with no compatibility alias.

## Goals / Non-Goals

**Goals:**
- Resolve the token from the canonical `api-token` key.
- Remove the bootstrap-password dependency from outpost readiness.
- Use the automation token for all Authentik control-plane calls.

**Non-Goals:**
- Any change to the `ldap` relation contract or transport.

## Decisions

### Library-driven token resolution

`AuthentikServerInfoRequirer.get_authentik_token()` (LIBPATCH 4) returns the `api-token` value. The outpost relies on the library for resolution rather than reading secret keys directly.

### Readiness no longer needs the password

`ServerInfoIntegration.get_info()` requires only host and token. `ServerInfo` exposes `api_token`; the previously required `bootstrap_password` field is removed because the outpost never used it for API access.

## Risks / Trade-offs

- **Clean cutover:** Provider and consumer are upgraded together; there is no legacy `bootstrap-token` fallback or bootstrap-password field.
