"""tests/test_scenario.py — Senaryo hattı Faz 2: senaryo dokümanı şeması + store + miras.

Kapsam (plan: docs/superpowers/plans/2026-07-30-scenario-line-plan.md, Faz 2):
  - Page / MediaSlot / EvidenceDecl (oneOf zorunlu alt alanlar) / ScenarioDocument modelleri
  - EvidenceDecl discriminated union: her kanıt türünün ZORUNLU alt alanları (kabul: oneOf)
  - Store: scenarios tablosu roundtrip + sahiplik + kota-boyut
  - Miras: objective en-yakın-atadan (nearest wins) / ORPHAN_PAGE
  - MCP araçları: create/upsert_node/upsert_page/reorder/tree/delete_* akışları

NOT: gaps ayrıntıları tests/test_scenario_gaps.py, compile tests/test_scenario_compile.py.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from core.project import Objective, OutlineNode
from core.scenario import (
    MediaSlot,
    Page,
    ScenarioDocument,
    compiled_objective_ids,
    inherited_objective,
    new_page_id,
    new_scenario_id,
    parse_evidence,
    resolve_pedagogy_pack,
)


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _outline():
    return [
        OutlineNode(id="u1", kind="unit", title="Ünite 1",
                    objective=Objective(id="obj_u1", description="üst hedef"),
                    pedagogy_pack="gagne-9"),
        OutlineNode(id="s1", parent_id="u1", kind="section", title="Bölüm 1.1",
                    objective=Objective(id="obj_s1", description="yakın hedef")),
        OutlineNode(id="s2", parent_id="u1", kind="section", title="Bölüm 1.2"),
        OutlineNode(id="u2", kind="unit", title="Ünite 2 (hedefsiz)"),
    ]


def _page(**kw) -> Page:
    base = dict(id="p1", node_id="s1", order=0, title="Sayfa")
    base.update(kw)
    return Page(**base)


def _doc(**kw) -> ScenarioDocument:
    base = dict(id="scn_T", title="Senaryo", outline=_outline(), pages=[],
                owner_key_id="key_local")
    base.update(kw)
    return ScenarioDocument(**base)


# --------------------------------------------------------------------------- #
# Model: id üreticileri + ScenarioDocument
# --------------------------------------------------------------------------- #
def test_id_generators_prefixes():
    assert new_scenario_id().startswith("scn_")
    assert new_page_id().startswith("pg_")


def test_document_defaults_and_version():
    d = _doc()
    assert d.schema_version == 1
    assert d.audience_pack is None
    assert d.duration_target_sec is None
    assert d.dial_overrides is None
    assert d.pages == []


def test_document_roundtrip_json():
    d = _doc(pages=[_page(copy={"body_md": "# başlık\n\nmetin"})],
             audience_pack="k12-lise", duration_target_sec=600,
             dial_overrides={"ton": "resmi"})
    d2 = ScenarioDocument.model_validate_json(d.model_dump_json())
    assert d2 == d


# --------------------------------------------------------------------------- #
# Model: Page + MediaSlot
# --------------------------------------------------------------------------- #
def test_page_minimal_defaults():
    p = _page()
    assert p.phase is None
    assert p.screen_type is None
    assert p.copy.body_md is None
    assert p.copy.narration is None
    assert p.media_slots == []
    assert p.evidence is None
    assert p.evidence_from == []
    assert p.scoring.scored is False
    assert p.scoring.points is None
    assert p.extra_objective_refs == []
    assert p.duration_hint_sec is None
    assert p.notes is None


def test_media_slot_shape_faz3_contract():
    s = MediaSlot(slot_id="m1", role="kanit", kind="image", spec="hücre diyagramı")
    assert s.source_hint is None
    assert s.asset_id is None
    assert s.a11y.alt_text is None
    assert s.a11y.transcript_html is None
    assert s.a11y.captions_asset_id is None
    assert s.provenance is None


def test_media_slot_role_and_kind_enums():
    with pytest.raises(PydanticValidationError):
        MediaSlot(slot_id="m1", role="dekoratif", kind="image", spec="x")  # dekoratif YOK (3.6)
    with pytest.raises(PydanticValidationError):
        MediaSlot(slot_id="m1", role="kanit", kind="hologram", spec="x")


def test_page_id_machine_friendly():
    with pytest.raises(PydanticValidationError):
        _page(id="boşluklu id")


# --------------------------------------------------------------------------- #
# Model: EvidenceDecl — oneOf (her türün ZORUNLU alt alanları)
# --------------------------------------------------------------------------- #
def test_evidence_islenmis_ornek_requires_two_steps():
    ev = parse_evidence({"kind": "islenmis_ornek", "steps": [
        {"action": "a1", "reasoning": "r1"}, {"action": "a2", "reasoning": "r2"}]})
    assert ev.kind == "islenmis_ornek"
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "islenmis_ornek",
                        "steps": [{"action": "a1", "reasoning": "r1"}]})  # min 2
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "islenmis_ornek",
                        "steps": [{"action": "a1"}, {"action": "a2"}]})  # reasoning zorunlu


def test_evidence_karsit_cift_required_fields():
    ev = parse_evidence({"kind": "karsit_cift", "dogru": "d", "bozuk": "b", "fark": "f"})
    assert ev.fark == "f"
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "karsit_cift", "dogru": "d", "bozuk": "b"})  # fark yok


def test_evidence_anotasyonlu_artefakt_required_fields():
    ev = parse_evidence({"kind": "anotasyonlu_artefakt", "artefakt_ref": "m1",
                         "anotasyonlar": ["ok işareti: giriş noktası"]})
    assert ev.artefakt_ref == "m1"
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "anotasyonlu_artefakt", "artefakt_ref": "m1",
                        "anotasyonlar": []})  # min 1


def test_evidence_ogrenci_kesfi_required_fields():
    ev = parse_evidence({"kind": "ogrenci_kesfi",
                         "kayit_yontemi": "tahminini yaz, sonra deneyle karşılaştır",
                         "commit_prompt": "Sence ne olur?"})
    assert ev.commit_prompt
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "ogrenci_kesfi", "kayit_yontemi": "x"})  # commit_prompt yok


def test_evidence_hatali_ornek_required_fields():
    ev = parse_evidence({"kind": "hatali_ornek", "hata": "h",
                         "neden_yanlis": "n", "dogru_karsilik": "d"})
    assert ev.dogru_karsilik == "d"
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "hatali_ornek", "hata": "h", "neden_yanlis": "n"})


def test_evidence_unknown_kind_rejected():
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "serbest_metin"})


def test_evidence_oneof_cross_fields_rejected():
    """oneOf gerçekten ayrık: bir türün alanı diğerine sızamaz (extra=forbid)."""
    with pytest.raises(PydanticValidationError):
        parse_evidence({"kind": "karsit_cift", "dogru": "d", "bozuk": "b", "fark": "f",
                        "steps": [{"action": "a", "reasoning": "r"}]})


def test_page_with_evidence_discriminates():
    p = _page(evidence={"kind": "hatali_ornek", "hata": "h", "neden_yanlis": "n",
                        "dogru_karsilik": "d"})
    assert p.evidence.kind == "hatali_ornek"
    p2 = Page.model_validate_json(p.model_dump_json())
    assert p2.evidence == p.evidence
    assert p2.evidence.kind == "hatali_ornek"


# --------------------------------------------------------------------------- #
# Miras: objective en-yakın-atadan + ORPHAN
# --------------------------------------------------------------------------- #
def test_inherited_objective_nearest_wins():
    """s1'in kendi hedefi u1'inkini gölgeler (iki atalı zincirde EN YAKIN kazanır)."""
    d = _doc()
    assert inherited_objective(d, _page(node_id="s1")).id == "obj_s1"


def test_inherited_objective_walks_up():
    """s2'nin hedefi yok → u1'den miras."""
    d = _doc()
    assert inherited_objective(d, _page(node_id="s2")).id == "obj_u1"


def test_inherited_objective_orphan_none():
    """u2 zincirinde hiç hedef yok → None (gaps bunu ORPHAN_PAGE yapar)."""
    d = _doc()
    assert inherited_objective(d, _page(node_id="u2")) is None


def test_inherited_objective_dangling_node_none():
    d = _doc()
    assert inherited_objective(d, _page(node_id="yok")) is None


def test_compiled_objective_ids_inherited_plus_extra_dedup_stable():
    d = _doc()
    p = _page(node_id="s2", extra_objective_refs=["obj_s1", "obj_u1", "obj_s1"])
    # miras (obj_u1) önce; extra'lar beyan sırasıyla; dedup (obj_u1 ve tekrar obj_s1 düşer)
    assert compiled_objective_ids(d, p) == ["obj_u1", "obj_s1"]


def test_resolve_pedagogy_pack_nearest():
    d = _doc()
    assert resolve_pedagogy_pack(d, _page(node_id="s1")) == "gagne-9"  # u1'den miras
    assert resolve_pedagogy_pack(d, _page(node_id="u2")) is None


# --------------------------------------------------------------------------- #
# Store: scenarios tablosu — roundtrip + sahiplik + boyut
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_store_scenario_roundtrip(tmp_path):
    from core.store import create_store

    st = create_store(str(tmp_path / "t.db"), str(tmp_path / "data"))
    await st.init()
    d = _doc(id=new_scenario_id(), owner_key_id="key_A",
             pages=[_page(copy={"body_md": "m"})])
    await st.create_scenario(d)
    got = await st.get_scenario(d.id, "key_A")
    assert got == d

    got.title = "Yeni Başlık"
    await st.update_scenario(got)
    again = await st.get_scenario(d.id, "key_A")
    assert again.title == "Yeni Başlık"
    await st.close()


@pytest.mark.asyncio
async def test_store_scenario_ownership_isolated(tmp_path):
    from core.store import create_store

    st = create_store(str(tmp_path / "t.db"), str(tmp_path / "data"))
    await st.init()
    d = _doc(id=new_scenario_id(), owner_key_id="key_A")
    await st.create_scenario(d)
    assert await st.get_scenario(d.id, "key_B") is None  # yabancı anahtar göremez
    assert await st.get_scenario(d.id, "key_A") is not None
    await st.close()


@pytest.mark.asyncio
async def test_store_scenario_size_counts_into_total_bytes(tmp_path):
    from core.store import create_store

    st = create_store(str(tmp_path / "t.db"), str(tmp_path / "data"))
    await st.init()
    before = await st.total_bytes("key_A")
    d = _doc(id=new_scenario_id(), owner_key_id="key_A",
             pages=[_page(copy={"body_md": "x" * 2000})])
    await st.create_scenario(d)
    after = await st.total_bytes("key_A")
    assert after > before
    assert after >= 2000  # doküman gövdesi kotaya sayılır
    await st.close()


# --------------------------------------------------------------------------- #
# MCP araçları — create/upsert/tree/reorder/delete akışları
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tool_create_and_tree():
    import server

    await server.SVC.ensure()
    from fastmcp import Client

    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "Hücre Bölünmesi",
            "outline": [n.model_dump() for n in _outline()],
        })
        sid = r.data["scenario_id"]
        assert sid.startswith("scn_")

        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "p1", "node_id": "s1", "title": "Giriş",
                     "screen_type": "content_slide"},
        })
        t = await c.call_tool("scenario_tree", {"scenario_id": sid})
        tree = t.data
        assert tree["title"] == "Hücre Bölünmesi"
        u1 = next(n for n in tree["nodes"] if n["id"] == "u1")
        s1 = next(n for n in u1["children"] if n["id"] == "s1")
        assert [p["id"] for p in s1["pages"]] == ["p1"]
        assert tree["page_count"] == 1
        assert tree["node_count"] == 4


@pytest.mark.asyncio
async def test_tool_create_rejects_broken_outline():
    import server
    from fastmcp.exceptions import ToolError as MCPToolError

    await server.SVC.ensure()
    from fastmcp import Client

    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError):
            await c.call_tool("create_scenario", {
                "title": "Bozuk",
                "outline": [{"id": "a", "parent_id": "yok", "kind": "unit", "title": "A"}],
            })


@pytest.mark.asyncio
async def test_tool_upsert_node_and_page_update_in_place():
    import server
    from fastmcp import Client

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "T", "outline": [{"id": "u1", "kind": "unit", "title": "Eski"}]})
        sid = r.data["scenario_id"]
        await c.call_tool("scenario_upsert_node", {
            "scenario_id": sid, "node": {"id": "u1", "kind": "unit", "title": "Yeni"}})
        pr = await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid, "page": {"node_id": "u1", "title": "P"}})
        pid = pr.data["page_id"]
        assert pid.startswith("pg_")
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid, "page": {"id": pid, "node_id": "u1", "title": "P2"}})
        t = await c.call_tool("scenario_tree", {"scenario_id": sid})
        u1 = next(n for n in t.data["nodes"] if n["id"] == "u1")
        assert u1["title"] == "Yeni"
        assert u1["pages"][0]["title"] == "P2"
        assert t.data["page_count"] == 1


@pytest.mark.asyncio
async def test_tool_reorder_pages():
    import server
    from fastmcp import Client
    from fastmcp.exceptions import ToolError as MCPToolError

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "T", "outline": [{"id": "u1", "kind": "unit", "title": "U"}]})
        sid = r.data["scenario_id"]
        for pid in ("a", "b", "c"):
            await c.call_tool("scenario_upsert_page", {
                "scenario_id": sid, "page": {"id": pid, "node_id": "u1", "title": pid}})
        await c.call_tool("scenario_reorder", {
            "scenario_id": sid, "page_ids_in_order": ["c", "a", "b"]})
        t = await c.call_tool("scenario_tree", {"scenario_id": sid})
        u1 = next(n for n in t.data["nodes"] if n["id"] == "u1")
        assert [p["id"] for p in u1["pages"]] == ["c", "a", "b"]
        # eksik/fazla liste reddedilir
        with pytest.raises(MCPToolError):
            await c.call_tool("scenario_reorder", {
                "scenario_id": sid, "page_ids_in_order": ["a", "b"]})


@pytest.mark.asyncio
async def test_tool_delete_node_refuse_then_reparent():
    import server
    from fastmcp import Client
    from fastmcp.exceptions import ToolError as MCPToolError

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "T", "outline": [n.model_dump() for n in _outline()]})
        sid = r.data["scenario_id"]
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid, "page": {"id": "p1", "node_id": "s1", "title": "P"}})
        # u1'in çocukları var → varsayılan strategy=refuse reddeder
        with pytest.raises(MCPToolError):
            await c.call_tool("scenario_delete_node", {"scenario_id": sid, "node_id": "u1"})
        # s1 sil (reparent): p1 sayfası u1'e taşınır
        await c.call_tool("scenario_delete_node", {
            "scenario_id": sid, "node_id": "s1", "strategy": "reparent"})
        t = await c.call_tool("scenario_tree", {"scenario_id": sid})
        u1 = next(n for n in t.data["nodes"] if n["id"] == "u1")
        assert [p["id"] for p in u1["pages"]] == ["p1"]
        assert all(n["id"] != "s1" for n in u1["children"])


@pytest.mark.asyncio
async def test_tool_delete_root_node_with_pages_reparent_refused():
    """Kök düğüme bağlı sayfa, reparent'ta ebeveynsiz kalırdı (node_id zorunlu) → hata."""
    import server
    from fastmcp import Client
    from fastmcp.exceptions import ToolError as MCPToolError

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "T", "outline": [{"id": "u1", "kind": "unit", "title": "U"}]})
        sid = r.data["scenario_id"]
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid, "page": {"id": "p1", "node_id": "u1", "title": "P"}})
        with pytest.raises(MCPToolError):
            await c.call_tool("scenario_delete_node", {
                "scenario_id": sid, "node_id": "u1", "strategy": "reparent"})


