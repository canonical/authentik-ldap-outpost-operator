# ADR 002: Proxy Protocol v2 and Dynamic Trusted Proxy CIDR Discovery for Client IP Propagation

## Status
Accepted

## Context
In a production reverse-proxied reverse directory topology, client IP address propagation is essential for several security and operational reasons:
1. **Auditing & Threat Intelligence**: Security teams must trace the original source IP of authentication requests in Authentik logs.
2. **Brute Force & Lockout Protection**: Authentik contains IP-based rate limits and lockout protection. If all connections appear to originate from Traefik's IP, a single brute-force attack from one client could trigger a lockout that blocks all legitimate directory traffic cluster-wide.
3. **Layer 4 Limitations**: Because LDAP/LDAPS traffic operates over raw TCP (Layer 4), Traefik cannot inject standard Layer 7 HTTP headers (such as `X-Forwarded-For`). The standard solution for Layer 4 IP propagation is the **Proxy Protocol** (v1 or v2).

However, introducing Proxy Protocol poses implementation challenges within Kubernetes:
- **Dynamic Pod IPs**: Traefik acts as a dynamic deployment. Connections to the LDAP Outpost originate from ephemeral Traefik Pod IPs (e.g., `10.1.x.x`), which change on rescheduling or scaling.
- **Trust Configuration**: Authentik requires a comma-separated list of trusted proxies (`AUTHENTIK_LISTEN__TRUSTED_PROXY_CIDRS`) to parse Proxy Protocol headers. If a connection with Proxy Protocol headers arrives from an untrusted IP, the connection is refused, or the headers are ignored.
- **Juju Relation Boundaries**: Juju relations natively exchange static Service IPs or egress subnets, but not the ephemeral pod IPs where traffic is actually routed from inside the container network overlay.

## Decision
We have decided to standardize on the following architectural changes to enable robust, production-grade client IP propagation:

1. **Upstream Proxy Protocol v2**: Configure Traefik's dynamic TCP Service configuration template (`templates/traefik-route.json.j2`) to explicitly prepend Proxy Protocol Version 2 headers to the upstream LDAP Outpost server.
2. **Dual-Layer Proxy Trust System**:
   - **Dynamic Discovery**: Query the `traefik-route` relation dynamically to read and append Juju-exchanged subnets or egress IPs.
   - **Static Private IP (RFC 1918) Trust**: Pre-seed `AUTHENTIK_LISTEN__TRUSTED_PROXY_CIDRS` with standard private ranges (`127.0.0.1/32`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) to guarantee that any ephemeral Traefik Pod IP connecting over the internal Kubernetes overlay network is instantly recognized and trusted.
3. **Provider-Level Headless Workaround**: Map the LDAP Provider's `authorization_flow` to the headless `bind_flow` instead of the standard web-based authentication flow, preventing simple binds from hitting interactive consent pages.

## Consequences
- **High-Fidelity Logs**: Authentik correctly audits the real external client IP address (`client` field in `authentik-ldap` workload container logs), rather than masking them behind Traefik's Pod IP.
- **Lockout Protection Isolation**: Authentik's rate limiters and lockouts successfully isolate and block malicious clients individually, preventing a cluster-wide service denial.
- **Self-Healing & Zero-Config**: Administrators do not need to configure any manual subnets or trusted proxies. The charm automatically discovers the configuration dynamically.
- **Compatibility**: Standard LDAP clients (e.g., SSSD or PAM) connecting to Traefik do not need to support Proxy Protocol, because Traefik handles the header prepending transparently.
