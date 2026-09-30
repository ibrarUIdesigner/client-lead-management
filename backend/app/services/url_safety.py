import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit

from app.core.errors import AppError

Resolver = Callable[[str], list[str]]

BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.google.com",
    "instance-data",
}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain")
MAX_URL_LENGTH = 2000


def assert_public_http_url(url: str, *, resolve: Resolver | None = None) -> str:
    """Return a normalized http(s) URL that is safe for the server to request."""
    if not isinstance(url, str) or not url.strip() or len(url) > MAX_URL_LENGTH:
        _blocked()

    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or parsed.username or parsed.password:
        _blocked()
    host = parsed.hostname
    if host is None or parsed.port == 0:
        _blocked()

    addresses = _addresses(host, resolve or resolve_host)
    if not addresses or any(ip_is_blocked(address) for address in addresses):
        _blocked()

    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, parsed.query, ""))


def resolve_host(host: str) -> list[str]:
    if _is_ip(host):
        return [host]
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(5)
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise AppError(
            code="URL_UNREACHABLE",
            message="The website address could not be found.",
            status_code=400,
        ) from None
    finally:
        socket.setdefaulttimeout(previous)
    return [str(info[4][0]) for info in infos]


def ip_is_blocked(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.split("%", maxsplit=1)[0])
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def host_is_blocked(host: str) -> bool:
    name = host.lower().rstrip(".")
    if "0x" in name:
        return True
    return name in BLOCKED_HOSTS or name.endswith(BLOCKED_SUFFIXES)


def _addresses(host: str, resolve: Resolver) -> list[str]:
    if host_is_blocked(host):
        _blocked()
    literal = _literal_ip(host)
    if literal is not None:
        return [literal]
    try:
        return resolve(host)
    except AppError:
        raise
    except OSError:
        raise AppError(
            code="URL_UNREACHABLE",
            message="The website address could not be found.",
            status_code=400,
        ) from None


def _literal_ip(host: str) -> str | None:
    if host.isdigit():
        try:
            return str(ipaddress.IPv4Address(int(host)))
        except (ValueError, ipaddress.AddressValueError):
            _blocked()
    if host.count(".") == 3 and all(part.isdigit() for part in host.split(".")):
        parts = host.split(".")
        if any(len(part) > 1 and part.startswith("0") for part in parts):
            _blocked()
    if _is_ip(host):
        return host
    return None


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.split("%", maxsplit=1)[0])
    except ValueError:
        return False
    return True


def _blocked() -> None:
    raise AppError(
        code="URL_BLOCKED",
        message="That website address cannot be analyzed.",
        status_code=400,
    )
