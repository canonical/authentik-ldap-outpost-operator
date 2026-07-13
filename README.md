# Charmed Authentik LDAP Outpost

[![CharmHub Badge](https://charmhub.io/authentik-ldap-outpost/badge.svg)](https://charmhub.io/authentik-ldap-outpost)
[![Juju](https://img.shields.io/badge/Juju%20-3.0+-%23E95420)](https://github.com/juju/juju)
[![License](https://img.shields.io/github/license/canonical/authentik-ldap-outpost-operator?label=License)](https://github.com/canonical/authentik-ldap-outpost-operator/blob/main/LICENSE)
[![Continuous Integration Status](https://github.com/canonical/authentik-ldap-outpost-operator/actions/workflows/on_push.yaml/badge.svg?branch=main)](https://github.com/canonical/authentik-ldap-outpost-operator/actions?query=branch%3Amain)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

## Description

The **Charmed Authentik LDAP Outpost** is a lightweight, zero-configuration Python operator designed to run on Kubernetes. It orchestrates the deployment and configuration of the Authentik LDAP Outpost, which acts as a secure, high-performance gateway exposing Authentik's centralized directory to external LDAP client applications.

By combining the simplicity of Juju model-driven architecture with Authentik's enterprise identity platform, the charm automates directory provisioning, lifecycle management, and security boundary isolation.

---

## Technical Architecture & Security Design

This operator incorporates advanced directory management practices that significantly enhance security and efficiency:

### 1. Dynamic, Relation-Driven Service Accounts
Rather than sharing a single global administrator credential across all client applications (which represents a critical security risk), this charm implements isolated credentials:
* **Zero Credential Sharing**: On a `relation-joined` event with a consuming client (such as Nextcloud or GitLab), the charm leader dynamically calls the Authentik REST API to provision a unique, isolated Service Account user (`ldap-client-<charm-name>-<relation-id>`) with a strong, randomly generated password.
* **Access Revocation**: When the relation is severed (`relation-broken`), the corresponding Service Account user is automatically deleted from the Authentik database, preventing credential rot and keeping the directory clean.
* **Resource Efficiency**: Only **one** Kubernetes pod for the Outpost is spawned in the Juju model, serving all integrated downstream LDAP clients concurrently via their respective secure accounts.

### 2. Automated Non-Interactive Bind Flow Resolution
Standard LDAP bind operations are non-interactive. The default Authentik authentication flow includes interactive multi-factor authentication (MFA) stages, which would ordinarily block command-line or machine-level LDAP binds.
* To address this, the charm automatically provisions a dedicated, non-interactive **LDAP Bind Flow** (`default-ldap-bind-flow`) containing only the `identification`, `password`, and `login` stages.
* The charm automatically configures this flow as the `authentication_flow` of the LDAP Provider, allowing clients to authenticate seamlessly and securely while protecting other enterprise flows.

---

## Supported Relations

| Relation Name | Role | Interface | Description |
|:---|:---|:---|:---|
| `authentik-server-info` | Requirer | `authentik-server-info` | Receives endpoints and bootstrap credentials from the core Authentik Server charm. |
| `ldap` | Provider | `ldap` | Exposes LDAP service details (URLs, Base DN, Bind DN, and password) to directory consumer applications. |

---

## Declarative Juju Configurations

The following configurations can be declared to govern the global characteristics of the LDAP directory:

| Juju Config Key | Type | Default | Description |
|:---|:---|:---|:---|
| `base_dn` | string | `dc=ldap,dc=goauthentik,dc=io` | The Base DN under which directory objects are made accessible. |
| `search_group` | string | `authentik Admingroup` | The name or UUID of the group whose members can perform directory queries. |
| `search_mode` | string | `direct` | Access mode for searches: `direct` (live server queries) or `cached` (in-memory caching). |
| `bind_mode` | string | `direct` | Access mode for binds: `direct` or `cached`. |
| `mfa_support` | boolean | `false` | Enable/disable multi-factor authentication support via password-appending. |
| `ingress_domain` | string | `""` | The custom domain name to use for the external ingress route (e.g., `outpost.example.com`). If unset, the route rule defaults to `HostSNI(*)` to match all incoming TLS traffic on port 636. |


---

## Getting Started

### 1. Deployment
Deploy a complete, integrated Authentik identity stack along with an LDAP client (`glauth-k8s`):

```bash
# Deploy PostgreSQL database and Authentik Core services
juju deploy postgresql-k8s --channel 14/stable
juju deploy authentik-server --channel edge
juju deploy authentik-worker --channel edge

# Deploy the LDAP Outpost
juju deploy authentik-ldap-outpost --channel edge

# Relate Core services
juju relate authentik-server postgresql-k8s
juju relate authentik-worker authentik-server
juju relate authentik-ldap-outpost authentik-server

# Deploy and integrate an LDAP client app
juju deploy glauth-k8s --channel edge
juju relate glauth-k8s:ldap-client authentik-ldap-outpost:ldap
```

### 2. E2E Query Verification
To verify the end-to-end directory functionality using `ldapsearch`, retrieve the dynamic credentials from the consumer databag:

```bash
# Show dynamic client credentials
juju show-unit glauth-k8s/0 --endpoint ldap-client
```

Perform an `ldapsearch` query using the outputted IP, Bind DN, and password:
```bash
ldapsearch -x -H ldap://<outpost-ip>:3389 \
  -D "cn=ldap-client-authentik-ldap-outpost-<id>,ou=users,dc=ldap,dc=goauthentik,dc=io" \
  -w "<password>" \
  -b "dc=ldap,dc=goauthentik,dc=io"
```

A successful setup will output `result: 0 Success` along with your mapped directory objects.

### 3. Secure Multi-Outpost SNI Routing

When deploying multiple independent outposts that share the same Traefik Ingress controller, you must configure a distinct `ingress_domain` for each outpost to leverage SNI multiplexing on port `636`. Without this, the catch-all `HostSNI(*)` rule creates routing conflicts.

To deploy two outposts with SNI-based multiplexing:

1. **Configure distinct ingress subdomains** for each outpost:
   ```bash
   juju config outpost-a ingress_domain="outpost-a.identity.example.com"
   juju config outpost-b ingress_domain="outpost-b.identity.example.com"
   ```

2. **Relate both outposts to Traefik**:
   ```bash
   juju relate outpost-a:traefik-route traefik-k8s:traefik-route
   juju relate outpost-b:traefik-route traefik-k8s:traefik-route
   ```

In this setup, Traefik's relation handlers automatically detect the custom domains and dynamically obtain distinct secure certificates for each subdomain from the related certificate provider (e.g. `self-signed-certificates` or `vault-k8s`).

---


---

## Security

Please see [SECURITY.md](https://github.com/canonical/authentik-ldap-outpost-operator/blob/main/SECURITY.md) for guidelines on reporting security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this charm, and [CONTRIBUTING.md](https://github.com/canonical/authentik-ldap-outpost-operator/blob/main/CONTRIBUTING.md) for developer guidance.

## License

The Charmed Authentik LDAP Outpost is free software, distributed under the Apache Software License, version 2.0. See [LICENSE](https://github.com/canonical/authentik-ldap-outpost-operator/blob/main/LICENSE) for more information.
