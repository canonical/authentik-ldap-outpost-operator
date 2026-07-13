## Why

Exposing the LDAP/LDAPS directory service securely requires a highly available, single-VIP external endpoint. Because standard Juju `ingress_per_unit` in TCP mode triggers a multi-unit scaling bug (Issue #406), we need to adopt the `traefik-route` relation to define custom entrypoints and bind Port 636 natively under a single Traefik IP.

## What Changes

- **Drop StartTLS support**: Restrict secure external access strictly to implicit LDAPS (Port 636) and drop opportunistic StartTLS support on Port 389.
- **Adopt `traefik-route`**: Replace the `ingress_per_unit` relation with `traefik-route` for external L4 ingress configuration.
- **Dynamic Port Mapping**: Allow the outpost charm to dynamically request a custom secure entrypoint on Traefik for Port 636.

## Non-goals

- Exposing plain, unencrypted LDAP (Port 389) publicly via Traefik.
- Handling TLS handshakes or managing TLS certificates directly inside the outpost workload container.
- Supporting legacy `ingress_per_unit` relationships for TCP traffic.

## Capabilities

### New Capabilities
- `traefik-route-integration`: Implement the `traefik-route` Juju relation to dynamically configure a secure, single-VIP external LDAPS endpoint on Port 636.

### Modified Capabilities
<!-- Leave empty as no existing spec requirements are modified -->

## Impact

- `src/charm.py`: Add event handlers and register `traefik-route` updates inside the holistic `_reconcile()` loop.
- `src/integrations.py`: Create wrapper classes and Pydantic validation models for the Traefik route configuration data.
- `src/constants.py`: Define ports (LDAPS Port 636, unencrypted Port 3389) and relation constants.
- `charmcraft.yaml`: Expose the new `traefik-route` relation interface.
