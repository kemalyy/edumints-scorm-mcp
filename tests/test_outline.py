"""tests/test_outline.py — Senaryo hattı Faz 1: outline şeması + doğrulama.

Kapsam (plan: docs/superpowers/plans/2026-07-30-scenario-line-plan.md, Faz 1):
  - OutlineNode modeli (unit/section, makine-dostu id, ops. Objective, ops. pedagogy_pack)
  - CourseSpec.outline / Project.outline (additive) + ScreenBase.node_id (additive)
  - CourseSpec.audience_pack — REZERVE alan (yalnız kabul+sakla+makine-dostu doğrula; davranış Faz 5)
  - Objective.outcome_type — additive opsiyonel alan
  - Sert doğrulamalar (veri bütünlüğü, 3.8): sarkan parent_id, döngü, derinlik>3,
    yinelenen düğüm id'si, sarkan screen.node_id, hedef-ad-alanı çakışması
  - Outline YOKSA doğrulama çıktısı SIFIR yeni kalem (geriye uyum)

NOT (Faz 1 kapsam kararı): ORPHAN_PAGE / en-yakın-atadan hedef mirası Faz 2 derleme
mantığıdır — burada YALNIZ yapısal doğrulama var (ref/derinlik/döngü/tekillik).
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.project import (
    ContentSlide,
    CourseSpec,
    Objective,
    OutlineNode,
    Project,
    SummaryScreen,
    TitleSlide,
)
from core.validator import validate_project


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _screens():
    return [
        TitleSlide(id="t1", title="Başlık"),
        ContentSlide(id="c1", title="İçerik", body_html="<p>x</p>"),
        SummaryScreen(id="s1", title="Özet"),
    ]


def _project(**kw) -> Project:
    base = dict(id="proj_T", title="T", screens=_screens())
    base.update(kw)
    return Project(**base)


def _outline_errors(project: Project):
    """Yalnız outline/node_id kaynaklı doğrulama kalemleri (path'e göre)."""
    return [e for e in validate_project(project)
            if (e.path or "").startswith("outline") or ".node_id" in (e.path or "")]


# --------------------------------------------------------------------------- #
# Model: OutlineNode
# --------------------------------------------------------------------------- #
def test_outline_node_minimal():
    n = OutlineNode(id="u1", kind="unit", title="Ünite 1")
    assert n.parent_id is None
    assert n.objective is None
    assert n.pedagogy_pack is None


def test_outline_node_full():
    n = OutlineNode(
        id="s1.1", parent_id="u1", kind="section", title="Bölüm",
        objective=Objective(id="obj_a", description="d"), pedagogy_pack="gagne-9",
    )
    assert n.objective.id == "obj_a"
    assert n.pedagogy_pack == "gagne-9"


@pytest.mark.parametrize("bad_id", ["", "a b", "tr/çğ", "x" * 65, "a#b"])
def test_outline_node_id_must_be_machine_friendly(bad_id):
    with pytest.raises(PydanticValidationError):
        OutlineNode(id=bad_id, kind="unit", title="T")


def test_outline_node_kind_restricted():
    with pytest.raises(PydanticValidationError):
        OutlineNode(id="n1", kind="page", title="T")  # "page" Faz 2 (senaryo sayfaları)


# --------------------------------------------------------------------------- #
# Model: additive alanlar
# --------------------------------------------------------------------------- #
def test_coursespec_outline_and_project_outline_default_empty():
    spec = CourseSpec(title="T", screens=_screens())
    assert spec.outline == []
    assert _project().outline == []


def test_screenbase_node_id_default_none_and_settable():
    s = ContentSlide(title="X", body_html="<p>x</p>")
    assert s.node_id is None
    s2 = ContentSlide(title="X", body_html="<p>x</p>", node_id="u1")
    assert s2.node_id == "u1"


def test_objective_outcome_type_additive():
    assert Objective(id="o1").outcome_type is None
    assert Objective(id="o1", outcome_type="skill").outcome_type == "skill"
    with pytest.raises(PydanticValidationError):
        Objective(id="o1", outcome_type="not valid!")


def test_audience_pack_reserved_accepted_and_stored():
    spec = CourseSpec(title="T", screens=_screens(), audience_pack="k12-lise")
    assert spec.audience_pack == "k12-lise"
    p = _project(audience_pack="k12-lise")
    assert p.audience_pack == "k12-lise"


def test_audience_pack_default_none_and_machine_friendly_only():
    assert CourseSpec(title="T", screens=_screens()).audience_pack is None
    with pytest.raises(PydanticValidationError):
        CourseSpec(title="T", screens=_screens(), audience_pack="Lise Öğrencisi")


def test_spec_roundtrip_preserves_outline():
    spec = CourseSpec.model_validate({
        "title": "T",
        "outline": [
            {"id": "u1", "kind": "unit", "title": "Ü1",
             "objective": {"id": "o1", "outcome_type": "knowledge"}},
            {"id": "b1", "parent_id": "u1", "kind": "section", "title": "B1"},
        ],
        "audience_pack": "yetiskin",
        "screens": [{"type": "content_slide", "id": "c1", "title": "C",
                     "body_html": "<p>x</p>", "node_id": "b1"}],
    })
    dumped = spec.model_dump()
    assert dumped["outline"][0]["id"] == "u1"
    assert dumped["outline"][1]["parent_id"] == "u1"
    assert dumped["screens"][0]["node_id"] == "b1"
    assert dumped["audience_pack"] == "yetiskin"


# --------------------------------------------------------------------------- #
# Doğrulama: sert hatalar (veri bütünlüğü)
# --------------------------------------------------------------------------- #
def _ol(*nodes) -> list[OutlineNode]:
    return [OutlineNode(**n) for n in nodes]


def test_validate_dangling_parent_id():
    p = _project(outline=_ol({"id": "u1", "kind": "unit", "title": "A", "parent_id": "yok"}))
    errs = _outline_errors(p)
    assert errs and any("parent_id" in (e.path or "") for e in errs)


def test_validate_cycle():
    p = _project(outline=_ol(
        {"id": "a", "kind": "unit", "title": "A", "parent_id": "b"},
        {"id": "b", "kind": "unit", "title": "B", "parent_id": "a"},
    ))
    assert any("döngü" in e.message for e in _outline_errors(p))


def test_validate_self_parent_is_cycle():
    p = _project(outline=_ol({"id": "a", "kind": "unit", "title": "A", "parent_id": "a"}))
    assert any("döngü" in e.message for e in _outline_errors(p))


def test_validate_depth_over_three():
    p = _project(outline=_ol(
        {"id": "l1", "kind": "unit", "title": "1"},
        {"id": "l2", "kind": "section", "title": "2", "parent_id": "l1"},
        {"id": "l3", "kind": "section", "title": "3", "parent_id": "l2"},
        {"id": "l4", "kind": "section", "title": "4", "parent_id": "l3"},
    ))
    assert any("derinlik" in e.message for e in _outline_errors(p))


def test_validate_depth_three_ok():
    p = _project(outline=_ol(
        {"id": "l1", "kind": "unit", "title": "1"},
        {"id": "l2", "kind": "section", "title": "2", "parent_id": "l1"},
        {"id": "l3", "kind": "section", "title": "3", "parent_id": "l2"},
    ))
    assert _outline_errors(p) == []


def test_validate_duplicate_node_ids():
    p = _project(outline=_ol(
        {"id": "u1", "kind": "unit", "title": "A"},
        {"id": "u1", "kind": "unit", "title": "B"},
    ))
    assert any("Yinelenen" in e.message and "u1" in e.message for e in _outline_errors(p))


def test_validate_screen_node_id_dangling():
    screens = _screens()
    screens[1].node_id = "olmayan"
    p = _project(screens=screens,
                 outline=_ol({"id": "u1", "kind": "unit", "title": "A"}))
    errs = _outline_errors(p)
    assert any(".node_id" in (e.path or "") and "olmayan" in e.message for e in errs)


def test_validate_screen_node_id_without_outline_is_dangling():
    """node_id verilmiş ama outline hiç yok → sarkan referans (sert hata)."""
    screens = _screens()
    screens[1].node_id = "u1"
    p = _project(screens=screens)
    assert any(".node_id" in (e.path or "") for e in validate_project(p))


def test_validate_node_objective_conflicts_with_course_objective():
    """Outline hedefleri kurs hedef ad-alanına KAYDOLUR → id çakışması sert hata."""
    p = _project(
        objectives=[Objective(id="o1")],
        outline=_ol({"id": "u1", "kind": "unit", "title": "A",
                     "objective": {"id": "o1"}}),
    )
    assert any("hedef" in e.message and "o1" in e.message for e in _outline_errors(p))


def test_validate_node_objective_duplicate_across_nodes():
    p = _project(outline=_ol(
        {"id": "u1", "kind": "unit", "title": "A", "objective": {"id": "ox"}},
        {"id": "u2", "kind": "unit", "title": "B", "objective": {"id": "ox"}},
    ))
    assert any("ox" in e.message for e in _outline_errors(p))


def test_validate_valid_outline_zero_errors():
    screens = _screens()
    screens[0].node_id = "u1"
    screens[1].node_id = "b1"
    p = _project(screens=screens, outline=_ol(
        {"id": "u1", "kind": "unit", "title": "Ü1", "objective": {"id": "o_u1"}},
        {"id": "b1", "kind": "section", "title": "B1", "parent_id": "u1"},
    ))
    assert _outline_errors(p) == []


def test_validate_outline_absent_zero_new_output():
    """Outline yokken doğrulayıcı outline kaynaklı TEK kalem bile üretmez (geriye uyum)."""
    p = _project()
    all_errs = validate_project(p)
    assert [e for e in all_errs if "outline" in ((e.path or "") + e.message).lower()] == []


# --------------------------------------------------------------------------- #
# server.py — build_from_spec taşıması (objectives/source_item_count deseni)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_build_from_spec_carries_outline_and_audience_pack():
    """CourseSpec.outline + audience_pack + screen.node_id → Project'e AYNEN taşınır."""
    from fastmcp import Client

    import server

    spec = {
        "title": "Outline taşıma",
        "outline": [
            {"id": "u1", "kind": "unit", "title": "Ünite 1",
             "objective": {"id": "o_u1", "outcome_type": "knowledge"}},
            {"id": "b1", "parent_id": "u1", "kind": "section", "title": "Bölüm 1.1"},
        ],
        "audience_pack": "yetiskin",
        "screens": [
            {"type": "title_slide", "id": "t1", "title": "Başlık", "node_id": "u1"},
            {"type": "content_slide", "id": "c1", "title": "İçerik",
             "body_html": "<p>x</p>", "node_id": "b1"},
            {"type": "summary", "id": "s1", "title": "Özet"},
        ],
    }
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        assert res.data.status == "done"
        pid = res.data.project_id
    # auth kapalı test ortamında tüm projeler anonim yerel principal'a yazılır (conftest notu)
    p = await server.SVC.store.get_project(pid, "key_local")
    assert p is not None
    assert [n.id for n in p.outline] == ["u1", "b1"]
    assert p.outline[0].objective.id == "o_u1"
    assert p.outline[0].objective.outcome_type == "knowledge"
    assert p.audience_pack == "yetiskin"
    assert p.screens[0].node_id == "u1"
    assert p.screens[1].node_id == "b1"
    assert p.screens[2].node_id is None


@pytest.mark.asyncio
async def test_build_from_spec_rejects_dangling_node_id():
    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    import server

    spec = {
        "title": "Sarkan node_id",
        "outline": [{"id": "u1", "kind": "unit", "title": "Ü1"}],
        "screens": [
            {"type": "content_slide", "id": "c1", "title": "İçerik",
             "body_html": "<p>x</p>", "node_id": "olmayan"},
        ],
    }
    async with Client(server.mcp) as c:
        with pytest.raises(ToolError, match="node_id"):
            await c.call_tool("build_from_spec", {"spec": spec})
