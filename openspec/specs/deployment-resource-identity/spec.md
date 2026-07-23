# deployment-resource-identity Specification

## Purpose
Defines the deployment-unique naming scheme for the Authentik objects the LDAP outpost manages (provider, application, outpost, role, bind users, and secret labels), so multiple deployments sharing one Authentik instance never collide.
## Requirements
### Requirement: Managed resource names include stable deployment identity
The charm SHALL sanitize the Juju application name and append a deterministic twelve-hexadecimal-character SHA-256 prefix derived from the stable Juju model UUID. Provider, application name and slug, outpost, managed role, bind users, and charm-owned secret labels SHALL include that same deployment identity.

#### Scenario: Same application name exists in separate models
- **WHEN** two deployments have the same application name and different model UUIDs
- **THEN** every managed Authentik resource name and charm-owned secret label differs between the deployments

#### Scenario: Reconciliation repeats in one model
- **WHEN** the charm computes names repeatedly for the same application and model UUID
- **THEN** it produces identical names and labels

### Requirement: Provisioning uses only deployment-specific resources
The charm SHALL create or reuse only exact deployment-specific Authentik resources (provider, application, outpost, role, bind users, and secret labels) identified by the deployment identity.

#### Scenario: Fresh model provisions resources
- **WHEN** no core resource IDs are cached and target names are unoccupied
- **THEN** the charm creates provider, application, outpost, role, bind users, and secret labels with the deployment identity

