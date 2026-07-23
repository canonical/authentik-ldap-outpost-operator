## 1. Library and integration

- [x] 1.1 Sync `lib/charms/authentik_server/v0/authentik_server_info.py` to LIBPATCH 4 with the canonical `api-token` contract
- [x] 1.2 Rename `ServerInfo.bootstrap_token` to `api_token` and drop the bootstrap-password requirement in `src/integrations.py`

## 2. Charm reconciliation

- [x] 2.1 Authenticate every control-plane `AuthentikApiClient` with the automation token in `src/charm.py`

## 3. Verification

- [x] 3.1 Run focused charm and integration unit tests
- [x] 3.2 Parent-owned repository-wide verification
