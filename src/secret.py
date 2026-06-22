# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Juju secrets management."""

import logging
from typing import Optional

from ops.charm import CharmBase
from ops.model import Model, Secret

logger = logging.getLogger(__name__)


class Secrets:
    """Juju secrets management helper."""

    def __init__(self, model: Model):
        self._model = model

    def get_secret(self, id: str | None = None, label: str | None = None) -> Optional[Secret]:
        """Get a secret by ID or label.

        Args:
            id: Secret ID.
            label: Secret label.

        Returns:
            Secret if found, None otherwise.
        """
        try:
            if id:
                return self._model.get_secret(id=id)
            if label:
                return self._model.get_secret(label=label)
        except Exception:
            return None
        return None

    def get_secret_content(self, secret: Secret) -> dict[str, str]:
        """Get secret content safely.

        Args:
            secret: The secret to read.

        Returns:
            Dict of secret content or empty dict on error.
        """
        try:
            return secret.get_content()
        except Exception:
            return {}


class ServerInfoSecrets:
    """Secrets handling for authentik-server-info relation."""

    def __init__(self, charm: CharmBase):
        self._charm = charm
        self._secrets = Secrets(charm.model)

    def get_bootstrap_password(self, secret_id: str) -> Optional[str]:
        """Get bootstrap password from secret ID.

        Args:
            secret_id: Juju secret ID.

        Returns:
            Password string or None.
        """
        secret = self._secrets.get_secret(id=secret_id)
        if not secret:
            return None
        content = self._secrets.get_secret_content(secret)
        return content.get("bootstrap-password")

    def get_bootstrap_token(self, secret_id: str) -> Optional[str]:
        """Get bootstrap token from secret ID.

        Args:
            secret_id: Juju secret ID.

        Returns:
            Token string or None.
        """
        secret = self._secrets.get_secret(id=secret_id)
        if not secret:
            return None
        content = self._secrets.get_secret_content(secret)
        return content.get("bootstrap-token")
