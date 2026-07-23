## Why

LDAP searches and binds should keep working during transient Authentik API outages. Making Authentik's cached provider modes the charm defaults improves availability, but operators need explicit guidance about cache warm-up, stale data, credential changes, and revocation latency before upgrading.

## What Changes

- **BREAKING**: change the `search_mode` and `bind_mode` defaults in `charmcraft.yaml` from `direct` to `cached`; existing deployments that have not explicitly set these options adopt cached behavior after upgrade.
- Keep `direct` as a supported explicit value and preserve the existing propagation path in `src/charm.py` and `src/api_client.py`.
- Update focused configuration tests for the new defaults and the explicit `direct` override.
- Document cache freshness and warm-up behavior, delayed password and session revocation effects, and how to pin both options to `direct` before upgrading.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `charmcraft-config`: define cached search and bind defaults while retaining explicit direct mode and documenting the operational behavior of each mode.

## Impact

- Affected configuration: `charmcraft.yaml`.
- Affected implementation paths (behavior preserved, no source edit expected): `src/charm.py` and `src/api_client.py`.
- Affected tests and documentation: focused unit tests, `README.md`, and the LDAP configuration specification.

## Non-goals

- Removing or changing `search_group`.
- Changing Authentik's cache implementation, refresh interval, or invalidation behavior.
- Updating documentation in the Authentik server repository.
