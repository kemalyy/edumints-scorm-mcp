"""tests/test_demo.py — 1.1: /demo yüzeyinde review UI hiç render edilmemeli (BUG fix testleri).

publish_demo → _render_preview_html → render_html(mode="preview") daha önce review FAB'ını da
basıyordu (mode="preview" iki işlevi karıştırıyordu); üstelik rToken() yalnız /preview/{token}
yolunu bildiği için /demo'da buton bozuk çalışıyordu. Çözüm: render_html(..., review=False)
bağımsız bayrağı — review=False iken reviewBtn/reviewPanel/reviewFab id'leri HİÇ basılmaz
(gizlenmez, yoktur)."""

import pathlib

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError as MCPToolError

import server
from components.renderer import render_html
from core.project import ContentSlide, Project, new_project_id
from core.store import DemoMeta


async def _http_get(path: str, headers: dict | None = None) -> httpx.Response:
    """Sunucunun ASGI uygulamasına doğrudan istek (custom_route'ları test etmek için)."""
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get(path, headers=headers or {})


def _course():
    p = Project(id=new_project_id(), title="Demo Kursu")
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    return p


def test_demo_html_has_no_review_ui():
    # doğrudan renderer sözleşmesi: review=False (varsayılan) → markup hiç yok
    html = render_html(_course(), mode="preview", runtime_js="/*rt*/")
    assert "reviewBtn" not in html
    assert "reviewPanel" not in html
    assert "reviewFab" not in html


def test_preview_html_still_has_review_ui():
    html = render_html(_course(), mode="preview", runtime_js="/*rt*/", review=True)
    assert "reviewBtn" in html
    assert "reviewPanel" in html
    assert "reviewFab" in html


async def test_publish_demo_route_has_no_review_ui():
    # uçtan uca: gerçek publish_demo yolu (server.py) → diske yazılan /demo HTML'inde review yok
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "Demo Review Yok", "scorm_version": "1.2",
            "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
        }})
        pid = res.data.project_id
        out = await c.call_tool("publish_demo", {"project_id": pid, "slug": "test-demo-no-review"})
        d = out.data if isinstance(out.data, dict) else out.data.__dict__
        assert d["url"].endswith("/demo/test-demo-no-review")

        f = pathlib.Path(server.SETTINGS.data_dir) / "demos" / "test-demo-no-review.html"
        html = f.read_text(encoding="utf-8")
        assert "reviewBtn" not in html
        assert "reviewPanel" not in html
        assert "reviewFab" not in html
        # package modu (SCORM sözleşmesi) bu maddenin kapsamı dışı ama davranış aynı kalmalı
        assert "window.__PREVIEW__ = true;" in html  # mode="preview" hâlâ tek-dosya asset gömme yapar


# --------------------------------------------------------------------------- #
# 1.2 — DemoMeta store + list_demos/unpublish_demo + kota muhasebesi
# --------------------------------------------------------------------------- #
async def _build_pid(c: Client, title: str = "Demo K") -> str:
    res = await c.call_tool("build_from_spec", {"spec": {
        "title": title, "scorm_version": "1.2",
        "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
    }})
    return res.data.project_id


async def test_demo_meta_upsert_preserves_created_at_updates_rest():
    """core/store.py — upsert_demo doğrudan: aynı slug'a ikinci upsert created_at'ı KORUR,
    diğer alanları (title/size_bytes/updated_at) günceller."""
    from datetime import timedelta

    from core.project import utcnow

    await server.SVC.ensure()
    store = server.SVC.store
    t0 = utcnow()
    m1 = DemoMeta(slug="store-upsert-2", project_id="p1", owner_key_id="key_local",
                  title="Başlık A", language="tr", size_bytes=100, created_at=t0, updated_at=t0)
    await store.upsert_demo(m1)
    got1 = await store.get_demo("store-upsert-2")
    assert got1.title == "Başlık A" and got1.size_bytes == 100

    t1 = t0 + timedelta(seconds=5)
    m2 = DemoMeta(slug="store-upsert-2", project_id="p1", owner_key_id="key_local",
                  title="Başlık B", language="en", size_bytes=250, created_at=t1, updated_at=t1)
    await store.upsert_demo(m2)
    got2 = await store.get_demo("store-upsert-2")
    assert got2.title == "Başlık B"
    assert got2.language == "en"
    assert got2.size_bytes == 250
    assert got2.created_at == got1.created_at  # ilk yayının created_at'ı korunur
    assert got2.updated_at == t1

    await store.delete_demo("store-upsert-2")
    assert await store.get_demo("store-upsert-2") is None


