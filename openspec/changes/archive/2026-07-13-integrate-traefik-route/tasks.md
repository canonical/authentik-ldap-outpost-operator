## 1. Declarations and Configuration

- [x] 1.1 Declare the `traefik-route` relation interface inside `charmcraft.yaml`
- [x] 1.2 Update ports and relation name constants inside `src/constants.py`
- [x] 1.3 Create the Traefik route configuration template `templates/traefik-route.json.j2`

## 2. Ingress Integrations

- [x] 2.1 Implement the Traefik Route L4 integration helper and data structures inside `src/integrations.py`
- [x] 2.2 Register and handle `traefik-route` relation events within `src/charm.py` and configure the custom entrypoints during the reconciliation loop
- [x] 2.3 Dynamically manage and write `ldaps_enabled=true` and connection URIs inside the `ldap` relation databag inside `src/charm.py`

## 3. Verification and Testing

- [x] 3.1 Implement unit tests verifying `traefik-route` L4 relation configuration and dynamic `ldaps_enabled` databag updates inside `tests/unit/test_charm.py`
- [x] 3.2 Implement integration tests verifying secure TCP L4 routing and connection parameters with the `traefik-k8s` charm inside `tests/integration/test_charm.py`
