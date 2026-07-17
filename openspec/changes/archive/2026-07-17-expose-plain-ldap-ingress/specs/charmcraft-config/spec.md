# charmcraft-config Delta Specification

## Purpose
This delta specification defines the additions to the Juju charm configuration (`charmcraft.yaml`) to support optionally exposing the cleartext LDAP endpoint.

## ADDED Requirements

### Requirement: Expose plain LDAP configuration option
The charm `charmcraft.yaml` MUST declare a boolean configuration option named `expose_ldap_ingress` with a default value of `false`.

#### Scenario: Configuration option is declared with correct default
- **WHEN** the charm metadata is parsed
- **THEN** the configuration contains `expose_ldap_ingress` of type `boolean` with a default of `false`
