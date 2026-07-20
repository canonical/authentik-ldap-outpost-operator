## Context

Diverse standard LDAP clients (Valkey, SSSD UNIX Identity, SSSD SSH keys) expect the LDAP outpost to return standard attributes (conforming to RFC 5020 and POSIX/SSH schemas) on query. Authentik's LDAP outpost does not serve these unless explicit LDAP Provider Property Mappings are linked to the LDAP Provider. We will extend our Python Authentik API client inside the Juju charm to automatically find or create these mappings and associate them with the LDAP Provider.

## Goals / Non-Goals

**Goals:**
- Automatically ensure four key standard property mappings exist with correct names, target object fields, and Python expressions.
- Automatically associate these mappings to the LDAP Provider during `get_or_create_provider`.
- Retrieve and preserve any pre-existing custom property mappings configured by administrators on the LDAP Provider, merging them dynamically.
- Expand unit tests to thoroughly mock and verify API client responses and mapping payloads.

**Non-Goals:**
- Creating custom user/group schemas inside Authentik.
- Modifying client charms or clients directly.

## Decisions

### Decision 1: Endpoint for Mapping
We will use `/api/v3/propertymappings/provider/ldap/` to query and manage the property mappings. This is the standard Authentik API endpoint for LDAP provider property mappings.

### Decision 2: Mapping Configuration
Four mappings will be defined:
1. **`entryDN`**:
   - **Name**: `authentik default LDAP Mapping: entryDN`
   - **Object Field**: `entryDN`
   - **Expression**: `return f"cn={user.username},ou=users,{provider.base_dn}"`
2. **SSSD POSIX UID/GID**:
   - **Name**: `authentik default LDAP Mapping: POSIX uidNumber/gidNumber`
   - **Object Field**: `uidNumber`
   - **Expression**: returns `uidNumber` and `gidNumber` dictionary.
3. **SSSD Home & Shell**:
   - **Name**: `authentik default LDAP Mapping: POSIX homeDirectory/loginShell`
   - **Object Field**: `homeDirectory`
   - **Expression**: returns `homeDirectory` and `loginShell` dictionary.
4. **SSSD SSH Keys**:
   - **Name**: `authentik default LDAP Mapping: sshPublicKey`
   - **Object Field**: `sshPublicKey`
   - **Expression**: returns a list of SSH public keys from user attributes.

### Decision 3: Precise Search Resolution
When querying existing mappings, we will use `/api/v3/propertymappings/all/?search=<name>` to find them. To avoid substring collision/namespaces, we will loop and perform an exact name string equality check on results.

### Decision  decision 4: Preservation & Assignment Strategy
When patching an existing LDAP Provider, we will perform a `GET /api/v3/providers/ldap/{id}/` to fetch its current configurations. We will extract its `property_mappings`, append any missing default mapping UUIDs, and use `PATCH` to update the provider, preventing duplicates and retaining custom mappings.

## Risks / Trade-offs

- **Risk:** High API traffic or timeouts.
  - *Mitigation:* The API client uses standard `tenacity` retries and robust caching structures to guarantee reliable reconciliation.
