## Why

Currently, the outpost charm exposes a Traefik L4 ingress but uses a wildcard `HostSNI(*)` rule, meaning only a single outpost can integrate with a given Traefik instance on port 636. To support multiple independent outposts on the same Traefik instance (multi-tenancy), the outpost charm must support a user-configurable ingress domain so that we can leverage SNI-based multiplexing with Traefik's dynamic per-subdomain TLS certificates.

## What Changes

- Add an `ingress_domain` configuration option to `charmcraft.yaml` so that administrators can define the explicit domain name used for the outpost's ingress route.
- Update `templates/traefik-route.json.j2` and its rendering logic to dynamically populate `HostSNI(<domain>)` if `ingress_domain` is set, falling back to `HostSNI(*)` if unset.
- Document deployment and configuration instructions in `README.md` to guide administrators on how to properly set up subdomain-based dynamic TLS ingress.

## Non-Goals

- Dynamically registering DNS records within the operator.
- Managing wildcard certificates inside the outpost workload container (termination remains offloaded to Traefik).

## Capabilities

### New Capabilities

- `ingress-sni-routing`: Dynamic SNI-based ingress routing for Traefik TCP proxying.

### Modified Capabilities

None.

## Impact

- `charmcraft.yaml`: Add new configuration parameter `ingress_domain`.
- `src/configs.py`: Parse and validate the new `ingress_domain` option.
- `src/services.py`: Use the parsed `ingress_domain` value when rendering the Traefik route configuration.
- `templates/traefik-route.json.j2`: Parameterize the `rule` attribute.
- `README.md`: Add a dedicated section on multi-outpost deployment and SNI-based TLS ingress configuration.
