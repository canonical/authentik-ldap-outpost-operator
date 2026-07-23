## Why

LDAP outpost reconciliation currently retries permanent Authentik API failures, treats any verification failure as missing state, and persists sensitive credentials in plaintext peer data. These behaviors can duplicate non-transactional Authentik mutations, hide authorization failures, and expose credentials unnecessarily.

## What Changes

- Reuse one HTTP session and classify Authentik API failures with typed errors, retrying only bounded connection, HTTP 429, and HTTP 5xx failures.
- Resolve only the invalidation flow required by LDAP provider creation and propagate non-not-found verification failures.
- Store the outpost token in an application-owned Juju secret, migrate legacy plaintext leader state only after verifying secret readability, and let followers resolve the secret by ID.
- Remove LDAP client bind passwords from peer JSON while retaining the existing `glauth_ldap` relation data and `bind_password_secret` contract.
- Recover existing bind passwords through `LdapProvider.get_bind_password()` and safely rotate/recreate credentials when that secret is unavailable.
- Keep orphan deletion tracking until Authentik confirms deletion or returns a typed not-found response.

## Capabilities

### New Capabilities

- `secure-ldap-reconciliation-state`: Defines retry classification, authoritative resource verification, secret-backed outpost tokens and LDAP bind credentials, and resumable deletion state.

### Modified Capabilities

None.

## Impact

- `src/api_client.py`: session reuse, typed errors, retries, and flow resolution.
- `src/charm.py`: verification semantics, peer-state migration, secret-backed credentials, and deletion tracking.
- `src/integrations.py`: existing-relation bind-password retrieval without changing consumer relation fields.
- `tests/unit/test_api_client.py`, `tests/unit/test_charm.py`, and related fixtures: focused behavioral coverage.

## Non-goals

- RBAC or search-group removal.
- Cached default values.
- Unique Authentik resource names.
- Automation-token contract changes.
- Changes to the consumer-facing `glauth_ldap` relation schema.
