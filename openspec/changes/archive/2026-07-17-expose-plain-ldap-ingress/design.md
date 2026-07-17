## Context

Standardizing strictly on LDAPS (Port 636) via Traefik is the default secure-by-default posture of this charm operator. However, inside internal enterprise networks or VPCs (where Traefik operates as an internal ingress), legacy clients or appliances might only support unencrypted LDAP (Port 389) and lack capability for modern implicit LDAPS or StartTLS. To enable such legacy workloads, the charm must conditionally permit cleartext LDAP route mapping on Traefik.

## Goals / Non-Goals

**Goals:**
- Provide a safe, optional way for operators to expose cleartext LDAP (Port 389) externally through Traefik.
- Keep the default behavior fully secure (LDAPS only).
- Ensure integration with Traefik Route is fully dynamic and reacts to configuration updates.

**Non-Goals:**
- Enabling cleartext ingress by default.
- Managing local TLS certificates within the workload container for the plain LDAP port.

## Decisions

### 1. New Config Option `expose_ldap_ingress`
We will introduce `expose_ldap_ingress` in `charmcraft.yaml` with a default of `false`. This parameter will be parsed by `CharmConfig` in `src/configs.py`.
* **Rationale:** Preserves secure-by-default posture. Only active if explicitly requested.

### 2. Conditionally exposing plain LDAP entrypoint in Traefik Route
When `expose_ldap_ingress` is enabled, the `TraefikRouteIntegration` in `src/integrations.py` will:
- Inject a new entrypoint named `ldap` mapped to port `389` in Traefik's `static_config`.
- Render `templates/traefik-route.json.j2` with `expose_ldap_ingress=True`.
- Conditionally render a second TCP router in the template that binds to the `ldap` entrypoint, utilizing the catch-all `HostSNI("*")` rule since cleartext TCP has no SNI headers.
* **Rationale:** Bypasses standard ingress limitation and allows dynamic L4 route definition directly in Traefik.

### 3. Maintain Independent LDAPS Status
Exposing plain LDAP does not modify the `ldaps_enabled` flag written to the `ldap` relation databag. This maintains clarity on whether secure LDAPS connections are available.
* **Rationale:** Keeps security signaling simple and accurate.

## Risks / Trade-offs

- **Risk: Plain TCP Ingress Multiplexing Conflict**
  - *Risk:* Since cleartext TCP lacks SNI headers, the router must use `HostSNI("*")`. If two different outpost charms on the same Traefik instance enable plain LDAP ingress, Traefik will face a routing conflict.
  - *Mitigation:* Document this clearly in the `charmcraft.yaml` option description and in user-facing guides. This is a known L4 TCP ingress limitation.
