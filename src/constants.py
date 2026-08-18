# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants."""

WORKLOAD_CONTAINER = "authentik-ldap"
SERVICE_NAME = "authentik-ldap"
COMMAND = "/ldap"
# Port served by the outpost process inside the workload container. This is
# cleartext LDAP and is the only listener the container actually starts.
LDAP_PORT = 3389

# Traefik entrypoint ports. Nothing inside the container listens on these:
# Traefik terminates LDAPS on 636 and forwards cleartext to LDAP_PORT, and
# exposes cleartext 389 only when expose_ldap_ingress is enabled. Upstream
# authentik would serve LDAPS on 6636, but the charm never provisions the
# outpost with a certificate, so that listener is never started.
EXTERNAL_LDAP_PORT = 389
EXTERNAL_LDAPS_PORT = 636

# Prometheus scrapes this pod-to-pod via the published pod IP. It is
# deliberately never opened on the unit: doing so would expose unauthenticated
# metrics through the Kubernetes Service.
METRICS_PORT = 9300

SERVER_INFO_RELATION = "authentik-server-info"
LDAP_RELATION = "ldap"
TRAEFIK_ROUTE_RELATION = "traefik-route"
PEER_RELATION = "authentik-ldap-peers"
LOGGING_RELATION = "logging"
METRICS_ENDPOINT_RELATION = "metrics-endpoint"
GRAFANA_DASHBOARD_RELATION = "grafana-dashboard"
TRACING_RELATION = "tracing"
PEBBLE_READY_CHECK_NAME = "ready"

BASE_DN = "DC=ldap,DC=goauthentik,DC=io"
BIND_DN = "cn=akadmin,ou=users,DC=ldap,DC=goauthentik,DC=io"

AUTHENTIK_INSECURE = "true"
