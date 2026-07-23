## Why

The LDAP outpost charm currently depends on a shared, operator-supplied Authentik search group and uses resource names that can collide when multiple Juju models target one Authentik deployment. The charm must own a least-privilege, provider-scoped RBAC role and uniquely identify every managed resource while upgrading existing deployments safely.

## What Changes

- Replace runtime search-group lookup and membership with a charm-managed Authentik role carrying `authentik_providers_ldap.search_full_directory` for exactly the managed LDAP provider.
- Add typed `src/api_client.py` operations for exact role lookup/create, idempotent membership, scoped permission assignment/removal, and verification that rejects global permission assignments.
- Namespace provider, application and slug, outpost, role, bind users, and charm-owned secret labels with a deterministic sanitized application/model-UUID identity.
- Migrate legacy resources only when cached identifiers and exact application-provider linkage prove ownership; rename them idempotently and refuse collisions or ambiguous ownership without mutation.
- Remove the `search_group` charm option outright (pre-release charm, no backward-compatibility shim).
- Update `src/charm.py`, `src/integrations.py`, metadata/configuration, and focused unit tests for RBAC reconciliation, migration, uniqueness, and collision refusal.

## Capabilities

### New Capabilities
- `authentik-ldap-rbac`: Charm-owned role membership and strictly provider-scoped LDAP full-directory-search authorization.
- `deployment-resource-identity`: Deployment-unique names and safe cached-ID migration for Authentik and Juju secret resources.

### Modified Capabilities
- `charm-reconcile`: Reconciliation provisions and verifies managed RBAC and migrates owned legacy resources before normal updates.
- `charmcraft-config`: `search_group` is removed.

## Impact

The change affects `src/api_client.py`, `src/charm.py`, `src/integrations.py`, `src/exceptions.py`, `charmcraft.yaml`, and focused tests under `tests/unit/`. It uses Authentik 2026.5.3 RBAC APIs but does not change internal HTTP, the public LDAP relation contract, or server automation-token handoff.

## Non-goals

- Automating server-to-outpost API token handoff.
- Changing LDAP consumer relation data or Authentik internal HTTP transport.
- Adopting, deleting, or renaming resources whose ownership cannot be proven.
