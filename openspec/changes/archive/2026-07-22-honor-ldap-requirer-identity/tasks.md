## 1. API client

- [x] 1.1 Add `get_group_by_name`, `add_user_to_group`, and `remove_user_from_group` to `src/api_client.py`

## 2. Charm reconciliation

- [x] 2.1 Read requirer `user`/`group` from the `ldap` relation databag in `src/charm.py`
- [x] 2.2 Derive the namespaced, requirer-aware bind username and rename on change with collision refusal
- [x] 2.3 Adopt-only group membership with `last_group` change detection in peer data
- [x] 2.4 Extend the per-relation peer record with `last_user`/`last_group`

## 3. Tests and docs

- [x] 3.1 Add API client tests for group lookup/membership in `tests/unit/test_api_client.py`
- [x] 3.2 Add charm tests for requirer-derived naming, user rename, group adopt/skip/change, and collision refusal in `tests/unit/test_charm.py`
- [x] 3.3 Document the Authentik-vs-glauth `user`/`group` semantics in `README.md`
- [x] 3.4 Run focused api-client and charm unit tests
- [x] 3.5 Parent-owned repository-wide verification
