## Why

`charmcraft.yaml` declares `logging`, `tracing`, `metrics-endpoint`, and `grafana-dashboard` relations but zero code handles them. The charm also has `cpu` and `memory` config options with no Kubernetes resource patching wired. This is a production gap: operators cannot forward logs, scrape metrics, view dashboards, or collect traces from the LDAP outpost.

The Canonical Identity Platform pattern (as seen in `hydra-operator` and `tenant-service-operator`) provides a well-established set of libraries and integration points for exactly this use case.

## What Changes

- Fetch charm libs: `loki_k8s.v1.loki_push_api`, `prometheus_k8s.v0.prometheus_scrape`, `grafana_k8s.v0.grafana_dashboard`, `tempo_coordinator_k8s.v0.tracing`, `observability_libs.v0.kubernetes_compute_resources_patch`
- Add `LogForwarder` (Loki log forwarding — passive)
- Add `MetricsEndpointProvider` (Prometheus scrape job on LDAP port `:3389`)
- Add `GrafanaDashboardProvider` + placeholder dashboard template
- Add `TracingEndpointRequirer` + `TracingIntegration(EnvVarConvertible)` in `integrations.py`
- Add `KubernetesComputeResourcesPatch` wired to `cpu`/`memory` config options
- Add placeholder Prometheus and Loki alert rules
- Add relation name constants to `src/constants.py`

## Capabilities

### New Capabilities

- `observability`: Loki log forwarding, Prometheus metrics scraping, Grafana dashboard, Tempo OTLP HTTP tracing, Kubernetes CPU/memory resource patching

## Non-goals

- Real Grafana dashboard content (placeholder template only)
- Real alert rule content (placeholder rules only)
- Changes to `charmcraft.yaml` relations — already declared; this change only wires them in code
- `charmcraft.yaml` modifications beyond verifying observability relations are present

## Impact

- `src/charm.py` — 5 new initialisers in `__init__`, `_resource_reqs()`, `_on_resource_patch_failed()`
- `src/integrations.py` — add `TracingIntegration(EnvVarConvertible)`
- `src/constants.py` — new relation name constants for observability relations
- `src/grafana_dashboards/authentik-ldap.json.tmpl` — new placeholder file
- `src/prometheus_alert_rules/authentik_ldap.rule` — new placeholder alert
- `src/loki_alert_rules/authentik_ldap.rule` — new placeholder alert
- `lib/charms/` — new fetched libs
- `tests/unit/` — tests for `TracingIntegration` and resource patch

## Dependencies

Requires `authentik-ldap-charmcraft-fix` (correct relation names in `charmcraft.yaml`) and `authentik-ldap-refactor` (clean `integrations.py`) to be merged first.
