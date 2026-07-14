## 1. Charm Configuration & Parsing

- [x] 1.1 Add the `ingress_domain` configuration option under options in `charmcraft.yaml`.
- [x] 1.2 Update `src/configs.py` to parse, validate, and expose `ingress_domain` in the `CharmConfig` wrapper class.

## 2. Dynamic Route Rendering

- [x] 2.1 Modify `templates/traefik-route.json.j2` to accept and use a dynamic `{{ rule }}` parameter for the router's rule attribute.
- [x] 2.2 Update the dynamic route rendering logic in `src/services.py` to calculate the appropriate `HostSNI` rule string based on `config.ingress_domain` and pass it to the Jinja rendering call.

## 3. Documentation & Verification

- [x] 3.1 Add a detailed section to `README.md` containing instructions on how administrators can deploy multiple outposts and configure subdomains using `traefik-k8s` with `self-signed-certificates` / Vault.
- [x] 3.2 Update unit tests in `tests/unit/test_charm.py` to verify that `HostSNI(<domain>)` is correctly written to the relation databag when `ingress_domain` is set, and falls back to `HostSNI(*)` when unset.
