# traefik-route-integration Specification

## Purpose

This specification defines the requirements for integrating the Authentik LDAP Outpost Charm with Traefik Route to expose custom secure LDAPS (Port 636) and optional unencrypted LDAP (Port 389) endpoints, allowing external clients to connect to the LDAP outpost.

## Requirements
### Requirement: Expose traefik-route integration for LDAPS
The charm SHALL define a `traefik-route` integration of interface `traefik_route` to declare custom TCP entrypoints for Port 636 (LDAPS).

#### Scenario: Charm configures traefik-route relation for LDAPS
- **WHEN** the `traefik-route` relation is established
- **THEN** the charm configures a custom secure TCP entrypoint on Traefik mapping Port 636 to the internal unencrypted Port 3389

### Requirement: Declare LDAPS entrypoint in the Traefik databag
The charm SHALL declare the custom `ldaps` entrypoint definition in its relation databag with Traefik so that the Traefik ingress controller configures and exposes the external port 636.

#### Scenario: Submitting route and entrypoint definition
- **WHEN** configuring the `traefik-route` relation
- **THEN** the charm writes the custom entrypoint definition (e.g. binding Port 636 for LDAPS L4 traffic) and the TCP route configuration to the Traefik relation databag

### Requirement: Advertise LDAPS status to directory consumers
The charm SHALL set `ldaps_enabled=true` inside the `ldap` relation databag if and only if the `traefik-route` relation is active, the external ingress endpoint is fully resolved, and the secure LDAPS service is ready.

#### Scenario: Enable LDAPS advertisement when Traefik is ready
- **WHEN** the Traefik route is active and provides a valid external hostname
- **THEN** the charm updates the `ldap` relation databag setting `ldaps_enabled=true` and publishes the secure connection URI `ldaps://<external_host>:636`

### Requirement: Declare plain LDAP entrypoint when enabled
When the `expose_ldap_ingress` configuration option is set to `true`, the charm SHALL declare a custom cleartext `ldap` entrypoint on port `389` using `HostSNI("*")` in addition to the secure `ldaps` entrypoint.

#### Scenario: Submit plain LDAP route to Traefik when enabled
- **WHEN** the `traefik-route` relation is established and `expose_ldap_ingress` is `true`
- **THEN** the charm writes both the `ldaps` and `ldap` entrypoint definitions and their TCP route configurations to the Traefik relation databag