async def test_publish_demo_republish_updates_metadata():
    """publish_demo tool'u ile: içerik değişince metadata (title/size_bytes) güncellenir,
    slug/project_id aynı kalır."""
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Republish Testi")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "republish-meta"})
        meta1 = await server.SVC.store.get_demo("republish-meta")
        assert meta1 is not None
        assert meta1.title == "Republish Testi"
        assert meta1.project_id == pid

        # içeriği büyüt → HTML boyutu değişir → republish sonrası size_bytes güncellenmeli
        await c.call_tool("add_screen", {"project_id": pid, "screen": {
            "type": "content_slide", "id": "c1", "title": "Ekstra",
            "body_html": "<p>" + ("x" * 5000) + "</p>",
        }})
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "republish-meta"})
        meta2 = await server.SVC.store.get_demo("republish-meta")
        assert meta2.size_bytes > meta1.size_bytes
        assert meta2.created_at == meta1.created_at  # ilk yayının created_at'ı korunur
        assert meta2.updated_at >= meta1.updated_at


async def test_publish_demo_foreign_owner_rejected_via_store():
    """Sahiplik artık store'daki DemoMeta'dan doğrulanır: farklı owner_key_id'li bir satır
    doğrudan store'a eklenir (eski .owner dosyası mekanizması DEĞİL) → publish_demo forbidden döner."""
    await server.SVC.ensure()
    from core.project import utcnow

    now = utcnow()
    await server.SVC.store.upsert_demo(DemoMeta(
        slug="foreign-slug", project_id="someone-elses-project", owner_key_id="rival-owner",
        title="Rakip Demo", language="tr", size_bytes=10, created_at=now, updated_at=now,
    ))
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Benim Projem")
        with pytest.raises(MCPToolError, match="forbidden"):
            await c.call_tool("publish_demo", {"project_id": pid, "slug": "foreign-slug"})


async def test_list_demos_returns_own_only():
    await server.SVC.ensure()
    from core.project import utcnow

    now = utcnow()
    await server.SVC.store.upsert_demo(DemoMeta(
        slug="not-mine", project_id="rival-project", owner_key_id="rival-owner-2",
        title="Rakip", language="tr", size_bytes=10, created_at=now, updated_at=now,
    ))
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Listelenecek Proje")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "mine-listed"})
        out = await c.call_tool("list_demos", {})
        d = out.data if isinstance(out.data, dict) else out.data.__dict__
        slugs = {item["slug"] for item in d["demos"]}
        assert "mine-listed" in slugs
        assert "not-mine" not in slugs
        mine = next(item for item in d["demos"] if item["slug"] == "mine-listed")
        assert mine["url"].endswith("/demo/mine-listed")
        assert mine["project_id"] == pid


async def test_unpublish_demo_removes_metadata_and_html_then_route_404s():
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Silinecek Proje")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "to-unpublish"})
        html_path = pathlib.Path(server.SETTINGS.data_dir) / "demos" / "to-unpublish.html"
        assert html_path.exists()
        assert await server.SVC.store.get_demo("to-unpublish") is not None

        out = await c.call_tool("unpublish_demo", {"slug": "to-unpublish"})
        d = out.data if isinstance(out.data, dict) else out.data.__dict__
        assert d["ok"] is True

        # metadata gitti + dosya gitti → /demo/{slug} rotası artık 404 üretecek
        # (route, path.exists() kontrolüne dayanır — burada aynı koşulu doğrudan doğruluyoruz)
        assert await server.SVC.store.get_demo("to-unpublish") is None
        assert not html_path.exists()


async def test_unpublish_demo_foreign_owner_rejected():
    await server.SVC.ensure()
    from core.project import utcnow

    now = utcnow()
    await server.SVC.store.upsert_demo(DemoMeta(
        slug="foreign-unpublish", project_id="rival-project-2", owner_key_id="rival-owner-3",
        title="Rakip", language="tr", size_bytes=10, created_at=now, updated_at=now,
    ))
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError, match="forbidden"):
            await c.call_tool("unpublish_demo", {"slug": "foreign-unpublish"})
    # yabancı satır dokunulmadan kaldı
    assert await server.SVC.store.get_demo("foreign-unpublish") is not None


