# authentik-ldap-rbac Specification

## Purpose
Defines how the LDAP outpost grants directory-search authorization through a charm-managed, provider-scoped Authentik RBAC role rather than group membership: exact role lookup and create, idempotent membership, a provider-scoped permission verified after assignment, and managed authorization for every bind user.
## Requirements
### Requirement: Charm manages an exact deployment role
The charm SHALL locate roles by exact name through `/api/v3/rbac/roles/` and SHALL create a role only when no exact match exists. The role name SHALL include the deployment identity. Multiple exact matches or malformed API records SHALL raise a typed permanent error without mutation.

#### Scenario: Existing exact role is reused
- **WHEN** the role list includes one role whose name exactly equals the deployment role name
- **THEN** the charm reuses its UUID and does not create another role

#### Scenario: Ambiguous exact roles block reconciliation
- **WHEN** more than one role has the exact deployment role name
- **THEN** reconciliation raises a typed permanent error before changing membership or permissions

### Requirement: Role membership is idempotent
The API client SHALL add and remove integer user primary keys with `roles/{role_uuid}/add_user/` and `remove_user/`. Repeating either operation SHALL have the same final membership state and SHALL not fail solely because the user is already added or removed.

#### Scenario: Tracked users are repeatedly reconciled
- **WHEN** reconciliation runs more than once for the same tracked bind users
- **THEN** every user remains a member of the deployment role without duplicate-membership failure

### Requirement: Directory search permission is provider scoped
The charm SHALL assign `authentik_providers_ldap.search_full_directory` to the deployment role with model `authentik_providers_ldap.ldapprovider` and `object_pk` equal to the managed provider integer primary key. Permission assignment and unassignment SHALL use Authentik's assigned-by-role action endpoints and fixed typed payload.

#### Scenario: Provider permission is assigned
- **WHEN** core resources and the deployment role are reconciled
- **THEN** the client assigns full-directory search for exactly the cached LDAP provider primary key

### Requirement: Permission scope is verified after assignment
After assignment, the client SHALL query assigned-by-role permissions with the LDAP provider model and intended object primary key. It SHALL require an exact role entry whose `object_permissions` contains the expected codename, model, app label, and stringified provider primary key. It SHALL reject a matching entry in `model_permissions`, an absent exact object permission, or a global permission as a typed permanent authorization error.

#### Scenario: Exact object assignment verifies
- **WHEN** the intended permission appears only in `object_permissions` with `object_pk` equal to the provider primary key
- **THEN** authorization reconciliation succeeds

#### Scenario: Nonexistent provider produced a global grant
- **WHEN** Authentik reports the intended codename in `model_permissions` after assignment
- **THEN** reconciliation raises a typed permanent authorization error and does not treat the role as authorized

### Requirement: All bind users receive managed authorization
The charm SHALL add every bind user proven by tracked peer data, including newly created bind users, to the deployment role. It SHALL NOT perform Authentik search-group lookup or group membership calls.

#### Scenario: Existing deployment upgrades
- **WHEN** tracked bind-user IDs exist during the first RBAC reconciliation
- **THEN** each integer user ID is added to the managed role

#### Scenario: New LDAP relation is created
- **WHEN** a new bind user is provisioned for an LDAP relation
- **THEN** the user is added to the managed role before relation credentials are published

