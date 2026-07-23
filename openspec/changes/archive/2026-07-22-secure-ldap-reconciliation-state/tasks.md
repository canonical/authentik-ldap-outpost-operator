## 1. Authentik API Transport

- [x] 1.1 Add reusable session, typed API failures, and bounded retry classification in `src/api_client.py`.
- [x] 1.2 Remove authorization-flow lookup and resolve only the invalidation flow in `src/api_client.py`.
- [x] 1.3 Update `tests/unit/test_api_client.py` for session reuse, retry classification, typed errors, and flow requests.

## 2. Reconciliation State

- [x] 2.1 Make existing-resource verification reprovision only on typed not-found in `src/charm.py`.
- [x] 2.2 Add secret-backed outpost token storage and safe legacy migration in `src/charm.py`.
- [x] 2.3 Remove bind passwords from peer state and add library-secret recovery/rotation in `src/charm.py` and `src/integrations.py`.
- [x] 2.4 Preserve orphan deletion tracking until successful or typed-not-found completion in `src/charm.py` and `src/api_client.py`.

## 3. Reconciliation Tests

- [x] 3.1 Update `tests/unit/conftest.py` and `tests/unit/test_charm.py` for token migration and follower secret reads.
- [x] 3.2 Add `tests/unit/test_charm.py` coverage for unchanged LDAP secret contracts, missing-bind-secret rotation, verification classification, and deletion retries.

## 4. Verification

- [x] 4.1 Run impacted API client and charm unit modules and fix all regressions.
- [x] 4.2 Confirm OpenSpec status reports all implementation tasks complete.
