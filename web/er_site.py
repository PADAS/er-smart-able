"""One EarthRanger site as a load target: its host, and whether a token works there."""
import ipaddress
import re
from urllib.parse import urlparse

import httpx

_HOST = re.compile(r"^[a-z0-9.-]+$")


class TokenRejected(Exception):
    pass


class SiteUnreachable(Exception):
    pass


def normalize_host(url: str) -> str:
    """'https://Site.pamdas.org/api/v1.0/' -> 'site.pamdas.org'."""
    s = (url or "").strip()
    if "://" not in s:
        s = "https://" + s
    parsed = urlparse(s)
    try:
        has_port = parsed.port is not None
    except ValueError:
        has_port = True
    if has_port or parsed.username:
        raise ValueError("Enter just the site's host name, like site.pamdas.org")
    host = (parsed.hostname or "").lower()
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip or host == "localhost":
        raise ValueError("Enter the site's host name, like site.pamdas.org")
    if not host or not _HOST.match(host) or "." not in host:
        raise ValueError("Enter the site's host name, like site.pamdas.org")
    return host


def _transport():
    return None  # httpx's default; tests swap in a MockTransport


def check_token(host: str, token: str) -> str:
    """The username the token resolves to on the site."""
    try:
        with httpx.Client(transport=_transport(), timeout=15) as c:
            r = c.get(f"https://{host}/api/v1.0/user/me", headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise SiteUnreachable(f"could not reach {host}: {type(e).__name__}") from e
    if r.status_code in (401, 403):
        raise TokenRejected(f"{host} answered {r.status_code} {r.reason_phrase}")
    if r.status_code != 200:
        raise SiteUnreachable(f"{host} answered {r.status_code} {r.reason_phrase}")
    try:
        data = r.json().get("data") or {}
        return data.get("username") or data.get("email") or "?"
    except (ValueError, AttributeError) as e:
        raise SiteUnreachable(f"{host} did not answer like an EarthRanger site") from e
