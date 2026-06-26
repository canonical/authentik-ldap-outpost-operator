# integration-wrappers Specification

## Purpose
TBD - created by archiving change authentik-ldap-refactor. Update Purpose after archive.
## Requirements
### Requirement: `ServerInfoIntegration` implements `EnvVarConvertible`
`ServerInfoIntegration` SHALL be a standalone class (not nested in `Integrations`) that wraps `AuthentikServerInfoRequirer`. It SHALL implement `to_env_vars() -> dict[str, str]` returning `{"AUTHENTIK_HOST": host, "AUTHENTIK_TOKEN": token, "AUTHENTIK_INSECURE": "true"}` when `is_ready` is `True`, or an empty dict otherwise.

#### Scenario: Ready — env vars returned
- **WHEN** `AuthentikServerInfoRequirer.is_ready` is `True`
- **THEN** `ServerInfoIntegration.to_env_vars()` returns a dict with `AUTHENTIK_HOST`, `AUTHENTIK_TOKEN`, and `AUTHENTIK_INSECURE`

#### Scenario: Not ready — empty dict
- **WHEN** `AuthentikServerInfoRequirer.is_ready` is `False`
- **THEN** `ServerInfoIntegration.to_env_vars()` returns `{}`

### Requirement: `ServerInfoIntegration.is_ready` delegates to lib
`ServerInfoIntegration.is_ready` SHALL return `True` if and only if `AuthentikServerInfoRequirer.is_ready` is `True`.

#### Scenario: Delegation
- **WHEN** the underlying requirer is ready
- **THEN** `ServerInfoIntegration.is_ready` returns `True`

### Requirement: `LdapProviderIntegration.update_relation_data()` sets relation databag
`LdapProviderIntegration` SHALL wrap `LdapProvider` from `charms.glauth_k8s.v0.ldap`. Its `update_relation_data(relation_id: int, unit_address: str, base_dn: str, bind_dn: str, password: str)` method SHALL call `LdapProvider.update_relations_app_data()` with a `LdapProviderData` containing `urls`, `ldaps_urls`, `base_dn`, `bind_dn`, `bind_password`, `starttls=False`, and `auth_method="simple"` for the specified relation ID.

#### Scenario: Provider data written to relation
- **WHEN** `update_relation_data(11, "10.0.0.1", "dc=ldap", "cn=sa", "secret")` is called and a `ldap` relation exists
- **THEN** `LdapProvider.update_relations_app_data()` is called with correct URL and credential values for relation ID 11

### Requirement: `IngressIntegration` exposes ingress requirer events
`IngressIntegration` SHALL wrap two `IngressPerUnitRequirer` instances (one for `ingress`, one for `ldaps-ingress`). It SHALL expose `ldap_requirer` and `ldaps_requirer` properties so `charm.py` can observe their `on.ready` events directly.

#### Scenario: LDAP ingress ready event observable
- **WHEN** `IngressIntegration` is instantiated
- **THEN** `ingress.ldap_requirer.on.ready` can be observed via `framework.observe()`

### Requirement: Extraneous files are removed; `utils.py` is replaced
`src/cli.py`, `src/secret.py`, and `src/authentik_ldap_outpost.py` SHALL NOT exist in the repository after this change. `src/utils.py` SHALL be replaced with a clean version (see `utils-and-services` spec) — the old scaffold content is removed.

#### Scenario: No import references to deleted files remain
- **WHEN** `charm.py`, `integrations.py`, and `services.py` are parsed
- **THEN** none of them import from `cli`, `secret`, or `authentik_ldap_outpost`

