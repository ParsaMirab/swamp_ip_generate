"""Validation of the host/IP that the admin sets as replacement target."""

from __future__ import annotations

import ipaddress
import re

_MAX_HOSTNAME_LENGTH = 253

_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_HOSTNAME_RE = re.compile(rf"^(?:{_LABEL}\.)*{_LABEL}$")
_DIGITS_AND_DOTS_RE = re.compile(r"^[0-9.]+$")


class InvalidHostError(ValueError):
    """Raised when a value is neither a valid IP address nor a valid hostname."""


def validate_host(raw: str) -> str:
    """Return a normalised host, or raise :class:`InvalidHostError`.

    Accepts IPv4, IPv6 (with or without surrounding brackets) and DNS hostnames.
    A port is intentionally rejected: the admin only ever configures the host.
    """
    value = (raw or "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()

    if not value:
        raise InvalidHostError("مقدار خالی است.")
    if len(value) > _MAX_HOSTNAME_LENGTH:
        raise InvalidHostError("مقدار وارد شده بیش از حد طولانی است.")
    if any(character.isspace() for character in value):
        raise InvalidHostError("مقدار وارد شده نباید فاصله داشته باشد.")

    if ":" in value:
        try:
            return str(ipaddress.IPv6Address(value))
        except ipaddress.AddressValueError as exc:
            raise InvalidHostError(
                "IPv6 نامعتبر است. توجه کنید که Port نباید وارد شود."
            ) from exc

    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        pass

    if _DIGITS_AND_DOTS_RE.match(value):
        raise InvalidHostError("IPv4 نامعتبر است.")

    try:
        hostname = value.encode("idna").decode("ascii")
    except UnicodeError:
        hostname = value

    if not _HOSTNAME_RE.match(hostname):
        raise InvalidHostError("IP/Domain معتبر نیست.")

    return hostname.lower()


def format_host_for_url(host: str) -> str:
    """Render a host the way it must appear inside a URL authority.

    IPv6 literals have to be wrapped in square brackets, e.g. ``[2001:db8::1]``.
    """
    if ":" in host:
        return f"[{host}]"
    return host
