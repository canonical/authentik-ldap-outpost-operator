# integration-wrappers Specification

## Purpose

This specification defines the standalone integration wrappers found in `src/integrations.py`. It establishes a highly decoupled, composable integration design to replace monolithic patterns.

### Design Decisions
- **Decoupling the Monolith**: Replaces the unified `Integrations` god-object with discrete, individually injectable wrapper classes (`ServerInfoIntegration`, `LdapProviderIntegration`, `IngressIntegration`). Each class is injectable into `charm.py` and testable in total isolation.
- **`EnvVarConvertible` Standard**: Ensures integration data is standardized using Pydantic validation before being converted to standard environment variables via the `EnvVarConvertible` protocol.
- **Refactoring & Clean-Up**: Removed obsolete files such as `src/cli.py`, `src/secret.py`, and `src/authentik_ldap_outpost.py`. State management and secrets retrieval are delegated directly to standard relation libraries (`AuthentikServerInfoRequirer`), removing duplicated custom logic.

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

### Requirement: `LdapProviderIntegration.update_relation_data()` advertises only reachable endpoints
`LdapProviderIntegration` SHALL wrap `LdapProvider` from
`charms.glauth_k8s.v0.ldap`. Its
`update_relation_data(relation_id, cluster_address, base_dn, bind_dn, password, ldaps_enabled=False, external_host=None, expose_ldap_ingress=False, ingress_domain=None)`
method SHALL call `LdapProvider.update_relations_app_data()` with an
`LdapProviderData` containing `urls`, `ldaps_urls`, `base_dn`, `bind_dn`,
`bind_password`, `starttls=False`, and `auth_method="simple"` for the specified
relation ID. Callers SHALL pass arguments by keyword.

Endpoint construction SHALL advertise only endpoints that are actually
reachable:

- `urls` SHALL be `[ldap://<external_host>:<EXTERNAL_LDAP_PORT>]` when
  `expose_ldap_ingress` is enabled and an `external_host` is known, and SHALL
  otherwise be `[ldap://<cluster_address>:<LDAP_PORT>]`. `cluster_address` SHALL
  be the application's Kubernetes Service DNS name, never Traefik's host,
  because Traefik does not expose `LDAP_PORT`.
- `ldaps_urls` SHALL be `[ldaps://<host>:<EXTERNAL_LDAPS_PORT>]` when
  `ldaps_enabled` and a host is known, and SHALL otherwise be an empty list. The
  host SHALL be `ingress_domain` when set, falling back to `external_host`,
  because the LDAPS router matches `HostSNI` on that name.

#### Scenario: Provider data written to relation
- **WHEN** `update_relation_data()` is called with
  `cluster_address="authentik-ldap-outpost.my-model.svc.cluster.local"`, a
  `ldap` relation exists, and `expose_ldap_ingress` is disabled
- **THEN** `LdapProvider.update_relations_app_data()` is called for that relation
  ID with `urls` set to the in-cluster cleartext endpoint

#### Scenario: No LDAPS endpoint is advertised without Traefik
- **WHEN** `ldaps_enabled` is `False`
- **THEN** `ldaps_urls` is an empty list, because no certificate is ever
  provisioned to the container and there is no LDAPS listener to point at

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

