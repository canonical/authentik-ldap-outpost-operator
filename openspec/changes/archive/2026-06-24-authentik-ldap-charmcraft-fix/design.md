## Context

The charm was scaffolded from a template and `charmcraft.yaml` was never updated. The container name (`authentik-ldap-outpost`) does not match the constant in `constants.py` (`authentik-ldap`), the OCI image is a placeholder pointing to a non-existent canonical image, and all custom relations are absent. Additionally, a `pg-database` relation was left in from the template — the LDAP outpost has no PostgreSQL dependency.

This design change is straightforward: there are no architectural decisions or cross-cutting concerns. All changes are mechanical corrections to the YAML manifest and constant verification.

## Goals / Non-Goals

**Goals:**
- `charmcraft pack` produces a deployable charm
- `juju deploy` starts the `authentik-ldap` container correctly
- `juju integrate` works for all documented relations without "relation not found" errors
- No container-level uid/gid override (charm-user handles non-root)

**Non-Goals:**
- Code changes beyond `charmcraft.yaml` and `constants.py` verification
- Observability wiring
- Library rewrites
- TLS handling

## Decisions

### D1: Container name follows `constants.py`, not charm name

The charm is named `authentik-ldap-outpost` but `WORKLOAD_CONTAINER = "authentik-ldap"` in `constants.py`. The container in `charmcraft.yaml` must be `authentik-ldap` to match. Renaming `constants.py` would require touching more files and is deferred.

### D2: Remove `gid`/`uid` from container spec

The `charm-user: non-root` field in `charmcraft.yaml` is the canonical way to run as non-root for Canonical Identity Platform charms. Container-level `gid`/`uid` overrides are a non-standard pattern and conflict with the operator's non-root convention.

### D3: Remove `pg-database` relation

The LDAP outpost communicates with Authentik via HTTP API (over the `authentik-server-info` relation). There is no PostgreSQL dependency. Keeping this relation would mislead operators into thinking a database integration is required.

### D4: OCI image pinned to `2026.2.2`

The upstream goauthentik LDAP image is `ghcr.io/goauthentik/ldap`. Pin to `2026.2.2` to match the server charm. Version bumps are handled separately.

## Risks / Trade-offs

- [Risk]: Renaming the container in `charmcraft.yaml` while deploying over an existing deployment would require `juju remove-unit` + redeploy (not in-place upgrade). → Mitigation: Document in release notes; this is pre-production so no live upgrades are at risk.

## Migration Plan

1. Edit `charmcraft.yaml`: rename container, fix OCI image, remove uid/gid, remove pg-database, add missing relations.
2. Verify `src/constants.py` — no code changes expected.
3. Run `charmcraft pack` to confirm build succeeds.
4. Run `tox -e lint` to confirm no regressions.
