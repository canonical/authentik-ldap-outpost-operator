## MODIFIED Requirements

### Requirement: `_ensure_ldap_provider()` provisions isolated Service Accounts and sets relation data
`charm.py._ensure_ldap_provider()` SHALL use the ingress URL (from `IngressPerUnitRequirer`) if available, falling back to `model.get_binding(LDAP_RELATION).network.bind_address`. For each integrated `ldap` relation, the charm leader SHALL provision a unique Service Account on the Authentik server via the API client, set a strong random password, assign it to the directory search group, and populate the peer relation. The charm SHALL then call `ldap_provider.update_relation_data(relation_id, address, base_dn, bind_dn, password)` to populate the relation databag. Redundant Authentik API queries for group retrieval and assignment SHALL be avoided when the config is unchanged by caching `search_group` config in `last_search_group` in the peer metadata. When the `search_group` configuration changes, the charm leader SHALL update the group membership of all existing relation users to the new search group on Authentik.

#### Scenario: Address from ingress
- **WHEN** `IngressIntegration.ldap_requirer` has a ready URL and a relation is updated
- **THEN** the LDAP address is derived from the ingress URL

#### Scenario: Address from pod IP
- **WHEN** no ingress URL is available and a relation is updated
- **THEN** the LDAP address is derived from `model.get_binding(LDAP_RELATION).network.bind_address`

#### Scenario: Search group configuration changes
- **WHEN** the `search_group` configuration option changes
- **THEN** the charm leader detects the change and updates the group membership of all existing relation users on Authentik

### Requirement: `_on_collect_status()` reports all relevant statuses
`_on_collect_status` SHALL add statuses without early returns (accumulation pattern):
- `WaitingStatus("waiting for pebble")` if container not connected
- `BlockedStatus("missing authentik-server-info relation")` if `server_info.is_ready()` is `False`
- `BlockedStatus(...)` with service log message if `_workload_service.is_failing()` is `True`
- `WaitingStatus("waiting for service to start")` if `_workload_service.is_running()` is `False`
- `BlockedStatus("LDAP search group '<group>' not found in Authentik")` if the configured `search_group` is missing on the Authentik server
- `ActiveStatus()` as the final fallback

#### Scenario: Active when ready
- **WHEN** container can connect, `server_info.is_ready()` is `True`, service is running, and the search group exists on Authentik
- **THEN** `ActiveStatus` is added to the status event

#### Scenario: Blocked when search group does not exist
- **WHEN** the configured `search_group` does not exist on the Authentik server
- **THEN** `BlockedStatus` with message `"LDAP search group '<group>' not found in Authentik"` is added
