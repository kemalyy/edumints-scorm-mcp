"""tests/security/test_ssrf_regression.py — SSRF guard regression tests.
Checks for bypass vectors: DNS rebinding, redirect-to-internal, IPv6/decimal IP, file:// etc.
"""

import pytest
from auth.ssrf import _is_blocked_ip, assert_safe_url, safe_fetch_asset
from auth.errors import ToolError
import httpx
from unittest.mock import patch

@pytest.mark.parametrize("ip", [
    "127.0.0.1",
    "10.0.0.1",
    "172.16.0.1",
    "192.168.0.1",
    "169.254.169.254",
    "100.64.0.1",
    "::1",
    "fe80::1",
    "fc00::",
    "fd00::",
    "0.0.0.0",
    "255.255.255.255",
    "::",
])
def test_blocked_ips(ip):
    assert _is_blocked_ip(ip) is True

@pytest.mark.parametrize("ip", [
    "8.8.8.8",
    "1.1.1.1",
    "2001:4860:4860::8888",
])
def test_allowed_ips(ip):
    assert _is_blocked_ip(ip) is False

@pytest.mark.parametrize("url", [
    "http://127.0.0.1",
    "file:///etc/passwd",
    "gopher://localhost",
    "https://user:pass@google.com",
    "https://127.0.0.1",
    "https://[::1]",
    "https://localhost",
    "https://169.254.169.254",
    "https://2130706433", # 127.0.0.1 in decimal
    "https://0x7f000001", # 127.0.0.1 in hex
])
def test_assert_safe_url_blocks(url):
    with pytest.raises(ToolError) as excinfo:
        assert_safe_url(url)
    assert excinfo.value.code == "asset_error"

@pytest.mark.asyncio
async def test_ssrf_redirect_to_internal(monkeypatch):
    # Yönlendirmeler izlenmez (follow_redirects=False); her hop yeniden çözülüp denetlenir ve
    # denetlenen IP'ye sabitlenir (v1.9.1). İç adrese yönlendirme reddedilir.
    import auth.ssrf as ssrf

    async def resolve(host, port):
        return {"public-service.com": ["93.184.216.34"], "127.0.0.1": ["127.0.0.1"]}[host]

    monkeypatch.setattr(ssrf, "_resolve_ips_async", resolve)
    transport = httpx.MockTransport(
        lambda req: httpx.Response(302, headers={"location": "https://127.0.0.1/admin"}))
    with pytest.raises(ToolError) as excinfo:
        await safe_fetch_asset("https://public-service.com/redirect", max_bytes=1024, _transport=transport)
    assert "Engelli IP" in str(excinfo.value)

@pytest.mark.asyncio
async def test_dns_rebinding_protection():
    # DNS Rebinding protection check:
    # assert_safe_url resolves host and checks ALL returned IPs.
    
    host = "rebind.com"
    url = f"https://{host}/asset.png"
    
    with patch("auth.ssrf._resolve_ips", return_value=["93.184.216.34", "127.0.0.1"]):
        with pytest.raises(ToolError) as excinfo:
            assert_safe_url(url)
        assert "Engelli IP aralığı: 127.0.0.1" in str(excinfo.value)

def test_ipv4_mapped_ipv6_blocking():
    # ::ffff:127.0.0.1 should be blocked
    assert _is_blocked_ip("::ffff:7f00:1") is True
    assert _is_blocked_ip("::ffff:127.0.0.1") is True
