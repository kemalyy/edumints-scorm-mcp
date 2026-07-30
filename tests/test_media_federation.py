"""tests/test_media_federation.py — Senaryo hattı Faz 3: medya federasyonu ÇEKİRDEK.

Kapsam (plan: docs/superpowers/plans/2026-07-30-scenario-line-plan.md, Kol B):
  - MIME sniffing (magic bytes) + kind↔MIME eşleşme kuralları
  - provenance normalizasyonu (verildiği gibi saklanır + generated_at sunucuda damgalanır)
  - kanıt-rolü a11y kapısı (alt_text; audio/video için transcript) — A11Y_NO_TEXT_ALT sınıfı
  - match_manifest: exact/fuzzy/ambiguous eşleştirme — YALNIZ metadata, deterministik sıra
  - provenance_records: dolu slot başına TEK kayıt, deterministik sıra
  - Sözleşme değişikliği: MediaSlot.fallback_image_asset_id (TEK ek — additive) +
    ScenarioDocument.assets (paralel AssetRef listesi — senaryo varlık evi)
  - gaps: model_3d + fallback_image_asset_id yok → SLOT_KIND_UNSUPPORTED warn
  - compile eşlemesi: data_chart → görsel-render (image alanları), model_3d → fallback görsel

Araç (MCP) testleri tests/test_media_tools.py'de; paket PROVENANCE.json testleri
tests/test_media_provenance.py'de.
"""

import base64

import pytest

from core.media_federation import (
    kind_matches_mime,
    match_manifest,
    missing_a11y,
    normalize_provenance,
    provenance_records,
    sniff_mime,
)
from core.project import AssetRef, Objective, OutlineNode
from core.scenario import MediaSlot, Page, ScenarioDocument, gaps_report

# 1x1 şeffaf PNG (67 bayt) — testlerde gerçek görsel baytı
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _doc(pages=None, assets=None) -> ScenarioDocument:
    return ScenarioDocument(
        id="scn_T", title="Senaryo", owner_key_id="key_local",
        outline=[OutlineNode(id="u1", kind="unit", title="Ünite",
                             objective=Objective(id="obj_u1", description="hedef"))],
        pages=pages or [], assets=assets or [],
    )


def _slot(**kw) -> MediaSlot:
    base = dict(slot_id="hucre_zari", role="aciklayici", kind="image",
                spec="Hücre zarı diyagramı")
    base.update(kw)
    return MediaSlot(**base)


def _page(**kw) -> Page:
    base = dict(id="p1", node_id="u1", order=0, title="Sayfa")
    base.update(kw)
    return Page(**base)


def _ref(aid="ast_1", sha="a" * 64, size=10) -> AssetRef:
    return AssetRef(id=aid, filename="f.png", mime="image/png",
                    size_bytes=size, sha256=sha, rel_path="assets/f.png")


# --------------------------------------------------------------------------- #
# Sözleşme değişikliği: fallback_image_asset_id (TEK ek) + ScenarioDocument.assets
# --------------------------------------------------------------------------- #
def test_mediaslot_fallback_image_additive_and_optional():
    s = _slot()
    assert s.fallback_image_asset_id is None  # additive: eski dokümanlar geçerli kalır
    s2 = _slot(kind="model_3d", fallback_image_asset_id="ast_fb")
    assert s2.fallback_image_asset_id == "ast_fb"


def test_scenario_document_assets_default_empty_and_roundtrip():
    d = _doc(assets=[_ref()])
    d2 = ScenarioDocument.model_validate_json(d.model_dump_json())
    assert d2.assets[0].id == "ast_1"
    assert _doc().assets == []  # eski dokümanlar (alan yok) doğrulanmaya devam eder


