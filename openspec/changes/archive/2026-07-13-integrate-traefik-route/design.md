## Context

The Charmed Authentik LDAP Outpost requires highly available, secure, single-VIP external connectivity to service directory queries from consumer applications. 
Historically, Juju's standard `ingress_per_unit` in TCP mode has been blocked by a multi-unit scaling bug (Issue #406), where Traefik attempts to create a separate Kubernetes `LoadBalancer` Service for every backend outpost pod unit. This results in duplicate/blocking configurations on clusters with a single Virtual IP (VIP).
This design implements the Juju `traefik-route` relation to declare custom TCP entrypoints on Traefik, routing Port 636 to the unencrypted internal Port 3389 of the outpost pods.

## Goals / Non-Goals

**Goals:**
- Enable high-availability LDAPS access over Port 636 under a single external Traefik VIP.
- Standardize on implicit LDAPS (Port 636) and drop opportunistic StartTLS (Port 389).
- Dynamically manage and publish LDAPS status (`ldaps_enabled=true` and connection URIs) inside the `ldap` relation databag when ingress is ready.
- Declare the `ldaps` custom TCP entrypoint explicitly inside the `traefik-route` relation databag.
- Validate ingress routing and databag states using comprehensive unit and integration tests.

**Non-Goals:**
- Distributing corporate TLS certificates or performing TLS handshakes inside the outpost workload pods (offloaded completely to the Traefik proxy).

## Decisions

### Decision 1: Standardize on implicit LDAPS (Port 636)
- **Rationale**: StartTLS begins in cleartext on Port 389 and is highly opportunistic, leaving it open to TLS stripping attacks. Implicit LDAPS (Port 636) guarantees a fail-closed secure posture—if the handshake fails, the socket drops immediately. Standardizing on LDAPS allows us to offload TLS termination completely to the ingress proxy, removing the need for certificate management inside the outpost container.

### Decision 2: TCP entrypoint mapping and metadata via `traefik-route`
- **Rationale**: The `traefik-route` relation allows the outpost charm to supply a custom Traefik JSON/YAML configuration. We will provide BOTH the **static configuration** (defining the entrypoint on Traefik) and the **dynamic configuration** (defining the L4 routing rule to the backend service).
- **Static Configuration (`static` parameter)**:
  Defines the `ldaps` TCP port on Traefik. Passed via the `static` parameter to `submit_to_traefik()`.
  ```json
  {
    "entryPoints": {
      "ldaps": {
        "address": ":636"
      }
    }
  }
  ```
- **Dynamic Configuration (`config` parameter)**:
  Renders `templates/traefik-route.json.j2`. It defines the L4 TCP router and references the `ldaps` entrypoint.
  ```json
  {
    "tcp": {
      "routers": {
        "juju-{{ identifier }}-tcp-router": {
          "entryPoints": ["ldaps"],
          "rule": "HostSNI(`*`)",
          "service": "juju-{{ identifier }}-tcp-service",
          "tls": {
            "passthrough": false
          }
        }
      },
      "services": {
        "juju-{{ identifier }}-tcp-service": {
          "loadBalancer": {
            "servers": [{ "address": "{{ app }}.{{ model }}.svc.cluster.local:3389" }]
          }
        }
      }
    }
  }
  ```

### Decision 3: Dynamically advertise LDAPS status to Consumers
- **Rationale**: Consumer applications (e.g. SSSD, PAM, or standard clients) that connect to this outpost over the `ldap` relation need to know whether the endpoint supports secure LDAPS.
- **Handling Events**:
  - Whenever the `traefik-route` relation changes:
    1. If `traefik-route` is established and provides an `external_host` IP/domain, set `ldaps_enabled=true` inside the `ldap` relation databag.
    2. Format and publish the secure connection URI: `ldaps://{{ external_host }}:636` inside the databag.
    3. Trigger standard holistic `_reconcile()` to apply any configuration changes.
  - If `traefik-route` is broken or unconfigured:
    1. Set `ldaps_enabled=false` inside the `ldap` relation databag.
    2. Fall back to standard unencrypted LDAP URIs or internal endpoints.

## Risks / Trade-offs

- **[Risk]**: The `traefik-route` interface might have limited raw TCP and TLS routing maturity inside some production environments.
  - **Mitigation**: Keep the machine-based HAProxy VM topology with manual Kubernetes `LoadBalancer` Service IP mapping as a fully tested and documented fallback option (Phase 2).

## Verification Plan

### Automated Tests
- **Unit Tests**:
  - Mock `TraefikRouteRequirer` data (`external_host` and `scheme`).
  - Verify that `_reconcile()` correctly renders `templates/traefik-route.json.j2` and populates the relation databag.
  - Assert that `ldaps_enabled=true` is written to the `ldap` relation databag when Traefik is ready.
  - Assert that the custom static entrypoint mapping containing `ldaps` binding to `:636` is written into the `traefik-route` relation databag.
  - Assert that the connection URI `ldaps://<external_host>:636` is correctly advertised.
  - Assert that when `traefik-route` is broken, `ldaps_enabled=false` is set on the `ldap` relation databag.
- **Integration Tests**:
  - Deploy `authentik-ldap-outpost-operator` alongside `traefik-k8s`.
  - Establish `traefik-route` relation.
  - Query the Traefik external IP/host and verify successful secure LDAPS L4 routing to the outpost.

### Manual Verification
- Run integration tests with the `--no-juju-teardown` flag to keep the active Juju model and the local Kubernetes environment running.
- Access the local cluster, query Traefik's service VIP, and run LDAP queries over the secure Port 636 using external utilities (e.g. `ldapsearch` with custom trust parameters) to verify L4 load balancing and end-to-end connectivity.
