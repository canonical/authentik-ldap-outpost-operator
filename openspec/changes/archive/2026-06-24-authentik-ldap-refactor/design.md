## Context

The charm's current `integrations.py` partially follows the `EnvVarConvertible` pattern (classes have `to_env_vars()` partially implemented via `build_env()`) but wraps them all in an `Integrations` orchestrator. `charm.py` depends on this orchestrator and works around a broken lib with conditional event wiring. The lib (`authentik_server_info.py`) uses a hand-rolled event pattern that doesn't subclass `ObjectEvents` properly.

The fixed lib contract (from the server charm's `authentik-server-libs` change) is well-defined: `AuthentikServerInfoRequirer` with `on.ready`, `is_ready` property, and `get_info() -> ServerInfoData | None`.

## Goals / Non-Goals

**Goals:**
- `authentik_server_info.py` lib is correct and the LDAP outpost uses `server_info.on.ready`
- `integrations.py` exposes standalone `EnvVarConvertible` classes directly composable in `charm.py`
- `charm.py.__init__` observes events unconditionally — no runtime `hasattr`/`if` guards
- Dead code (`cli.py`, `secret.py`, `utils.py`, `authentik_ldap_outpost.py`) is gone
- `_reconcile()` is the single source of truth: builds env from `ServerInfoIntegration.to_env_vars()` and wires `LdapProvider`

**Non-Goals:**
- Observability (separate change)
- `charmcraft.yaml` changes
- Provider-side library (`AuthentikServerInfoProvider`)
- `configs.py` or `env_vars.py` changes beyond usage updates

## Decisions

### D1: Adopt fixed lib verbatim from server charm spec

The `authentik-server-libs` spec defines the exact `AuthentikServerInfoRequirer` interface. Rather than designing a new one, adopt that spec's implementation directly. This ensures the provider and requirer are aligned.

Key interface:
```python
class AuthentikServerInfoRequirer(Object):
    on = AuthentikServerInfoRequirerEvents()  # on.ready

    def is_ready(self) -> bool: ...          # all 3 fields present
    def get_info(self) -> ServerInfoData | None: ...  # host, bootstrap_token, bootstrap_password
```

### D2: Remove `Integrations` god-object; inject individual classes into `charm.py`

The canonical pattern (seen in `hydra-operator`, `identity-platform-admin-ui-operator`) instantiates integration wrappers directly in `charm.py.__init__`:

```python
self.server_info = ServerInfoIntegration(self)
self.ldap_provider = LdapProviderIntegration(self)
self.ingress = IngressIntegration(self)
```

This makes dependencies explicit and keeps `charm.py` readable without a god-object indirection.

### D3: `ServerInfoIntegration` implements `EnvVarConvertible`

`ServerInfoIntegration.to_env_vars()` returns the three env vars the workload needs:
```python
{"AUTHENTIK_HOST": ..., "AUTHENTIK_TOKEN": ..., "AUTHENTIK_INSECURE": "true"}
```
`charm.py._ensure_pebble_layer()` calls `self.server_info.to_env_vars()` and passes the result to `AuthentikLdapWorkload.build_layer()`.

### D4: Unconditional event wiring — no runtime guards

With the fixed lib, `server_info.on.ready` always exists. The `if self.integrations.server_info.events:` conditional and all fallback `relation_changed`/`relation_broken` observations are removed.

### D5: Delete extraneous files without replacement

- `cli.py` — `Pebble.exec()` is called directly where needed; no separate CLI wrapper required
- `secret.py` — secret access is done inline in `ServerInfoIntegration.get_info()` via the lib
- `utils.py` — `container_connectivity` decorator is replaced by the inline `if not container.can_connect(): return` guard in `_reconcile()`; `leader_unit` decorator is not used anywhere
- `authentik_ldap_outpost.py` — stub with no real implementation

### D6: `LdapProvider` address resolution

The unit LDAP address is derived in priority order:
1. Ingress URL (from `IngressIntegration.get_url()`) if ingress is ready
2. Pod IP via `model.get_binding("ldap").network.bind_address`

This logic lives in `charm.py._ensure_ldap_provider()`.

## Risks / Trade-offs

- [Risk]: Removing `Integrations` orchestrator is a structural change that could break tests. → Mitigation: Update all unit tests as part of this change.
- [Risk]: `lib/` is noted as "managed by charmcraft" (read-only convention). → Mitigation: The lib is a local copy; the convention means "don't edit the published API arbitrarily." Updating to a fixed version is the intended update path.

## Migration Plan

1. Rewrite `lib/charms/authentik_server/v0/authentik_server_info.py` per D1.
2. Delete `src/cli.py`, `src/secret.py`, `src/utils.py`, `src/authentik_ldap_outpost.py`.
3. Refactor `src/integrations.py` per D2/D3.
4. Rewrite `src/charm.py` per D4/D6.
5. Update unit tests.
6. Run `tox -e fmt && tox -e lint && tox -e unit`.