# --------------------------------------------------------------------------- #
# MIME sniffing (magic bytes)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("data,expected", [
    (PNG_1PX, "image/png"),
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
    (b"GIF89a\x01\x00", "image/gif"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    (b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"),
    (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image/svg+xml"),
    (b"ID3\x04\x00\x00\x00\x00\x00\x00", "audio/mpeg"),
    (b"\xff\xfb\x90\x00", "audio/mpeg"),
    (b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio/wav"),
    (b"OggS\x00\x02", "audio/ogg"),
    (b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00", "video/mp4"),
    (b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00", "audio/mp4"),
    (b"\x1a\x45\xdf\xa3\x00\x00", "video/webm"),
    (b'{"v":"5.5.7","layers":[],"assets":[]}', "application/json"),
    (b"glTF\x02\x00\x00\x00", "model/gltf-binary"),
    (b"\x00\x01\x02\x03tamamen bilinmeyen", "application/octet-stream"),
])
def test_sniff_mime(data, expected):
    assert sniff_mime(data) == expected


# --------------------------------------------------------------------------- #
# kind ↔ MIME kuralları (data_chart = görsel-render kararı burada görünür)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind,mime,ok", [
    ("image", "image/png", True),
    ("image", "image/svg+xml", True),
    ("image", "audio/mpeg", False),
    ("data_chart", "image/png", True),      # KARAR: data_chart slotu render edilmiş GÖRSEL taşır
    ("data_chart", "application/json", False),
    ("audio", "audio/mpeg", True),
    ("audio", "audio/mp4", True),
    ("audio", "video/mp4", False),
    ("video", "video/mp4", True),
    ("video", "image/png", False),
    ("lottie", "application/json", True),
    ("lottie", "image/png", False),
    ("model_3d", "model/gltf-binary", True),
    ("model_3d", "image/png", False),
    ("image", "application/octet-stream", False),  # tanınmayan bayt = uyuşmazlık (sert)
])
def test_kind_matches_mime(kind, mime, ok):
    assert kind_matches_mime(kind, mime) is ok


# --------------------------------------------------------------------------- #
# provenance normalizasyonu (plan §5.4: source, tool, ref, generated_at, license_note)
# --------------------------------------------------------------------------- #
def test_normalize_provenance_stamps_generated_at_when_absent():
    p = normalize_provenance({"source": "openverse", "tool": "search_images",
                              "license_note": "CC0"})
    assert p["source"] == "openverse"
    assert p["generated_at"]  # sunucu damgası (ISO-8601)
    assert "T" in p["generated_at"]


def test_normalize_provenance_keeps_given_generated_at_and_extra_keys():
    given = {"source": "dall-e", "generated_at": "2026-01-01T00:00:00+00:00",
             "ozel_alan": "aynen saklanır"}
    p = normalize_provenance(given)
    assert p["generated_at"] == "2026-01-01T00:00:00+00:00"  # verilen damga korunur
    assert p["ozel_alan"] == "aynen saklanır"                # verildiği gibi saklama


def test_normalize_provenance_none_yields_stamped_dict():
    p = normalize_provenance(None)
    assert set(p) == {"generated_at"}


def test_normalize_provenance_rejects_non_dict():
    with pytest.raises(ValueError):
        normalize_provenance("openverse")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# a11y kapısı — kanıt rolü: alt_text zorunlu; audio/video için transcript de
# --------------------------------------------------------------------------- #
def test_missing_a11y_kanit_requires_alt_text():
    assert missing_a11y("kanit", "image", None, None) == ["alt_text"]
    assert missing_a11y("kanit", "image", "hücre zarı", None) == []


def test_missing_a11y_kanit_audio_video_require_transcript_too():
    assert missing_a11y("kanit", "audio", None, None) == ["alt_text", "transcript_html"]
    assert missing_a11y("kanit", "video", "video özeti", None) == ["transcript_html"]
    assert missing_a11y("kanit", "video", "özet", "<p>transkript</p>") == []


def test_missing_a11y_aciklayici_role_not_gated():
    # açıklayıcı rolde fill engellenmez (E-A11Y taban denetimleri lint'te ayrıca çalışır)
    assert missing_a11y("aciklayici", "video", None, None) == []


# --------------------------------------------------------------------------- #
# match_manifest — YALNIZ metadata; deterministik; belirsizlik = aday listesi
# --------------------------------------------------------------------------- #
def _manifest_doc():
    return _doc(pages=[
        _page(id="p1", order=0, media_slots=[
            _slot(slot_id="hucre_zari", kind="image", spec="Hücre zarı diyagramı"),
            _slot(slot_id="mitoz_anlatim", kind="audio", spec="Mitoz seslendirme",
                  source_hint="stüdyo kaydı"),
        ]),
        _page(id="p2", order=1, media_slots=[
            _slot(slot_id="dolu_slot", asset_id="ast_var"),  # dolu → öneriye girmez
        ]),
    ])


def test_match_exact_filename_and_mime():
    r = match_manifest(_manifest_doc(), [
        {"name": "hucre-zari.png", "size": 6000, "sha256": "c" * 64, "mime": "image/png"},
        {"name": "mitoz_anlatim.mp3", "size": 90000, "sha256": "d" * 64, "mime": "audio/mpeg"},
    ])
    props = {p["slot_id"]: p for p in r["proposals"]}
    assert set(props) == {"hucre_zari", "mitoz_anlatim"}  # dolu slot önerilmez
    assert props["hucre_zari"]["proposed"] == "hucre-zari.png"
    assert props["mitoz_anlatim"]["proposed"] == "mitoz_anlatim.mp3"
    assert r["unmatched_files"] == []


def test_match_fuzzy_via_spec_tokens():
    r = match_manifest(_manifest_doc(), [
        {"name": "diyagram-hucre.png", "size": 500, "sha256": "e" * 64, "mime": "image/png"},
    ])
    props = {p["slot_id"]: p for p in r["proposals"]}
    cand = props["hucre_zari"]["candidates"]
    assert cand and cand[0]["name"] == "diyagram-hucre.png"
    assert cand[0]["score"] > 0
    # ses slotuna görsel aday DÜŞÜK/yok (mime uyuşmaz + token örtüşmez)
    assert all(c["name"] != "diyagram-hucre.png" for c in props["mitoz_anlatim"]["candidates"])


def test_match_ambiguous_no_auto_assignment():
    r = match_manifest(_manifest_doc(), [
        {"name": "hucre-zari-v1.png", "size": 500, "sha256": "1" * 64, "mime": "image/png"},
        {"name": "hucre-zari-v2.png", "size": 700, "sha256": "2" * 64, "mime": "image/png"},
    ])
    props = {p["slot_id"]: p for p in r["proposals"]}
    hz = props["hucre_zari"]
    assert hz["proposed"] is None            # belirsiz → OTOMATİK atama YOK
    assert len(hz["candidates"]) == 2        # skorlu aday listesi
    assert all("score" in c and "reasons" in c for c in hz["candidates"])


def test_match_already_ingested_flagged_for_dedup():
    doc = _manifest_doc()
    doc.assets.append(_ref(aid="ast_x", sha="f" * 64))
    r = match_manifest(doc, [
        {"name": "hucre-zari.png", "size": 6000, "sha256": "f" * 64, "mime": "image/png"},
    ])
    props = {p["slot_id"]: p for p in r["proposals"]}
    reasons = props["hucre_zari"]["candidates"][0]["reasons"]
    assert any("dedup" in x for x in reasons)


def test_match_size_suspect_flagged():
    r = match_manifest(_manifest_doc(), [
        {"name": "hucre-zari.png", "size": 0, "sha256": "9" * 64, "mime": "image/png"},
    ])
    props = {p["slot_id"]: p for p in r["proposals"]}
    reasons = props["hucre_zari"]["candidates"][0]["reasons"]
    assert any("size" in x for x in reasons)


def test_match_deterministic_ordering():
    files = [
        {"name": "b-hucre-zari.png", "size": 10, "sha256": "3" * 64, "mime": "image/png"},
        {"name": "a-hucre-zari.png", "size": 10, "sha256": "4" * 64, "mime": "image/png"},
    ]
    r1 = match_manifest(_manifest_doc(), files)
    r2 = match_manifest(_manifest_doc(), list(reversed(files)))
    assert r1 == r2  # girdi sırasından bağımsız — kararlı çıktı
    names = [c["name"] for c in
             {p["slot_id"]: p for p in r1["proposals"]}["hucre_zari"]["candidates"]]
    assert names == sorted(names)  # eşit skor → ada göre


def test_match_unmatched_files_listed():
    r = match_manifest(_manifest_doc(), [
        {"name": "alakasiz-belge.pdf", "size": 100, "sha256": "5" * 64,
         "mime": "application/pdf"},
    ])
    assert r["unmatched_files"] == ["alakasiz-belge.pdf"]


# --------------------------------------------------------------------------- #
# provenance_records — dolu slot başına TEK kayıt, deterministik sıra
# --------------------------------------------------------------------------- #
def test_provenance_records_one_per_filled_slot_ordered():
    doc = _doc(
        pages=[
            _page(id="p2", order=1, media_slots=[
                _slot(slot_id="s21", asset_id="ast_2",
                      provenance={"source": "upload", "generated_at": "2026-01-01T00:00:00+00:00"}),
            ]),
            _page(id="p1", order=0, media_slots=[
                _slot(slot_id="s11", asset_id="ast_1", provenance={"source": "openverse"}),
                _slot(slot_id="s12"),  # boş slot → kayıt YOK
            ]),
        ],
        assets=[_ref(aid="ast_1", sha="a" * 64), _ref(aid="ast_2", sha="b" * 64)],
    )
    recs = provenance_records(doc)
    assert [(r["page_id"], r["slot_id"]) for r in recs] == [("p1", "s11"), ("p2", "s21")]
    assert recs[0]["asset_id"] == "ast_1"
    assert recs[0]["sha256"] == "a" * 64
    assert recs[0]["provenance"] == {"source": "openverse"}
    assert recs[1]["role"] == "aciklayici" and recs[1]["kind"] == "image"


def test_provenance_records_empty_for_no_filled_slots():
    assert provenance_records(_doc(pages=[_page(media_slots=[_slot()])])) == []


# --------------------------------------------------------------------------- #
# gaps: SLOT_KIND_UNSUPPORTED (model_3d, fallback_image_asset_id yok) — warn
# --------------------------------------------------------------------------- #
def test_gaps_model_3d_without_fallback_warns():
    doc = _doc(pages=[_page(media_slots=[_slot(slot_id="molekul", kind="model_3d")])])
    r = gaps_report(doc)
    codes = [w["code"] for w in r["warnings"]]
    assert "SLOT_KIND_UNSUPPORTED" in codes
    w = next(w for w in r["warnings"] if w["code"] == "SLOT_KIND_UNSUPPORTED")
    assert "fallback_image_asset_id" in w["message"]


def test_gaps_model_3d_with_fallback_no_warn():
    doc = _doc(pages=[_page(media_slots=[
        _slot(slot_id="molekul", kind="model_3d", fallback_image_asset_id="ast_fb")])])
    codes = [w["code"] for w in gaps_report(doc)["warnings"]]
    assert "SLOT_KIND_UNSUPPORTED" not in codes


# --------------------------------------------------------------------------- #
# compile eşlemesi — kind → ekran alanı (data_chart görsel-render, model_3d fallback)
# --------------------------------------------------------------------------- #
def _compiled_screen(page):
    from core.scenario import compile_scenario
    spec, warnings = compile_scenario(_doc(pages=[page]))
    return spec["screens"][0], warnings, spec


def test_compile_image_slot_maps_to_media_asset_id_with_alt():
    scr, _, _ = _compiled_screen(_page(
        screen_type="content_slide",
        media_slots=[_slot(asset_id="ast_img",
                           a11y={"alt_text": "hücre zarı diyagramı"})]))
    assert scr["media_asset_id"] == "ast_img"
    assert scr["media_alt"] == "hücre zarı diyagramı"


def test_compile_data_chart_slot_maps_as_image_render():
    # KARAR: data_chart slotu = render edilmiş görsel → image alanlarına bağlanır
    # (data_chart EKRANI veri taşır, asset değil — orada bağlanmaz, SLOT_NOT_ATTACHED).
    scr, warnings, _ = _compiled_screen(_page(
        screen_type="content_slide",
        media_slots=[_slot(slot_id="grafik", kind="data_chart", asset_id="ast_chart",
                           a11y={"alt_text": "yıllara göre bölünme hızı"})]))
    assert scr["media_asset_id"] == "ast_chart"
    assert not [w for w in warnings if w["code"] == "SLOT_KIND_UNSUPPORTED"]


def test_compile_data_chart_slot_on_data_chart_screen_not_attached():
    scr, warnings, _ = _compiled_screen(_page(
        screen_type="data_chart",
        screen_payload={"chart_type": "bar",
                        "data": [{"label": "2020", "value": 3}]},
        media_slots=[_slot(slot_id="grafik", kind="data_chart", asset_id="ast_chart")]))
    assert "media_asset_id" not in scr  # data_chart ekranı veri taşır, asset değil
    assert [w["code"] for w in warnings] == ["SLOT_NOT_ATTACHED"]


def test_compile_model_3d_with_fallback_attaches_fallback_image():
    scr, warnings, _ = _compiled_screen(_page(
        screen_type="content_slide",
        media_slots=[_slot(slot_id="molekul", kind="model_3d", asset_id="ast_glb",
                           fallback_image_asset_id="ast_fb",
                           a11y={"alt_text": "molekül görünümü"})]))
    assert scr["media_asset_id"] == "ast_fb"  # render yolu = fallback görsel
    assert scr["media_alt"] == "molekül görünümü"
    assert not [w for w in warnings if w["code"] == "SLOT_KIND_UNSUPPORTED"]


def test_compile_model_3d_without_fallback_warns_and_skips():
    scr, warnings, _ = _compiled_screen(_page(
        screen_type="content_slide",
        media_slots=[_slot(slot_id="molekul", kind="model_3d", asset_id="ast_glb")]))
    assert "media_asset_id" not in scr
    assert "SLOT_KIND_UNSUPPORTED" in [w["code"] for w in warnings]


def test_compile_kanit_slot_page_stays_evidence_capable():
    """role=kanit slot taşıyan sayfa derlemede kanıt-yeteneğini KORUR: content_slide +
    media = koşullu kanıt hedefi (E1 ile hizalı) — antislop._is_evidentiary_target True."""
    from pydantic import TypeAdapter

    from core.antislop import _is_evidentiary_target
    from core.project import Project, Screen
    from core.scenario import parse_evidence

    page = _page(
        screen_type="content_slide",
        media_slots=[_slot(role="kanit", asset_id="ast_img",
                           a11y={"alt_text": "işaretli mikroskop görüntüsü"})],
        evidence=parse_evidence({"kind": "anotasyonlu_artefakt",
                                 "artefakt_ref": "hucre_zari",
                                 "anotasyonlar": ["zar çift katmanlı"]}),
    )
    scr, _, _ = _compiled_screen(page)
    screen = TypeAdapter(Screen).validate_python(scr)
    project = Project(id="proj_t", title="T", screens=[screen], owner_key_id="key_local")
    assert _is_evidentiary_target(screen, project) is True
