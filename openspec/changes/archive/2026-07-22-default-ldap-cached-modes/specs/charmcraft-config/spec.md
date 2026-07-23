## Purpose

Cached LDAP search and bind modes improve outpost availability during transient Authentik server outages, while direct modes provide live consistency. The charm defaults to cached operation and keeps direct operation as an explicit choice. Because cached data requires warm-up and can delay identity, password, and revocation changes, operator guidance is part of the configuration contract; changing `search_group` and controlling Authentik's cache lifecycle are out of scope.

## ADDED Requirements

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

The LDAP charm documentation MUST explain that cached operation requires cache warm-up, search results can remain stale until synchronization, and password changes and session revocations can take effect only after cached bind state is refreshed. It MUST provide commands that pin both modes to `direct` before an upgrade for operators who require live consistency.

#### Scenario: Operator assesses an upgrade

- **WHEN** an operator reviews the LDAP charm documentation before upgrading from a release whose implicit defaults were `direct`
- **THEN** the operator can identify the freshness, warm-up, password-change, and session-revocation implications of cached operation
- **THEN** the operator can find the command to explicitly set both modes to `direct` before refreshing the charm
