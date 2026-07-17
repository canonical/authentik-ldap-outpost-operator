# Changelog

## 1.0.0 (2026-07-17)


### Features

* expose plain LDAP ingress option via Traefik ([9f1d79b](https://github.com/canonical/authentik-ldap-outpost-operator/commit/9f1d79b08e1c48b3a4ae4343a9fabb9e31926b98))
* expose plain LDAP ingress option via Traefik ([#38](https://github.com/canonical/authentik-ldap-outpost-operator/issues/38)) ([5111d22](https://github.com/canonical/authentik-ldap-outpost-operator/commit/5111d2259e14f18240be6303094230f4829ffba3))
* **ingress:** add support for custom ingress domain and dynamic SNI routing ([f823d4d](https://github.com/canonical/authentik-ldap-outpost-operator/commit/f823d4d67891a497c27979208976e9f452af0683))
* **libs:** add and update Juju libraries for observability and server integration ([6170e8b](https://github.com/canonical/authentik-ldap-outpost-operator/commit/6170e8b407aadab71facd53f2145be17d9b78113))
* **proxy:** enable Proxy Protocol v2 and dynamic trusted proxy CIDR discovery ([ff8bb03](https://github.com/canonical/authentik-ldap-outpost-operator/commit/ff8bb037521977ee9536225e1dcfc9d425e33d68))
* support arm64 ([3fc10e8](https://github.com/canonical/authentik-ldap-outpost-operator/commit/3fc10e8bf0209ba79aa814f4fa6e44a561342d17))
* support arm64 ([#15](https://github.com/canonical/authentik-ldap-outpost-operator/issues/15)) ([552a96f](https://github.com/canonical/authentik-ldap-outpost-operator/commit/552a96f1d52fe35d6acf087599efa857e934e5a1))


### Bug Fixes

* check is_ready in TraefikRouteIntegration.ldaps_enabled ([7d87c20](https://github.com/canonical/authentik-ldap-outpost-operator/commit/7d87c2019866a03ec23e65b0381f843dd1096188))
* check is_ready in TraefikRouteIntegration.ldaps_enabled ([#39](https://github.com/canonical/authentik-ldap-outpost-operator/issues/39)) ([7efe52f](https://github.com/canonical/authentik-ldap-outpost-operator/commit/7efe52f9376d46b223fc9a0c301c2be162f34c9d))
* define env vars ([8e49c2e](https://github.com/canonical/authentik-ldap-outpost-operator/commit/8e49c2e3868d71556e1cc74406546c8863b22b7a))
* **deps:** update dependency cosl to ~=1.9.2 ([d0eb032](https://github.com/canonical/authentik-ldap-outpost-operator/commit/d0eb032430e8f59b82a6d951c2b34bba6dfe7428))
* **deps:** update dependency cosl to ~=1.9.2 ([#6](https://github.com/canonical/authentik-ldap-outpost-operator/issues/6)) ([4a7b5cf](https://github.com/canonical/authentik-ldap-outpost-operator/commit/4a7b5cf2663c2a30808bb921d2f7b1bdb50d6175))
* **deps:** update dependency lightkube to ~=0.22.0 ([f760b7f](https://github.com/canonical/authentik-ldap-outpost-operator/commit/f760b7f3a685d78f793d19abf66681719a0a3806))
* **deps:** update dependency lightkube to ~=0.22.0 ([#27](https://github.com/canonical/authentik-ldap-outpost-operator/issues/27)) ([8417437](https://github.com/canonical/authentik-ldap-outpost-operator/commit/84174378a76e3172022b0e947c4471d58b5b0e76))
* **deps:** update dependency requests to ~=2.33.0 [security] ([1dbd73a](https://github.com/canonical/authentik-ldap-outpost-operator/commit/1dbd73ad06e5aa512930f8a8396d17e5d27bae0a))
* **deps:** update dependency requests to ~=2.33.0 [security] ([#11](https://github.com/canonical/authentik-ldap-outpost-operator/issues/11)) ([9faeb3f](https://github.com/canonical/authentik-ldap-outpost-operator/commit/9faeb3fb153803a1c651f1ad868b2a13c148fd93))
* **deps:** update dependency requests to ~=2.34.2 ([351c0c8](https://github.com/canonical/authentik-ldap-outpost-operator/commit/351c0c81311ec9a4d6e53dbfe5e2544f2e78e463))
* **deps:** update dependency requests to ~=2.34.2 ([#16](https://github.com/canonical/authentik-ldap-outpost-operator/issues/16)) ([fffc482](https://github.com/canonical/authentik-ldap-outpost-operator/commit/fffc482b906d9d34b6ae8340a8640fb78ea283b5))
* **services:** update executable subcommand to --version and parse output ([ab9ed5c](https://github.com/canonical/authentik-ldap-outpost-operator/commit/ab9ed5cc493a6c09af6b9cb062143636fb4b8cfb))
* **test:** lock server/worker to stable revisions to prevent upstream breakages ([a23acf6](https://github.com/canonical/authentik-ldap-outpost-operator/commit/a23acf632a761450609337ebb42b9f1ae0d40267))


### Reverts

* **test:** remove revision pinning for server and worker ([e665f46](https://github.com/canonical/authentik-ldap-outpost-operator/commit/e665f46165570c5845d4d944867ba81d67ac0d8d))
