# conftest Specification

## Purpose
TBD - created by archiving change authentik-ldap-tests. Update Purpose after archive.
## Requirements
### Requirement: create_state factory
`tests/unit/conftest.py` SHALL export a module-level function `create_state()` that returns a complete `ops.testing.State` with sensible defaults. It MUST accept the keyword arguments: `leader` (bool, default `True`), `secrets` (list, default `[]`), `relations` (list, default `[]`), `containers` (list, default container with `can_connect=True`), `config` (dict, default `{}`), `can_connect` (bool, default `True`). When `containers` is not provided the default container MUST be `testing.Container("authentik-ldap", can_connect=can_connect)`.

#### Scenario: Minimal call returns leader state with connected container
- **WHEN** `create_state()` is called with no arguments
- **THEN** the returned `State` has `leader=True`
- **THEN** the returned `State` has one container named `"authentik-ldap"` with `can_connect=True`

#### Scenario: can_connect=False propagates to default container
- **WHEN** `create_state(can_connect=False)` is called
- **THEN** the default container has `can_connect=False`

#### Scenario: Custom relations are passed through
- **WHEN** `create_state(relations=[r])` is called with a list containing one relation
- **THEN** the returned `State` has exactly that one relation

### Requirement: mocked_k8s_resource_patch autouse fixture
`conftest.py` SHALL provide a `mocked_k8s_resource_patch` pytest fixture marked `autouse=True`. The fixture MUST patch `charm.KubernetesComputeResourcesPatch` so that no Kubernetes API call is made during charm instantiation in any unit test.

#### Scenario: No Kubernetes API calls during charm init
- **WHEN** any unit test instantiates `AuthentikLdapCharm` via Scenario
- **THEN** no real Kubernetes API call is made

### Requirement: context fixture
`conftest.py` SHALL provide a `context` pytest fixture that returns `testing.Context(AuthentikLdapCharm)`.

#### Scenario: context fixture returns correct type
- **WHEN** the `context` fixture is injected into a test
- **THEN** the returned object is a `testing.Context` wrapping `AuthentikLdapCharm`

### Requirement: container fixture
`conftest.py` SHALL provide a `container` pytest fixture that returns `testing.Container("authentik-ldap", can_connect=True)`.

#### Scenario: container fixture returns connected container
- **WHEN** the `container` fixture is injected into a test
- **THEN** the returned `Container` has name `"authentik-ldap"` and `can_connect=True`

### Requirement: server_info_relation fixture
`conftest.py` SHALL provide a `server_info_relation` pytest fixture that returns a `testing.Relation` for the `"authentik-server-info"` endpoint. The relation MUST populate `remote_app_data` with keys `authentik_host`, `bootstrap_token_secret_id`, and `bootstrap_password_secret_id`.

#### Scenario: server_info_relation fixture provides required remote app data
- **WHEN** the `server_info_relation` fixture is injected into a test
- **THEN** the relation endpoint is `"authentik-server-info"`
- **THEN** `remote_app_data["authentik_host"]` equals `"http://authentik:9000"`
- **THEN** `remote_app_data["bootstrap_token_secret_id"]` equals `"secret:xyz"`
- **THEN** `remote_app_data["bootstrap_password_secret_id"]` equals `"secret:abc"`

