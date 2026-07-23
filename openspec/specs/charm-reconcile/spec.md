# charm-reconcile Specification

## Purpose

This specification establishes the holistic reconciliation architecture of the Authentik LDAP Outpost Juju Charm. By aligning with the canonical patterns found across the platform (such as in `authentik-server` and `tenant-service`), it standardizes the event observation and orchestration model.

### Design Decisions
- **Unconditional Event Wiring**: Rather than checking for event existence dynamically (a runtime workaround for previous library constraints), `server_info.on.ready` and ingress events are observed unconditionally during charm initialization, guaranteeing predictable event-loop registration.
- **Holistic Reconciliation Pattern**: Relies on a single, unified orchestration pathway (`_reconcile()`) instead of scattered event-specific handlers. Most incoming Juju events delegate to `_on_holistic_handler` which triggers the main `_reconcile()` loop.
- **Status Accumulation Pattern**: Unit and application statuses are determined dynamically inside a centralized hook (`_on_collect_status`) rather than being modified continuously and haphazardly across different event handlers.
- **EAFP & Guard Rails**: Employs an *Easier to Ask Forgiveness than Permission (EAFP)* coding paradigm. Pre-reconciliation checks (`NOOP_CONDITIONS`) safely return early if the container is not ready or required relations are absent, avoiding unhandled tracebacks or premature state manipulation.
## Requirements
### Requirement: Events observed unconditionally
`AuthentikLdapCharm.__init__` SHALL observe `server_info.on.ready`, `ingress.ldap_requirer.on.ready`, and `ingress.ldaps_requirer.on.ready` without any `if hasattr` or `if .events` guards.

#### Scenario: No conditional wiring
- **WHEN** `AuthentikLdapCharm.__init__` runs
- **THEN** all event observations are unconditional — no `if self.xxx.events:` blocks exist

### Requirement: `_on_holistic_handler` sets MaintenanceStatus and delegates
`_on_holistic_handler(self, event)` SHALL set `self.unit.status = ops.MaintenanceStatus("Configuring resources")` then call `self._holistic_handler(event)`.

#### Scenario: Maintenance status set before reconcile
- **WHEN** `_on_holistic_handler` fires
- **THEN** `self.unit.status` is set to `MaintenanceStatus("Configuring resources")` and `_holistic_handler(event)` is called

### Requirement: `_holistic_handler` runs NOOP_CONDITIONS guard then reconciles
`_holistic_handler(self, event)` SHALL return early if any condition in `NOOP_CONDITIONS` returns `False`. Otherwise it reconciles: calls `_ensure_pebble_layer()` and `_ensure_ldap_provider()`.

#### Scenario: Guard prevents reconcile when container not ready
- **WHEN** `_holistic_handler` fires and `container_connectivity` returns `False`
- **THEN** no pebble layer is applied

### Requirement: `_on_pebble_ready` opens port, reconciles, sets version
`_on_pebble_ready(self, event)` SHALL call `self._workload_service.open_port()`, `self._on_holistic_handler(event)`, then `self._workload_service.set_version()`.

#### Scenario: Ports opened on pebble-ready
- **WHEN** the pebble-ready event fires
- **THEN** LDAP and LDAPS ports are opened on the unit

### Requirement: `_on_pebble_check_failed/recovered` log health transitions
`_on_pebble_check_failed` SHALL log a warning; `_on_pebble_check_recovered` SHALL log an info message. Both check `event.info.name == PEBBLE_READY_CHECK_NAME`.

#### Scenario: Health transitions are logged
- **WHEN** a pebble check named `PEBBLE_READY_CHECK_NAME` fails and later recovers
- **THEN** `_on_pebble_check_failed` logs a warning and `_on_pebble_check_recovered` logs an info message

### Requirement: `render_pebble_layer` uses EnvVarConvertible sources
`_ensure_pebble_layer()` SHALL call `self._pebble.render_pebble_layer(server_info, config)` passing `EnvVarConvertible` objects, instead of calling `AuthentikLdapWorkload.build_layer(build_env())` directly.

#### Scenario: Layer applied when ready
- **WHEN** `server_info.is_ready()` is `True`
- **THEN** `PebbleService.render_pebble_layer()` is called and `PebbleService.plan()` is called

#### Scenario: Layer not applied when not ready
- **WHEN** `server_info.is_ready()` is `False`
- **THEN** `PebbleService.render_pebble_layer()` is NOT called

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

### Requirement: Outpost authenticates with the api-token from server-info

The outpost charm SHALL authenticate to the Authentik REST API using the API token published over `authentik-server-info`, resolving it from the library's canonical `api-token` key, and SHALL NOT require a bootstrap password.

#### Scenario: Server publishes the canonical token
- **WHEN** the server-info token secret contains an `api-token` value
- **THEN** the outpost uses that value for every Authentik API client

#### Scenario: Readiness without bootstrap password
- **WHEN** server-info provides a host and token
- **THEN** the outpost resolves server info and reconciles without any bootstrap password

### Requirement: Bind account reflects the requirer-requested identity

For each `ldap` relation, the outpost SHALL derive the bind account username from the requirer-provided `user`, namespaced with the deployment identity and relation id to remain globally unique, and SHALL publish the resulting `bind_dn` (`cn=<username>,ou=users,<base_dn>`). When the requirer provides no `user`, the charm SHALL fall back to its deployment-unique generated name.

#### Scenario: Requested user reflected in bind username
- **WHEN** a requirer requests `user=svc`
- **THEN** the provisioned bind username contains `svc` and remains unique to the deployment and relation

#### Scenario: Missing requested user
- **WHEN** a requirer provides no `user`
- **THEN** the charm provisions its deployment-unique generated bind username

#### Scenario: Requested user changes
- **WHEN** a relation's requested `user` changes to a value whose target username is free
- **THEN** the charm renames the existing bind user to the new target and refuses if the target is owned by another user

### Requirement: Adopt-only group membership

The outpost SHALL add the bind user to an existing Authentik group whose name equals the requirer-provided `group`, and SHALL NOT create or delete groups. Full-directory search authorization remains provided by the managed RBAC role.

#### Scenario: Requested group exists
- **WHEN** the requested `group` matches an existing Authentik group
- **THEN** the bind user is added to that group

#### Scenario: Requested group does not exist
- **WHEN** no Authentik group matches the requested `group`
- **THEN** the charm logs and skips group membership without failing reconciliation

#### Scenario: Requested group changes
- **WHEN** a relation's requested `group` changes
- **THEN** the bind user is removed from the previously tracked group (if present) and added to the new group when it exists

