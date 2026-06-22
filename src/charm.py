#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm the Authentik LDAP outpost application."""

import logging

import ops
from constants import (
    LDAP_RELATION,
    LDAPS_PORT,
    PEER_RELATION,
    SERVER_INFO_RELATION,
    WORKLOAD_CONTAINER,
)
from integrations import Integrations
from services import PebbleService

logger = logging.getLogger(__name__)


class AuthentikLdapCharm(ops.CharmBase):
    """Authentik LDAP Outpost Operator."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self._container = self.unit.get_container(WORKLOAD_CONTAINER)
        self._pebble_service = PebbleService(self._container)
        self._config = None
        self.integrations = Integrations(self)

        for event in [
            self.on.install,
            self.on.config_changed,
            self.on.authentik_ldap_pebble_ready,
            self.on[PEER_RELATION].relation_joined,
        ]:
            self.framework.observe(event, self._on_event)

        if self.integrations.server_info.events:
            self.framework.observe(
                self.integrations.server_info.events.info_changed,
                self._on_event,
            )
            self.framework.observe(
                self.integrations.server_info.events.info_removed,
                self._on_event,
            )
        else:
            self.framework.observe(
                self.on[SERVER_INFO_RELATION].relation_changed,
                self._on_event,
            )
            self.framework.observe(
                self.on[SERVER_INFO_RELATION].relation_broken,
                self._on_event,
            )

        if self.integrations.ingress.ldap_events:
            self.framework.observe(
                self.integrations.ingress.ldap_events.ready,
                self._on_event,
            )
        if self.integrations.ingress.ldaps_events:
            self.framework.observe(
                self.integrations.ingress.ldaps_events.ready,
                self._on_event,
            )

        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

    def _on_event(self, event: ops.EventBase) -> None:
        self._reconcile()

    def _reconcile(self) -> None:
        if not self._container.can_connect():
            return
        self._ensure_pebble_layer()
        self._ensure_ldap_provider()

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        if not self._container.can_connect():
            event.add_status(ops.WaitingStatus("waiting for pebble"))
            return
        if not self.integrations.server_info.is_ready():
            event.add_status(ops.BlockedStatus("missing authentik-server-info relation"))
            return
        event.add_status(ops.ActiveStatus())

    def _ensure_pebble_layer(self) -> None:
        env = self.integrations.server_info.build_env()
        if not env:
            return
        from services import AuthentikLdapWorkload

        layer = AuthentikLdapWorkload.build_layer(env)
        self._pebble_service.plan(layer)
        self._container.open_port("tcp", 3389)
        self._container.open_port("tcp", LDAPS_PORT)

    def _ensure_ldap_provider(self) -> None:
        if not self.integrations.server_info.is_ready():
            return
        if not self.model.get_relation(LDAP_RELATION):
            return
        password = self.integrations.server_info.get_bootstrap_password()
        if not password:
            return
        unit_address = Integrations.get_unit_address(self.model, LDAP_RELATION)
        self.integrations.ldap_provider.update_data(unit_address, password)


if __name__ == "__main__":
    ops.main(AuthentikLdapCharm)
