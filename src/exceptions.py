# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Custom exception hierarchy."""


class CharmError(Exception):
    """Base exception for charm errors."""

    pass


class PebbleError(CharmError):
    """Raised when Pebble operations fail."""

    pass
