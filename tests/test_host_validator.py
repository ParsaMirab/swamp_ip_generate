import pytest

from app.services.host_validator import (
    InvalidHostError,
    format_host_for_url,
    validate_host,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("144.31.157.131", "144.31.157.131"),
        ("  144.31.157.131  ", "144.31.157.131"),
        ("2001:db8::1", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("2001:DB8::1", "2001:db8::1"),
        ("Example.COM", "example.com"),
        ("sub.example.co.uk", "sub.example.co.uk"),
        ("localhost", "localhost"),
    ],
)
def test_valid_hosts_are_normalised(raw, expected):
    assert validate_host(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "144.31.157.131:443",
        "example.com:443",
        "999.1.1.1",
        "1.2.3.256",
        "1.2.3",
        "not a host",
        "-leading.example.com",
        "2001:db8::zz",
        "x" * 254,
    ],
)
def test_invalid_hosts_are_rejected(raw):
    with pytest.raises(InvalidHostError):
        validate_host(raw)


def test_format_host_for_url_brackets_ipv6_only():
    assert format_host_for_url("144.31.157.131") == "144.31.157.131"
    assert format_host_for_url("example.com") == "example.com"
    assert format_host_for_url("2001:db8::1") == "[2001:db8::1]"
