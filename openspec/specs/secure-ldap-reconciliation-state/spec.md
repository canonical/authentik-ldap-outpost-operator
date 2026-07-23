# secure-ldap-reconciliation-state Specification

## Purpose
Defines the LDAP outpost's secure, resilient interaction with the Authentik REST API and its reconciliation state: a reused authenticated HTTP session, bounded typed-error retries, and safe persistence of provisioning state so partial failures resume without leaking credentials or duplicating resources.
## Requirements
### Requirement: Classified and bounded Authentik requests
The Authentik API client SHALL reuse one authenticated HTTP session and SHALL retry at most three attempts only for connection failures, HTTP 429 responses, and HTTP 5xx responses. It SHALL raise typed errors and SHALL NOT retry other HTTP failures.

#### Scenario: Permanent HTTP failure
- **WHEN** Authentik responds with HTTP 401, 403, or another non-429 4xx status
- **THEN** the client raises the corresponding typed API error after one request

#### Scenario: Transient HTTP failure
- **WHEN** a connection failure, HTTP 429, or HTTP 5xx response occurs
- **THEN** the client retries within the bounded attempt limit and returns a later successful response or raises the typed final failure

### Requirement: LDAP provider resolves only required flows
Provider provisioning SHALL resolve only the default invalidation flow and SHALL use the LDAP bind flow for both authentication and authorization fields.

#### Scenario: Provider creation
- **WHEN** the charm reconciles an LDAP provider
- **THEN** it requests the invalidation flow and does not request the default authorization flow

### Requirement: Definitive absence controls reprovisioning
Existing Authentik resources SHALL be reprovisioned only when verification raises a typed not-found error.

#### Scenario: Existing resource not found
- **WHEN** outpost verification returns typed HTTP 404
- **THEN** reconciliation proceeds to idempotent resource provisioning

#### Scenario: Verification cannot be trusted
- **WHEN** verification fails because of authentication, authorization, connection, throttling, or server failure
- **THEN** the failure bubbles and no fresh provisioning is attempted

### Requirement: Outpost token is secret-backed
The charm SHALL store the outpost token in an application-owned Juju secret whose content contains only `token`, and SHALL store only `outpost_token_secret_id` in peer data.

#### Scenario: Follower resolves token
- **WHEN** a follower sees `outpost_token_secret_id`
- **THEN** it reads `token` from that application secret for workload configuration

### Requirement: Bind passwords remain outside peer state
The charm SHALL store only the Authentik user ID and username in `client_<relation-id>` peer JSON, while preserving the existing `glauth_ldap` relation data and `bind_password_secret` contract.

#### Scenario: Existing bind relation
- **WHEN** peer identity and the library-managed bind secret exist
- **THEN** reconciliation retrieves the password through `LdapProvider.get_bind_password()` and republishes the unchanged relation contract without plaintext peer storage

#### Scenario: Existing bind secret is missing
- **WHEN** peer identity exists but `get_bind_password()` returns no password
- **THEN** the leader rotates the Authentik password and republishes a new library-managed secret, while followers wait safely

### Requirement: Orphan deletion is resumable
The charm SHALL preserve orphaned client tracking until Authentik deletion succeeds or returns typed HTTP 404.

#### Scenario: Deletion fails transiently
- **WHEN** deleting the tracked Authentik user raises a connection, throttling, authorization, or server error
- **THEN** peer tracking remains for a subsequent reconciliation attempt

#### Scenario: Deletion completes idempotently
- **WHEN** deleting the tracked user succeeds or Authentik reports typed not-found
- **THEN** the charm removes the relation's peer tracking

