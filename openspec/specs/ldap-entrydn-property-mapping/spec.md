# ldap-entrydn-property-mapping Specification

## Purpose
This specification defines the requirement to automatically create and assign a standard set of default LDAP Property Mappings in the Authentik LDAP Provider. This enables out-of-the-box compatibility with diverse LDAP clients beyond basic binds, including **Valkey** (which requires RFC 5020-compliant `entryDN` attributes), **SSSD (Linux logins)** (which requires POSIX attributes such as `uidNumber`, `gidNumber`, `homeDirectory`, and `loginShell`), and **SSSD (SSH Keys)** (which requires `sshPublicKey`). By automating this setup and merging new mappings with pre-existing ones, the operator guarantees standard-compliant and multi-client compatible LDAP outposts without administrative overhead.

## Requirements

### Requirement: LDAP Provider Property Mappings Creation
The Authentik API client SHALL search for each of the following four default LDAP Provider Property Mappings by name using `/api/v3/propertymappings/all/?search=<name>`. If a mapping does not exist (meaning no exact name match is found), the client SHALL perform a POST request to `/api/v3/propertymappings/provider/ldap/` to create it.

#### 1. Valkey and Client `entryDN` Matcher
- **Name**: `authentik default LDAP Mapping: entryDN`
- **Object field**: `entryDN`
- **Python Expression**:
  ```python
  return f"cn={user.username},ou=users,{provider.base_dn}"
  ```

#### 2. SSSD Unix Identity (POSIX UID/GID)
- **Name**: `authentik default LDAP Mapping: POSIX uidNumber/gidNumber`
- **Object field**: `uidNumber`
- **Python Expression**:
  ```python
  # Extracts the authoritative UID/GID synced from the upstream directory
  return {
      "uidNumber": user.attributes.get("uidNumber"),
      "gidNumber": user.attributes.get("gidNumber")
  }
  ```

#### 3. SSSD Unix Home & Shell
- **Name**: `authentik default LDAP Mapping: POSIX homeDirectory/loginShell`
- **Object field**: `homeDirectory`
- **Python Expression**:
  ```python
  # Extracts the authoritative POSIX home directory and shell synced from upstream
  return {
      "homeDirectory": user.attributes.get("homeDirectory") or user.attributes.get("home_directory"),
      "loginShell": user.attributes.get("loginShell") or user.attributes.get("login_shell")
  }
  ```

#### 4. SSSD SSH Public Keys Fetcher
- **Name**: `authentik default LDAP Mapping: sshPublicKey`
- **Object field**: `sshPublicKey`
- **Python Expression**:
  ```python
  # Fetches multi-valued SSH public keys from user attributes list
  keys = user.attributes.get("ssh_public_key") or user.attributes.get("ssh_public_keys")
  if isinstance(keys, list):
      return keys
  return [keys] if keys else None
  ```

---

### Requirement: LDAP Property Mappings Assignment and Merging
The Authentik API client SHALL retrieve the UUIDs of these default mappings and associate them with the LDAP Provider's `property_mappings` attribute.
To ensure administrative changes are not lost:
1. **WHEN** the LDAP Provider already exists
2. **THEN** the API client SHALL perform a GET request on `/api/v3/providers/ldap/{id}/` to fetch its current configuration
3. **AND** SHALL merge the pre-existing property mapping UUIDs with the default mapping UUIDs, preventing duplicates
4. **AND** SHALL patch the provider via `PATCH /api/v3/providers/ldap/{id}/` using the merged list of UUIDs in `property_mappings`
