"""
NHL API Client singleton instance.

This module provides a singleton instance of the NHL API client
for use throughout the application.
"""

import logging

from nhl_api.client import NHLAPIClient
from utils import args

logger = logging.getLogger("scoreboard")

# Singleton instance (initialized on first access)
_client = None


def _get_client():
    """
    Lazy initialization of the NHL API client.

    This ensures the client is created after logging is properly configured,
    allowing debug logs to be captured.
    """
    global _client

    if _client is None:
        # Determine SSL verification setting (invert the no-verify flag)
        ssl_verify = not args().nhl_no_ssl_verify

        logger.debug("Initializing NHL API client")
        logger.debug(f"Timeout: {args().nhl_timeout}s, SSL Verify: {ssl_verify}")

        # Create singleton client instance
        _client = NHLAPIClient(
            timeout=args().nhl_timeout,
            ssl_verify=ssl_verify
        )

    return _client


class _ClientProxy:
    """
    Proxy class that forwards all attribute access to the lazily-initialized client.

    This allows the module to be imported without creating the client immediately.
    """
    def __getattr__(self, name):
        return getattr(_get_client(), name)


# Export the proxy as 'client' - it will lazily initialize on first use
client = _ClientProxy()
