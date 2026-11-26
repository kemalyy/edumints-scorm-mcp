"""SSRF: bağlantı denetlenen IP'ye sabitlenir (DNS rebinding/TOCTOU), DNS asenkron, toplam süre sınırı."""
import asyncio

import httpx
import pytest

import auth.ssrf as ssrf
from auth.errors import ToolError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _resolver(answers: dict[str, list[list[str]]], calls: list):
    """host → art arda çağrılarda dönecek cevaplar (rebinding simülasyonu)."""
    async def fake(host, port):
        calls.append(host)
        seq = answers[host]
        return seq.pop(0) if len(seq) > 1 else seq[0]
    return fake


async def test_connection_goes_to_checked_ip_even_if_dns_changes(monkeypatch):
    calls, seen = [], []
    monkeypatch.setattr(ssrf, "_resolve_ips_async",
                        _resolver({"example.com": [["93.184.216.34"], ["127.0.0.1"]]}, calls))

    def handler(req: httpx.Request):
        seen.append(req)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    data, mime = await ssrf.safe_fetch_asset("https://example.com/a.png", max_bytes=1024,
                                             _transport=httpx.MockTransport(handler))
    assert data == PNG and mime == "image/png"
    assert calls == ["example.com"]  # tek çözümleme; ikinci (rebind) cevap hiç kullanılmaz
    req = seen[0]
    assert req.url.host == "93.184.216.34"
    assert req.headers["host"] == "example.com"
    assert req.extensions.get("sni_hostname") == "example.com"


async def test_redirect_to_internal_is_blocked(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve_ips_async", _resolver(
        {"public.test": [["93.184.216.34"]], "internal.test": [["10.0.0.5"]]}, []))

    def handler(req):
        return httpx.Response(302, headers={"location": "https://internal.test/admin"})

    with pytest.raises(ToolError, match="Engelli IP"):
        await ssrf.safe_fetch_asset("https://public.test/r", max_bytes=1024,
                                    _transport=httpx.MockTransport(handler))


async def test_any_blocked_ip_in_answer_rejects(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve_ips_async",
                        _resolver({"mix.test": [["93.184.216.34", "127.0.0.1"]]}, []))
    with pytest.raises(ToolError, match="127.0.0.1"):
        await ssrf.safe_fetch_asset("https://mix.test/a", max_bytes=1024,
                                    _transport=httpx.MockTransport(lambda r: httpx.Response(200)))


async def test_ipv6_pin_and_port_kept_in_host_header(monkeypatch):
    seen = []
    monkeypatch.setattr(ssrf, "_resolve_ips_async", _resolver({"v6.test": [["2001:4860:4860::8888"]]}, []))

    def handler(req):
        seen.append(req)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    await ssrf.safe_fetch_asset("https://v6.test:8443/a.png", max_bytes=1024,
                                _transport=httpx.MockTransport(handler))
    assert seen[0].url.host == "2001:4860:4860::8888" and seen[0].url.port == 8443
    assert seen[0].headers["host"] == "v6.test:8443"


async def test_total_deadline_cuts_slow_stream(monkeypatch):
    monkeypatch.setattr(ssrf, "_resolve_ips_async", _resolver({"slow.test": [["93.184.216.34"]]}, []))

    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(50):
                await asyncio.sleep(0.05)
                yield b"x"

    def handler(req):
        return httpx.Response(200, headers={"content-type": "image/png"}, stream=Slow())

    with pytest.raises(ToolError, match="zaman aşımı"):
        await ssrf.safe_fetch_asset("https://slow.test/a.png", max_bytes=10_000, total_timeout=0.3,
                                    _transport=httpx.MockTransport(handler))


async def test_dns_resolution_uses_event_loop_resolver(monkeypatch):
    loop = asyncio.get_running_loop()
    used = []

    async def fake_getaddrinfo(host, port, **kw):
        used.append(host)
        return [(2, 1, 6, "", ("93.184.216.34", port or 443))]

    monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)
    assert await ssrf._resolve_ips_async("example.com", 443) == ["93.184.216.34"]
    assert used == ["example.com"]
