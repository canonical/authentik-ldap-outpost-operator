## Context

`LdapRequirerData(user, group)` asks the provider to provision a bind account with that identity. The reference glauth provider creates `cn={user},ou={group}` and grants a search capability. Authentik differs: binds are fixed to `ou=users,<base_dn>`, search is granted through the RBAC `search_full_directory` permission (>=2024.8), and usernames are globally unique. The requirer consumes the returned `bind_dn`/`bind_password`, so the actual username need not equal its request.

## Goals / Non-Goals

**Goals:**
- Reflect the requested `user` in the (still deployment-unique) bind username.
- Add the bind user to an existing Authentik group matching the requested `group`.
- Detect and reconcile requirer changes idempotently, preserving current reconciliation semantics.

**Non-Goals:**
- Verbatim usernames (collision risk), group auto-creation, DN-OU changes, or altering RBAC search.

## Decisions

### Namespaced, requirer-derived bind username

`_bind_user_name(relation_id, requested_user)` returns `ldap-client-<sanitized-user>-<identity>-<relation_id>`, or `ldap-client-<identity>-<relation_id>` when no user is provided. `<identity>` is the existing model-UUID-hashed deployment identity, guaranteeing global uniqueness. Sanitization lowercases and strips to `[a-z0-9-]`.

Rejected: verbatim `user` (global collisions across relations/deployments/human users).

### Adopt-only group membership

The requested `group` is honored only if an Authentik group with that exact name already exists (`get_group_by_name`). The bind user is added to it via `add_user_to_group`. If absent, the charm logs and skips (search still works via the RBAC role). Groups are never created or deleted by this feature.

Rejected: auto-creating groups (directory pollution, collisions with managed groups, GC burden).

### Change detection and migration

Per-relation peer record `client_<relation_id>` gains `last_user` and `last_group`. On reconcile:
- If the target username (derived from the current `user`) differs from the tracked username, rename the bind user with the existing collision-refusing `rename_user` path and update peer + `bind_dn`.
- If `group` differs from `last_group`, remove the bind user from the old group (when it still exists) and add to the new (adopt-only); update `last_group`.
Existing relations provisioned before this change have no `last_user`; the current generated username is authoritative and is only renamed when a requested `user` is present and its target differs, blocking on an occupied target.

RBAC role membership for search is unchanged and remains separate from directory group membership.

## Risks / Trade-offs

- **Requested group missing** → membership skipped (logged); acceptable since search is RBAC-based.
- **Rename churn** if a requirer flips `user`; bounded by change detection.
- **`group`-as-OU not honored** → documented Authentik constraint.
