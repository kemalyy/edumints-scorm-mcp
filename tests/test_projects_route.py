"""tests/test_projects_route.py — /projects HTTP route: query paramları + sayfalı yanıt."""

import httpx

import server
from core.store import ApiKey  # ⚠ ApiKey core.store'da tanımlı (core.project DEĞİL — server.py de buradan alır)
from core.project import new_key_id, new_project_id, utcnow, Project


async def _auth_key() -> str:
    """key_local sahipli bir API-key üretir → route bunu owner='key_local' sayar (tool projeleriyle aynı)."""
    await server.SVC.ensure()
    raw = "sk_route_test_key_0001"
    key = ApiKey(
        id=new_key_id(), label="route-test", key_hash="",
        max_projects=1000, max_total_mb=100000,
        owner_principal="key_local", created_at=utcnow(),
    )
    await server.SVC.store.upsert_key(key, raw_key=raw)
    return raw


async def _seed_n(n: int, prefix: str) -> None:
    await server.SVC.ensure()
    for i in range(n):
        p = Project(
            id=new_project_id(), title=f"{prefix}-{i}", owner_key_id="key_local",
            scorm_version="1.2", screens=[{"type": "title_slide", "id": "s0", "title": "T"}],
        )
        await server.SVC.store.create_project(p)


async def _get(path: str, token: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get(path, headers={"Authorization": f"Bearer {token}"})


async def test_paginated_response_shape():
    token = await _auth_key()
    await _seed_n(5, "route-shape")
    r = await _get("/projects?page=1&page_size=2&q=route-shape", token)
    assert r.status_code == 200
    body = r.json()
    assert set(["projects", "total", "page", "page_size", "has_more"]).issubset(body)
    assert body["page"] == 1 and body["page_size"] == 2
    assert len(body["projects"]) == 2
    assert body["total"] == 5
    assert body["has_more"] is True


async def test_last_page_has_more_false():
    token = await _auth_key()
    await _seed_n(3, "route-last")
    r = await _get("/projects?page=2&page_size=2&q=route-last", token)
    body = r.json()
    assert body["has_more"] is False
    assert len(body["projects"]) == 1


async def test_page_size_clamped_to_50():
    # q=eşleşmeyen-önek → enrichment döngüsü boş (50 gerçek projeyi _build_preview'la render etmez)
    token = await _auth_key()
    r = await _get("/projects?page_size=999&q=route-clamp-no-match", token)
    assert r.status_code == 200
    assert r.json()["page_size"] == 50


async def test_unauthenticated_401():
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/projects")
    assert r.status_code == 401
