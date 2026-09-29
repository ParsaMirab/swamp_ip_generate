import base64
import json

import pytest

from app.services.config_replacer import (
    InvalidConfigError,
    UnsupportedProtocolError,
    replace_config_host,
)

NEW_HOST = "144.31.157.131"
OLD_HOST = "old-domain.com"


# --------------------------------------------------------------------------- #
# VLESS / Trojan / Hysteria2 (URI based)
# --------------------------------------------------------------------------- #
def test_vless_example_from_the_spec():
    config = f"vless://UUID@{OLD_HOST}:443?type=tcp&security=tls#MyConfig"

    result = replace_config_host(config, NEW_HOST)

    assert result.config == f"vless://UUID@{NEW_HOST}:443?type=tcp&security=tls#MyConfig"
    assert result.old_host == OLD_HOST
    assert result.protocol == "VLESS"


def test_query_and_fragment_are_never_touched():
    config = (
        "vless://11111111-2222-3333-4444-555555555555@old-domain.com:443"
        "?type=ws&security=tls&sni=old-domain.com&host=old-domain.com"
        "&path=%2Fold-domain.com#old-domain.com"
    )

    result = replace_config_host(config, NEW_HOST)

    # sni, host, path and the fragment keep the old domain ...
    assert result.config.count(OLD_HOST) == 4
    # ... and only the authority host is the new one.
    assert result.config.count(NEW_HOST) == 1
    assert f"@{NEW_HOST}:443?" in result.config


def test_trojan_password_may_contain_an_at_sign():
    config = f"trojan://p@ssw0rd@{OLD_HOST}:8443?sni={OLD_HOST}#Trojan"

    result = replace_config_host(config, NEW_HOST)

    assert result.config == f"trojan://p@ssw0rd@{NEW_HOST}:8443?sni={OLD_HOST}#Trojan"
    assert result.old_host == OLD_HOST


def test_path_after_the_port_is_preserved():
    config = f"vless://uuid@{OLD_HOST}:443/ws?type=ws#x"

    assert replace_config_host(config, NEW_HOST).config == (
        f"vless://uuid@{NEW_HOST}:443/ws?type=ws#x"
    )


@pytest.mark.parametrize("scheme", ["hysteria2", "hy2"])
def test_hysteria2_variants(scheme):
    config = f"{scheme}://auth@{OLD_HOST}:443?sni={OLD_HOST}&insecure=0#Hysteria"

    result = replace_config_host(config, NEW_HOST)

    assert result.config == f"{scheme}://auth@{NEW_HOST}:443?sni={OLD_HOST}&insecure=0#Hysteria"
    assert result.protocol == "Hysteria2"


def test_port_is_preserved_exactly():
    assert replace_config_host(f"trojan://pw@{OLD_HOST}:1234#x", NEW_HOST).config == (
        f"trojan://pw@{NEW_HOST}:1234#x"
    )
    # No port at all stays without a port.
    assert replace_config_host(f"hysteria2://pw@{OLD_HOST}#x", NEW_HOST).config == (
        f"hysteria2://pw@{NEW_HOST}#x"
    )
    # No userinfo at all.
    assert replace_config_host(f"hysteria2://{OLD_HOST}:443#x", NEW_HOST).config == (
        f"hysteria2://{NEW_HOST}:443#x"
    )


def test_ipv6_hosts_on_both_sides():
    config = "vless://uuid@[2001:db8::2]:443?type=tcp#x"

    result = replace_config_host(config, "2001:db8::1")

    assert result.config == "vless://uuid@[2001:db8::1]:443?type=tcp#x"
    assert result.old_host == "2001:db8::2"


def test_first_line_of_the_message_is_used():
    config = f"\n\n  vless://UUID@{OLD_HOST}:443#x  \nthis line is ignored"

    assert replace_config_host(config, NEW_HOST).config == (
        f"vless://UUID@{NEW_HOST}:443#x"
    )


# --------------------------------------------------------------------------- #
# Shadowsocks
# --------------------------------------------------------------------------- #
def test_shadowsocks_sip002_with_base64_userinfo_and_plugin():
    config = (
        "ss://YWVzLTI1Ni1nY206cGFzcw==@old-domain.com:8388"
        "?plugin=v2ray-plugin%3Btls#SS"
    )

    result = replace_config_host(config, NEW_HOST)

    assert result.config == (
        "ss://YWVzLTI1Ni1nY206cGFzcw==@144.31.157.131:8388"
        "?plugin=v2ray-plugin%3Btls#SS"
    )
    assert result.protocol == "Shadowsocks"
    assert result.old_host == "old-domain.com"


def test_shadowsocks_sip002_with_plain_userinfo():
    config = f"ss://aes-256-gcm:secret@{OLD_HOST}:8388#SS"

    assert replace_config_host(config, NEW_HOST).config == (
        f"ss://aes-256-gcm:secret@{NEW_HOST}:8388#SS"
    )


