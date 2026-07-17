## 1. Configuration & Declarative Package Metadata

- [x] 1.1 Add `expose_ldap_ingress` config option with type `boolean` and default `false` to `charmcraft.yaml`
- [x] 1.2 Support parsing, storing, and exposing `expose_ldap_ingress` in `src/configs.py`
- [x] 1.3 Add conditional check for `expose_ldap_ingress` in `templates/traefik-route.json.j2` to conditionally render the cleartext LDAP TCP router

## 2. Integration & Route Submission Logic

- [x] 2.1 Update `TraefikRouteIntegration.submit_route` in `src/integrations.py` to pass the `expose_ldap_ingress` configuration value to the route template rendering context
- [x] 2.2 Update `TraefikRouteIntegration.submit_route` in `src/integrations.py` to add the `ldap` entrypoint on port `389` to `static_config` when `expose_ldap_ingress` is enabled

## 3. Testing & Validation

- [x] 3.1 Update unit tests in `tests/unit/test_integrations.py` to verify that dynamic/static route configurations submitted to Traefik include or exclude the plain LDAP route depending on the configuration value of `expose_ldap_ingress`
- [x] 3.2 Update unit tests in `tests/unit/test_charm.py` to verify overall charm behaviour and ensure high-level config-changed scenarios trigger route updates properly
- [x] 3.3 Run unit tests via `tox -e unit` and format/lint check via `tox -e fmt && tox -e lint` to verify correct formatting and complete coverage
