## Why

`charmcraft.yaml` was never properly updated after scaffolding: the container name, OCI image, and relation declarations are all wrong. The charm cannot be deployed or integrated until these are corrected.

## What Changes

- Rename container `authentik-ldap-outpost` → `authentik-ldap` (matches `WORKLOAD_CONTAINER` in `constants.py`)
- Update OCI image `upstream-source` to `ghcr.io/goauthentik/ldap:2026.2.2`
- Remove `gid`/`uid` fields from the container (charm runs non-root via `charm-user`, not container-level uid/gid)
- Remove the bogus `pg-database` relation — this charm connects to Authentik's HTTP API, not PostgreSQL
- Add all missing relations to `charmcraft.yaml`:
  - `authentik-server-info` (requires, interface `authentik_server_info`, optional)
  - `ldap` (provides, interface `ldap`)
  - `ingress` (requires, interface `ingress`, optional, limit 1)
  - `ldaps-ingress` (requires, interface `ingress`, optional, limit 1)
  - `authentik-ldap-peers` (peer, interface `authentik_ldap_peers`)
- Verify `src/constants.py` has all needed constant values

## Capabilities

### New Capabilities

- `charmcraft-config`: Correct container, OCI image, and complete relation declarations in `charmcraft.yaml`

### Modified Capabilities

(none — all capabilities are net-new corrections)

## Non-goals

- Code changes to `charm.py`, `integrations.py`, or any `src/` file beyond `constants.py`
- Observability wiring (`LogForwarder`, `MetricsEndpointProvider`, `TracingEndpointRequirer`)
- Library rewrites (separate change: `authentik-ldap-refactor`)
- TLS or certificate handling
- Grafana dashboard content

## Impact

- `charmcraft.yaml` — structural corrections; `charmcraft pack` will produce a deployable charm
- `src/constants.py` — verify existing constants are complete and correct
