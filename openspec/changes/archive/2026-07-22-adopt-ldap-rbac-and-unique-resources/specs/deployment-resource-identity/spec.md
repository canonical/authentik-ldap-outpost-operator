## ADDED Requirements

### Requirement: Managed resource names include stable deployment identity
The charm SHALL sanitize the Juju application name and append a deterministic twelve-hexadecimal-character SHA-256 prefix derived from the stable Juju model UUID. Provider, application name and slug, outpost, managed role, bind users, and charm-owned secret labels SHALL include that same deployment identity.

#### Scenario: Same application name exists in separate models
- **WHEN** two deployments have the same application name and different model UUIDs
- **THEN** every managed Authentik resource name and charm-owned secret label differs between the deployments

#### Scenario: Reconciliation repeats in one model
- **WHEN** the charm computes names repeatedly for the same application and model UUID
- **THEN** it produces identical names and labels

### Requirement: Legacy ownership is proven before migration
The charm SHALL migrate a legacy provider and outpost only by cached peer identifiers. It SHALL require the exact legacy or target application to reference the cached provider and the cached outpost to contain that provider. It SHALL validate tracked bind users by cached integer user IDs. Name-only discovery SHALL NOT establish ownership.

#### Scenario: Cached resources have exact linkage
- **WHEN** the cached provider and outpost exist, the exact application references that provider, and every resource has its exact legacy or target name
- **THEN** the resources qualify for idempotent migration

#### Scenario: Application points to another provider
- **WHEN** the legacy-named application does not reference the cached provider
- **THEN** migration raises a typed permanent error without renaming, adopting, creating, or deleting any resource

### Requirement: Migration preflights target collisions
Before any rename or authorization mutation, the charm SHALL check every target provider name, application name and slug, outpost name, bind username, and secret label. A target occupied by a different resource, duplicate exact candidates, incomplete core cached identifiers, or an unexpected source name SHALL raise a typed permanent error without mutation.

#### Scenario: Target provider name is occupied
- **WHEN** another provider already has the deployment-specific target name
- **THEN** migration raises a typed permanent collision error and performs no PATCH, POST, or DELETE

#### Scenario: Ownership evidence is incomplete
- **WHEN** only some required provider/outpost/token cache identifiers are present
- **THEN** migration refuses to adopt legacy resources and performs no mutation

### Requirement: Validated rename is idempotent
After complete preflight, the charm SHALL rename only resources still using their exact legacy names. Resources already carrying target names SHALL be no-ops, allowing reconciliation to complete safely after an interrupted prior migration.

#### Scenario: Migration resumes after partial rename
- **WHEN** cached resources comprise a validated mix of exact legacy and exact target names
- **THEN** the charm patches only legacy-named resources and reaches the same fully namespaced state

### Requirement: Fresh provisioning never adopts legacy names
When no complete owned legacy cache exists, the charm SHALL create or reuse only exact deployment-specific resources. It SHALL refuse an occupied target rather than adopting it without ownership proof.

#### Scenario: Fresh model provisions resources
- **WHEN** no core resource IDs are cached and target names are unoccupied
- **THEN** the charm creates provider, application, outpost, role, bind users, and secret labels with the deployment identity
