# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants."""

WORKLOAD_CONTAINER = "authentik-ldap"
SERVICE_NAME = "authentik-ldap"
COMMAND = "/ldap"
LDAP_PORT = 3389
LDAPS_PORT = 6636

SERVER_INFO_RELATION = "authentik-server-info"
LDAP_RELATION = "ldap"
INGRESS_RELATION = "ingress"
LDAPS_INGRESS_RELATION = "ldaps-ingress"
PEER_RELATION = "authentik-ldap-peers"

BASE_DN = "DC=ldap,DC=goauthentik,DC=io"
BIND_DN = "cn=akadmin,ou=users,DC=ldap,DC=goauthentik,DC=io"

AUTHENTIK_INSECURE = "true"
