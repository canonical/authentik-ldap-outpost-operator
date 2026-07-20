## 1. Declarative Configuration Update

- [x] 1.1 Update default value of the `search_group` configuration option in `charmcraft.yaml` to `"authentik Admins"`

## 2. Extend State Caching in charm.py

- [x] 2.1 Update `_set_peer_config_metadata` in `src/charm.py` to accept and write `search_group` to the peer relation databag under the key `"last_search_group"`
- [x] 2.2 Update `_provision_authentik_resources` in `src/charm.py` to retrieve the current `search_group` configuration and the cached `last_search_group` from peer relation data, then include `last_search_group == search_group` in the `config_unchanged` condition check

## 3. Reconcile Existing Service Accounts and Enforce Existence

- [x] 3.1 Implement a helper method `_update_existing_users_groups(self, client: AuthentikApiClient, search_group_name: str)` in `src/charm.py` to look up the group UUID and register all active relation users in the new search group on the Authentik server
- [x] 3.2 Update `_verify_and_update_existing_resources` in `src/charm.py` to detect if the search group configuration changed (`last_search_group != search_group`), and if so, trigger `_update_existing_users_groups` to re-sync all existing active relation users
- [x] 3.3 Update `_on_collect_status` and status accumulation logic in `src/charm.py` to verify if the configured `search_group` exists on Authentik, and raise `BlockedStatus("LDAP search group '<group>' not found in Authentik")` if missing

## 4. Unit and Integration Testing

- [x] 4.1 Write unit tests in `tests/unit/test_charm.py` to assert peer config metadata tracking, `config_unchanged` state checks with `search_group` changes, and service account update triggers
- [x] 4.2 Write unit tests to mock search group validation failure and verify that the operator transitions to `BlockedStatus`
- [x] 4.3 Add or update integration tests in `tests/integration/` to verify that changing the `search_group` configuration option successfully validates the group, updates existing relation service accounts, and triggers the blocked status if the group is removed/missing
- [x] 4.4 Verify style and code quality by running linter checks inside `/home/nikos.sklikas@canonical.com/projects/authentik-charms/authentik-ldap-outpost-operator-search-group-fix`
