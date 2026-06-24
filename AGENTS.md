# Authentik LDAP Outpost Operator - AI Coding Instructions

This repository implements a Juju Charm for the [Authentik](https://goauthentik.io/) LDAP outpost, part of the Canonical Identity Platform. It follows the Canonical Identity Platform's standard charm architecture.

## Project Context & Architecture

- **Framework**: Python `ops` framework (Juju), Kubernetes charm.
- **Charm User**: Must always run as non-root. Do not modify `charm-user` in `charmcraft.yaml`.
- **Workload**: Authentik LDAP outpost (`/ldap` binary) exposing LDAP (:3389) and LDAPS (:6636).

### Design Pattern: Physical Separation & Data Flow

- **`src/charm.py`**: Orchestrator — events, `_reconcile()` holistic handler. Keep minimal.
- **`src/services.py`**: `AuthentikLdapWorkload` + `PebbleService` — builds and applies Pebble layer.
- **`src/configs.py`**: `CharmConfig` — validates charm config.
- **`src/integrations.py`**: Relation wrappers (`ServerInfoIntegration`, `LdapProviderIntegration`, `TracingIntegration`), data transformation, `EnvVarConvertible` implementations.
- **`src/constants.py`**: String constants, integration names, ports (LDAP :3389, LDAPS :6636).
- **`src/env_vars.py`**: `DEFAULT_CONTAINER_ENV`, `EnvVarConvertible` protocol.
- **`src/exceptions.py`**: Custom exception hierarchy.

Data flows: **Sources** (Config, Relations) → `charm.py` → **Sinks** (Pebble Layer, Relation Databags).
Validate data in `integrations.py` using **Pydantic** models before passing to services.
All data sources implement `EnvVarConvertible` (`to_env_vars() -> EnvVars`).

## Critical Workflows

- **Formatting**: `tox -e fmt` (isort + ruff format). **Always run before committing.**
- **Linting**: `tox -e lint` (ruff, codespell).
- **Unit Tests**: `tox -e unit` — use `ops.testing` (Scenario), fixtures in `tests/unit/conftest.py`.
- **Integration Tests**: `tox -e integration` — uses `jubilant`.
- **Build**: `charmcraft pack`.
- **Dev Environment**: `tox devenv`.
- **Library Management**: `lib/charms/` files are managed by `charmcraft` — treat as **read-only**.

## Coding Conventions

- **Holistic Handler**: `_reconcile()` in `charm.py` centralizes reconciliation. Most events delegate to `_on_event` → `_reconcile()`.
- **Status**: Reported via `_on_collect_status` (`collect-unit-status` hook).
- **Limit `event.defer()`**: Prefer holistic reconciliation over deferring.
- **Type Hinting**: Strict. Use `list`, `dict`, `tuple` (not `typing.List`).
- **Logging**: Lazy formatting (`logger.info("key: %s", value)`), no f-strings.
- **Docstrings**: Google-style for all classes and public methods.
- **Error Handling**: Custom exceptions in `exceptions.py`. Catch in `charm.py` for status.
- **Control Flow**: EAFP over LBYL.
- **Env var naming**: Authentik env vars use double-underscore namespace separators (e.g. `AUTHENTIK_POSTGRESQL__HOST`, `AUTHENTIK_LISTEN__HTTP`). The `to_env_vars()` return type must be `EnvVars` (from `env_vars.py`), never `dict[str, Any]`.

## Relations

### Required
- `authentik-server-info` (`authentik_server_info`) — Receive Authentik host + bootstrap credentials from the server operator

### Optional
- `logging` (`loki_push_api`) — Forward logs to Loki
- `tracing` (`tracing`) — Send traces to Tempo
- `ingress` (`ingress`) — Traefik IngressPerUnit for LDAP (:3389)
- `ldaps-ingress` (`ingress`) — Traefik IngressPerUnit for LDAPS (:6636)

### Provided
- `ldap` (`glauth_ldap`) — Expose LDAP connection details (host, port, base DN, bind DN) to consuming applications
- `metrics-endpoint` (`prometheus_scrape`) — Prometheus metrics
- `grafana-dashboard` (`grafana_dashboard`) — Grafana dashboards

### Peer
- `authentik-ldap-peers` — Share state across units

## Testing Strategy

- **Unit**: `ops.testing` (Scenario). Group by events. Mock `Container` and external libs. Mock `KubernetesComputeResourcesPatch` to return `ActiveStatus`.
- **Integration**: `jubilant`. Lifecycle: deploy → scale up → integrations → scale down → removal. Deploy/removal must be skippable.

## Scoped Guidelines

Detailed guidelines are in scoped instruction files that load automatically:

- **`tests/` code**: `.agents/instructions/testing.instructions.md` — Test file structure, `create_state()` factory, mocking rules.

<!-- headroom:rtk-instructions -->
# RTK (Rust Token Killer) - Token-Optimized Commands

When running shell commands, **always prefix with `rtk`**. This reduces context
usage by 60-90% with zero behavior change. If rtk has no filter for a command,
it passes through unchanged — so it is always safe to use.

## Key Commands
```bash
# Git (59-80% savings)
rtk git status          rtk git diff            rtk git log

# Files & Search (60-75% savings)
rtk ls <path>           rtk read <file>         rtk grep <pattern>
rtk find <pattern>      rtk diff <file>

# Test (90-99% savings) — shows failures only
rtk pytest tests/       rtk cargo test          rtk test <cmd>

# Build & Lint (80-90% savings) — shows errors only
rtk tsc                 rtk lint                rtk cargo build
rtk prettier --check    rtk mypy                rtk ruff check

# Analysis (70-90% savings)
rtk err <cmd>           rtk log <file>          rtk json <file>
rtk summary <cmd>       rtk deps                rtk env

# GitHub (26-87% savings)
rtk gh pr view <n>      rtk gh run list         rtk gh issue list

# Infrastructure (85% savings)
rtk docker ps           rtk kubectl get         rtk docker logs <c>

# Package managers (70-90% savings)
rtk pip list            rtk pnpm install        rtk npm run <script>
```

## Rules
- In command chains, prefix each segment: `rtk git add . && rtk git commit -m "msg"`
- For debugging, use raw command without rtk prefix
- `rtk proxy <cmd>` runs command without filtering but tracks usage
<!-- /headroom:rtk-instructions -->
