"""Small helpers for reporting DNS failures from external AI services."""

import logging
import socket


logger = logging.getLogger(__name__)


class ExternalDnsError(RuntimeError):
    """An external provider hostname could not be resolved."""


def _is_dns_error(exc: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, socket.gaierror) or "getaddrinfo failed" in str(current).lower():
            return True
        current = current.__cause__ or current.__context__
    return False


def external_call(host: str, operation: str, callback):
    """Run a provider call and preserve its error while adding DNS context."""
    try:
        return callback()
    except Exception as exc:
        if not _is_dns_error(exc):
            raise
        message = f"DNS resolution failed for {host} while {operation}."
        logger.error(message)
        raise ExternalDnsError(message) from exc