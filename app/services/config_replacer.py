"""Protocol-aware replacement of the host inside a proxy config.

The bot does exactly one thing: take a config the user sent, find the *host*
of the server inside it and swap that host with the host the admin configured.
Everything else must survive untouched — port, UUID, password, path, query
parameters (``sni``, ``host``, ...), the fragment name and any other field.

That is why a plain ``str.replace`` is never used: the previous host may also
appear as an SNI value, a Host header, inside a path or in the fragment, and
blindly replacing it would corrupt the config. Instead each protocol is parsed
on its own terms:

* URI based (``vless``, ``trojan``, ``hysteria2``/``hy2``): the authority is
  ``[userinfo@]host[:port][/path]`` and the query/fragment are split off and
  carried over verbatim, so the only byte that can change is the host.
* ``ss`` (Shadowsocks): the SIP002 form keeps the host in the authority, the
  legacy form hides ``method:password@host:port`` inside base64 — decode,
  replace the host, re-encode with the same alphabet and padding.
* ``vmess``: the payload is base64 encoded JSON, so the ``add`` field is
  rewritten and the JSON re-encoded; ``host``, ``sni``, ``path`` and friends
  are left alone.

Percent-encoding of userinfo is taken as given: if a password contains a raw
``?`` or ``#`` the config is malformed per the URI standard and parsing may
fail, which is reported as an invalid config rather than producing garbage.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from app.services.host_validator import format_host_for_url

__all__ = [
    "ConfigError",
    "InvalidConfigError",
    "UnsupportedProtocolError",
    "ReplacementResult",
    "SUPPORTED_PROTOCOLS",
    "replace_config_host",
]


class ConfigError(Exception):
    """Base class for every config processing failure."""


class UnsupportedProtocolError(ConfigError):
    """The config uses a protocol this bot does not handle."""


class InvalidConfigError(ConfigError):
    """The config is malformed, or its host could not be located."""


@dataclass(frozen=True)
class ReplacementResult:
    """Outcome of a successful replacement."""

    config: str
    protocol: str
    old_host: str
    new_host: str


_PRETTY_NAMES = {
    "vless": "VLESS",
    "vmess": "VMess",
    "trojan": "Trojan",
    "ss": "Shadowsocks",
    "shadowsocks": "Shadowsocks",
    "hysteria2": "Hysteria2",
    "hy2": "Hysteria2",
}

SUPPORTED_PROTOCOLS = tuple(sorted({name for name in _PRETTY_NAMES.values()}))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def replace_config_host(config: str, new_host: str) -> ReplacementResult:
    """Replace the server host of ``config`` with ``new_host``.

    Raises :class:`UnsupportedProtocolError` when the config uses a protocol we
    do not speak and :class:`InvalidConfigError` when it cannot be parsed.
    """
    raw = _first_line(config)
    scheme, separator, _ = raw.partition("://")
    if not separator:
        raise InvalidConfigError("متن ارسال شده یک Config قابل شناسایی نیست.")

    scheme = scheme.strip().lower()
    handler = _HANDLERS.get(scheme)
    if handler is None:
        raise UnsupportedProtocolError(scheme)

    if not new_host:
        raise InvalidConfigError("IP جایگزین تنظیم نشده است.")

    new_config, old_host = handler(raw, new_host)
    return ReplacementResult(
        config=new_config,
        protocol=_PRETTY_NAMES[scheme],
        old_host=old_host,
        new_host=new_host,
    )


def _first_line(config: str) -> str:
    """Return the first non-empty line of the message the user sent."""
    for line in (config or "").splitlines():
        candidate = line.strip()
        if candidate:
            return candidate
    raise InvalidConfigError("متن ارسال شده خالی است.")


# --------------------------------------------------------------------------- #
# URI based protocols (VLESS / Trojan / Hysteria2)
# --------------------------------------------------------------------------- #
def _replace_uri_based(config: str, new_host: str) -> Tuple[str, str]:
    head, rest = _split_scheme(config)

    # Split the query and the fragment off first and re-attach them untouched.
    # This guarantees that e.g. `sni=`, `host=` or the `#name` can never change.
    body, fragment_separator, fragment = rest.partition("#")
    body, query_separator, query = body.partition("?")

    userinfo, at_sign, hostport = body.rpartition("@")
    host, port = _split_host_port(hostport)

    new_body = f"{userinfo}{at_sign}{format_host_for_url(new_host)}{port}"
    new_config = (
        f"{head}{new_body}{query_separator}{query}{fragment_separator}{fragment}"
    )
    return new_config, host


# --------------------------------------------------------------------------- #
# Shadowsocks
# --------------------------------------------------------------------------- #
def _replace_shadowsocks(config: str, new_host: str) -> Tuple[str, str]:
    head, rest = _split_scheme(config)

    body, fragment_separator, fragment = rest.partition("#")
    body, query_separator, query = body.partition("?")

    if "@" in body:
        # SIP002: ss://[base64(method:password)|method:password]@host:port
        userinfo, _, hostport = body.rpartition("@")
        host, port = _split_host_port(hostport)
        new_authority = f"{userinfo}@{format_host_for_url(new_host)}{port}"
    else:
        # Legacy: ss://base64(method:password@host:port)
        decoded, style = _base64_decode(body)
        userinfo, separator, hostport = decoded.rpartition("@")
        if not separator:
            raise InvalidConfigError("ساختار Shadowsocks قابل شناسایی نیست.")
        host, port = _split_host_port(hostport)
        new_authority = _base64_encode(
            f"{userinfo}@{format_host_for_url(new_host)}{port}", style
        )

    new_config = (
        f"{head}{new_authority}{query_separator}{query}{fragment_separator}{fragment}"
    )
    return new_config, host


# --------------------------------------------------------------------------- #
# VMess
# --------------------------------------------------------------------------- #
def _replace_vmess(config: str, new_host: str) -> Tuple[str, str]:
    head, rest = _split_scheme(config)

    payload, fragment_separator, fragment = rest.partition("#")
    payload, query_separator, query = payload.partition("?")

    try:
        decoded, style = _base64_decode(payload)
    except InvalidConfigError:
        # Not base64 at all: a few clients emit `vmess://` as a plain URI.
        return _replace_vmess_uri(config, new_host)

    data = _parse_json_object(decoded)
    if data is None:
        # Decodable, but not a JSON object either — same plain URI fallback.
        return _replace_vmess_uri(config, new_host)

    address = data.get("add")
    if not isinstance(address, str) or not address.strip():
        # A real VMess JSON without `add` is simply broken: do not fall back,
        # otherwise the payload would be "parsed" as a URI and silently mangled.
        raise InvalidConfigError("فیلد add در Config VMess پیدا نشد.")

    # Only `add` (the server address) is rewritten; port/id/host/sni/path/... are
    # re-serialised exactly as they were parsed.
    data["add"] = new_host
    encoded = _base64_encode(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), style
    )

    new_config = (
        f"{head}{encoded}{query_separator}{query}{fragment_separator}{fragment}"
    )
    return new_config, address.strip()


def _replace_vmess_uri(config: str, new_host: str) -> Tuple[str, str]:
    """Handle the ``vmess://uuid@host:port`` form used by some clients."""
    _, rest = _split_scheme(config)
    body = rest.partition("#")[0].partition("?")[0]
    if "@" not in body or ":" not in body:
        raise InvalidConfigError("ساختار Config VMess قابل شناسایی نیست.")
    return _replace_uri_based(config, new_host)


