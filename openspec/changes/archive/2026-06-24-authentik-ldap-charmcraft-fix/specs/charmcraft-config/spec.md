## Purpose

The `charmcraft.yaml` was scaffolded but never updated to reflect the real workload. Three problems prevent the charm from deploying:

1. **Wrong container name**: `authentik-ldap-outpost` instead of `authentik-ldap`. The Pebble layer in `services.py` already targets `WORKLOAD_CONTAINER = "authentik-ldap"` from `constants.py`. A mismatch means the layer is applied to a container that doesn't exist.
2. **Wrong OCI image**: `ghcr.io/canonical/authentik-ldap-outpost:v0.2.0` is a non-existent image. The correct upstream image is `ghcr.io/goauthentik/ldap:2026.2.2`.
3. **Missing relations**: All custom relations (`authentik-server-info`, `ldap`, `ingress`, `ldaps-ingress`, `authentik-ldap-peers`) are absent from the YAML, so `juju integrate` fails for all of them.

Additional cleanup:
- `gid`/`uid` on the container are wrong — this charm uses `charm-user: non-root` in `charmcraft.yaml` for non-root execution; container-level uid/gid override is not needed and conflicts with the non-root convention.
- `pg-database` relation is bogus — the LDAP outpost does not use PostgreSQL; it connects to Authentik via HTTP API over `authentik-server-info`.

**Non-goals**: No code changes beyond `charmcraft.yaml` and `constants.py` constant verification.

## ADDED Requirements

### Requirement: Container name matches constant
`charmcraft.yaml` SHALL declare a container named `authentik-ldap` matching `WORKLOAD_CONTAINER` in `src/constants.py`. The container SHALL NOT set `gid` or `uid` fields.

#### Scenario: Pebble layer applied to correct container
- **WHEN** the charm is deployed
- **THEN** Pebble connects to the container named `authentik-ldap`
- **THEN** no `ContainerNotFoundError` is raised

### Requirement: OCI image points to upstream goauthentik image
`charmcraft.yaml` SHALL declare a resource `oci-image` with `upstream-source: ghcr.io/goauthentik/ldap:2026.2.2`.

#### Scenario: Kubernetes pulls the workload image
- **WHEN** the charm is deployed
- **THEN** Kubernetes pulls `ghcr.io/goauthentik/ldap:2026.2.2` successfully

### Requirement: All required relations declared
`charmcraft.yaml` SHALL declare the following relations:

| Name | Role | Interface | Optional | Limit |
|------|------|-----------|----------|-------|
| `authentik-server-info` | requires | `authentik_server_info` | yes | — |
| `ldap` | provides | `ldap` | no | — |
| `ingress` | requires | `ingress` | yes | 1 |
| `ldaps-ingress` | requires | `ingress` | yes | 1 |
| `authentik-ldap-peers` | peer | `authentik_ldap_peers` | — | — |

The `pg-database` relation SHALL be removed.

#### Scenario: Server info relation can be integrated
- **WHEN** the operator runs `juju integrate authentik-ldap-outpost:authentik-server-info authentik-server:authentik-server-info`
- **THEN** Juju does not raise "could not find relation" error

#### Scenario: LDAP provider relation can be integrated
- **WHEN** the operator runs `juju integrate glauth:ldap authentik-ldap-outpost:ldap`
- **THEN** Juju does not raise "could not find relation" error

#### Scenario: Ingress relations can be integrated
- **WHEN** the operator runs `juju integrate authentik-ldap-outpost:ingress traefik:ingress-per-unit`
- **THEN** Juju does not raise "could not find relation" error

#### Scenario: Peer relation is self-established
- **WHEN** the charm is deployed
- **THEN** the peer relation `authentik-ldap-peers` is established automatically by Juju

### Requirement: Constants file is complete
`src/constants.py` SHALL define `WORKLOAD_CONTAINER = "authentik-ldap"`, `LDAP_PORT = 3389`, `LDAPS_PORT = 6636`, all relation name constants used in `charm.py` and `integrations.py`, `BASE_DN`, `BIND_DN`, and `AUTHENTIK_INSECURE`.

#### Scenario: No undefined constant references
- **WHEN** `src/charm.py` and `src/integrations.py` import from `constants`
- **THEN** all imported names resolve without `ImportError`
