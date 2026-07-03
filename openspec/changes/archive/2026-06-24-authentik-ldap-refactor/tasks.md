## 1. Update `lib/charms/authentik_server/v0/authentik_server_info.py`

- [x] 1.1 Define `AuthentikServerInfoRequirerReadyEvent(EventBase)` and `AuthentikServerInfoRequirerEvents(ObjectEvents)` with `ready = EventSource(AuthentikServerInfoRequirerReadyEvent)`
- [x] 1.2 Define `ServerInfoData(BaseModel)` with fields `host: str`, `bootstrap_token: str`, `bootstrap_password: str`
- [x] 1.3 Rewrite `AuthentikServerInfoRequirer.__init__` to observe `relation_changed` via `self.framework.observe()`
- [x] 1.4 Implement `_on_changed()` handler that calls `self.on.ready.emit()` when `is_ready` is `True`
- [x] 1.5 Implement `is_ready` property checking `host`, `bootstrap_token_secret_id`, `bootstrap_password_secret_id`
- [x] 1.6 Implement `get_info() -> ServerInfoData | None` retrieving secrets via `model.get_secret(id=...)`
- [x] 1.7 Increment `LIBPATCH` by 1
- [x] 1.8 Remove the broken `AuthentikServerInfoRequirerEvents` hand-rolled class and all `info_changed`/`info_removed` references

## 2. Delete extraneous `src/` files and replace `src/utils.py`

- [x] 2.1 Delete `src/authentik_ldap_outpost.py`
- [x] 2.2 Delete `src/cli.py`
- [x] 2.3 Delete `src/secret.py`
- [x] 2.4 Replace `src/utils.py` with a clean version: `container_connectivity(charm) -> bool`, `server_info_integration_exists(charm) -> bool`, `NOOP_CONDITIONS` tuple; remove all old scaffold content (`condition_factory`, `database_integration_exists`, `leader_unit`)

## 2b. Fix `src/env_vars.py` and `src/configs.py`

- [x] 2b.1 Remove `EnvVarMerger` class from `src/env_vars.py`; add `EnvVars: TypeAlias = Mapping[str, Union[str, bool]]`; update `EnvVarConvertible.to_env_vars()` return type to `EnvVars`; update `DEFAULT_CONTAINER_ENV` to include `AUTHENTIK_HOST: ""`, `AUTHENTIK_TOKEN: ""`, `AUTHENTIK_INSECURE: "true"`, `AUTHENTIK_LOG_LEVEL: "info"`
- [x] 2b.2 Add `to_env_vars(self) -> EnvVars` to `CharmConfig` in `src/configs.py` returning `AUTHENTIK_LOG_LEVEL`, `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`; remove the `log_level` property and `is_valid()` method

## 2c. Update `src/services.py`

- [x] 2c.1 Add `PEBBLE_READY_CHECK_NAME = "ready"` to `src/constants.py` (needed by WorkloadService)
- [x] 2c.2 Add `WorkloadService` class to `src/services.py`: `__init__(unit: Unit)`, `version: str` property (exec `/ldap version`, return empty on error), `set_version()`, `open_port()` (LDAP_PORT + LDAPS_PORT), `is_running() -> bool` (service running AND check UP), `is_failing() -> bool` (service running AND check DOWN)
- [x] 2c.3 Change `startup: "enabled"` → `"disabled"` in `AuthentikLdapWorkload.build_layer()` in `src/services.py`
- [x] 2c.4 Add `PebbleService.render_pebble_layer(*env_var_sources: EnvVarConvertible) -> Layer` that merges `DEFAULT_CONTAINER_ENV` with each source's `to_env_vars()` and returns a `Layer` in `src/services.py`
- [x] 2c.5 Fix `PebbleService.plan(layer)` in `src/services.py`: call `container.add_layer(SERVICE_NAME, layer, combine=True)`, then `container.start(SERVICE_NAME)` if service is not running, else `container.replan()`; raise `PebbleError` on failure

## 3. Refactor `src/integrations.py`

- [x] 3.1 Remove the `Integrations` god-object class entirely
- [x] 3.2 Remove the `HAS_AUTHENTIK_LIB` try/except guard — import directly (lib is now correct)
- [x] 3.3 Update `ServerInfoIntegration` constructor to instantiate `AuthentikServerInfoRequirer` directly (no conditional fallback)
- [x] 3.4 Rename `build_env()` → `to_env_vars()` on `ServerInfoIntegration`; update return type to `EnvVars`
- [x] 3.5 Remove `ServerInfoIntegration.events` property (no longer needed)
- [x] 3.6 Update `IngressIntegration` to expose `ldap_requirer` and `ldaps_requirer` properties (not `ldap_events`/`ldaps_events`)
- [x] 3.7 Remove `Integrations.get_unit_address()` static method

