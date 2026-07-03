---
description: "Use when writing or modifying unit tests, integration tests, test fixtures, or conftest files for the charm. Covers test file structure, create_state() factory, ops.testing (Scenario) usage, and test organization."
applyTo: "tests/**"
---

# Testing Guidelines

## File Structure

One file per concern:

| File | Scope |
|------|-------|
| `test_charm.py` | Lifecycle events, `_reconcile()`, collect-status, relation events |
| `test_integrations.py` | Integration wrapper classes tested in isolation |
| `test_configs.py` | `CharmConfig` validation and env var output |

## Unit Tests (`tests/unit/`)

- **Framework**: `ops.testing` (Scenario). Do not use legacy `Harness`.
- **State factory**: Use `create_state()` — a **module-level factory function** in `conftest.py` (NOT a fixture). Import it directly in test files.
- **Do NOT** use `dataclasses.replace()` to modify states. Always create a fresh state via `create_state()`.
- Group tests in classes by event or feature (e.g., `TestPebbleReadyEvent`, `TestCollectStatusEvent`).

### `create_state()` Factory Pattern

```python
from unit.conftest import create_state

# Minimal state (leader=True, can_connect=True, no relations)
state = create_state()

# Custom state
state = create_state(
    leader=False,
    relations=[server_info_relation, peer_relation],
    config={"log_level": "debug"},
    can_connect=False,
)
```

Supported kwargs: `leader`, `secrets`, `relations`, `containers`, `config`, `can_connect`.
The factory builds a complete `testing.State` with sensible defaults (leader=True, can_connect=True).

### Mocking Rules

- **`mocked_k8s_resource_patch`** — Autouse fixture that mocks `KubernetesComputeResourcesPatch`.
- For `collect-unit-status` tests, mock integration `is_ready()` methods to control status path.
- Use `create_autospec()` for library objects in integration wrapper tests.

### Integration Wrapper Test Pattern

Test wrappers in isolation using `create_autospec()` for library objects:
- `to_env_vars()`: verify correct env var keys and values
- `is_ready()`: test true/false paths

These are pure mock tests — no `create_state()` needed.

```python
def test_server_info_integration_env_vars() -> None:
    requirer = create_autospec(AuthentikServerInfoRequirer)
    requirer.get_info.return_value = ServerInfoData(
        host="http://authentik:9000",
        bootstrap_token="test-token",
        bootstrap_password="test-password",
    )
    integration = ServerInfoIntegration(requirer)
    env = integration.to_env_vars()
    assert env["AUTHENTIK_BOOTSTRAP_TOKEN"] == "test-token"
```

## Integration Tests (`tests/integration/`)

- **Framework**: `jubilant` library.
- **Lifecycle order**: deploy → health check → scale up → integrations → scale down → removal.
- **Skippable**: Deploy (`--no-deploy`) and removal (`--keep-models`) must be skippable.
- Use `conftest.py` for model/charm fixtures, `constants.py` for app names, `utils.py` for helpers.
