# Changelog

## [1.3.1](https://github.com/canonical/authentik-ldap-outpost-operator/compare/v1.3.0...v1.3.1) (2026-08-21)


### Bug Fixes

* **terraform:** declare a minimum Juju provider version ([#72](https://github.com/canonical/authentik-ldap-outpost-operator/issues/72)) ([c7dcbe3](https://github.com/canonical/authentik-ldap-outpost-operator/commit/c7dcbe37218434b2181aa00ccd3d1253fb46efac))
* **terraform:** declare a minimum Juju provider version, not a pessimistic one ([510a01d](https://github.com/canonical/authentik-ldap-outpost-operator/commit/510a01dc6939accbb5562844750e8b286052a130))

## [1.3.0](https://github.com/canonical/authentik-ldap-outpost-operator/compare/v1.2.1...v1.3.0) (2026-08-18)


### Features

* add working COS alert rules and dashboard ([4a568d3](https://github.com/canonical/authentik-ldap-outpost-operator/commit/4a568d3c332739fc7030a2aecc29eff81bb0709f))
* add working COS alert rules and dashboard ([#67](https://github.com/canonical/authentik-ldap-outpost-operator/issues/67)) ([90b64c8](https://github.com/canonical/authentik-ldap-outpost-operator/commit/90b64c8add6245c1ecc815b4069f1ee59b2f6e52))


### Bug Fixes

* cache LDAP role membership to cut redundant Authentik API calls ([ce98438](https://github.com/canonical/authentik-ldap-outpost-operator/commit/ce984382289d10ebe10c337637f4e88283695e67))
* **deps:** update dependency lightkube to v1 ([a27ad3f](https://github.com/canonical/authentik-ldap-outpost-operator/commit/a27ad3fa9db7df6a04f13f6d5d8e5f3577ce4003))
* **deps:** update dependency lightkube to v1 ([#65](https://github.com/canonical/authentik-ldap-outpost-operator/issues/65)) ([7621622](https://github.com/canonical/authentik-ldap-outpost-operator/commit/762162259d2d530f36ed0b6038fad1177bfa9916))
* **deps:** update dependency lightkube-models to ~=1.36.3.8 ([dd30649](https://github.com/canonical/authentik-ldap-outpost-operator/commit/dd30649ead917a98208d364e3145d3ea414c7874))
* **deps:** update dependency lightkube-models to ~=1.36.3.8 ([#58](https://github.com/canonical/authentik-ldap-outpost-operator/issues/58)) ([09be2ef](https://github.com/canonical/authentik-ldap-outpost-operator/commit/09be2ef33db714ea32bcf6edbd5210e65490f221))
* **ldap:** advertise only reachable LDAP and LDAPS endpoints ([6e661c5](https://github.com/canonical/authentik-ldap-outpost-operator/commit/6e661c501869f476a3a3d0ab80ca964d07ae5099))
* make LDAP bind-flow provisioning race-safe and idempotent ([97eed1e](https://github.com/canonical/authentik-ldap-outpost-operator/commit/97eed1ed29913e5973e4424fa2c04d1fecdf49a1))
* reconcile on upgrade-charm ([f841ff7](https://github.com/canonical/authentik-ldap-outpost-operator/commit/f841ff75072fe462dd1a7e0dcce9d8efcb2af181))
* stop verifying the outpost token secret in-hook ([b405b7a](https://github.com/canonical/authentik-ldap-outpost-operator/commit/b405b7ac0c1ca78461178731352e721a3e466fa5))
* stop verifying the outpost token secret in-hook ([#69](https://github.com/canonical/authentik-ldap-outpost-operator/issues/69)) ([5e74b4f](https://github.com/canonical/authentik-ldap-outpost-operator/commit/5e74b4f1ace170630c3db79c58b06f25430b69fc))
* surface Authentik API health in status and cache role membership ([#56](https://github.com/canonical/authentik-ldap-outpost-operator/issues/56)) ([f22c2bb](https://github.com/canonical/authentik-ldap-outpost-operator/commit/f22c2bbcc2a485feda0f557b26eaf58155f41d3c))

## [1.2.1](https://github.com/canonical/authentik-ldap-outpost-operator/compare/v1.2.0...v1.2.1) (2026-07-24)


### Bug Fixes

* outpost resilience and API efficiency ([eae6480](https://github.com/canonical/authentik-ldap-outpost-operator/commit/eae64800f22b87bde20b19cb67f2e40986369359))
* outpost resilience and API efficiency ([#51](https://github.com/canonical/authentik-ldap-outpost-operator/issues/51)) ([a1d4465](https://github.com/canonical/authentik-ldap-outpost-operator/commit/a1d44659f2b59b83a91491be2cd00c71513570d9))
* outpost resilience, TLS-verification knob, and API efficiency ([a004681](https://github.com/canonical/authentik-ldap-outpost-operator/commit/a0046813830d64b04ee6f532232f53813ae6eeb0))

## [1.2.0](https://github.com/canonical/authentik-ldap-outpost-operator/compare/v1.1.0...v1.2.0) (2026-07-23)


### Features

* adopt LDAP RBAC, deployment-unique resources, and honor requirer identity ([38e02ea](https://github.com/canonical/authentik-ldap-outpost-operator/commit/38e02eaae0f22bdb7d8cd513955ffd9e5f929e62))

## [1.1.0](https://github.com/canonical/authentik-ldap-outpost-operator/compare/v1.0.0...v1.1.0) (2026-07-21)


### Features

* **terraform:** add ldap juju offer ([#41](https://github.com/canonical/authentik-ldap-outpost-operator/issues/41)) ([c262166](https://github.com/canonical/authentik-ldap-outpost-operator/commit/c2621666fc7e9cfefb36e83a6869c0e59520d239))


### Bug Fixes

* add ldap juju offer ([f1052f0](https://github.com/canonical/authentik-ldap-outpost-operator/commit/f1052f02eb7e23763d70fe5ee1c79ec1260dff99))
* create and assign standard entryDN property mapping for LDAP Provider ([#44](https://github.com/canonical/authentik-ldap-outpost-operator/issues/44)) ([1fc8604](https://github.com/canonical/authentik-ldap-outpost-operator/commit/1fc8604ac49d19560b6d04d978d872978fafd5fc))
* **deps:** update dependency cosl to ~=1.10.1 ([d83cabc](https://github.com/canonical/authentik-ldap-outpost-operator/commit/d83cabcbbe543da72e80c0bc255e61100c608e98))
* **deps:** update dependency cosl to ~=1.10.1 ([#32](https://github.com/canonical/authentik-ldap-outpost-operator/issues/32)) ([fb54e4c](https://github.com/canonical/authentik-ldap-outpost-operator/commit/fb54e4c2c3844cbc6766528ee054a0bf8955dcb8))
* implement search group validation, caching, and existing user sync ([0494c62](https://github.com/canonical/authentik-ldap-outpost-operator/commit/0494c623424c71c24dc3c66444b884fca05a9ea9))
* implement search group validation, caching, and existing user sync ([#42](https://github.com/canonical/authentik-ldap-outpost-operator/issues/42)) ([0a12994](https://github.com/canonical/authentik-ldap-outpost-operator/commit/0a12994ce2ca8accd0a1329cb39ad82daad0a279))
* support diverse LDAP clients by automatically creating and assigning default property mappings ([e0ac3f6](https://github.com/canonical/authentik-ldap-outpost-operator/commit/e0ac3f692f65c8cf7b8848ff0169312bac6b9206))

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
