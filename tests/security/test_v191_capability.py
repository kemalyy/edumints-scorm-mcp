"""Capability URL'leri: ortak geçerlilik, /feedback sınırları, başlıklar, log maskeleme."""
import logging
from pathlib import Path

import httpx
import pytest

import server
from core.project import new_project_id


async def _req(method: str, path: str, **kw) -> httpx.Response:
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.request(method, path, **kw)


async def _preview(ttl: int) -> tuple[str, str]:
    await server.SVC.ensure()
    pid, tok = new_project_id(), f"tok{new_project_id()[-10:]}"
    await server.SVC.store.put_preview(tok, pid, ttl)
    d = Path(server.SETTINGS.data_dir) / "previews"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tok}.html").write_text("<html>ok</html>", encoding="utf-8")
    return tok, pid


async def test_expired_preview_token_cannot_write_feedback():
    tok, pid = await _preview(-60)
    r = await _req("POST", "/feedback", json={"preview_token": tok, "comment": "merhaba"})
    assert r.status_code == 410
    assert await server.SVC.store.list_feedback(pid) == []
    assert (await _req("GET", f"/preview/{tok}")).status_code == 410


async def test_valid_preview_token_still_writes_feedback():
    tok, pid = await _preview(600)
    r = await _req("POST", "/feedback", json={"preview_token": tok, "comment": "merhaba"})
    assert r.status_code == 200 and len(await server.SVC.store.list_feedback(pid)) == 1


async def test_large_feedback_body_rejected_unread():
    tok, _ = await _preview(600)
    body = b'{"preview_token":"' + tok.encode() + b'","comment":"' + b"x" * (1024 * 1024) + b'"}'
    r = await _req("POST", "/feedback", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 413


async def test_feedback_rate_limited_per_token():
    tok, _ = await _preview(600)
    codes = [(await _req("POST", "/feedback", json={"preview_token": tok, "comment": f"c{i}"})).status_code
             for i in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429


async def test_preview_response_has_privacy_headers():
    tok, _ = await _preview(600)
    r = await _req("GET", f"/preview/{tok}")
    assert r.status_code == 200
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "no-store" in r.headers["cache-control"] and "private" in r.headers["cache-control"]
    assert r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("path, masked", [
    ("/preview/abcdef1234567890", "/preview/abcdef…"),
    ("/files/zzzzzz999999?x=1", "/files/zzzzzz…"),
])
def test_access_log_masks_tokens(path, masked):
    f = server._TokenMaskFilter()
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4", "GET", path, "1.1", 200), None)
    assert f.filter(rec) is True
    out = rec.getMessage()
    assert masked in out and "1234567890" not in out and "999999" not in out
