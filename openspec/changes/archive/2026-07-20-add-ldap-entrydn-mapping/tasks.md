## 1. Implementation of API client helpers

- [x] 1.1 Implement `DEFAULT_LDAP_PROPERTY_MAPPINGS` representing the four diverse standard client LDAP mappings.
- [x] 1.2 Implement `get_or_create_ldap_property_mappings` in `src/api_client.py` to check for and provision missing mappings.
- [x] 1.3 Update `get_or_create_provider` in `src/api_client.py` to retrieve current provider details via `GET`, merge property mappings to avoid duplicates, and update the provider via `PATCH`.

## 2. Unit Testing and Quality Checks

- [x] 2.1 Add and update unit tests in `tests/unit/test_api_client.py` to cover exact string checks, creation, and merging/patching of property mappings.
- [x] 2.2 Run formatting and linting checks using `tox -e fmt` and `tox -e lint` to ensure upstream Canonical compliance.
- [x] 2.3 Run unit tests using `tox -e unit` to verify everything is functional.
