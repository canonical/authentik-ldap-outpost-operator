## Why

The existing unit tests for `authentik-ldap-outpost-operator` use the legacy `Harness` API and ad-hoc `testing.Harness` calls, inconsistent with the `ops.testing` (Scenario) + `create_state()` pattern used by `authentik-server-operator` and `tenant-service-operator`. This leaves the test suite fragile, hard to extend, and out of sync with project conventions.

## What Changes

- **DELETE** legacy `Harness`-based tests from `tests/unit/test_charm.py`, `tests/unit/test_integrations.py`, and `tests/unit/test_services.py`.
- **CREATE** `tests/unit/conftest.py` with the `create_state()` factory and shared fixtures (`mocked_k8s_resource_patch`, `context`, `container`, `server_info_relation`).
- **REWRITE** `tests/unit/test_charm.py` using Scenario classes: `TestHolisticHandler`, `TestCollectStatus`, `TestPebbleReadyEvent`.
- **REWRITE** `tests/unit/test_integrations.py` using `create_autospec()` isolation: `TestServerInfoIntegration`, `TestTracingData`.
- **REWRITE** `tests/unit/test_services.py` using `create_autospec()` isolation: `TestPebbleService`, `TestWorkloadService`.

## Capabilities

### New Capabilities

- `conftest`: `tests/unit/conftest.py` with `create_state()` factory and autouse fixtures for resource-patch mocking, a `context` fixture, a `container` fixture, and a `server_info_relation` fixture.
- `test-charm`: Rewritten `tests/unit/test_charm.py` with `TestHolisticHandler`, `TestCollectStatus`, and `TestPebbleReadyEvent` test classes covering NOOP guard paths, status reporting, and pebble-ready side effects.
- `test-integrations`: Rewritten `tests/unit/test_integrations.py` for `ServerInfoIntegration` (`is_ready`, `to_env_vars`) and `TracingData` (`load`, `to_env_vars`) using `create_autospec()`.
- `test-services`: Rewritten `tests/unit/test_services.py` for `PebbleService` (layer merging, plan start/replan) and `WorkloadService` (`open_port`, `is_running`, `is_failing`) using `create_autospec()`.

### Modified Capabilities

## Impact

- `tests/unit/conftest.py` — new file
- `tests/unit/test_charm.py` — full rewrite (references `charm.py`, `constants.py`, `integrations.py`, `services.py`)
- `tests/unit/test_integrations.py` — full rewrite (references `integrations.py`, `env_vars.py`)
- `tests/unit/test_services.py` — full rewrite (references `services.py`, `constants.py`)
- No changes to `src/` modules, `lib/charms/`, or integration tests.