def _parse_json_object(value: str) -> Optional[dict]:
    """Return the decoded JSON object, or ``None`` if it is not one."""
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------- #
# Shared parsing helpers
# --------------------------------------------------------------------------- #
def _split_scheme(config: str) -> Tuple[str, str]:
    """Split ``scheme://rest`` keeping the original scheme casing."""
    marker = config.find("://")
    if marker == -1:
        raise InvalidConfigError("Config فاقد scheme است.")
    return config[: marker + 3], config[marker + 3 :]


def _split_host_port(hostport: str) -> Tuple[str, str]:
    """Split ``host:port`` into ``(host, port_suffix)``.

    ``port_suffix`` is returned verbatim (it may also carry a trailing path) so
    that re-building the authority cannot alter anything but the host.
    """
    value = hostport.strip()
    if not value:
        raise InvalidConfigError("Host در Config پیدا نشد.")

    if value.startswith("["):
        closing = value.find("]")
        if closing == -1:
            raise InvalidConfigError("IPv6 در Config نامعتبر است.")
        host = value[1:closing]
        suffix = value[closing + 1 :]
        if suffix and not suffix.startswith(":"):
            raise InvalidConfigError("ساختار Host:Port نامعتبر است.")
    else:
        host, separator, remainder = value.partition(":")
        suffix = f":{remainder}" if separator else ""

    host = host.strip()
    if not host or any(character in host for character in "@/?#"):
        raise InvalidConfigError("Host در Config پیدا نشد.")

    return host, suffix


@dataclass(frozen=True)
class _Base64Style:
    """How the original payload was encoded, so we can mirror it on the way out."""

    urlsafe: bool
    padded: bool


def _base64_decode(value: str) -> Tuple[str, _Base64Style]:
    compact = "".join(value.split())
    if not compact:
        raise InvalidConfigError("محتوای Base64 خالی است.")

    style = _Base64Style(
        urlsafe="-" in compact or "_" in compact,
        padded=compact.endswith("="),
    )
    padding = "=" * (-len(compact) % 4)
    decoder = base64.urlsafe_b64decode if style.urlsafe else base64.b64decode

    try:
        decoded = decoder(compact + padding)
    except (binascii.Error, ValueError) as exc:
        raise InvalidConfigError("محتوای Base64 معتبر نیست.") from exc

    try:
        return decoded.decode("utf-8"), style
    except UnicodeDecodeError as exc:
        raise InvalidConfigError("محتوای Base64 قابل خواندن نیست.") from exc


def _base64_encode(text: str, style: _Base64Style) -> str:
    encoder = base64.urlsafe_b64encode if style.urlsafe else base64.b64encode
    encoded = encoder(text.encode("utf-8")).decode("ascii")
    return encoded if style.padded else encoded.rstrip("=")


_Handler = Callable[[str, str], Tuple[str, str]]

_HANDLERS: dict[str, _Handler] = {
    "vless": _replace_uri_based,
    "trojan": _replace_uri_based,
    "hysteria2": _replace_uri_based,
    "hy2": _replace_uri_based,
    "ss": _replace_shadowsocks,
    "shadowsocks": _replace_shadowsocks,
    "vmess": _replace_vmess,
}
