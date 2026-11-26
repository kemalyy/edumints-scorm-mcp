"""v1.9.1 ikinci bağımsız inceleme düzeltmeleri."""
import httpx
import pytest
from fastmcp import Client

import auth.ssrf as ssrf
import server
from auth.oauth import ApiKeyVerifier
from core.project import new_project_id
from core.store import ApiKey

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


async def _req(method, path, **kw):
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.request(method, path, **kw)


async def test_build_package_after_revoke_links_gives_new_link():
    async with Client(server.mcp) as c:
        spec = {"title": "r", "screens": [{"type": "content_slide", "title": "a", "body_html": "<p>x</p>"}]}
        out = (await c.call_tool("build_from_spec", {"spec": spec})).data
        await c.call_tool("revoke_links", {"project_id": out.project_id})
        b = (await c.call_tool("build_package", {"project_id": out.project_id})).data
        st = (await c.call_tool("build_status", {"project_id": out.project_id})).data
    url = getattr(st, "download_url", None) or getattr(b, "download_url", None)
    assert url, "revoke_links sonrası build_package yeni link vermeli"
    assert (await _req("GET", "/files/" + url.rsplit("/", 1)[-1])).status_code == 200


async def test_ip_fallback_also_on_connect_timeout(monkeypatch):
    seen = []

    async def resolve(host, port):
        return ["2001:4860:4860::8888", "93.184.216.34"]

    monkeypatch.setattr(ssrf, "_resolve_ips_async", resolve)

    def handler(req):
        seen.append(req.url.host)
        if ":" in req.url.host:
            raise httpx.ConnectTimeout("dropped", request=req)
        return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)

    data, _ = await ssrf.safe_fetch_asset("https://dual.test/a.png", max_bytes=1024,
                                          _transport=httpx.MockTransport(handler))
    assert data == PNG and len(seen) == 2


async def test_revoke_hides_demo_and_drops_links(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "admin_api_token", "adm")
    principal = "key_local"  # yerel testlerin principal'ı
    async with Client(server.mcp) as c:
        spec = {"title": "d", "screens": [{"type": "content_slide", "title": "a", "body_html": "<p>x</p>"}]}
        out = (await c.call_tool("build_from_spec", {"spec": spec})).data
        slug = f"rv-{new_project_id()[-8:]}".lower()
        await c.call_tool("publish_demo", {"project_id": out.project_id, "slug": slug})
        prev = (await c.call_tool("preview", {"project_id": out.project_id})).data
    assert (await _req("GET", f"/demo/{slug}")).status_code == 200
    try:
        r = await _req("POST", "/admin/principals/revoke", headers={"Authorization": "Bearer adm"},
                       json={"principal": principal})
        assert r.status_code == 200
        assert (await _req("GET", f"/demo/{slug}")).status_code == 404
        assert (await _req("GET", "/preview/" + prev.hosted_url.rsplit("/", 1)[-1])).status_code == 404
    finally:
        await _req("POST", "/admin/principals/restore", headers={"Authorization": "Bearer adm"},
                   json={"principal": principal})
    assert (await _req("GET", f"/demo/{slug}")).status_code == 200  # geri alınabilir: demo silinmedi


@pytest.mark.parametrize("body", [{"principal": {"a": 1}}, {"principal": "x"}, {"principal": "logto:"}])
async def test_admin_principal_shape(monkeypatch, body):
    monkeypatch.setattr(server.SETTINGS, "admin_api_token", "adm")
    r = await _req("POST", "/admin/principals/revoke", headers={"Authorization": "Bearer adm"}, json=body)
    assert r.status_code == 400


async def test_api_key_of_revoked_principal_rejected_even_if_not_disabled():
    await server.SVC.ensure()
    principal = f"logto:u{new_project_id()[-8:]}"
    await server.SVC.store.set_principal_revoked(principal, True)
    raw = f"sk_{new_project_id()}"
    await server.SVC.store.upsert_key(ApiKey(id=f"key_{new_project_id()[-8:]}", label="t", key_hash="",
                                             owner_principal=principal), raw_key=raw)  # yarışla eklenmiş
    v = ApiKeyVerifier(ensure=server.SVC.ensure, get_key=server.SVC.store.get_key,
                       is_revoked=server.SVC.store.is_principal_revoked)
    assert await v.verify_token(raw) is None
    assert await server._validate_bearer(raw) == (None, [])


async def test_build_slot_not_leaked_when_status_update_fails(monkeypatch):
    await server.SVC.ensure()
    pk = server.SVC.packager
    monkeypatch.setattr(pk, "_tasks", {})
    monkeypatch.setattr(pk, "_task_owner", {})
    real = server.SVC.store.update_job
    calls = {"n": 0}

    async def flaky(job):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return await real(job)

    monkeypatch.setattr(server.SVC.store, "update_job", flaky)
    from core.project import ContentSlide, Project
    p = Project(id=new_project_id(), title="q", owner_key_id="leak")
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    job = await pk.submit(p)
    await pk.wait(job.id, timeout=5)
    assert pk._tasks == {} and pk._task_owner == {}


def test_client_ip_uses_proxy_appended_entry():
    class R:
        headers = {"x-forwarded-for": "6.6.6.6, 1.2.3.4"}
        client = None
    assert server._client_ip(R()) == "1.2.3.4"


def test_publish_demo_is_destructive():
    assert server._annotations_for("publish_demo").destructiveHint is True


def test_tool_decorator_with_explicit_name():
    ann = server._annotations_for("get_guide")
    assert ann.title
    with pytest.raises(RuntimeError):
        server._annotations_for("nope")
