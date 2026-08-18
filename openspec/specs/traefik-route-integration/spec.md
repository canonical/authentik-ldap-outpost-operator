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
- **THEN** the charm updates the `ldap` relation databag setting `ldaps_enabled=true` and publishes the secure connection URI `ldaps://<host>:636`, where `<host>` is the configured `ingress_domain` if set and Traefik's external hostname otherwise

### Requirement: Declare plain LDAP entrypoint when enabled
When the `expose_ldap_ingress` configuration option is set to `true`, the charm SHALL declare a custom cleartext `ldap` entrypoint on port `389` using `HostSNI("*")` in addition to the secure `ldaps` entrypoint.

#### Scenario: Submit plain LDAP route to Traefik when enabled
- **WHEN** the `traefik-route` relation is established and `expose_ldap_ingress` is `true`
- **THEN** the charm writes both the `ldaps` and `ldap` entrypoint definitions and their TCP route configurations to the Traefik relation databag

### Requirement: Advertise no LDAPS endpoint when Traefik is absent
When `ldaps_enabled` is `false`, the charm SHALL publish an empty `ldaps_urls`
list on every `ldap` relation. It SHALL NOT fall back to advertising
`ldaps://<unit-or-service-address>:636`: TLS is terminated exclusively at
Traefik, no certificate is ever provisioned to the outpost container, and the
container serves no LDAPS listener, so such a URI would never be usable.
Consumers SHALL determine LDAPS availability from the `ldaps_enabled` databag
field rather than from the presence of `ldaps_urls`.

#### Scenario: LDAPS advertisement is withdrawn without Traefik
- **WHEN** no `traefik-route` relation is active, or Traefik reports a
  non-HTTPS scheme
- **THEN** the `ldap` relation databag contains `ldaps_enabled=false` and
  `ldaps_urls` serialised as an empty list

### Requirement: Advertise the SNI-matched host for LDAPS
The charm SHALL advertise `ldaps://<ingress_domain>:636` whenever
`ingress_domain` is configured, rather than Traefik's own external hostname.
The LDAPS router rule is ``HostSNI(`<ingress_domain>`)``, so advertising any
other host would make clients present an SNI that cannot match the rule, and
Traefik would drop the connection.

#### Scenario: Configured ingress domain is the advertised LDAPS host
- **WHEN** `ingress_domain` is set and the Traefik route is active over HTTPS
- **THEN** the `ldap` relation databag advertises
  `ldaps://<ingress_domain>:636`

### Requirement: Advertise Traefik's cleartext entrypoint when exposed
The charm SHALL advertise `ldap://<external_host>:389` on every `ldap` relation
when `expose_ldap_ingress` is `true` and Traefik has published an external host,
matching the cleartext entrypoint it declares. Otherwise it SHALL advertise the
in-cluster endpoint `ldap://<service-dns>:3389`.

#### Scenario: Cleartext ingress endpoint replaces the in-cluster one when exposed
- **WHEN** `expose_ldap_ingress` is `true` and Traefik reports an external host
- **THEN** `urls` is `["ldap://<external_host>:389"]`

