# charm-reconcile Specification

## Purpose
TBD - created by archiving change authentik-ldap-refactor. Update Purpose after archive.
## Requirements
### Requirement: Events observed unconditionally
`AuthentikLdapCharm.__init__` SHALL observe `server_info.on.ready`, `ingress.ldap_requirer.on.ready`, and `ingress.ldaps_requirer.on.ready` without any `if hasattr` or `if .events` guards.

#### Scenario: No conditional wiring
- **WHEN** `AuthentikLdapCharm.__init__` runs
- **THEN** all event observations are unconditional — no `if self.xxx.events:` blocks exist

### Requirement: `_on_holistic_handler` sets MaintenanceStatus and delegates
`_on_holistic_handler(self, event)` SHALL set `self.unit.status = ops.MaintenanceStatus("Configuring resources")` then call `self._holistic_handler(event)`.

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

### Requirement: `render_pebble_layer` uses EnvVarConvertible sources
`_ensure_pebble_layer()` SHALL call `self._pebble.render_pebble_layer(server_info, config)` passing `EnvVarConvertible` objects, instead of calling `AuthentikLdapWorkload.build_layer(build_env())` directly.

#### Scenario: Layer applied when ready
- **WHEN** `server_info.is_ready()` is `True`
- **THEN** `PebbleService.render_pebble_layer()` is called and `PebbleService.plan()` is called

#### Scenario: Layer not applied when not ready
- **WHEN** `server_info.is_ready()` is `False`
- **THEN** `PebbleService.render_pebble_layer()` is NOT called

### Requirement: `_ensure_ldap_provider()` provisions isolated Service Accounts and sets relation data
`charm.py._ensure_ldap_provider()` SHALL use the ingress URL (from `IngressPerUnitRequirer`) if available, falling back to `model.get_binding(LDAP_RELATION).network.bind_address`. For each integrated `ldap` relation, the charm leader SHALL provision a unique Service Account on the Authentik server via the API client, set a strong random password, assign it to the directory search group, and populate the peer relation. The charm SHALL then call `ldap_provider.update_relation_data(relation_id, address, base_dn, bind_dn, password)` to populate the relation databag.

#### Scenario: Address from ingress
- **WHEN** `IngressIntegration.ldap_requirer` has a ready URL and a relation is updated
- **THEN** the LDAP address is derived from the ingress URL

#### Scenario: Address from pod IP
- **WHEN** no ingress URL is available and a relation is updated
- **THEN** the LDAP address is derived from `model.get_binding(LDAP_RELATION).network.bind_address`

### Requirement: `_on_collect_status()` reports all relevant statuses
`_on_collect_status` SHALL add statuses without early returns (accumulation pattern):
- `WaitingStatus("waiting for pebble")` if container not connected
- `BlockedStatus("missing authentik-server-info relation")` if `server_info.is_ready()` is `False`
- `BlockedStatus(...)` with service log message if `_workload_service.is_failing()` is `True`
- `WaitingStatus("waiting for service to start")` if `_workload_service.is_running()` is `False`
- `ActiveStatus()` as the final fallback

#### Scenario: Active when ready
- **WHEN** container can connect, `server_info.is_ready()` is `True`, and service is running
- **THEN** `ActiveStatus` is added to the status event

#### Scenario: Blocked without server info
- **WHEN** `server_info.is_ready()` is `False`
- **THEN** `BlockedStatus` with message `"missing authentik-server-info relation"` is added

