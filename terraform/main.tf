# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

/**
 * # Terraform module for the authentik-ldap-outpost charm
 *
 * This is a Terraform module facilitating the deployment of the authentik-ldap-outpost
 * charm using the Juju Terraform provider.
 */

resource "juju_application" "application" {
  name        = var.app_name
  model_uuid  = var.model_uuid
  trust       = true
  config      = var.config
  constraints = var.constraints
  resources   = var.resources
  units       = var.units

  charm {
    name     = "authentik-ldap-outpost"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }
}

resource "juju_offer" "ldap" {
  name             = "ldap"
  model_uuid       = var.model_uuid
  application_name = juju_application.application.name
  endpoints        = ["ldap"]
}