## 4. Rewrite `src/charm.py`

- [x] 4.1 Add imports: `WorkloadService` from `services`, `NOOP_CONDITIONS`, `container_connectivity`, `server_info_integration_exists` from `utils`, `TracingData` from `integrations` (after observability change)
- [x] 4.2 Replace `self.integrations = Integrations(self)` with individual assignments: `self.server_info = ServerInfoIntegration(self)`, `self.ldap_provider = LdapProviderIntegration(self)`, `self.ingress = IngressIntegration(self)`
- [x] 4.3 Add `self._workload_service = WorkloadService(self.unit)` in `__init__`
- [x] 4.4 Remove the `if self.integrations.server_info.events:` conditional block; observe `self.server_info.on.ready` unconditionally
- [x] 4.5 Observe `self.ingress.ldap_requirer.on.ready` and `self.ingress.ldaps_requirer.on.ready` unconditionally — replace all `_on_event` observations with `_on_holistic_handler`
- [x] 4.6 Replace `self.framework.observe(self.on.authentik_ldap_pebble_ready, self._on_event)` with `self.framework.observe(self.on.authentik_ldap_pebble_ready, self._on_pebble_ready)`
- [x] 4.7 Add `_on_pebble_ready(self, event: ops.PebbleReadyEvent)`: call `self._workload_service.open_port()`, `self._on_holistic_handler(event)`, `self._workload_service.set_version()`
- [x] 4.8 Add `_on_pebble_check_failed(self, event: ops.PebbleCheckFailedEvent)`: log warning if `event.info.name == PEBBLE_READY_CHECK_NAME`
- [x] 4.9 Add `_on_pebble_check_recovered(self, event: ops.PebbleCheckRecoveredEvent)`: log info if `event.info.name == PEBBLE_READY_CHECK_NAME`
- [x] 4.10 Observe `self.on.authentik_ldap_pebble_check_failed` and `self.on.authentik_ldap_pebble_check_recovered` in `__init__`
- [x] 4.11 Rename `_on_event` → `_on_holistic_handler`; have it set `self.unit.status = ops.MaintenanceStatus("Configuring resources")` then call `self._holistic_handler(event)`
- [x] 4.12 Add `_holistic_handler(self, event)`: guard with `if not all(condition(self) for condition in NOOP_CONDITIONS): return`; then call `_ensure_pebble_layer()` and `_ensure_ldap_provider()`
- [x] 4.13 Update `_ensure_pebble_layer()` to call `self._pebble.render_pebble_layer(self.server_info, self._config)` instead of `build_env()` + `build_layer()`; skip if `server_info.is_ready()` returns False
- [x] 4.14 Update `_ensure_ldap_provider()` to resolve address via ingress fallback (ingress URL first, then `model.get_binding(LDAP_RELATION).network.bind_address`)
- [x] 4.15 Update `_on_collect_status`: remove early returns; add `is_failing` / `is_running` checks; add `resources_patch.get_status()` call (needed after observability change adds `KubernetesComputeResourcesPatch`)
- [x] 4.16 Remove all imports of deleted modules (`cli`, `secret`, `authentik_ldap_outpost`)

## 5. Update unit tests

- [x] 5.1 Update `tests/unit/` to remove `Integrations` references; mock `ServerInfoIntegration`, `LdapProviderIntegration`, `IngressIntegration` individually
- [x] 5.2 Add test: `server_info.on.ready` triggers `_holistic_handler()`
- [x] 5.3 Add test: `to_env_vars()` returns correct env vars when `is_ready()` is `True`
- [x] 5.4 Add test: `to_env_vars()` returns `{}` when `is_ready()` is `False`
- [x] 5.5 Add test: `_on_collect_status` adds `BlockedStatus` when server info not ready
- [x] 5.6 Add test: `AuthentikServerInfoRequirer` emits `on.ready` when all fields present
- [x] 5.7 Add test: `get_info()` returns `None` without relation

## 6. Format and lint

- [x] 6.1 Run `tox -e fmt`
- [x] 6.2 Run `tox -e lint` — no errors
- [x] 6.3 Run `tox -e unit` — all tests pass
