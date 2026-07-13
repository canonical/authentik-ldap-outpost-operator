# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants."""

WORKLOAD_CONTAINER = "authentik-ldap"
SERVICE_NAME = "authentik-ldap"
COMMAND = "/ldap"
LDAP_PORT = 3389
LDAPS_PORT = 636
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
