# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""CLI wrapper for workload interactions via Pebble exec."""

import logging
from typing import Optional

from ops import Container
from ops.pebble import ExecError

logger = logging.getLogger(__name__)


class CLI:
    """Wrapper for CLI interactions with the workload container."""

    def __init__(self, container: Container):
        self._container = container

    def exec(
        self,
        command: list[str],
        timeout: Optional[float] = None,
    ) -> tuple[int, str, str]:
        """Execute a command in the container.

        Args:
            command: Command and arguments as list.
            timeout: Optional timeout in seconds.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        try:
            process = self._container.exec(
                command,
                timeout=timeout,
            )
            stdout, stderr = process.wait_output()
            return process.exit_code, stdout, stderr
        except ExecError as e:
            logger.exception("Failed to execute %s", command)
            return e.exit_code, "", str(e)
        except Exception as e:
            logger.exception("Unexpected error executing %s", command)
            return -1, "", str(e)
