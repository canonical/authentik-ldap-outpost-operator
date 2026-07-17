# traefik-route-integration Delta Specification

## Purpose
This delta specification defines the additions to the Traefik route integration requirements to dynamically register standard cleartext LDAP TCP routers on port 389.

## ADDED Requirements

### Requirement: Declare plain LDAP entrypoint when enabled
When the `expose_ldap_ingress` configuration option is set to `true`, the charm SHALL declare a custom cleartext `ldap` entrypoint on port `389` using `HostSNI("*")` in addition to the secure `ldaps` entrypoint.

#### Scenario: Submit plain LDAP route to Traefik when enabled
- **WHEN** the `traefik-route` relation is established and `expose_ldap_ingress` is `true`
- **THEN** the charm writes both the `ldaps` and `ldap` entrypoint definitions and their TCP route configurations to the Traefik relation databag
