## MODIFIED Requirements

### Requirement: `_ensure_ldap_provider()` provisions isolated Service Accounts and sets relation data
`charm.py._ensure_ldap_provider()` SHALL use the Traefik route address when available and otherwise use the application service address. For each integrated `ldap` relation, the leader SHALL provision a deployment-unique Authentik bind user, set a strong random password, add the user idempotently to the deployment-specific managed role, and populate peer tracking without plaintext passwords. The role SHALL carry a post-verified provider-object-scoped full-directory-search permission. The charm SHALL call `ldap_provider.update_relation_data(relation_id, address, base_dn, bind_dn, password)` without changing the public LDAP relation contract. Reconciliation SHALL add every already tracked bind user to the managed role and SHALL NOT query or mutate Authentik search groups.

#### Scenario: Address from Traefik route
- **WHEN** the Traefik route has a ready external host
- **THEN** the LDAP address is derived from that route

#### Scenario: Address from application service
- **WHEN** no external route is available
- **THEN** the LDAP address is derived from the Juju application and model service name

#### Scenario: Existing users gain managed role membership
- **WHEN** an existing deployment with tracked bind-user IDs is upgraded
- **THEN** all tracked users are added idempotently to the deployment-specific role
- **THEN** no search-group lookup or group membership API call is made

#### Scenario: Relation contract remains stable
- **WHEN** a relation user is successfully authorized
- **THEN** URLs, base DN, bind DN, bind password, authentication method, and LDAPS flag remain compatible with existing consumers

### Requirement: `_on_collect_status()` reports all relevant statuses
`_on_collect_status` SHALL add statuses without early returns (accumulation pattern):
- `WaitingStatus("waiting for pebble")` if container not connected
- `BlockedStatus("missing authentik-server-info relation")` if `server_info.is_ready()` is `False`
- `BlockedStatus(...)` with service log message if `_workload_service.is_failing()` is `True`
- `WaitingStatus("waiting for service to start")` if `_workload_service.is_running()` is `False`
- `ActiveStatus()` as the final fallback

Managed provider-scoped RBAC replaces the removed `search_group` option, so status
collection SHALL NOT perform any Authentik group lookup or raise a search-group status.

#### Scenario: Active when ready
- **WHEN** container can connect, `server_info.is_ready()` is `True`, and the service is running
- **THEN** `ActiveStatus` is added to the status event

#### Scenario: No search-group status is produced
- **WHEN** status is collected
- **THEN** no `BlockedStatus` referring to a missing LDAP search group is added