def test_shadowsocks_legacy_base64_payload_with_a_slash_in_it():
    # base64 output contains a literal '/', so splitting the raw payload on '/'
    # (as a URL parser would) corrupts this config.
    plaintext = f"aes-256-gcm:ab?@{OLD_HOST}:8388"
    encoded = base64.b64encode(plaintext.encode()).decode()
    assert "/" in encoded

    result = replace_config_host(f"ss://{encoded}#Legacy", NEW_HOST)

    expected = base64.b64encode(f"aes-256-gcm:ab?@{NEW_HOST}:8388".encode()).decode()
    assert result.config == f"ss://{expected}#Legacy"
    assert result.old_host == OLD_HOST


def test_shadowsocks_legacy_base64_payload_with_at_and_slash_in_password():
    result = replace_config_host(
        "ss://YWVzLTI1Ni1nY206cEBzcy93b3JkQG9sZC1kb21haW4uY29tOjgzODg=#Legacy",
        NEW_HOST,
    )

    expected = base64.b64encode(
        f"aes-256-gcm:p@ss/word@{NEW_HOST}:8388".encode()
    ).decode()
    assert result.config == f"ss://{expected}#Legacy"
    assert result.old_host == OLD_HOST


def test_shadowsocks_padding_style_is_preserved():
    encoded = base64.b64encode(f"aes-256-gcm:secret@{OLD_HOST}:8388".encode()).decode()
    assert encoded.endswith("=")

    padded = replace_config_host(f"ss://{encoded}", NEW_HOST).config[len("ss://") :]
    assert padded.endswith("=")

    unpadded = replace_config_host(
        f"ss://{encoded.rstrip('=')}", NEW_HOST
    ).config[len("ss://") :]
    assert not unpadded.endswith("=")


# --------------------------------------------------------------------------- #
# VMess
# --------------------------------------------------------------------------- #
def _decode_vmess(config: str) -> dict:
    """Decode the base64 JSON payload of a ``vmess://`` config."""
    payload = config[len("vmess://") :]
    return json.loads(base64.b64decode(payload + "=" * (-len(payload) % 4)).decode())


def _vmess_payload(**overrides):
    payload = {
        "v": "2",
        "ps": "My Server",
        "add": OLD_HOST,
        "port": "443",
        "id": "11111111-2222-3333-4444-555555555555",
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": OLD_HOST,
        "path": "/ws",
        "tls": "tls",
        "sni": OLD_HOST,
    }
    payload.update(overrides)
    return payload


def test_vmess_json_only_the_address_changes():
    encoded = base64.b64encode(json.dumps(_vmess_payload()).encode()).decode()

    result = replace_config_host(f"vmess://{encoded}", NEW_HOST)

    assert result.protocol == "VMess"
    assert result.old_host == OLD_HOST
    decoded = _decode_vmess(result.config)
    assert decoded["add"] == NEW_HOST
    assert decoded["host"] == OLD_HOST
    assert decoded["sni"] == OLD_HOST
    assert decoded["path"] == "/ws"
    assert decoded["port"] == "443"
    assert decoded["id"] == "11111111-2222-3333-4444-555555555555"
    assert decoded["ps"] == "My Server"


def test_vmess_keeps_the_base64_padding_style():
    encoded = base64.b64encode(json.dumps(_vmess_payload()).encode()).decode()
    assert encoded.endswith("=")

    result = replace_config_host(f"vmess://{encoded.rstrip('=')}", NEW_HOST)

    assert not result.config.endswith("=")
    assert _decode_vmess(result.config)["add"] == NEW_HOST


def test_vmess_non_ascii_values_survive():
    encoded = base64.b64encode(
        json.dumps(_vmess_payload(ps="سرور من"), ensure_ascii=False).encode()
    ).decode()

    result = replace_config_host(f"vmess://{encoded}", NEW_HOST)

    decoded = _decode_vmess(result.config)
    assert decoded["ps"] == "سرور من"
    assert decoded["add"] == NEW_HOST


def test_vmess_accepts_a_plain_uri_payload():
    config = f"vmess://11111111-2222-3333-4444-555555555555@{OLD_HOST}:443?type=ws#VM"

    result = replace_config_host(config, NEW_HOST)

    assert result.config == (
        f"vmess://11111111-2222-3333-4444-555555555555@{NEW_HOST}:443?type=ws#VM"
    )


def test_vmess_without_an_add_field_is_invalid():
    encoded = base64.b64encode(json.dumps({"v": "2", "port": "443"}).encode()).decode()

    with pytest.raises(InvalidConfigError):
        replace_config_host(f"vmess://{encoded}", NEW_HOST)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("config", ["", "   ", "\n\n", "plain text", "vless://"])
def test_invalid_configs(config):
    with pytest.raises(InvalidConfigError):
        replace_config_host(config, NEW_HOST)


@pytest.mark.parametrize(
    "config",
    [
        "wireguard://key@host:51820",
        "http://example.com/path",
        "socks://user:pass@host:1080",
    ],
)
def test_unsupported_protocols(config):
    with pytest.raises(UnsupportedProtocolError):
        replace_config_host(config, NEW_HOST)


def test_missing_replacement_host_is_invalid():
    with pytest.raises(InvalidConfigError):
        replace_config_host(f"vless://uuid@{OLD_HOST}:443#x", "")
