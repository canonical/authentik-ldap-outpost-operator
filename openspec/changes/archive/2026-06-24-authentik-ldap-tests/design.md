## Context

The `authentik-ldap-outpost-operator` test suite currently uses the legacy `ops.testing.Harness` API mixed with isolated class instantiations. Both `authentik-server-operator` and `tenant-service-operator` have migrated fully to `ops.testing` (Scenario) with a `create_state()` module-level factory in `conftest.py`. The ldap-outpost tests must align with this convention so that contributors can apply the same mental model across all three charms.

The other in-flight changes (`authentik-ldap-charmcraft-fix`, `authentik-ldap-refactor`, `authentik-ldap-observability`) will reshape the charm's public surface — introducing `AuthentikLdapCharm`, `WorkloadService`, `PebbleService`, `ServerInfoIntegration`, `TracingData`, and `IngressIntegration`. The new test suite is written against that post-refactor surface.

## Goals / Non-Goals

**Goals:**
- Replace all legacy `Harness` usage with `ops.testing` Scenario.
- Introduce `create_state()` factory in `conftest.py` matching the authentik-server pattern.
- Provide autouse `mocked_k8s_resource_patch` so every test starts in a neutral resource-patch state.
- Test `charm.py` event handlers via Scenario state-in/state-out.
- Test integration wrappers (`ServerInfoIntegration`, `TracingData`) in isolation with `create_autospec()`.
- Test service classes (`PebbleService`, `WorkloadService`) in isolation with `create_autospec()` mocks for the Pebble container.

**Non-Goals:**
- No changes to `src/` modules.
- No integration (jubilant) test changes.
- No tests for `lib/charms/` libraries.
- No test for `LdapProviderIntegration.update_data` network path (covered by integration tests).

## Decisions

### Decision 1: `create_state()` as module-level function, not a fixture

Identical to authentik-server. Fixtures cannot be called with arbitrary keyword arguments; a plain function can. Tests import it directly: `from conftest import create_state`.

### Decision 2: Two test strategies — Scenario for charm events, `create_autospec()` for wrappers

- **Charm events** (`test_charm.py`): Use `ctx.run(ctx.on.<event>(...), state)` → inspect `state_out`. This tests the full reconciliation path including conditions, pebble plan, and status.
- **Wrapper isolation** (`test_integrations.py`, `test_services.py`): Instantiate wrappers with `create_autospec()`-mocked dependencies. No `create_state()` needed. This keeps unit tests fast and explicit about which dependency path is exercised.

### Decision 3: `mocked_k8s_resource_patch` is autouse

`KubernetesComputeResourcesPatch` calls the Kubernetes API on charm init. Making the mock autouse ensures no test accidentally hits the real API. Same pattern as authentik-server `conftest.py`.

### Decision 4: `server_info_relation` fixture returns pre-populated Relation

Avoids repeating remote app data in every test. The fixture holds:
- `remote_app_data={"authentik_host": "http://authentik:9000", "bootstrap_token_secret_id": "secret:xyz", "bootstrap_password_secret_id": "secret:abc"}`

## Risks / Trade-offs

- **Post-refactor dependency**: Tests are written against the future charm surface. If the refactor changes method signatures, tests will need updating — but that is the intended coupling point.
- **Holistic handler condition mocking**: Tests that want to skip the `NOOP_CONDITIONS` guard must patch `container_connectivity` and `server_info_integration_exists`. Patching at the `charm` module level (e.g., `mocker.patch("charm.container_connectivity", ...)`) is the correct approach — same as authentik-server.
