## 1. Fetch charm libs

- [x] 1.1 Run `charmcraft fetch-lib charms.loki_k8s.v1.loki_push_api`
- [x] 1.2 Run `charmcraft fetch-lib charms.prometheus_k8s.v0.prometheus_scrape`
- [x] 1.3 Run `charmcraft fetch-lib charms.grafana_k8s.v0.grafana_dashboard`
- [x] 1.4 Run `charmcraft fetch-lib charms.tempo_coordinator_k8s.v0.tracing`
- [x] 1.5 Run `charmcraft fetch-lib charms.observability_libs.v0.kubernetes_compute_resources_patch`

## 2. Add constants to `src/constants.py`

- [x] 2.1 Add `LOGGING_RELATION = "logging"`
- [x] 2.2 Add `METRICS_ENDPOINT_RELATION = "metrics-endpoint"`
- [x] 2.3 Add `GRAFANA_DASHBOARD_RELATION = "grafana-dashboard"`
- [x] 2.4 Add `TRACING_RELATION = "tracing"`

## 3. Add `MetricsEndpointProvider` and verify metrics port

- [x] 3.1 Import `MetricsEndpointProvider` from `charms.prometheus_k8s.v0.prometheus_scrape`
- [x] 3.2 Verify the actual Prometheus metrics port used by `ghcr.io/goauthentik/ldap:2026.2.2` (check upstream docs or container inspect — may be `:3389` or a separate port)
- [x] 3.3 Instantiate `MetricsEndpointProvider` in `__init__` with `jobs=[{"static_configs": [{"targets": [f"*:{METRICS_PORT}"]}]}]` using the verified port
- [x] 3.4 Create `src/prometheus_alert_rules/authentik_ldap.rule` with a placeholder `AuthentikLdapUnavailable` alert rule (valid YAML, placeholder expr)

## 4. Add `LogForwarder`

- [x] 4.1 Import `LogForwarder` from `charms.loki_k8s.v1.loki_push_api`
- [x] 4.2 Instantiate `LogForwarder(charm=self, relation_name=LOGGING_RELATION)` in `__init__`
- [x] 4.3 Create `src/loki_alert_rules/authentik_ldap.rule` with a placeholder log alert rule

## 5. Add `GrafanaDashboardProvider`

- [x] 5.1 Import `GrafanaDashboardProvider` from `charms.grafana_k8s.v0.grafana_dashboard`
- [x] 5.2 Instantiate `GrafanaDashboardProvider(charm=self, relation_name=GRAFANA_DASHBOARD_RELATION)` in `__init__`
- [x] 5.3 Create `src/grafana_dashboards/authentik-ldap.json.tmpl` with a minimal valid Grafana dashboard JSON template (placeholder title and one empty row)

## 6. Add `TracingEndpointRequirer` and `TracingData`

- [x] 6.1 Import `TracingEndpointRequirer` from `charms.tempo_coordinator_k8s.v0.tracing`
- [x] 6.2 Instantiate `TracingEndpointRequirer(charm=self, relation_name=TRACING_RELATION, protocols=["otlp_http"])` in `__init__`, assigned to `self.tracing_requirer`
- [x] 6.3 Add `TracingData` as a `@dataclass(frozen=True)` to `src/integrations.py` with fields `is_ready: bool = False` and `http_endpoint: str = ""`; implement `to_env_vars() -> EnvVars` returning `{"AUTHENTIK_OUTPOST__DISCOVER__OTLP_TRACES_ENDPOINT": self.http_endpoint}` when `is_ready`, else `{}`; add `load(requirer: TracingEndpointRequirer) -> TracingData` classmethod
- [x] 6.4 Observe `self.tracing_requirer.on.endpoint_changed` and `endpoint_removed` → `self._on_holistic_handler` in `src/charm.py`
- [x] 6.5 Pass `TracingData.load(self.tracing_requirer)` as a source to `self._pebble.render_pebble_layer(...)` in `_ensure_pebble_layer()`

## 7. Add `KubernetesComputeResourcesPatch`

- [x] 7.1 Import `KubernetesComputeResourcesPatch`, `ResourceRequirements`, `K8sResourcePatchFailedEvent`, and `adjust_resource_requirements` from `charms.observability_libs.v0.kubernetes_compute_resources_patch`
- [x] 7.2 Implement `_resource_reqs_from_config(self) -> ResourceRequirements` reading `self.model.config.get("cpu")` and `self.model.config.get("memory")`; call `adjust_resource_requirements(limits, {"cpu": "100m", "memory": "200Mi"}, adhere_to_requests=True)`
- [x] 7.3 Instantiate `self.resources_patch = KubernetesComputeResourcesPatch(self, WORKLOAD_CONTAINER, resource_reqs_func=self._resource_reqs_from_config)` in `__init__`
- [x] 7.4 Observe `self.resources_patch.on.patch_failed` → `self._on_resource_patch_failed`
- [x] 7.5 Implement `_on_resource_patch_failed(self, event: K8sResourcePatchFailedEvent)`: log `event.message` as an error, then call `self._on_holistic_handler(event)`

## 8. Update unit tests

- [x] 8.1 Add `KubernetesComputeResourcesPatch` mock to `conftest.py` (return `ActiveStatus`)
- [x] 8.2 Add test: `TracingIntegration.to_env_vars()` returns correct env when tracing relation ready
- [x] 8.3 Add test: `TracingIntegration.to_env_vars()` returns `{}` without relation
- [x] 8.4 Add test: `_on_resource_patch_failed` sets `BlockedStatus`

## 9. Format and lint

- [x] 9.1 Run `tox -e fmt`
- [x] 9.2 Run `tox -e lint` — no errors
- [x] 9.3 Run `tox -e unit` — all tests pass
