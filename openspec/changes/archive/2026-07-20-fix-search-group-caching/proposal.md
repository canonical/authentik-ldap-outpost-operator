## Why

The default `search_group` configuration option is set to `"authentik Admingroup"`, which does not exist in standard Authentik installations (where the default is `"authentik Admins"`). This mismatch prevents programmatic service accounts from being assigned search permissions, causing integration lookups to fail silently. Currently, the `search_group` configuration is not tracked in the operator's peer metadata caching mechanism, which would trigger redundant Authentik API queries on every charm hook invocation if we try to reconcile it. Furthermore, if the search group is missing or changed, existing relation users are not updated, and the operator incorrectly remains in `ActiveStatus` instead of alerting administrators by entering a blocked state.

## What Changes

- Change default value of `search_group` config option in `charmcraft.yaml` to `"authentik Admins"`.
- Extend the peer config metadata tracking in `src/charm.py` to cache `last_search_group`.
- Re-verify and update existing service accounts' group membership when `search_group` is changed, while avoiding redundant API calls when the config is unchanged.
- Enforce the existence of the `search_group` on the Authentik server during reconciliation. If the group is missing, the charm SHALL enter `BlockedStatus` with a descriptive message.

## Non-goals

- Automatically creating missing groups inside the upstream Authentik server.
- Managing user roles or policies within Authentik.

## Capabilities

### New Capabilities

*(None)*

### Modified Capabilities

- `charmcraft-config`: Update default search group config value to match standard Authentik setups.
- `charm-reconcile`: Cache the search group config to avoid duplicate Authentik API calls on every invocation, reconcile existing service accounts upon configuration changes, and enforce group existence by entering `BlockedStatus` if the group is missing on Authentik.

## Impact

- `charmcraft.yaml`: Default config value update.
- `src/charm.py`: Add peer caching/change detection for `search_group`, support group re-synchronization on change, and update status collection to enforce group existence.
