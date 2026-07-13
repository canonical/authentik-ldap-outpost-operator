## ADDED Requirements

### Requirement: Support ingress_domain configuration option
The charm SHALL define and support an `ingress_domain` configuration option of type `string` inside `charmcraft.yaml` to let administrators configure a custom domain name for the external ingress route.

#### Scenario: Parse and validate ingress_domain configuration
- **WHEN** the `ingress_domain` config option is updated
- **THEN** the charm validates and parses the option, ensuring it is a valid domain or IP string, and stores it in the `CharmConfig` instance.

### Requirement: Generate dynamic HostSNI rule based on ingress_domain
The charm SHALL dynamically construct the `HostSNI` rule for Traefik's dynamic route configuration based on the configured `ingress_domain`.

#### Scenario: Rule generation when ingress_domain is set
- **WHEN** generating the dynamic Traefik route config and `ingress_domain` is configured
- **THEN** the charm templates the router's rule attribute with `HostSNI(<ingress_domain>)`.

#### Scenario: Rule generation when ingress_domain is unset
- **WHEN** generating the dynamic Traefik route config and `ingress_domain` is unset
- **THEN** the charm templates the router's rule attribute with the default wildcard `HostSNI(*)`.
