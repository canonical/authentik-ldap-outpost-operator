## Why

The charm was created in a hackathon with structural shortcuts that make it fragile and hard to maintain. Five issues must be resolved before the charm can be considered production-ready:

1. **Broken lib**: `lib/charms/authentik_server/v0/authentik_server_info.py` has a broken event infrastructure (`ObjectEvents` not subclassed correctly) and a secret persistence bug. The server charm has fixed the canonical copy; the LDAP outpost must adopt it.
2. **Extraneous/wrong files**: `src/authentik_ldap_outpost.py`, `src/cli.py`, `src/secret.py` are dead code. `src/utils.py` exists but contains scaffold leftovers (`condition_factory`, `database_integration_exists`) not relevant to this charm.
3. **`Integrations` god-object**: `integrations.py` exposes an `Integrations` wrapper holding all sub-integrations instead of individual `EnvVarConvertible` classes. This makes `charm.py` depend on an aggregate object rather than composable units.
4. **Awkward conditional event wiring**: `charm.py.__init__` checks `if self.integrations.server_info.events:` before observing events, working around the broken lib. With the fixed lib, events can be observed unconditionally.
5. **Missing structural patterns**: The charm does not follow the canonical Canonical Identity Platform patterns used by authentik-server and tenant-service: no `WorkloadService`, no `NOOP_CONDITIONS` guard, no `_on_holistic_handler` rename, no `_on_pebble_ready` / check handlers, `startup: "enabled"` in Pebble layer (should be `"disabled"`), and `configs.py` is missing `to_env_vars()`.

## What Changes

- Update `lib/charms/authentik_server/v0/authentik_server_info.py` to the fixed version (correct `ObjectEvents` subclassing, idempotent secret creation, `on.ready` event, `get_info()` returning `ServerInfoData`)
- Delete `src/authentik_ldap_outpost.py`, `src/cli.py`, `src/secret.py`; replace `src/utils.py` with a clean version containing `container_connectivity`, `server_info_integration_exists`, `NOOP_CONDITIONS`
- Refactor `src/integrations.py`: remove `Integrations` god-object; keep `ServerInfoIntegration(EnvVarConvertible)`, `LdapProviderIntegration`, `IngressIntegration` as standalone classes
- Add `WorkloadService` to `src/services.py` (is_running, is_failing, open_port, set_version); fix `PebbleService`: `startup: "disabled"`, health check, proper start vs replan logic
- Fix `src/env_vars.py`: remove `EnvVarMerger`, add `EnvVars` TypeAlias, align `DEFAULT_CONTAINER_ENV` with actual env vars; fix `src/configs.py` to implement `to_env_vars()` with log_level and proxy vars
- Rewrite `src/charm.py`: rename `_on_event` → `_on_holistic_handler` (sets MaintenanceStatus), add `_holistic_handler()` with NOOP_CONDITIONS guard; add `_on_pebble_ready`, `_on_pebble_check_failed/recovered`; observe `server_info.on.ready` unconditionally; use `EnvVarConvertible` sources in `render_pebble_layer()`; improve `_on_collect_status` with is_running/is_failing

## Capabilities

### New Capabilities

- `server-info-lib`: Fixed `authentik_server_info` requirer with correct event infrastructure and `ServerInfoData` model
- `integration-wrappers`: Individual `EnvVarConvertible` integration classes replacing the god-object
- `utils-and-services`: Clean `utils.py` (NOOP_CONDITIONS), `WorkloadService` in `services.py`, Pebble layer fixes
- `charm-reconcile`: Clean `charm.py` with `_on_holistic_handler`, NOOP_CONDITIONS guard, pebble event handlers, improved collect_status

### Modified Capabilities

(none — all existing capabilities are replaced or removed)

## Non-goals

- Observability wiring (`LogForwarder`, `MetricsEndpointProvider`, `KubernetesComputeResourcesPatch`) — separate change: `authentik-ldap-observability`
- Changes to `charmcraft.yaml` — handled in `authentik-ldap-charmcraft-fix`
- Provider-side library changes (server charm's responsibility)
- TLS handling

## Impact

- `lib/charms/authentik_server/v0/authentik_server_info.py` — full rewrite
- `src/utils.py` — replace with clean NOOP_CONDITIONS version
- `src/services.py` — add `WorkloadService`; fix `PebbleService` (startup, restart logic)
- `src/env_vars.py` — remove `EnvVarMerger`, add `EnvVars` TypeAlias, align defaults
- `src/configs.py` — add `to_env_vars()` with log_level and proxy vars
- `src/integrations.py` — refactor; remove `Integrations` class
- `src/charm.py` — rename handler, add WorkloadService, NOOP_CONDITIONS, pebble event handlers
- `src/authentik_ldap_outpost.py`, `src/cli.py`, `src/secret.py` — deleted
- `tests/unit/` — update for new class structure
