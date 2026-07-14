# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "The Juju application name"
  value       = juju_application.application.name
}

output "application" {
  description = "The deployed juju_application resource"
  value       = juju_application.application
}

output "requires" {
  description = "The Juju integrations that the charm requires"
  value = {
    logging               = "logging"
    tracing               = "tracing"
    authentik-server-info = "authentik-server-info"
    traefik-route         = "traefik-route"
  }
}

output "provides" {
  description = "The Juju integrations that the charm provides"
  value = {
    metrics-endpoint  = "metrics-endpoint"
    grafana-dashboard = "grafana-dashboard"
    ldap              = "ldap"
  }
}
