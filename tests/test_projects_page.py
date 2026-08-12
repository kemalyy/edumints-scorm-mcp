"""tests/test_projects_page.py — list_projects_page: sayfalama+sıralama+filtre (store seviyesi)."""

from datetime import datetime, timezone

import server
from core.project import Project, new_project_id


def _mk(title: str, *, scorm: str = "1.2", n_screens: int = 1, y: int = 2026, mo: int = 1, d: int = 1) -> Project:
    """key_local sahipli, açık zaman damgalı bir Project üretir (screens dict→Screen coerce edilir)."""
    ts = datetime(y, mo, d, tzinfo=timezone.utc)
    screens = [{"type": "title_slide", "id": f"s{i}", "title": "T"} for i in range(n_screens)]
    return Project(
        id=new_project_id(), title=title, owner_key_id="key_local",
        scorm_version=scorm, screens=screens, created_at=ts, updated_at=ts,
    )


async def _seed(*projects: Project) -> None:
    await server.SVC.ensure()
    for p in projects:
        await server.SVC.store.create_project(p)


# ⚠ YALITIM: conftest oturum-başına TEK paylaşımlı DB kurar ve TÜM suite'teki tool-üretimi
# projeler 'key_local' sahiplidir + updated_at=GERÇEK-şimdi (fixture'ların Oca–Tem damgalarını
# yener). Bu yüzden HER test benzersiz başlık öneki + o önekle `q=` filtresi + `limit=50` kullanır
# → tüm assertler deterministik, dosya-tek-başına VE tam-suite koşumunda aynı geçer.

async def test_updated_desc_is_default_and_newest_first():
    await _seed(_mk("q1a-eski", d=1), _mk("q1a-orta", d=2), _mk("q1a-yeni", d=3))
    rows, total = await server.SVC.store.list_projects_page("key_local", q="q1a", limit=50)
    assert [p.title for p in rows] == ["q1a-yeni", "q1a-orta", "q1a-eski"]
    assert total == 3


async def test_updated_asc_reverses():
    await _seed(_mk("q2a-a", d=5), _mk("q2a-b", d=6))
    rows, _ = await server.SVC.store.list_projects_page("key_local", sort="updated_asc", q="q2a", limit=50)
    assert [p.title for p in rows] == ["q2a-a", "q2a-b"]


async def test_title_asc_alphabetical():
    await _seed(_mk("q3a-Zebra", mo=2), _mk("q3a-Alpha", mo=2))
    rows, _ = await server.SVC.store.list_projects_page("key_local", sort="title_asc", q="q3a", limit=50)
    assert [p.title for p in rows] == ["q3a-Alpha", "q3a-Zebra"]


async def test_q_filters_by_title_case_insensitive():
    await _seed(_mk("q4a-Fatura", mo=3), _mk("q4a-Guvenlik", mo=3))
    rows, total = await server.SVC.store.list_projects_page("key_local", q="q4A-fatura")
    assert total == 1 and rows[0].title == "q4a-Fatura"


async def test_scorm_filter():
    await _seed(_mk("q5a-v12", scorm="1.2", mo=4), _mk("q5a-v2004", scorm="2004", mo=4))
    rows, total = await server.SVC.store.list_projects_page("key_local", scorm="2004", q="q5a", limit=50)
    assert total == 1 and rows[0].scorm_version == "2004"


async def test_screens_desc():
    await _seed(_mk("q6a-bir", n_screens=1, mo=5), _mk("q6a-uc", n_screens=3, mo=5))
    rows, _ = await server.SVC.store.list_projects_page("key_local", sort="screens_desc", q="q6a", limit=50)
    assert [p.title for p in rows] == ["q6a-uc", "q6a-bir"]


async def test_pagination_bounds_and_total():
    await _seed(_mk("q7a-p1", mo=6, d=1), _mk("q7a-p2", mo=6, d=2), _mk("q7a-p3", mo=6, d=3))
    page1, total = await server.SVC.store.list_projects_page("key_local", q="q7a", limit=2, offset=0)
    page2, _ = await server.SVC.store.list_projects_page("key_local", q="q7a", limit=2, offset=2)
    assert total == 3
    assert len(page1) == 2 and len(page2) == 1
    ids1 = {p.id for p in page1}
    ids2 = {p.id for p in page2}
    assert ids1.isdisjoint(ids2)  # sayfalar çakışmaz


async def test_unknown_sort_falls_back_to_updated_desc():
    await _seed(_mk("q8a-x", mo=7, d=1), _mk("q8a-y", mo=7, d=2))
    rows, _ = await server.SVC.store.list_projects_page("key_local", sort="__bogus__", q="q8a", limit=50)
    assert [p.title for p in rows] == ["q8a-y", "q8a-x"]  # updated_desc gibi davranır
