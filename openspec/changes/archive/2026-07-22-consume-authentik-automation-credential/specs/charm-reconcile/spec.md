## ADDED Requirements

### Requirement: Outpost authenticates with the api-token from server-info

The outpost charm SHALL authenticate to the Authentik REST API using the API token published over `authentik-server-info`, resolving it from the library's canonical `api-token` key, and SHALL NOT require a bootstrap password.

#### Scenario: Server publishes the canonical token
- **WHEN** the server-info token secret contains an `api-token` value
- **THEN** the outpost uses that value for every Authentik API client

#### Scenario: Readiness without bootstrap password
- **WHEN** server-info provides a host and token
- **THEN** the outpost resolves server info and reconciles without any bootstrap password
