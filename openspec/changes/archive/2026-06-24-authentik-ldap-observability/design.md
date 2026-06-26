## Context

Four observability relations are declared in `charmcraft.yaml` but no code handles them. The reference implementations are `hydra-operator/src/charm.py` and `tenant-service-operator/src/charm.py`, both of which wire the same five integrations. The LDAP outpost follows the same pattern, with one difference: the metrics endpoint targets LDAP port `:3389` rather than an HTTP application port.

After `authentik-ldap-refactor`, `integrations.py` exposes standalone `EnvVarConvertible` classes. `TracingIntegration` fits naturally into that pattern.

## Goals / Non-Goals

**Goals:**
- All four observability relations are functional in code
- `cpu` and `memory` config options take effect via Kubernetes resource patching
- `TracingIntegration` follows `EnvVarConvertible` so tracing env vars flow into `_reconcile()`'s env var merge without special-casing
- Placeholder dashboard and alert rules satisfy the provider init without requiring real content

**Non-Goals:**
- Real Grafana dashboard panels or alert rule expressions
- `charmcraft.yaml` relation additions (already done in `authentik-ldap-charmcraft-fix`)
- Worker or server charm observability

## Decisions

### D1: All passive integrations initialised in `__init__` only

`LogForwarder`, `MetricsEndpointProvider`, `GrafanaDashboardProvider`, and `TracingEndpointRequirer` are self-contained — they handle their own relation events internally. Only `KubernetesComputeResourcesPatch` requires an extra observer (`on.patch_failed`). `_reconcile()` gains only the tracing env vars merge; no other changes.

### D2: Tracing env vars via `TracingIntegration(EnvVarConvertible)`

```python
class TracingIntegration:
    def __init__(self, tracing: TracingEndpointRequirer) -> None:
        self._tracing = tracing

    @property
    def is_ready(self) -> bool:
        return self._tracing.is_ready()

    def to_env_vars(self) -> dict[str, str]:
        if not self.is_ready:
            return {}
        endpoint = self._tracing.get_endpoint("otlp_http")
        return {"OTEL_EXPORTER_OTLP_ENDPOINT": endpoint} if endpoint else {}
```

`charm.py._ensure_pebble_layer()` merges `TracingIntegration.to_env_vars()` into the env dict alongside `ServerInfoIntegration.to_env_vars()`.

### D3: Metrics endpoint targets LDAP port `:3389`

The LDAP outpost exposes Prometheus metrics at `/metrics` on the same port it serves LDAP (`:3389`). This differs from the server charm (`:9000`). `MetricsEndpointProvider` is configured with `jobs=[{"static_configs": [{"targets": [f"*:{LDAP_PORT}"]}]}]`.

> **Note for implementer**: Verify whether the upstream goauthentik LDAP binary actually exposes `/metrics` on `:3389` or on a separate port. If a different port is used, update `METRICS_PORT` constant and the `MetricsEndpointProvider` init accordingly before completing this task.

### D4: `KubernetesComputeResourcesPatch` wired to `cpu`/`memory` config

```python
self.resources_patch = KubernetesComputeResourcesPatch(
    self,
    WORKLOAD_CONTAINER,
    resource_reqs_func=self._resource_reqs,
)
self.framework.observe(self.resources_patch.on.patch_failed, self._on_resource_patch_failed)
```

`_resource_reqs()` reads `self.config["cpu"]` and `self.config["memory"]`; `_on_resource_patch_failed()` sets `BlockedStatus`.

### D5: Placeholder dashboard and alert rules follow hydra pattern

One JSON dashboard template at `src/grafana_dashboards/authentik-ldap.json.tmpl` with minimal valid structure. One Prometheus alert rule at `src/prometheus_alert_rules/authentik_ldap.rule` and one Loki alert rule at `src/loki_alert_rules/authentik_ldap.rule`. These satisfy `GrafanaDashboardProvider` and alert rule dir scanning without committing to specific content.

### D6: Fetch libs via `charmcraft fetch-lib`

Required libs (all fetched, not hand-written):
- `charms.loki_k8s.v1.loki_push_api`
- `charms.prometheus_k8s.v0.prometheus_scrape`
- `charms.grafana_k8s.v0.grafana_dashboard`
- `charms.tempo_coordinator_k8s.v0.tracing`
- `charms.observability_libs.v0.kubernetes_compute_resources_patch`

## Risks / Trade-offs

- [Risk]: Metrics port for the LDAP binary may not be `:3389`. → Mitigation: Task 3.3 includes a verification step before finalising the `MetricsEndpointProvider` init.
- [Risk]: `KubernetesComputeResourcesPatch` requires a Kubernetes API available at charm init. → Mitigation: Mock it in unit tests (same pattern as the server charm).
