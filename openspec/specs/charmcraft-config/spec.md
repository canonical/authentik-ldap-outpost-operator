# charmcraft-config Specification

## Purpose

This specification defines the declarative Juju charm configuration (`charmcraft.yaml`) required to package, build, deploy, and integrate the Authentik LDAP Outpost Charm.

### Design Decisions
- **Non-Root Container Policy**: Standardizes container deployment to run securely as non-root under the Juju `charm-user`, explicitly removing hardcoded container-level `uid` and `gid` configurations.
- **Container Realignment**: Standardizes the workload container name as `authentik-ldap` (realigned from the legacy scaffold `authentik-ldap-outpost`) to synchronize the declarative package configuration with internal Python constants.
- **Upstream Outpost Sync**: Pin the OCI image's upstream source to a verified, stable release of the `goauthentik/ldap` binary (`2026.2.2`).
- **Clean Interface & Relation Declarations**: Removes irrelevant database relations (like PostgreSQL `pg-database` inherited from template boilerplate) and explicitly defines required and optional charm interfaces:
  - `authentik-server-info` (receive Authentik host & token info)
  - `ldap` (provide LDAP connections to consuming apps)
  - `ingress` & `ldaps-ingress` (expose LDAP/S outside the K8s cluster)
  - `authentik-ldap-peers` (replicate outpost unit states)
- **Cached LDAP Availability**: Defaults search and bind operations to Authentik's cache for outage tolerance while retaining explicit `direct` modes for live consistency. Cached data requires warm-up and can delay search freshness, password changes, and revocations, so operators receive migration and security guidance.
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

### Requirement: Expose plain LDAP configuration option
The charm `charmcraft.yaml` MUST declare a boolean configuration option named `expose_ldap_ingress` with a default value of `false`.

#### Scenario: Configuration option is declared with correct default
- **WHEN** the charm metadata is parsed
- **THEN** the configuration contains `expose_ldap_ingress` of type `boolean` with a default of `false`

### Requirement: Declare LDAP provider modes with cached defaults
The charm `charmcraft.yaml` MUST declare string configuration options named `search_mode` and `bind_mode`. Both options MUST default to `cached`, and both MUST continue to support explicit `direct` values.

#### Scenario: Unset provider modes use cached behavior
- **WHEN** an operator deploys or upgrades the charm without explicitly configuring `search_mode` or `bind_mode`
- **THEN** the effective value of each option is `cached`
- **THEN** the charm sends `cached` for both modes when reconciling the Authentik LDAP provider

#### Scenario: Operator selects live provider modes
- **WHEN** an operator explicitly configures `search_mode=direct` and `bind_mode=direct`
- **THEN** the charm accepts the configuration
- **THEN** the charm sends `direct` for both modes when reconciling the Authentik LDAP provider

### Requirement: Document cached-mode migration and security behavior
The LDAP charm documentation MUST explain that cached operation requires cache warm-up, search results can remain stale until synchronization, and password changes and session revocations can take effect only after cached bind state is refreshed. It MUST instruct operators who require live consistency to run `juju config authentik-ldap-outpost search_mode=direct bind_mode=direct` before refreshing the charm.

#### Scenario: Operator assesses an upgrade
- **WHEN** an operator reviews the LDAP charm documentation before upgrading from a release whose implicit defaults were `direct`
- **THEN** the operator can identify the freshness, warm-up, password-change, and session-revocation implications of cached operation
- **THEN** the operator can find the command to explicitly set both modes to `direct` before refreshing the charm