@pytest.mark.asyncio
async def test_tool_delete_page_cleans_evidence_from():
    """Sayfa silme, ona işaret eden evidence_from referanslarını TEMİZLER (sarkma değil,
    boşalan alan gaps'te blocker olur — plan Faz 2)."""
    import server
    from fastmcp import Client

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "T", "outline": [
                {"id": "u1", "kind": "unit", "title": "U",
                 "objective": {"id": "obj1"}}]})
        sid = r.data["scenario_id"]
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "ev1", "node_id": "u1", "title": "Kanıt",
                     "evidence": {"kind": "hatali_ornek", "hata": "h",
                                  "neden_yanlis": "n", "dogru_karsilik": "d"}}})
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "q1", "node_id": "u1", "title": "Soru",
                     "scoring": {"scored": True}, "evidence_from": ["ev1"]}})
        await c.call_tool("scenario_delete_page", {"scenario_id": sid, "page_id": "ev1"})
        g = await c.call_tool("scenario_gaps", {"scenario_id": sid})
        codes = {b["code"] for b in g.data["blockers"]}
        # ev1 referansı sarkmıyor (DANGLING yok); boşalan evidence_from blocker'ı VAR
        assert "DANGLING_EVIDENCE_FROM" not in codes
        assert "SCORED_NO_EVIDENCE_FROM" in codes