async def test_unpublish_demo_not_found():
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError, match="not_found"):
            await c.call_tool("unpublish_demo", {"slug": "never-existed-xyz"})


async def test_publish_demo_size_counts_toward_quota():
    """Demo HTML boyutu owner'ın total_bytes'ına dahil olmalı (enforce_size_quota, publish anında)."""
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Kota Testi")
        before = await server.SVC.store.total_bytes("key_local")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "quota-counts"})
        meta = await server.SVC.store.get_demo("quota-counts")
        after = await server.SVC.store.total_bytes("key_local")
        assert after - before == meta.size_bytes
        assert meta.size_bytes > 0

        await c.call_tool("unpublish_demo", {"slug": "quota-counts"})
        after_unpublish = await server.SVC.store.total_bytes("key_local")
        assert after_unpublish == before


async def test_publish_demo_over_quota_rejected(monkeypatch):
    """max_total_mb'ı 0'a düşürünce herhangi bir demo boyutu kotayı aşar → quota_exceeded."""
    await server.SVC.ensure()
    monkeypatch.setattr(server.SETTINGS, "max_project_mb", 0)
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Kota Aşımı")
        with pytest.raises(MCPToolError, match="quota_exceeded"):
            await c.call_tool("publish_demo", {"project_id": pid, "slug": "over-quota-slug"})
    # kota reddedilince ne metadata ne dosya yazılmamalı
    assert await server.SVC.store.get_demo("over-quota-slug") is None
    assert not (pathlib.Path(server.SETTINGS.data_dir) / "demos" / "over-quota-slug.html").exists()


# --------------------------------------------------------------------------- #
# 1.3 — /demo önbellek başlıkları (ETag + Cache-Control + If-None-Match → 304)
# --------------------------------------------------------------------------- #
async def test_demo_route_has_etag_and_cache_control():
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Önbellek Testi")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "cache-headers-demo"})

    r = await _http_get("/demo/cache-headers-demo")
    assert r.status_code == 200
    assert r.headers.get("etag")
    assert r.headers["etag"].startswith('"') and r.headers["etag"].endswith('"')
    cc = r.headers.get("cache-control", "")
    assert "public" in cc
    assert "max-age=" in cc
    assert "must-revalidate" in cc


async def test_demo_returns_304_on_matching_etag():
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "304 Testi")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "cache-304-demo"})

    first = await _http_get("/demo/cache-304-demo")
    etag = first.headers["etag"]

    second = await _http_get("/demo/cache-304-demo", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""


async def test_demo_etag_stable_across_requests_and_changes_on_republish():
    """ETag aynı içerik için tekrar isteklerde SABİT kalır (restart'a dayanıklı olmalı);
    içerik değişince (republish) değişmeli."""
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "ETag Kararlılık")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "etag-stable-demo"})

    r1 = await _http_get("/demo/etag-stable-demo")
    r2 = await _http_get("/demo/etag-stable-demo")
    assert r1.headers["etag"] == r2.headers["etag"]

    async with Client(server.mcp) as c:
        await c.call_tool("add_screen", {"project_id": pid, "screen": {
            "type": "content_slide", "id": "extra1", "title": "Ekstra",
            "body_html": "<p>değişiklik</p>",
        }})
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "etag-stable-demo"})

    r3 = await _http_get("/demo/etag-stable-demo")
    assert r3.headers["etag"] != r1.headers["etag"]


async def test_preview_route_unaffected_by_demo_cache_headers():
    """/preview TTL'li kalır — ETag/Cache-Control eklenmemeli (1.3 kapsamı /demo ile sınırlı)."""
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Preview Kapsam Dışı")
        res = await c.call_tool("preview", {"project_id": pid})
        d = res.data if isinstance(res.data, dict) else res.data.__dict__
        token = d["hosted_url"].rsplit("/", 1)[-1]

    r = await _http_get(f"/preview/{token}")
    assert r.status_code == 200
    assert "etag" not in {k.lower() for k in r.headers.keys()}


