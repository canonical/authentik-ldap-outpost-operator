## Why

The `ldap` interface requirer supplies `user` and `group` (the bind account it wants), but the outpost ignores them and always mints `ldap-client-<identity>-<relation_id>`. The interface's functional contract (a working, search-capable bind account whose `bind_dn`/`bind_password` are returned) is already met, but the requested identity is not reflected, hurting operator traceability.

## What Changes

- Read the requirer's `user`/`group` from the `ldap` relation databag during reconciliation.
- Fold the sanitized requested `user` into the still-unique bind username: `ldap-client-<user>-<identity>-<relation_id>` (falls back to the current form when `user` is absent). The requirer is unaffected because it consumes the returned `bind_dn`.
- Adopt-only group membership: if an Authentik group with the requested `group` name already exists, add the bind user to it; otherwise log and skip. Groups are never auto-created (avoids directory pollution and collisions with managed groups). Full-directory search stays on the RBAC role.
- Track `last_user`/`last_group` per relation in peer data; on change, rename the bind user (collision-refused) and move group membership idempotently.
- Reintroduce Authentik group lookup/membership methods on the API client (distinct from RBAC role membership).

## Capabilities

### Modified Capabilities
- `charm-reconcile`: Bind-account provisioning reflects the requirer's requested `user`/`group` while preserving deployment-unique naming and RBAC-based search.

## Non-goals

- Honoring `group` as the bind DN's OU (Authentik fixes binds to `ou=users`).
- Auto-creating Authentik groups from arbitrary requirer input.
- Changing RBAC-based search authorization or the consumer-facing relation schema.

## Impact

- `src/api_client.py`: group lookup + membership methods.
- `src/charm.py`: requirer-data-driven bind username and group membership with change detection.
- `tests/unit/`: naming, change detection, group adopt/skip, collision refusal.
