# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Custom exception hierarchy."""


class CharmError(Exception):
    """Base exception for charm errors."""

    pass


class PebbleError(CharmError):
    """Raised when Pebble operations fail."""

    pass


class AuthentikPermanentError(CharmError):
    """Raised when Authentik reconciliation cannot safely retry without operator action."""

    pass


class AuthentikMigrationError(AuthentikPermanentError):
    """Raised when an Authentik rename or ownership operation would be unsafe."""

    pass


class AuthentikAuthorizationError(AuthentikPermanentError):
    """Raised when managed Authentik authorization is not strictly object scoped."""

    pass
