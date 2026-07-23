## Context

The charm currently discovers an operator-selected Authentik group, adds bind users to it, and creates provider/application/outpost/user resources from only the Juju application name. Shared Authentik deployments therefore have excessive implicit authorization and cross-model naming collisions. Existing releases cache provider, outpost, token-secret, and relation-user identifiers in the peer databag; those identifiers are the only trustworthy ownership evidence available during upgrade.

Authentik is pinned to 2026.5.3. LDAP provider property mappings intentionally remain `LDAPSourcePropertyMapping` objects created through `/propertymappings/source/ldap/`. Internal HTTP, public LDAP relation data, and server token handoff are unchanged.

## Goals / Non-Goals

**Goals:**
- Authorize bind users through a charm-owned role with `search_full_directory` scoped to exactly one LDAP provider.
- Give all charm-managed names and secret labels a deterministic deployment identity.
- Upgrade owned legacy resources without adopting or deleting ambiguous resources.
- Make RBAC operations typed, repeatable, and verified after assignment.

**Non-Goals:**
- Server automation-token handoff.
- Cleanup or adoption of resources not proven by cached identifiers.
- Changes to LDAP consumer relation fields or transport.

## Decisions

### Derive one deterministic deployment identity

`src/charm.py` derives a slug-safe application component and appends the first twelve hexadecimal characters of SHA-256 over the Juju model UUID. Resource names use this identity consistently: `ldap-provider-<identity>`, `ldap-app-<identity>` (name and slug), `ldap-outpost-<identity>`, `ldap-search-<identity>`, `ldap-client-<identity>-<relation-id>`, and `authentik-ldap-outpost-token-<identity>`.

Using the model name was rejected because model names are mutable and repeat across controllers. Using the raw UUID was rejected because it makes labels needlessly long; a stable 48-bit hash suffix is sufficient for operational uniqueness and is directly covered by cross-model tests.

### Model RBAC contracts explicitly

`src/api_client.py` exposes typed role and assigned-permission records. Exact role lookup filters server search results by equality, role creation validates returned identifiers, role membership uses Authentik's idempotent `add_user`/`remove_user` actions, and permission mutation uses `assigned_by_roles/{role_uuid}/assign|unassign/` with the fixed permission codename, LDAP-provider model, and integer provider primary key.

After every assignment, the client lists role assignments and accepts only a record whose permission, model, and `object_pk` match the intended provider. A matching permission with absent/null/empty `object_pk` is a global grant and raises a typed permanent authorization error. Trusting a successful assign response was rejected because Authentik can turn a nonexistent object primary key into a global assignment.

### Preflight migration before mutation

When cached identifiers exist, reconciliation fetches the provider and outpost by those exact IDs, loads the legacy or target application by exact slug, and requires the application provider and outpost provider list to reference the cached provider. Tracked bind users are fetched by cached integer IDs. Every resource must have either its exact legacy name or exact target name.

Before the first PATCH, reconciliation searches every target name/slug/username and rejects any target owned by a different ID. Missing linkage, unexpected names, duplicate candidates, partially cached core identifiers, or occupied targets raise `AuthentikPermanentError`. No create, rename, delete, role, or membership mutation occurs until the whole preflight succeeds. Once validated, PATCH operations rename only legacy-named resources; target-named resources are no-ops, making retries safe after interruption.

Name-only legacy discovery was rejected because another model may legitimately own the same old name. Automatic deletion was rejected because cached IDs establish identity, not permission to destroy conflicting objects.

### Reconcile authorization before exposing users

Fresh provisioning creates uniquely named core resources and the unique role, assigns and verifies the scoped permission, then adds every tracked bind user. New bind users use unique names and are added to the same cached role immediately. The `search_group` option is removed from `charmcraft.yaml` and `last_search_group` is no longer stored in peer metadata.

## Risks / Trade-offs

- [Truncated model hash can theoretically collide] → Twelve hexadecimal characters provide 48 bits and target-occupancy checks still refuse unsafe adoption.
- [Upgrade encounters manually renamed resources] → Refuse mutation with a permanent typed error rather than guessing ownership; the operator must resolve the conflict.
- [Failure between validated PATCH operations leaves a partial rename] → Each rerun accepts both exact legacy and exact target states and repeats only unfinished patches.
- [A malformed/global Authentik grant exists] → Verification rejects it; reconciliation does not report success.
- [`search_group` removed while a dev deployment set it] → Acceptable: the charm is pre-release, so the option is deleted outright with no compatibility shim; Juju rejects the now-unknown option on refresh and the operator drops it.

## Migration Plan

1. On leader reconciliation, compute the deployment identity and read cached IDs.
2. If all core cached IDs exist, preflight legacy/current core resources and tracked bind users, including every target collision check and exact application-provider/outpost linkage check.
3. Apply only the validated idempotent renames, migrate the charm-owned secret label by cached secret ID, and record the role UUID.
4. Create or locate the exact unique role, assign and verify the provider-scoped permission, and add every tracked user.
5. Continue normal provider updates and relation publication. Fresh deployments skip legacy migration and create only unique names.
6. Rollback may run the older charm because IDs remain cached, but renamed resources will not be rediscovered by old name-based fresh provisioning; operators should resolve any rollback manually rather than permitting automatic duplicate creation.

## Open Questions

None. `search_group` is removed outright because the charm is still in development.
