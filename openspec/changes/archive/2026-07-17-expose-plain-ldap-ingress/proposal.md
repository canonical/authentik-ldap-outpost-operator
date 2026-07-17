## Why

Legacy client services and appliances running inside trusted internal networks often lack support for modern implicit LDAPS (Port 636). To support these legacy workloads when Traefik is utilized as an internal ingress controller, operators need a way to optionally expose plain, unencrypted LDAP (Port 389) via Traefik.

## What Changes

- Add a new boolean configuration option `expose_ldap_ingress` (default `false`) to the charm.
- When enabled, update Traefik Route integration to configure a plain TCP router on Traefik targeting the `ldap` entrypoint on port `389`.
- When disabled, preserve secure-by-default behavior (only LDAPS on port 636 is routed).

## Non-goals

- Enabling plain LDAP ingress by default.
- Supporting TLS-terminated STARTTLS on the cleartext port via Traefik (this relies strictly on plain TCP routing).
- Modifying internal workload listening ports (the outpost workload continues to listen on port `3389`).

## Capabilities

### New Capabilities

<!-- None -->

### Modified Capabilities

- `charmcraft-config`: Add the `expose_ldap_ingress` config option.
- `traefik-route-integration`: Conditionally support plain LDAP TCP routing over port 389 when requested by the charm configuration.

## Impact

- `charmcraft.yaml`: Define the new configuration option `expose_ldap_ingress`.
- `templates/traefik-route.json.j2`: Conditionally add the TCP router for plain `ldap` entrypoint.
- `src/configs.py`: Support reading and exposing the new configuration flag.
- `src/integrations.py`: Implement conditional generation of static and dynamic Traefik route configs based on configuration state.
- `src/charm.py`: Ensure that when configuration changes, the Traefik route is appropriately reconfigured and submitted.