@pytest.mark.asyncio
async def test_tool_scenario_ownership_not_found_for_stranger(tmp_path, monkeypatch):
    """Sahiplik: araçlar yabancı senaryoyu not_found ile reddeder (projelerle aynı idiom)."""
    import server
    from fastmcp import Client
    from fastmcp.exceptions import ToolError as MCPToolError

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {"title": "T", "outline": [
            {"id": "u1", "kind": "unit", "title": "U"}]})
        sid = r.data["scenario_id"]
    # dokümanı başka sahibe taşı → aynı (key_local) istemci artık göremez
    assert await server.SVC.store.get_scenario(sid, "key_local") is not None
    await server.SVC.store.db.execute(
        "UPDATE scenarios SET owner_key_id='key_other' WHERE id=?", (sid,))
    await server.SVC.store.db.commit()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError):
            await c.call_tool("scenario_tree", {"scenario_id": sid})


# --------------------------------------------------------------------------- #
# Geriye uyum (kabul #5): senaryo araçları yokken mevcut akışlar dokunulmadı
# --------------------------------------------------------------------------- #
def test_backward_compat_no_new_fields_on_existing_models():
    """Faz 2 mevcut modellere ALAN EKLEMEZ: Project/CourseSpec/ScreenBase alan kümeleri
    Faz 1 sonrası halleriyle aynı kalır (senaryo dokümanı ayrı tablodadır)."""
    from core.project import CourseSpec, Project, ScreenBase

    for model in (Project, CourseSpec, ScreenBase):
        assert not any("scenario" in f or "page" in f for f in model.model_fields), model


def test_backward_compat_plain_project_validates_unchanged(examples_dir):
    import json
    import os

    from core.project import CourseSpec, Project
    from core.validator import validate_project

    spec = CourseSpec.model_validate(
        json.load(open(os.path.join(examples_dir, "small.json"), encoding="utf-8")))
    p = Project(id="proj_T", title=spec.title, screens=spec.screens,
                objectives=spec.objectives, owner_key_id="k")
    for i, s in enumerate(p.screens):
        if not s.id:
            s.id = f"scr_{i}"
    assert [e for e in validate_project(p) if "scenario" in (e.path or "")] == []
