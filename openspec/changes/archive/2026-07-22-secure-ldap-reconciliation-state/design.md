## Context

Authentik mutations cannot be rolled back by Juju. The current client creates a new transport per request, retries by parsing exception text, and collapses several HTTP failures into one exception. Reconciliation also stores outpost and bind credentials in the peer databag, treats all outpost verification failures as absence, and discards orphan deletion state after failures.

## Goals / Non-Goals

**Goals:**

- Make HTTP retry and reconciliation decisions from typed failure categories.
- Reuse one authenticated `requests.Session` per client with bounded attempts.
- Keep secrets out of peer data without changing the public LDAP relation contract.
- Migrate existing deployments safely and make credential/deletion recovery resumable.

**Non-Goals:**

- RBAC/search-group removal, cached defaults, unique resource names, or automation-token changes.
- Persisting transient status or changing internal HTTP/`AUTHENTIK_INSECURE` behavior.
- Changing `glauth_ldap` fields or the `bind_password_secret` consumer contract.

## Decisions

1. **Typed errors and retry boundary.** `AuthentikApiError` remains the base type, with explicit connection and HTTP subclasses and a typed not-found subclass. A client-owned `requests.Session` carries headers. `_request` retries at most three attempts only for connection failures, HTTP 429, and HTTP 5xx; all other HTTP failures escape immediately. This keeps mutation retries finite while preserving caller classification. A broad time-based retry or status-string inspection was rejected because it can blindly replay permanent failures.

2. **Only required flow lookup.** Provider provisioning resolves the invalidation flow by its direct slug and uses the LDAP bind flow for both authentication and authorization provider fields. The unused default authorization-flow request and separate retry loop are removed; transport-level retry policy remains authoritative.

3. **Definitive absence controls reprovisioning.** Existing resource verification returns false only for a typed 404. Authentication, authorization, connection, rate-limit exhaustion, and server errors bubble to reconciliation rather than triggering more non-transactional mutations.

4. **Outpost token secret migration.** The leader stores `{"token": value}` in an application-owned Juju secret and writes only `outpost_token_secret_id` to peer data. On legacy state, it creates the secret, reads it back by ID, verifies the token, then removes plaintext. Followers read the ID and secret content directly. A failed verification leaves plaintext intact for retry.

5. **Bind password ownership.** Peer `client_<id>` JSON stores only `user_id` and `username`. Existing relation passwords come from `LdapProvider.get_bind_password()`, whose managed secret continues to publish `bind_password_secret`. If peer identity exists but that secret is absent, the leader rotates the Authentik password, republishes through the library, and followers wait until the secret becomes readable. Legacy plaintext is removed only after the library secret is published.

6. **Deletion completion.** Orphan state is cleared only after successful deletion. The API client's `delete_user` treats typed 404 as successful idempotent completion; every other typed failure preserves tracking for a later hook.

## Risks / Trade-offs

- A connection loss after Authentik accepts a mutation can still lead to replay; bounded retries reduce but cannot eliminate this external non-transactional ambiguity.
- Secret migration temporarily retains plaintext when Juju secret verification fails; this deliberately favors recoverability and is retried by later reconciliation.
- Missing bind secrets require password rotation, temporarily invalidating an old consumer credential until the unchanged relation contract republishes the new secret revision.
