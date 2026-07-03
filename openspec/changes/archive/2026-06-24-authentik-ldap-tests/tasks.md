## 1. Conftest and Shared Fixtures

- [x] 1.1 Create `tests/unit/conftest.py` with the `create_state()` module-level factory function accepting `leader`, `secrets`, `relations`, `containers`, `config`, and `can_connect` kwargs; default container is `testing.Container("authentik-ldap", can_connect=can_connect)`
- [x] 1.2 Add `mocked_resource_patch` fixture in `conftest.py` that patches `charms.observability_libs.v0.kubernetes_compute_resources_patch.ResourcePatcher` with `autospec=True`
- [x] 1.3 Add `mocked_k8s_resource_patch` autouse fixture in `conftest.py` that patches `charm.KubernetesComputeResourcesPatch` to prevent real Kubernetes API calls
- [x] 1.4 Add `context` fixture returning `testing.Context(AuthentikLdapCharm)`
- [x] 1.5 Add `container` fixture returning `testing.Container("authentik-ldap", can_connect=True)`
- [x] 1.6 Add `server_info_relation` fixture returning a `testing.Relation` for `"authentik-server-info"` with `remote_app_data={"authentik_host": "http://authentik:9000", "bootstrap_token_secret_id": "secret:xyz", "bootstrap_password_secret_id": "secret:abc"}`

## 2. Rewrite test_charm.py

- [x] 2.1 Delete all existing test functions from `tests/unit/test_charm.py`
- [x] 2.2 Add `TestHolisticHandler.test_when_pebble_not_ready_skips_planning`: run `config_changed` with `can_connect=False`; assert container plan is empty / no layer added
- [x] 2.3 Add `TestHolisticHandler.test_when_server_info_missing_skips_planning`: run `config_changed` with `can_connect=True` and no server-info relation; assert no Pebble layer applied
- [x] 2.4 Add `TestHolisticHandler.test_when_all_ready_plans_pebble_layer`: run `config_changed` with `can_connect=True` and `server_info_relation`; assert output container plan contains service `"authentik-ldap"`
- [x] 2.5 Add `TestCollectStatus.test_when_pebble_not_ready_adds_waiting_status`: run `collect_unit_status` with `can_connect=False`; assert `state_out.unit_status` is `WaitingStatus`
- [x] 2.6 Add `TestCollectStatus.test_when_server_info_missing_adds_blocked_status`: run `collect_unit_status` with `can_connect=True` and no server-info relation; assert `state_out.unit_status` is `BlockedStatus`
- [x] 2.7 Add `TestCollectStatus.test_when_all_ready_adds_active_status`: run `collect_unit_status` with `can_connect=True`, `server_info_relation`, and service mocked as running; assert `state_out.unit_status` is `ActiveStatus()`
- [x] 2.8 Add `TestPebbleReadyEvent.test_open_port_called_on_pebble_ready`: run `pebble_ready` and assert `WorkloadService.open_port` is called once (patch at `charm` module level)
- [x] 2.9 Add `TestPebbleReadyEvent.test_set_version_called_on_pebble_ready`: run `pebble_ready` and assert `WorkloadService.set_version` is called once; assert `state_out.workload_version` reflects the mocked return value

## 3. Rewrite test_integrations.py

- [x] 3.1 Delete all existing test code from `tests/unit/test_integrations.py`
- [x] 3.2 Add `TestServerInfoIntegration.test_to_env_vars_returns_env_when_ready`: construct `ServerInfoIntegration` with `create_autospec()` requirer where `is_ready()=True` and host/token set; assert result contains `"AUTHENTIK_HOST"` and `"AUTHENTIK_TOKEN"`
- [x] 3.3 Add `TestServerInfoIntegration.test_to_env_vars_empty_when_not_ready`: mock `is_ready()=False`; assert `to_env_vars()` returns `{}`
- [x] 3.4 Add `TestServerInfoIntegration.test_is_ready_delegates_to_requirer`: verify `True` and `False` return values are propagated correctly
- [x] 3.5 Add `TestTracingData.test_load_returns_empty_when_not_ready`: mock tracing requirer as not ready; assert `TracingData.load()` returns instance with no endpoint
- [x] 3.6 Add `TestTracingData.test_load_returns_endpoint_when_ready`: mock tracing requirer returning an OTLP gRPC endpoint; assert returned `TracingData` has endpoint set
- [x] 3.7 Add `TestTracingData.test_to_env_vars_returns_otlp_endpoint_when_ready`: assert `to_env_vars()` returns dict containing the tracing env var key with the endpoint value
- [x] 3.8 Add `TestTracingData.test_to_env_vars_empty_when_not_ready`: assert `to_env_vars()` returns `{}` when no endpoint is present

## 4. Rewrite test_services.py

- [x] 4.1 Delete all existing test code from `tests/unit/test_services.py`
- [x] 4.2 Add `TestPebbleService.test_render_pebble_layer_merges_sources`: call `PebbleService` layer rendering with a sample env dict; assert the resulting `pebble.Layer` has service `SERVICE_NAME`, the env vars in `environment`, and a TCP check on `LDAP_PORT`
- [x] 4.3 Add `TestPebbleService.test_plan_starts_service_when_not_running`: provide a `create_autospec()` container mock with service reported as not running; assert `container.replan()` is called
- [x] 4.4 Add `TestPebbleService.test_plan_replans_when_running`: provide a container mock with service as active; assert `container.replan()` is still called
- [x] 4.5 Add `TestWorkloadService.test_open_port_opens_ldap_and_ldaps`: call `WorkloadService.open_port()` with a mocked unit; assert port `3389` and port `6636` are both opened
- [x] 4.6 Add `TestWorkloadService.test_is_running_true_when_service_up_and_check_up`: mock service `ACTIVE` and check passing; assert `is_running()` returns `True`
- [x] 4.7 Add `TestWorkloadService.test_is_failing_true_when_service_up_and_check_down`: mock service `ACTIVE` and check failing; assert `is_failing()` returns `True`

## 5. Validation

- [x] 5.1 Run `tox -e unit` and confirm all new tests pass with zero `Harness` references remaining
- [x] 5.2 Run `tox -e lint` to confirm no ruff or codespell errors in the rewritten test files
