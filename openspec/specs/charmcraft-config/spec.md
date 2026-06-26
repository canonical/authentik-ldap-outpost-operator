# charmcraft-config Specification

## Purpose
TBD - created by archiving change authentik-ldap-charmcraft-fix. Update Purpose after archive.
## Requirements
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

