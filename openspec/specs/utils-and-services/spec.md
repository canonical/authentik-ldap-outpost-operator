# utils-and-services Specification

## Purpose
TBD - created by archiving change authentik-ldap-refactor. Update Purpose after archive.
## Requirements
### Requirement: `utils.py` contains only `container_connectivity`, `server_info_integration_exists`, and `NOOP_CONDITIONS`
`src/utils.py` SHALL define:
- `container_connectivity(charm: AuthentikLdapCharm) -> bool` — returns `charm.unit.get_container(WORKLOAD_CONTAINER).can_connect()`
- `server_info_integration_exists(charm: AuthentikLdapCharm) -> bool` — returns `bool(charm.model.get_relation(SERVER_INFO_RELATION))`
- `NOOP_CONDITIONS: tuple[Condition, ...] = (container_connectivity, server_info_integration_exists)`

All other helpers from the old `utils.py` (`condition_factory`, `database_integration_exists`, `leader_unit`) SHALL be removed.

#### Scenario: container_connectivity returns False when not connected
- **WHEN** the container cannot connect
- **THEN** `container_connectivity(charm)` returns `False`

#### Scenario: NOOP_CONDITIONS contains exactly the two conditions
- **WHEN** `NOOP_CONDITIONS` is inspected
- **THEN** it contains `container_connectivity` and `server_info_integration_exists`

### Requirement: `WorkloadService` provides lifecycle helpers
`services.py` SHALL define a `WorkloadService` class with:
- `__init__(self, unit: Unit)` — stores `unit` and `container = unit.get_container(WORKLOAD_CONTAINER)`
- `version: str` property — runs `/ldap version` via pebble exec; returns empty string on error
- `set_version(self) -> None` — calls `self._unit.set_workload_version(self.version)` with error handling
- `open_port(self) -> None` — `self._unit.open_port(protocol="tcp", port=LDAP_PORT)` and `port=LDAPS_PORT`
- `is_running(self) -> bool` — checks service is running AND `PEBBLE_READY_CHECK_NAME` check is UP
- `is_failing(self) -> bool` — checks service is running AND `PEBBLE_READY_CHECK_NAME` check is DOWN

#### Scenario: open_port opens both LDAP ports
- **WHEN** `open_port()` is called
- **THEN** TCP port 3389 and 6636 are opened on the unit

#### Scenario: is_running returns False when check is DOWN
- **WHEN** the service is running but the health check is DOWN
- **THEN** `is_running()` returns `False`

### Requirement: `PebbleService` uses `startup: "disabled"` and `render_pebble_layer()`
`AuthentikLdapWorkload.build_layer()` SHALL set `startup: "disabled"` (not `"enabled"`).

`PebbleService` SHALL expose `render_pebble_layer(*env_var_sources: EnvVarConvertible) -> Layer` that merges `DEFAULT_CONTAINER_ENV` with each source's `to_env_vars()` (last wins) and returns a `Layer` object.

`PebbleService.plan(layer)` SHALL:
1. Call `container.add_layer(SERVICE_NAME, layer, combine=True)`
2. If the service is not running: call `container.start(SERVICE_NAME)`
3. Otherwise: call `container.replan()`
4. Raise `PebbleError` on failure

#### Scenario: startup is disabled
- **WHEN** `render_pebble_layer()` is called
- **THEN** the returned layer has `startup: "disabled"` for the service

### Requirement: `env_vars.py` uses `EnvVars` TypeAlias and removes `EnvVarMerger`
`env_vars.py` SHALL define `EnvVars: TypeAlias = Mapping[str, Union[str, bool]]`, update `EnvVarConvertible.to_env_vars()` to return `EnvVars`, and remove `EnvVarMerger`. `DEFAULT_CONTAINER_ENV` SHALL contain the base env vars for the workload (`AUTHENTIK_INSECURE`, placeholder `AUTHENTIK_HOST`, `AUTHENTIK_TOKEN`, `AUTHENTIK_LOG_LEVEL`).

### Requirement: `configs.py` implements `to_env_vars()`
`CharmConfig` SHALL implement `to_env_vars() -> EnvVars` returning:
- `"AUTHENTIK_LOG_LEVEL": self._config.get("log_level", "info")`
- `"HTTP_PROXY": self._config.get("http_proxy", "")`
- `"HTTPS_PROXY": self._config.get("https_proxy", "")`
- `"NO_PROXY": self._config.get("no_proxy", "")`

The existing `log_level` property and `is_valid()` method SHALL be removed (superseded by `to_env_vars()`).

#### Scenario: to_env_vars returns log level env var
- **WHEN** `CharmConfig({"log_level": "debug"}).to_env_vars()` is called
- **THEN** `AUTHENTIK_LOG_LEVEL` equals `"debug"`

