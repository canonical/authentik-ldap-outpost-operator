## 1. Authentik API contracts

- [x] 1.1 Add typed exact role lookup/create and idempotent membership methods in `src/api_client.py`
- [x] 1.2 Add typed provider-scoped permission assign/unassign and strict post-assignment object-scope verification in `src/api_client.py`
- [x] 1.3 Add exact resource inspection, collision detection, and rename helpers needed for cached-ID migration in `src/api_client.py`

## 2. Charm reconciliation and migration

- [x] 2.1 Add typed permanent migration and authorization failures in `src/exceptions.py` and handle them as non-transient reconciliation failures in `src/charm.py`
- [x] 2.2 Derive stable model-UUID-hashed names for providers, applications/slugs, outposts, roles, bind users, and secret labels in `src/charm.py`
- [x] 2.3 Implement preflighted, cached-ID legacy migration with exact application-provider/outpost linkage and collision refusal in `src/charm.py`
- [x] 2.4 Replace search-group runtime and peer metadata behavior with verified managed-role authorization for all tracked and new bind users in `src/charm.py`

## 3. Upgrade compatibility

- [x] 3.1 Remove the `search_group` option from `charmcraft.yaml` (pre-release; no compatibility shim)
- [x] 3.2 Remove remaining search-group integration assumptions while preserving the public LDAP relation contract in `src/integrations.py`

## 4. Focused verification

- [x] 4.1 Add focused role idempotency and object-versus-global permission tests in `tests/unit/test_api_client.py`
- [x] 4.2 Add focused migration, cross-model naming, tracked/new-user role membership, and collision-refusal tests in `tests/unit/test_charm.py` and fixtures in `tests/unit/conftest.py`
- [x] 4.3 Run the focused API-client and charm unit tests and record passing commands
- [x] 4.4 Parent owner runs repository-wide format, lint, and test verification
