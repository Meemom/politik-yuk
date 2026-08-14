import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlparse

from app.ingestion.models import IngestionError, IngestionFailureKind

Resolver = Callable[[str], list[str]]


def default_resolver(hostname: str) -> list[str]:
    addresses = socket.getaddrinfo(hostname, None)
    return list({str(address[4][0]) for address in addresses})


def validate_url_for_ingestion(url: str, *, resolver: Resolver = default_resolver) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise IngestionError(
            "Only http and https URLs can be ingested.",
            kind=IngestionFailureKind.INVALID_URL,
        )
    if parsed.username or parsed.password:
        raise IngestionError(
            "URLs with embedded credentials cannot be ingested.",
            kind=IngestionFailureKind.INVALID_URL,
        )
    if not parsed.hostname:
        raise IngestionError("URL must include a hostname.", kind=IngestionFailureKind.INVALID_URL)

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost", "0.0.0.0"} or hostname.endswith(".localhost"):
        raise IngestionError(
            "Localhost URLs cannot be ingested.",
            kind=IngestionFailureKind.INVALID_URL,
        )

    for address in resolver(hostname):
        if _is_blocked_address(address):
            raise IngestionError(
                "URL resolves to a private or reserved network address.",
                kind=IngestionFailureKind.INVALID_URL,
            )

    return parsed.geturl()


def _is_blocked_address(address: str) -> bool:
    ip_address = ipaddress.ip_address(address)
    return (
        ip_address.is_private
        or ip_address.is_loopback
        or ip_address.is_link_local
        or ip_address.is_multicast
        or ip_address.is_reserved
        or ip_address.is_unspecified
    )
