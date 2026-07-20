## ADDED Requirements

### Requirement: LDAP Provider Property Mappings Creation
The Authentik API client SHALL search for each of the following four default LDAP Provider Property Mappings by name using `/api/v3/propertymappings/all/?search=<name>`. If a mapping does not exist, the client SHALL perform a POST request to `/api/v3/propertymappings/provider/ldap/` to create it.

#### 1. Valkey and Client `entryDN` Matcher
- **Name**: `authentik default LDAP Mapping: entryDN`
- **Object field**: `entryDN`
- **Python Expression**: `return f"cn={user.username},ou=users,{provider.base_dn}"`

#### 2. SSSD Unix Identity (POSIX UID/GID)
- **Name**: `authentik default LDAP Mapping: POSIX uidNumber/gidNumber`
- **Object field**: `uidNumber`
- **Python Expression**: returns `uidNumber` and `gidNumber` dictionary.

#### 3. SSSD Unix Home & Shell
- **Name**: `authentik default LDAP Mapping: POSIX homeDirectory/loginShell`
- **Object field**: `homeDirectory`
- **Python Expression**: returns `homeDirectory` and `loginShell` dictionary.

#### 4. SSSD SSH Public Keys Fetcher
- **Name**: `authentik default LDAP Mapping: sshPublicKey`
- **Object field**: `sshPublicKey`
- **Python Expression**: returns list of SSH public keys from user attributes.

---

### Requirement: LDAP Property Mappings Assignment and Merging
The Authentik API client SHALL retrieve the UUIDs of these default mappings and associate them with the LDAP Provider's `property_mappings` attribute.
To ensure administrative changes are not lost:
1. **WHEN** the LDAP Provider already exists
2. **THEN** the API client SHALL perform a GET request on `/api/v3/providers/ldap/{id}/` to fetch its current configuration
3. **AND** SHALL merge the pre-existing property mapping UUIDs with the default mapping UUIDs, preventing duplicates
4. **AND** SHALL patch the provider via `PATCH /api/v3/providers/ldap/{id}/` using the merged list of UUIDs in `property_mappings`
