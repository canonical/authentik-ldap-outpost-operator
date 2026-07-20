## Why

Diverse standard LDAP clients (such as Valkey, SSSD Linux Logins, SSH keys fetchers, Apache Ranger, and OpenSearch) fail to authenticate against Authentik's LDAP Outpost out-of-the-box due to a very restricted set of returned attributes by default. For example, Valkey relies on a standard `entryDN` attribute, while SSSD relies on POSIX identity attributes (`uidNumber`, `gidNumber`, `homeDirectory`, `loginShell`) and SSH public keys (`sshPublicKey`). Automatically creating and binding standard LDAP Provider Property Mappings resolving these attributes solves this globally in the charm without manual administrator overhead.

## What Changes

- Add a list constant `DEFAULT_LDAP_PROPERTY_MAPPINGS` in `src/api_client.py` representing standard property mappings for `entryDN`, `POSIX uidNumber/gidNumber`, `POSIX homeDirectory/loginShell`, and `sshPublicKey`.
- Implement an idempotent helper method `get_or_create_ldap_property_mappings` in `src/api_client.py` to ensure all default mappings are created via POST to `/api/v3/propertymappings/provider/ldap/`.
- Update `get_or_create_provider` to fetch the current LDAP Provider's configuration using `GET`, merge any existing property mappings with the default ones to avoid duplicates or losing custom admin configurations, and apply the update via `PATCH`.
- Update and write robust unit tests covering the creation, fetching, and merging behavior.

## Non-goals

- Implementing any changes inside client charms (such as Valkey, SSSD, Apache Ranger, or OpenSearch).
- Managing properties or user/group attributes of LDAP sources (syncing from external directories).

## Capabilities

### New Capabilities
- `ldap-entrydn-property-mapping`: Automated creation and assignment of default, robust LDAP Property Mappings (`entryDN`, POSIX UID/GID, POSIX Home/Shell, SSH keys) to the LDAP Provider for compatibility with diverse clients.

### Modified Capabilities

## Impact

- `src/api_client.py`: Adds `DEFAULT_LDAP_PROPERTY_MAPPINGS`, `get_or_create_ldap_property_mappings`, and updates `get_or_create_provider`.
- `tests/unit/test_api_client.py`: Replaces old tests with comprehensive testing of multiple mappings creation, exact name resolution, and patch merging.
