# test-charm Specification

## Purpose

This specification defines the unit tests written for the core charm orchestration module in `tests/unit/test_charm.py`. It establishes comprehensive, event-driven test coverage utilizing the `ops.testing` (Scenario) library.

### Design Decisions
- **Unified Scenario Framework**: Replaces the fragile, stateful `Harness` approach with `ops.testing.Scenario`, evaluating the charm's event handling via immutable inputs and output state transitions.
- **Critical Flow Test Coverage**:
  - **Reconciliation Guards**: Asserts that `_holistic_handler` properly returns early (NOOP) without attempting to render layers or write relation data when pre-requisites are unfulfilled.
  - **Pebble Readiness Side Effects**: Asserts that workload container startup opens the required network ports, applies the configuration, and sets the active version.
  - **centralized Status Verification**: Exhaustively tests status accumulation scenarios (`ActiveStatus`, `WaitingStatus`, and various custom `BlockedStatus` conditions) to prevent user-facing status regressions.

## Requirements
### Requirement: TestHolisticHandler — NOOP guard skips planning when container not ready
`test_charm.py` SHALL contain a class `TestHolisticHandler`. It MUST include a test `test_when_pebble_not_ready_skips_planning` that asserts the Pebble service plan is NOT updated when `can_connect=False`.

#### Scenario: Pebble not ready skips planning
- **WHEN** a `config_changed` event is run with `can_connect=False` and no relations
- **THEN** the output state's container has no service plan applied by the charm

### Requirement: TestHolisticHandler — NOOP guard skips planning when server-info missing
`TestHolisticHandler` MUST include a test `test_when_server_info_missing_skips_planning` that asserts the Pebble service plan is NOT updated when `can_connect=True` but no `authentik-server-info` relation is present.

#### Scenario: Server-info relation missing skips planning
- **WHEN** a `config_changed` event is run with `can_connect=True` and no server-info relation
- **THEN** the output state's container has no service plan applied by the charm

### Requirement: TestHolisticHandler — plans Pebble layer when all conditions met
`TestHolisticHandler` MUST include a test `test_when_all_ready_plans_pebble_layer` that asserts the Pebble layer IS applied when `can_connect=True` and a valid `server_info_relation` is present.

#### Scenario: All conditions satisfied applies Pebble layer
- **WHEN** a `config_changed` event is run with `can_connect=True` and a populated `server_info_relation`
- **THEN** the output state's container has a non-empty plan with service `"authentik-ldap"`

### Requirement: TestCollectStatus — WaitingStatus when pebble not ready
`test_charm.py` SHALL contain a class `TestCollectStatus`. It MUST include a test `test_when_pebble_not_ready_adds_waiting_status` verifying that a `WaitingStatus` is emitted when `can_connect=False`.

#### Scenario: Container not connected produces WaitingStatus
- **WHEN** `collect_unit_status` event is run with `can_connect=False`
- **THEN** `state_out.unit_status` is `testing.WaitingStatus`

### Requirement: TestCollectStatus — BlockedStatus when server-info missing
`TestCollectStatus` MUST include a test `test_when_server_info_missing_adds_blocked_status` verifying that a `BlockedStatus` is emitted when `can_connect=True` but no server-info relation is present.

#### Scenario: Missing server-info relation produces BlockedStatus
- **WHEN** `collect_unit_status` event is run with `can_connect=True` and no server-info relation
- **THEN** `state_out.unit_status` is `testing.BlockedStatus`

### Requirement: TestCollectStatus — ActiveStatus when all ready
`TestCollectStatus` MUST include a test `test_when_all_ready_adds_active_status` verifying `ActiveStatus` when container is connected, server-info relation is present, and the workload service is running.

#### Scenario: All ready produces ActiveStatus
- **WHEN** `collect_unit_status` event is run with `can_connect=True`, a populated `server_info_relation`, and the service reported as running
- **THEN** `state_out.unit_status` is `testing.ActiveStatus()`

### Requirement: TestPebbleReadyEvent — open_port called
`test_charm.py` SHALL contain a class `TestPebbleReadyEvent`. It MUST include a test `test_open_port_called_on_pebble_ready` verifying that `WorkloadService.open_port()` is called when the pebble-ready event fires.

#### Scenario: pebble_ready triggers open_port
- **WHEN** a `pebble_ready` event fires with `can_connect=True`
- **THEN** `WorkloadService.open_port` is called exactly once

### Requirement: TestPebbleReadyEvent — set_version called
`TestPebbleReadyEvent` MUST include a test `test_set_version_called_on_pebble_ready` verifying that `WorkloadService.set_version()` is called and the resulting workload version is set on the state.

#### Scenario: pebble_ready triggers set_version
- **WHEN** a `pebble_ready` event fires with `can_connect=True`
- **THEN** `WorkloadService.set_version` is called exactly once
- **THEN** `state_out.workload_version` reflects the version returned by `set_version`

