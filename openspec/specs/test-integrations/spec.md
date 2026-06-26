# test-integrations Specification

## Purpose
TBD - created by archiving change authentik-ldap-tests. Update Purpose after archive.
## Requirements
### Requirement: TestServerInfoIntegration — to_env_vars returns env when ready
`test_integrations.py` SHALL contain a class `TestServerInfoIntegration`. It MUST include a test `test_to_env_vars_returns_env_when_ready` that constructs `ServerInfoIntegration` with a `create_autospec()`-mocked requirer whose `is_ready()` returns `True` and whose data yields `authentik_host` and a resolved bootstrap token. The test MUST assert that `to_env_vars()` returns a dict containing keys `AUTHENTIK_HOST` and `AUTHENTIK_TOKEN`.

#### Scenario: Ready requirer produces AUTHENTIK_HOST and AUTHENTIK_TOKEN
- **WHEN** `ServerInfoIntegration.to_env_vars()` is called with `is_ready()` mocked to `True` and host/token provided
- **THEN** the result contains `"AUTHENTIK_HOST"` with the expected host value
- **THEN** the result contains `"AUTHENTIK_TOKEN"` with the expected token value

### Requirement: TestServerInfoIntegration — to_env_vars empty when not ready
`TestServerInfoIntegration` MUST include a test `test_to_env_vars_empty_when_not_ready` asserting that `to_env_vars()` returns an empty dict when `is_ready()` returns `False`.

#### Scenario: Not-ready requirer produces empty env vars
- **WHEN** `ServerInfoIntegration.to_env_vars()` is called with `is_ready()` mocked to `False`
- **THEN** the result is an empty dict `{}`

### Requirement: TestServerInfoIntegration — is_ready delegates to requirer
`TestServerInfoIntegration` MUST include a test `test_is_ready_delegates_to_requirer` verifying that `ServerInfoIntegration.is_ready()` returns the value reported by the underlying requirer object.

#### Scenario: is_ready propagates True
- **WHEN** the mocked requirer's ready state is `True`
- **THEN** `ServerInfoIntegration.is_ready()` returns `True`

#### Scenario: is_ready propagates False
- **WHEN** the mocked requirer's ready state is `False`
- **THEN** `ServerInfoIntegration.is_ready()` returns `False`

### Requirement: TestTracingData — load returns empty when not ready
`test_integrations.py` SHALL contain a class `TestTracingData`. It MUST include a test `test_load_returns_empty_when_not_ready` asserting that `TracingData.load()` returns a `TracingData` instance with no endpoint set when the tracing requirer is not ready.

#### Scenario: Tracing requirer not ready produces empty TracingData
- **WHEN** `TracingData.load()` is called with a mocked requirer that is not ready
- **THEN** the returned `TracingData` has no OTLP endpoint set

### Requirement: TestTracingData — load returns endpoint when ready
`TestTracingData` MUST include a test `test_load_returns_endpoint_when_ready` asserting that `TracingData.load()` returns a `TracingData` instance with the OTLP endpoint populated when the tracing requirer is ready.

#### Scenario: Tracing requirer ready produces TracingData with endpoint
- **WHEN** `TracingData.load()` is called with a mocked requirer that returns an OTLP gRPC endpoint
- **THEN** the returned `TracingData` has the endpoint set to the expected value

### Requirement: TestTracingData — to_env_vars returns OTLP endpoint when ready
`TestTracingData` MUST include a test `test_to_env_vars_returns_otlp_endpoint_when_ready` asserting that `TracingData.to_env_vars()` returns a dict with the `AUTHENTIK_BLUEPRINTS_CONFIGOVERLAYS` or appropriate tracing env var key containing the OTLP endpoint when data is present.

#### Scenario: TracingData with endpoint produces tracing env var
- **WHEN** `TracingData.to_env_vars()` is called on an instance with an endpoint set
- **THEN** the result contains the expected tracing env var key with the endpoint value

### Requirement: TestTracingData — to_env_vars empty when not ready
`TestTracingData` MUST include a test `test_to_env_vars_empty_when_not_ready` asserting that `TracingData.to_env_vars()` returns an empty dict when no endpoint is present.

#### Scenario: TracingData without endpoint produces empty env vars
- **WHEN** `TracingData.to_env_vars()` is called on an instance with no endpoint
- **THEN** the result is an empty dict `{}`

