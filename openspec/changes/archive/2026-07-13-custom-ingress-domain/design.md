## Context

The `authentik-ldap-outpost-operator` implements a secure L4 Traefik integration via Juju's `traefik_route` relation interface. Currently, the dynamic TCP configuration templates the router's SNI rule with `HostSNI(*)` to capture all traffic on port 636. While this works perfectly for single-instance outposts, in multi-outpost topologies this wildcard causes immediate routing conflicts inside Traefik. To resolve this, we will introduce a configurable `ingress_domain` and dynamically template the Traefik router SNI rule.

## Goals / Non-Goals

**Goals:**
- Introduce a user-configurable `ingress_domain` option in `charmcraft.yaml`.
- Support dynamic rendering of the `HostSNI` rule using the configured `ingress_domain` (falling back to `HostSNI(*)` if unset).
- Provide clear README documentation detailing how to configure the Traefik wildcard and the Juju certificate-management ecosystem for SNI-multiplexed deployment.

**Non-Goals:**
- Bypassing TLS termination at Traefik (TLS termination remains offloaded to Traefik).
- Registering DNS entries automatically.

## Decisions

### Decision 1: Add `ingress_domain` configuration
- **Rationale**: An explicit configuration parameter allows administrators to define the exact domain name assigned to each outpost unit, making it straightforward to support multi-tenant routing paths.
- **Implementation**:
  - Define `ingress_domain` option in `charmcraft.yaml`.
  - Parse and validate `ingress_domain` inside `src/configs.py`.

### Decision 2: Dynamically template `HostSNI` rule in `traefik-route.json.j2`
- **Rationale**: If `ingress_domain` is set, the dynamic router's rule is templated with `HostSNI(<ingress_domain>)`. If unset, it falls back to `HostSNI(*)` for backward compatibility and simplified developer validation.
- **Implementation**:
  - Modify `templates/traefik-route.json.j2` to accept a `rule` variable.
  - Modify `src/services.py` to compute the rule string based on `config.ingress_domain` and pass it during Jinja rendering.

## Risks / Trade-offs

- **[Risk]**: Invalid domain inputs could break Traefik configuration parsing.
  - **Mitigation**: Validate the domain structure inside `src/configs.py` using standard pydantic string rules or regex validators.
