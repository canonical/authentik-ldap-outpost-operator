## Purpose

This spec covers the full observability stack for the LDAP outpost: log forwarding (Loki), metrics scraping (Prometheus), dashboard (Grafana), distributed tracing (Tempo), and Kubernetes resource patching. All four relations are already declared in `charmcraft.yaml` but none are wired in code.

## ADDED Requirements

### Requirement: `LogForwarder` initialised in `__init__`
`charm.py.__init__` SHALL instantiate `LogForwarder(charm=self, relation_name=LOGGING_RELATION)`. No additional event wiring or `_reconcile()` changes are required — `LogForwarder` is passive.

#### Scenario: Log forwarding integrated
- **WHEN** `juju integrate authentik-ldap-outpost:logging loki:logging`
- **THEN** logs from the workload container are forwarded to Loki

### Requirement: `MetricsEndpointProvider` initialised with the metrics port
`charm.py.__init__` SHALL instantiate `MetricsEndpointProvider` with a scrape job named `authentik_ldap_outpost_metrics` targeting `METRICS_PORT` (`:9300`) on the default `/metrics` path. `METRICS_PORT` SHALL NOT be opened with `unit.open_port()` — `prometheus_scrape` publishes the pod IP, so Prometheus reaches it pod-to-pod and opening the port would expose unauthenticated metrics through the Kubernetes Service.

#### Scenario: Prometheus scrape job available
- **WHEN** `juju integrate authentik-ldap-outpost:metrics-endpoint prometheus:metrics-endpoint`
- **THEN** Prometheus can scrape metrics from the unit

### Requirement: `GrafanaDashboardProvider` initialised with dashboard template
`charm.py.__init__` SHALL instantiate `GrafanaDashboardProvider(charm=self, relation_name=GRAFANA_DASHBOARD_RELATION)`. A dashboard template SHALL exist at `src/grafana_dashboards/authentik-ldap.json.tmpl`.

#### Scenario: Dashboard pushed to Grafana
- **WHEN** `juju integrate authentik-ldap-outpost:grafana-dashboard grafana:grafana-dashboard`
- **THEN** a dashboard appears in Grafana

### Requirement: `TracingEndpointRequirer` + `TracingData` frozen dataclass
`charm.py.__init__` SHALL instantiate `TracingEndpointRequirer(charm=self, relation_name=TRACING_RELATION, protocols=["otlp_http"])`, assigned to `self.tracing_requirer`. `integrations.py` SHALL define `TracingData` as a `@dataclass(frozen=True)` with fields `is_ready: bool = False` and `http_endpoint: str = ""`, implementing `to_env_vars() -> EnvVars` and a `load(requirer) -> TracingData` classmethod — mirroring the pattern in authentik-server. `charm.py._ensure_pebble_layer()` SHALL pass `TracingData.load(self.tracing_requirer)` to `render_pebble_layer()`.

#### Scenario: Tracing env var injected when relation ready
- **WHEN** `juju integrate authentik-ldap-outpost:tracing tempo:tracing`
- **THEN** `AUTHENTIK_OUTPOST__DISCOVER__OTLP_TRACES_ENDPOINT` is set in the workload container environment

#### Scenario: No tracing env var without relation
- **WHEN** no tracing relation is established
- **THEN** `TracingData.load(requirer).to_env_vars()` returns `{}`

### Requirement: `KubernetesComputeResourcesPatch` wired to `cpu`/`memory` config; `_on_resource_patch_failed` logs and re-runs handler
`charm.py.__init__` SHALL instantiate `KubernetesComputeResourcesPatch(self, WORKLOAD_CONTAINER, resource_reqs_func=self._resource_reqs_from_config)`. `_resource_reqs_from_config()` SHALL call `adjust_resource_requirements()` with baseline requests `{"cpu": "100m", "memory": "200Mi"}`. `_on_resource_patch_failed(event: K8sResourcePatchFailedEvent)` SHALL log `event.message` as an error and call `self._on_holistic_handler(event)`.

#### Scenario: CPU limit applied
- **WHEN** `juju config authentik-ldap-outpost cpu=500m`
- **THEN** the Kubernetes pod spec is patched with `resources.limits.cpu: 500m`

#### Scenario: Resource patch failure logs and reconciles
- **WHEN** the Kubernetes API returns an error during patching
- **THEN** the error is logged and `_on_holistic_handler` is called

### Requirement: Alert rules exist
`src/prometheus_alert_rules/` SHALL contain `authentik_ldap_outpost_unavailable.rule` (alerts `AuthentikLdapOutpostUnavailable-multiple` and `-all`) and `authentik_ldap_outpost_disconnected.rule` (alert `AuthentikLdapOutpostDisconnected`, firing when `authentik_outpost_connection == 0` for 5 minutes). `src/loki_alert_rules/` SHALL contain `authentik_ldap_outpost_high_severity_log.rule` (alert `HighFrequencyHighSeverityLog`, using the `{%%juju_topology%%}` stub). `MetricsEndpointProvider` SHALL be configured to load rules from `src/prometheus_alert_rules/`.

#### Scenario: Alert rule files are valid YAML
- **WHEN** the alert rule files are parsed
- **THEN** they contain valid YAML with `groups`, `rules`, `alert`, `expr` fields

### Requirement: Constants defined for all observability relation names
`src/constants.py` SHALL define `LOGGING_RELATION`, `METRICS_ENDPOINT_RELATION`, `GRAFANA_DASHBOARD_RELATION`, and `TRACING_RELATION` matching the relation names in `charmcraft.yaml`.

#### Scenario: No hardcoded relation name strings in `charm.py`
- **WHEN** `charm.py` references any observability relation name
- **THEN** it uses a constant from `constants.py`, not a bare string literal
