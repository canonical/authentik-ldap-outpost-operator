# test-services Specification

## Purpose
TBD - created by archiving change authentik-ldap-tests. Update Purpose after archive.
## Requirements
### Requirement: TestPebbleService — render_pebble_layer merges sources
`test_services.py` SHALL contain a class `TestPebbleService`. It MUST include a test `test_render_pebble_layer_merges_sources` asserting that `PebbleService.render_pebble_layer()` (or equivalent layer-building call) produces a `pebble.Layer` that contains the service definition from the workload and any environment variables sourced from the integration wrappers.

#### Scenario: Layer contains service with merged env vars
- **WHEN** `PebbleService` renders a Pebble layer with a dict of env vars
- **THEN** the resulting layer contains a service named `"authentik-ldap"` (the `SERVICE_NAME` constant)
- **THEN** the service's `environment` dict contains the supplied env vars
- **THEN** the layer contains a `checks` section with a TCP health check on `LDAP_PORT`

### Requirement: TestPebbleService — plan starts service when not running
`TestPebbleService` MUST include a test `test_plan_starts_service_when_not_running` asserting that when the service is not currently running, calling `PebbleService.plan()` (or equivalent) invokes `container.replan()` on the Pebble container mock.

#### Scenario: Service not running triggers replan
- **WHEN** `PebbleService.plan()` is called and the container mock reports the service as not running
- **THEN** `container.replan()` is called

### Requirement: TestPebbleService — plan replans when running
`TestPebbleService` MUST include a test `test_plan_replans_when_running` asserting that when the service is already running, `PebbleService.plan()` still calls `container.replan()` to apply updated configuration.

#### Scenario: Service already running still triggers replan
- **WHEN** `PebbleService.plan()` is called and the container mock reports the service as active
- **THEN** `container.replan()` is called

### Requirement: TestWorkloadService — open_port opens LDAP and LDAPS
`test_services.py` SHALL contain a class `TestWorkloadService`. It MUST include a test `test_open_port_opens_ldap_and_ldaps` asserting that `WorkloadService.open_port()` calls the underlying unit `open_port` API (or equivalent) for both `LDAP_PORT` (3389) and `LDAPS_PORT` (6636).

#### Scenario: open_port opens both LDAP and LDAPS ports
- **WHEN** `WorkloadService.open_port()` is called
- **THEN** port `3389` (LDAP_PORT) is opened
- **THEN** port `6636` (LDAPS_PORT) is opened

### Requirement: TestWorkloadService — is_running true when service up and check up
`TestWorkloadService` MUST include a test `test_is_running_true_when_service_up_and_check_up` asserting that `WorkloadService.is_running()` returns `True` when the Pebble service status is `ACTIVE` and the `PEBBLE_READY_CHECK_NAME` check is passing.

#### Scenario: Service active and check passing reports running
- **WHEN** the service status is `pebble.ServiceStatus.ACTIVE` and the ready check is passing
- **THEN** `WorkloadService.is_running()` returns `True`

### Requirement: TestWorkloadService — is_failing true when service up and check down
`TestWorkloadService` MUST include a test `test_is_failing_true_when_service_up_and_check_down` asserting that `WorkloadService.is_failing()` returns `True` when the Pebble service is `ACTIVE` but the `PEBBLE_READY_CHECK_NAME` check is failing.

#### Scenario: Service active but check failing reports is_failing
- **WHEN** the service status is `pebble.ServiceStatus.ACTIVE` and the ready check is failing
- **THEN** `WorkloadService.is_failing()` returns `True`

