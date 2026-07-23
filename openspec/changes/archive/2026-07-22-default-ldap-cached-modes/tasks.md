## 1. Configuration

- [x] 1.1 Change the `search_mode` and `bind_mode` defaults to `cached` while retaining `direct` support in `charmcraft.yaml`.

## 2. Documentation

- [x] 2.1 Update `README.md` with cached-mode freshness, warm-up, password-change, session-revocation, and pre-upgrade direct-pinning guidance.
- [x] 2.2 Update the LDAP configuration contract in `openspec/specs/charmcraft-config/spec.md` to describe cached defaults, explicit direct mode, and the operator guidance contract.

## 3. Unit Tests

- [x] 3.1 Update focused default-mode coverage and add an explicit-direct override case in `tests/unit/test_charm.py`.

## 4. Verification

- [x] 4.1 Run only the focused unit tests covering cached defaults and explicit direct mode.
- [x] 4.2 Parent-owned: run repository-wide verification after the isolated worktree changes are integrated.