# --------------------------------------------------------------------------- #
# 1.4 — OG / twitter meta etiketleri
# --------------------------------------------------------------------------- #
def test_render_html_emits_og_tags_when_description_and_canonical_given():
    p = _course()
    p.description = "Kısa açıklama"
    html = render_html(
        p, mode="preview", runtime_js="/*rt*/",
        canonical_url="https://mcp.edumints.com/scorm/demo/demo-kursu",
    )
    assert 'property="og:type" content="website"' in html
    assert 'property="og:title" content="Demo Kursu"' in html
    assert 'property="og:description" content="Kısa açıklama"' in html
    assert 'property="og:url" content="https://mcp.edumints.com/scorm/demo/demo-kursu"' in html
    assert 'name="twitter:card"' in html


def test_render_html_omits_og_block_when_description_and_canonical_missing():
    html = render_html(_course(), mode="preview", runtime_js="/*rt*/")
    assert "og:" not in html
    assert "twitter:card" not in html


def test_render_html_og_description_only_no_canonical_omits_og_url():
    p = _course()
    p.description = "Yalnız açıklama"
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'property="og:description" content="Yalnız açıklama"' in html
    assert "og:url" not in html


async def test_publish_demo_route_has_og_url_and_title():
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "OG Demo Kursu", "description": "OG açıklaması", "scorm_version": "1.2",
            "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
        }})
        pid = res.data.project_id
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "og-demo-test"})

    html = (pathlib.Path(server.SETTINGS.data_dir) / "demos" / "og-demo-test.html").read_text(
        encoding="utf-8"
    )
    assert 'property="og:title" content="OG Demo Kursu"' in html
    assert 'property="og:description" content="OG açıklaması"' in html
    assert f'property="og:url" content="{server.SETTINGS.public_base_url}/demo/og-demo-test"' in html


async def test_preview_route_html_has_no_og_url():
    """/preview canonical_url geçmez (yalnız demo'da anlamlı) — og:url hiç basılmaz."""
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "Preview OG", "description": "açıklama var", "scorm_version": "1.2",
            "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
        }})
        pid = res.data.project_id
        out = await c.call_tool("preview", {"project_id": pid})
        d = out.data if isinstance(out.data, dict) else out.data.__dict__
        token = d["hosted_url"].rsplit("/", 1)[-1]

    r = await _http_get(f"/preview/{token}")
    assert "og:url" not in r.text


# --------------------------------------------------------------------------- #
# 1.5 — Gömme modu (embed=1) + frame-ancestors politikası
# --------------------------------------------------------------------------- #
def test_render_html_has_embed_css_and_boot_js():
    """BASE_CSS'te body[data-embed="1"] kuralları + boot JS'te location.search'ten embed algılama
    HER render'da var (tek dosya, ayrı render yolu YOK — cache tek dosya kalır)."""
    html = render_html(_course(), mode="preview", runtime_js="/*rt*/")
    assert 'body[data-embed="1"]' in html
    assert "dataset.embed" in html
    assert "embed=1" in html or "'embed'" in html or '"embed"' in html


async def test_demo_embed_query_param_serves_identical_cached_html():
    """/demo/{slug}?embed=1 sunucuda YENİDEN RENDER edilmez — aynı önbellekli HTML (aynı ETag)."""
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Embed Testi")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "embed-cache-demo"})

    plain = await _http_get("/demo/embed-cache-demo")
    embedded = await _http_get("/demo/embed-cache-demo?embed=1")
    assert plain.text == embedded.text
    assert plain.headers["etag"] == embedded.headers["etag"]


async def test_demo_route_frame_ancestors_default_self():
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Frame Testi")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "frame-default-demo"})

    r = await _http_get("/demo/frame-default-demo")
    assert r.headers.get("content-security-policy") == "frame-ancestors 'self'"


async def test_demo_route_frame_ancestors_configurable_via_settings(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "demo_frame_ancestors", "https://portal.edumints.com")
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        pid = await _build_pid(c, "Frame Env Testi")
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "frame-env-demo"})

    r = await _http_get("/demo/frame-env-demo")
    assert r.headers.get("content-security-policy") == "frame-ancestors https://portal.edumints.com"
