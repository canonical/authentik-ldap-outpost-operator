## 1. Fix `charmcraft.yaml` — container and OCI image

- [x] 1.1 Rename container `authentik-ldap-outpost` → `authentik-ldap` in the `containers:` block
- [x] 1.2 Remove `gid: 584792` and `uid: 584792` from the container spec
- [x] 1.3 Update `resources.oci-image.upstream-source` to `ghcr.io/goauthentik/ldap:2026.2.2`

## 2. Fix `charmcraft.yaml` — relations

- [x] 2.1 Remove the `pg-database` entry from `requires:`
- [x] 2.2 Add `authentik-server-info` under `requires:` (interface `authentik_server_info`, optional: true)
- [x] 2.3 Add `ingress` under `requires:` (interface `ingress`, optional: true, limit: 1)
- [x] 2.4 Add `ldaps-ingress` under `requires:` (interface `ingress`, optional: true, limit: 1)
- [x] 2.5 Add `ldap` under `provides:` (interface `ldap`)
- [x] 2.6 Add `authentik-ldap-peers` under `peers:` (interface `authentik_ldap_peers`)

## 3. Verify `src/constants.py`

- [x] 3.1 Confirm `WORKLOAD_CONTAINER = "authentik-ldap"` is present
- [x] 3.2 Confirm `SERVER_INFO_RELATION`, `LDAP_RELATION`, `INGRESS_RELATION`, `LDAPS_INGRESS_RELATION`, `PEER_RELATION` constants are present and match `charmcraft.yaml` relation names

## 4. Build and lint

- [x] 4.1 Run `charmcraft pack` — confirm it succeeds without errors
- [x] 4.2 Run `tox -e lint` — no errors
