## ADDED Requirements

### Requirement: Bind account reflects the requirer-requested identity

For each `ldap` relation, the outpost SHALL derive the bind account username from the requirer-provided `user`, namespaced with the deployment identity and relation id to remain globally unique, and SHALL publish the resulting `bind_dn` (`cn=<username>,ou=users,<base_dn>`). When the requirer provides no `user`, the charm SHALL fall back to its deployment-unique generated name.

#### Scenario: Requested user reflected in bind username
- **WHEN** a requirer requests `user=svc`
- **THEN** the provisioned bind username contains `svc` and remains unique to the deployment and relation

#### Scenario: Missing requested user
- **WHEN** a requirer provides no `user`
- **THEN** the charm provisions its deployment-unique generated bind username

#### Scenario: Requested user changes
- **WHEN** a relation's requested `user` changes to a value whose target username is free
- **THEN** the charm renames the existing bind user to the new target and refuses if the target is owned by another user

### Requirement: Adopt-only group membership

The outpost SHALL add the bind user to an existing Authentik group whose name equals the requirer-provided `group`, and SHALL NOT create or delete groups. Full-directory search authorization remains provided by the managed RBAC role.

#### Scenario: Requested group exists
- **WHEN** the requested `group` matches an existing Authentik group
- **THEN** the bind user is added to that group

#### Scenario: Requested group does not exist
- **WHEN** no Authentik group matches the requested `group`
- **THEN** the charm logs and skips group membership without failing reconciliation

#### Scenario: Requested group changes
- **WHEN** a relation's requested `group` changes
- **THEN** the bind user is removed from the previously tracked group (if present) and added to the new group when it exists
