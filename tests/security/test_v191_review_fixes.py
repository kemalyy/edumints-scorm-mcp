"""v1.9.1 final inceleme düzeltmeleri — SSRF hop başına yeni bağlantı, proxy env yok sayılır, çoklu IP denemesi,
IPv6 Host, dosya uzantısı ↔ MIME, 6to4/Teredo, entegrasyonlarda asenkron denetim, gerçek /mcp ile süresi dolmuş anahtar."""
import base64
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastmcp import FastMCP

import auth.ssrf as ssrf
from auth.errors import ToolError
from auth.oauth import ApiKeyVerifier, build_auth_provider
from core.store import ApiKey

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _spy_clients(monkeypatch):
    made = []
    real = httpx.AsyncClient

    def factory(*a, **kw):
        made.append(kw)
        return real(*a, **kw)

    monkeypatch.setattr(ssrf.httpx, "AsyncClient", factory)
    return made


async def test_each_hop_uses_fresh_client_without_proxy_env(monkeypatch):
    # I1: aynı IP'ye sabitlenen iki ad arasında yönlendirme — 2. hop 1. hop'un TLS oturumunu kullanmamalı
    made = _spy_clients(monkeypatch)

    async def resolve(host, port):
        return ["93.184.216.34"]

    monkeypatch.setattr(ssrf, "_resolve_ips_async", resolve)

    def handler(req):
        if req.headers["host"] == "a.test":
            return httpx.Response(302, headers={"location": "https://b.test/x.png"})
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    data, _ = await ssrf.safe_fetch_asset("https://a.test/", max_bytes=1024, _transport=httpx.MockTransport(handler))
    assert data == PNG
    assert len(made) == 2  # hop başına yeni istemci (bağlantı havuzu paylaşılmaz)
    assert all(kw.get("trust_env") is False for kw in made)  # M2: HTTPS_PROXY sabitlemeyi bozamaz


async def test_tries_next_allowed_ip_on_connect_error(monkeypatch):
    seen = []

    async def resolve(host, port):
        return ["2001:4860:4860::8888", "93.184.216.34"]

    monkeypatch.setattr(ssrf, "_resolve_ips_async", resolve)

    def handler(req):
        seen.append(req.url.host)
        if ":" in req.url.host:
            raise httpx.ConnectError("no ipv6 route", request=req)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    data, _ = await ssrf.safe_fetch_asset("https://dual.test/a.png", max_bytes=1024,
                                          _transport=httpx.MockTransport(handler))
    assert data == PNG and seen == ["2001:4860:4860::8888", "93.184.216.34"]


async def test_ipv6_literal_host_header_bracketed(monkeypatch):
    seen = []

    def handler(req):
        seen.append(req.headers["host"])
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    await ssrf.safe_fetch_asset("https://[2001:4860:4860::8888]:8443/a.png", max_bytes=1024,
                                _transport=httpx.MockTransport(handler))
    assert seen == ["[2001:4860:4860::8888]:8443"]


@pytest.mark.parametrize("ip", ["2002:7f00:1::", "2001:0:4136:e378:8000:63bf:80ff:fffe"])
def test_6to4_and_teredo_embedding_private_are_blocked(ip):
    assert ssrf._is_blocked_ip(ip) is True


@pytest.mark.parametrize("filename, mime, html_ok, ok", [
    ("x.html", "image/png", False, False),
    ("x.HTM", "text/html", False, False),      # HTML profili kapalı çağrı yeri
    ("x.html", "text/html", True, True),       # build_from_spec HTML profili
    ("x.svg", "image/png", False, False),
    ("x.svg", "image/svg+xml", False, True),
    ("photo.png", "image/png", False, True),
    ("noext", "image/png", False, True),
])
def test_extension_must_match_mime(filename, mime, html_ok, ok):
    if ok:
        ssrf.check_extension(filename, mime, html_ok=html_ok)
    else:
        with pytest.raises(ToolError):
            ssrf.check_extension(filename, mime, html_ok=html_ok)


async def test_add_asset_rejects_html_extension(monkeypatch):
    import server
    from fastmcp import Client
    from fastmcp.exceptions import ToolError as MCPToolError
    src = "data:image/png;base64," + base64.b64encode(PNG).decode()
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
        with pytest.raises(MCPToolError, match="uzantı"):
            await c.call_tool("add_asset", {"project_id": pid, "source": src, "filename": "x.html"})


async def test_integrations_use_async_url_check(monkeypatch):
    from core.integrations import openverse, wikimedia
    assert openverse.assert_safe_url_async is ssrf.assert_safe_url_async
    assert wikimedia.assert_safe_url_async is ssrf.assert_safe_url_async
    assert not hasattr(openverse, "assert_safe_url") and not hasattr(wikimedia, "assert_safe_url")


async def test_real_mcp_request_with_expired_key_is_401():
    # Kabul: gerçek /mcp isteği (dual-auth yığını) süresi dolmuş sk_ ile 401
    expired = ApiKey(id="k", label="t", key_hash="", owner_principal="logto:u",
                     expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))

    async def noop():
        return None

    async def get_key(raw):
        return expired

    auth = build_auth_provider(issuer="https://issuer.test/oidc", jwks_uri="https://issuer.test/jwks",
                               audience="https://mcp.test/mcp", base_url="https://mcp.test",
                               api_key_verifier=ApiKeyVerifier(ensure=noop, get_key=get_key))
    app = FastMCP(name="t", auth=auth)

    @app.tool
    def ping() -> str:
        return "pong"

    transport = httpx.ASGITransport(app=app.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="https://mcp.test") as c:
        r = await c.post("/mcp", headers={"Authorization": "Bearer sk_expired",
                                          "Accept": "application/json, text/event-stream"},
                         json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
