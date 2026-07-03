# server-info-lib Specification

## Purpose

This specification defines the contract of the shared Juju library `lib/charms/authentik_server/v0/authentik_server_info.py`. It corrects fundamental flaws in the event dispatch system and aligns the library interface across the Authentik server and outpost operators.

### Design Decisions
- **Standard Juju Event Machinery Integration**: Corrects the custom, hand-rolled event dispatcher by making `AuthentikServerInfoRequirerEvents` properly subclass `ObjectEvents`, restoring compatibility with Juju's core lifecycle execution.
- **Unified Event Pipeline**: Replaces complex, non-standard state change event pairs (`info_changed`/`info_removed`) with a single, reliable positive trigger: `on.ready`. Consumers observe a single event which fires only when a complete databag is established.
- **Pydantic Validation**: Uses a Pydantic `BaseModel` (`ServerInfoData`) for rigid, runtime type validation of host and bootstrap secret metadata.
- **Standard Secret Identifiers**: Standardizes app databag field names (`host`, `bootstrap_token_secret_id`, `bootstrap_password_secret_id`) to maintain cross-charm interoperability.

## Requirements
### Requirement: Requirer emits `on.ready` when all fields are present
`AuthentikServerInfoRequirer` SHALL subclass `ops.Object` and declare `on = AuthentikServerInfoRequirerEvents()` where `AuthentikServerInfoRequirerEvents` subclasses `ObjectEvents`. It SHALL observe `charm.on[relation_name].relation_changed` and emit `on.ready` when `is_ready` is `True`.

#### Scenario: Ready event fires when databag is complete
- **WHEN** the provider writes `host`, `bootstrap_token_secret_id`, and `bootstrap_password_secret_id` to the app databag
- **THEN** `AuthentikServerInfoRequirer` receives `relation_changed`
- **THEN** `AuthentikServerInfoRequirer.is_ready` returns `True`
- **THEN** `on.ready` is emitted

#### Scenario: Ready event does not fire when databag is incomplete
- **WHEN** the provider writes only `host` to the app databag
- **THEN** `AuthentikServerInfoRequirer.is_ready` returns `False`
- **THEN** `on.ready` is NOT emitted

### Requirement: `is_ready` property checks all three fields
`AuthentikServerInfoRequirer.is_ready` SHALL return `True` if and only if the relation exists and the provider app databag contains non-empty values for `host`, `bootstrap_token_secret_id`, and `bootstrap_password_secret_id`.

#### Scenario: All fields present
- **WHEN** all three fields have non-empty values in the databag
- **THEN** `is_ready` returns `True`

#### Scenario: No relation
- **WHEN** no `authentik-server-info` relation is established
- **THEN** `is_ready` returns `False`

### Requirement: `get_info()` returns `ServerInfoData` or `None`
`AuthentikServerInfoRequirer.get_info()` SHALL return a `ServerInfoData(host, bootstrap_token, bootstrap_password)` Pydantic `BaseModel` when `is_ready` is `True`, or `None` otherwise. It SHALL retrieve secret values using `model.get_secret(id=...)`.

#### Scenario: Full data available
- **WHEN** `is_ready` is `True` and both secrets are accessible
- **THEN** `get_info()` returns `ServerInfoData` with correct values for `host`, `bootstrap_token`, `bootstrap_password`

#### Scenario: Relation not ready
- **WHEN** `is_ready` is `False`
- **THEN** `get_info()` returns `None`

### Requirement: `LIBPATCH` is incremented
The `LIBPATCH` constant in the library file SHALL be incremented by 1 from its current value.

#### Scenario: Library version bump
- **WHEN** the updated library file is committed
- **THEN** `LIBPATCH` is greater than its previous value

