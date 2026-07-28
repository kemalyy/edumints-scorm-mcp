"""tests/test_www_authenticate.py — #98: özel HTTP rotalarının 401'lerinde WWW-Authenticate.

MCP 2026-07-28 authorization spec'i (RFC 9728): korumalı kaynak 401'i, protected-resource
metadata'ya işaret eden `WWW-Authenticate` başlığı taşımalı. MCP endpoint'inde bunu
RemoteAuthProvider zaten yapıyor; bu testler custom Starlette rotalarını (server.py) kapsar.

Metadata URL'si TAHMİN değil: RemoteAuthProvider'ın gerçekten mount ettiği yol,
mcp.server.auth.routes.build_resource_metadata_url(PUBLIC_BASE_URL + streamable_http_path)
ile birebir aynı olmalı (RFC 9728 §3.1 — /.well-known/... host ile resource path ARASINA girer).
"""

import httpx
import pytest

import server

# 5 korumalı custom route (server.py) — 401'i çıplak JSON dönenler #98'den önce bunlardı.
PROTECTED_ROUTES = [
    ("GET", "/usage"),
    ("POST", "/keys"),
    ("GET", "/keys"),
    ("DELETE", "/keys/kid_yok"),
    ("GET", "/projects"),
]


async def _request(method: str, path: str, headers: dict | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.request(method, path, headers=headers or {})


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_401_carries_plain_bearer_when_api_key_only(method, path, monkeypatch):
    """OAuth kapalı (API-key-only) → 401 + `WWW-Authenticate: Bearer` (metadata URL'siz)."""
    monkeypatch.setattr(server.SETTINGS, "oauth_enabled", False)
    r = await _request(method, path)
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_401_carries_resource_metadata_when_oauth(method, path, monkeypatch):
    """OAuth açık → 401 + resource_metadata'lı Bearer challenge (RFC 9728)."""
    monkeypatch.setattr(server.SETTINGS, "oauth_enabled", True)
    r = await _request(method, path)
    assert r.status_code == 401
    expected_url = "https://mcp.test/.well-known/oauth-protected-resource/scorm/mcp"
    assert r.headers.get("www-authenticate") == f'Bearer resource_metadata="{expected_url}"'


async def test_metadata_url_matches_remoteauthprovider_mount(monkeypatch):
    """Başlıktaki URL, RemoteAuthProvider'ın FİİLEN mount edeceği metadata URL'siyle birebir aynı
    (build_resource_metadata_url = SDK'nın RFC 9728 §3.1 türetmesi — tahmin değil, kaynak)."""
    import fastmcp
    from mcp.server.auth.routes import build_resource_metadata_url
    from pydantic import AnyHttpUrl

    monkeypatch.setattr(server.SETTINGS, "oauth_enabled", True)
    sdk_url = str(build_resource_metadata_url(
        AnyHttpUrl(server.SETTINGS.public_base_url + fastmcp.settings.streamable_http_path)
    ))
    assert server._www_authenticate_value() == f'Bearer resource_metadata="{sdk_url}"'


async def test_200_path_unchanged():
    """Geçerli API-key ile /usage 200 döner ve WWW-Authenticate TAŞIMAZ (challenge yalnız 401'de)."""
    from core.project import new_key_id
    from core.store import ApiKey

    await server.SVC.ensure()
    raw = "sk_test_wwwauth_200"
    key = ApiKey(id=new_key_id(), label="t", key_hash="", max_projects=5, max_total_mb=10)
    await server.SVC.store.upsert_key(key, raw_key=raw)

    r = await _request("GET", "/usage", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200
    assert "www-authenticate" not in r.headers
    assert r.json()["principal"] == key.id
