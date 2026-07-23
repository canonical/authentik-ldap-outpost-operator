## Context

The charm currently declares `direct` as the default for both LDAP provider modes and passes either configured value unchanged through `src/charm.py` to `src/api_client.py`. Authentik also supports `cached`, which serves directory activity from the outpost cache and reduces dependence on live server requests. Changing a deployed application's implicit default changes its availability and security characteristics, so this configuration-only change requires migration and risk documentation.

## Goals / Non-Goals

**Goals:**

- Make `cached` the default for new and upgraded deployments that have not explicitly set either mode.
- Keep `direct` available as an explicit operator choice.
- Make cache warm-up, freshness, password-change, and session-revocation trade-offs visible before operators upgrade.
- Cover default and explicit-direct behavior with focused tests.

**Non-Goals:**

- Change the upstream Authentik cache, its refresh interval, or its invalidation behavior.
- Change `search_group` or provider reconciliation logic.
- Change documentation outside this LDAP charm repository.

## Decisions

- Change only the two defaults in `charmcraft.yaml`. The existing reconciliation and API-client paths already transmit string values without rewriting them, so adding another abstraction or compatibility shim would add no value.
- Keep the declared configuration type as `string` and describe both supported values. This preserves the current Juju configuration interface and explicit `direct` support.
- Document pinning as two `juju config` assignments performed before refresh. Pinning makes the operator's choice durable instead of relying on the old implicit default.
- Describe cached operation conservatively: initial cache population is required; searches can be stale until synchronization; password changes and session revocations may not immediately invalidate cached bind decisions. Do not promise a fixed refresh interval because the charm does not control one.

Alternatives considered: retaining `direct` would not provide the requested outage tolerance by default; automatically pinning existing applications would require deployment-state migration machinery and would prevent the intended default cutover.

## Risks / Trade-offs

- Cached searches can temporarily return stale identity or group data; operators must account for synchronization delay.
- Cached binds can temporarily accept an old password or a session whose access was revoked, increasing revocation latency.
- A cold or incomplete cache can make entries unavailable until warm-up completes.
- Operators requiring live consistency can mitigate these risks by setting both modes to `direct` before upgrade, at the cost of dependence on Authentik server availability.
