"""Capability link kontrolleri: iptal edilebilir linkler (revoke_links) ve yalnız-görüntüleme preview
(allow_feedback=False)."""
import httpx
from fastmcp import Client

import server


async def _req(method, path, **kw):
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.request(method, path, **kw)


def _tok(url: str) -> str:
    return url.rsplit("/", 1)[-1]


async def _project(c):
    spec = {"title": "link", "screens": [{"type": "content_slide", "title": "a", "body_html": "<p>x</p>"}]}
    return (await c.call_tool("build_from_spec", {"spec": spec})).data


async def test_revoke_links_kills_preview_and_download():
    async with Client(server.mcp) as c:
        out = await _project(c)
        prev = (await c.call_tool("preview", {"project_id": out.project_id})).data
        st = (await c.call_tool("build_status", {"project_id": out.project_id})).data
        dl = st.download_url if hasattr(st, "download_url") else st["download_url"]
        assert (await _req("GET", f"/preview/{_tok(prev.hosted_url)}")).status_code == 200
        assert (await _req("GET", f"/files/{_tok(dl)}")).status_code == 200
        r = (await c.call_tool("revoke_links", {"project_id": out.project_id})).data
        assert r["previews_revoked"] >= 1 and r["packages_revoked"] >= 1
    assert (await _req("GET", f"/preview/{_tok(prev.hosted_url)}")).status_code == 404
    assert (await _req("GET", f"/files/{_tok(dl)}")).status_code == 404
    r = await _req("POST", "/feedback", json={"preview_token": _tok(prev.hosted_url), "comment": "x"})
    assert r.status_code == 404


async def test_view_only_preview_rejects_feedback_and_hides_review_ui():
    async with Client(server.mcp) as c:
        out = await _project(c)
        prev = (await c.call_tool("preview", {"project_id": out.project_id, "allow_feedback": False})).data
    tok = _tok(prev.hosted_url)
    page = await _req("GET", f"/preview/{tok}")
    assert page.status_code == 200 and "reviewFab" not in page.text
    r = await _req("POST", "/feedback", json={"preview_token": tok, "comment": "x"})
    assert r.status_code == 403


async def test_default_preview_still_accepts_feedback():
    async with Client(server.mcp) as c:
        out = await _project(c)
        prev = (await c.call_tool("preview", {"project_id": out.project_id})).data
    r = await _req("POST", "/feedback", json={"preview_token": _tok(prev.hosted_url), "comment": "ok"})
    assert r.status_code == 200
