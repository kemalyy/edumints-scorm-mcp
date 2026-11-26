"""Onay kaldırıldığında erişim iptali; sub'sız token 'unknown'a düşmez."""
from types import SimpleNamespace

import httpx
import pytest

import server
from auth.errors import ToolError
from auth.oauth import ApiKeyVerifier
from core.project import new_project_id
from core.store import ApiKey

ADMIN = "adm_test_secret_123"


async def _req(method, path, token=ADMIN, **kw):
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.request(method, path, headers=headers, **kw)


def _oauth(monkeypatch, sub, scopes=("mcp",)):
    monkeypatch.setattr(server.SETTINGS, "oauth_enabled", True)
    tok = SimpleNamespace(subject=sub, scopes=list(scopes), claims={"sub": sub} if sub else {})
    monkeypatch.setattr(server, "get_access_token", lambda: tok)


async def test_token_without_sub_is_rejected(monkeypatch):
    _oauth(monkeypatch, None)
    with pytest.raises(ToolError) as e:
        await server._owner_resolve()
    assert e.value.code == "unauthorized"


async def _principal_with_key():
    await server.SVC.ensure()
    principal = f"logto:u{new_project_id()[-8:]}"
    raw = f"sk_{new_project_id()}"
    key = ApiKey(id=f"key_{new_project_id()[-8:]}", label="t", key_hash="", owner_principal=principal)
    await server.SVC.store.upsert_key(key, raw_key=raw)
    return principal, raw


async def test_revoke_disables_keys_and_blocks_oauth(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "admin_api_token", ADMIN)
    principal, raw = await _principal_with_key()
    verifier = ApiKeyVerifier(ensure=server.SVC.ensure, get_key=server.SVC.store.get_key)
    assert await verifier.verify_token(raw) is not None

    r = await _req("POST", "/admin/principals/revoke", json={"principal": principal})
    assert r.status_code == 200 and r.json()["keys_disabled"] == 1
    assert await verifier.verify_token(raw) is None  # anahtar artık çalışmaz

    _oauth(monkeypatch, principal.removeprefix("logto:"))
    with pytest.raises(ToolError) as e:
        await server._owner_resolve()
    assert e.value.code == "forbidden"

    r = await _req("POST", "/admin/principals/restore", json={"principal": principal})
    assert r.status_code == 200
    assert (await server._owner_resolve()).id == principal  # OAuth yeniden açılır
    assert await verifier.verify_token(raw) is None  # eski anahtar devre dışı kalır (yeniden üretilmeli)


@pytest.mark.parametrize("token, code", [(None, 401), ("wrong", 401)])
async def test_admin_route_requires_admin_token(monkeypatch, token, code):
    monkeypatch.setattr(server.SETTINGS, "admin_api_token", ADMIN)
    r = await _req("POST", "/admin/principals/revoke", token=token, json={"principal": "logto:x"})
    assert r.status_code == code


async def test_admin_route_disabled_without_configured_token(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "admin_api_token", "")
    r = await _req("POST", "/admin/principals/revoke", token="", json={"principal": "logto:x"})
    assert r.status_code == 404


async def test_admin_route_validates_principal(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "admin_api_token", ADMIN)
    r = await _req("POST", "/admin/principals/revoke", json={"principal": ""})
    assert r.status_code == 400


async def test_validate_bearer_rejects_revoked_or_subless_jwt(monkeypatch):
    # HTTP rotaları (/keys, /usage, /projects): iptal edilen kullanıcının hâlâ geçerli JWT'si yeni anahtar
    # üretemez; sub'sız JWT 'unknown'a düşmez
    principal = f"logto:u{new_project_id()[-8:]}"
    await server.SVC.ensure()
    await server.SVC.store.set_principal_revoked(principal, True)

    class V:
        def __init__(self, sub):
            self.sub = sub

        async def verify_token(self, raw):
            return SimpleNamespace(subject=self.sub, scopes=["mcp"], claims={})

    monkeypatch.setattr(server, "_jwt_verifier", lambda: V(principal.removeprefix("logto:")))
    assert await server._validate_bearer("eyJ.jwt") == (None, [])
    monkeypatch.setattr(server, "_jwt_verifier", lambda: V(None))
    assert await server._validate_bearer("eyJ.jwt") == (None, [])
