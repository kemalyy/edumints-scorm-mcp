"""tests/test_conformance.py — Faz 1: imsmanifest.xml resmi XSD conformance.

Üretilen 1.2 ve 2004 manifestleri resmi ADL/IMS XSD'lerine karşı doğrulanır (offline, no_network).
Şemalar çevrimdışı (fetch edilemez) ise test atlanır — schema_unavailable bloklamayan uyarıdır.
"""

import pytest

from core.manifest import (
    NS_ADLCP_12,
    NS_ADLCP_2004,
    NS_IMSMD_12,
    NS_IMSMD_2004,
    NS_IMSSS,
    build_manifest,
)
from core.project import (
    Choice,
    ContentSlide,
    CourseMetadata,
    MCQScreen,
    Objective,
    Project,
    new_project_id,
)


def _proj(ver: str, passing_score: int | None = None, metadata: CourseMetadata | None = None,
          objectives: list[Objective] | None = None,
          bind: dict[str, list[str]] | None = None) -> Project:
    p = Project(id=new_project_id(), title=f"Conformance {ver}", scorm_version=ver)
    p.screens = [
        ContentSlide(id="c", title="İçerik", body_html="<p>Merhaba</p>"),
        MCQScreen(id="q", title="Soru", prompt_html="<p>?</p>",
                  options=[Choice(id="a", text_html="1", correct=True),
                           Choice(id="b", text_html="2")]),
    ]
    if passing_score is not None:
        p.tracking.passing_score = passing_score
    if metadata is not None:
        p.metadata = metadata
    if objectives is not None:
        p.objectives = objectives
        for s in p.screens:
            if s.id in (bind or {}):
                s.objective_ids = (bind or {})[s.id]
    return p


_FULL_METADATA = CourseMetadata(
    description="Kapsamlı bir örnek kurs açıklaması.",
    keywords=["scorm", "e-öğrenme"],
    intended_audience="Yeni başlayan yöneticiler",
    typical_learning_time="PT1H30M",
)


@pytest.mark.parametrize("ver,passing_score,metadata", [
    ("1.2", 80, None), ("1.2", 0, None), ("1.2", 80, _FULL_METADATA),
    ("2004", 80, None), ("2004", 0, None), ("2004", 80, _FULL_METADATA),
])
def test_manifest_xsd_valid(ver, passing_score, metadata, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))  # izole şema cache
    import core.schema_validate as sv
    sv._compiled_schema.cache_clear()
    from core.schema_validate import validate_manifest_xsd, SCHEMA_UNAVAILABLE, CONFORMANCE_ERROR
    p = _proj(ver, passing_score, metadata)
    xml = build_manifest(p, file_list=["index.html", "runtime/scorm-again.min.js"]).encode()
    errs = validate_manifest_xsd(xml, ver)
    if any(e.code == SCHEMA_UNAVAILABLE for e in errs):
        pytest.skip("SCORM XSD şemaları çevrimdışı — fetch edilemedi")
    conf = [e for e in errs if e.code == CONFORMANCE_ERROR]
    assert conf == [], f"{ver}/{passing_score}/metadata={metadata is not None} XSD ihlali: {[e.message for e in conf]}"
    sv._compiled_schema.cache_clear()


# --------------------------------------------------------------------------- #
# 2.1 (S6) — geçme notu manifest'e: adlcp:masteryscore (1.2) /
# adlcp:completionThreshold + imsss:sequencing→objectives→primaryObjective→
# minNormalizedMeasure (2004). passing_score 0/yok → hiçbiri basılmaz.
# --------------------------------------------------------------------------- #
def _item(xml_bytes: bytes):
    from lxml import etree
    root = etree.fromstring(xml_bytes)
    return root.find(".//{*}organizations/{*}organization/{*}item")


def test_masteryscore_12_present_when_passing_score_set():
    from lxml import etree
    p = _proj("1.2", 75)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    tags = [etree.QName(c).localname for c in item]
    assert tags == ["title", "masteryscore"], tags
    ms = item.find(f"{{{NS_ADLCP_12}}}masteryscore")
    assert ms is not None and ms.text == "75"


def test_masteryscore_12_absent_when_passing_score_zero():
    from lxml import etree
    p = _proj("1.2", 0)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    assert item.find(f"{{{NS_ADLCP_12}}}masteryscore") is None
    tags = [etree.QName(c).localname for c in item]
    assert tags == ["title"]


def test_2004_completion_and_sequencing_present_when_passing_score_set():
    from lxml import etree
    p = _proj("2004", 80)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    tags = [etree.QName(c).localname for c in item]
    assert tags == ["title", "completionThreshold", "sequencing"], tags

    ct = item.find(f"{{{NS_ADLCP_2004}}}completionThreshold")
    assert ct is not None and ct.text == "0.8"

    seq = item.find(f"{{{NS_IMSSS}}}sequencing")
    assert seq is not None
    # [6022] — leaf item'a controlMode EKLENMEZ.
    assert seq.find(f"{{{NS_IMSSS}}}controlMode") is None

    primary = seq.find(f"{{{NS_IMSSS}}}objectives/{{{NS_IMSSS}}}primaryObjective")
    assert primary is not None
    mnm = primary.find(f"{{{NS_IMSSS}}}minNormalizedMeasure")
    assert mnm is not None and mnm.text == "0.8"


def test_2004_completion_and_sequencing_absent_when_passing_score_zero():
    from lxml import etree
    p = _proj("2004", 0)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    assert item.find(f"{{{NS_ADLCP_2004}}}completionThreshold") is None
    assert item.find(f"{{{NS_IMSSS}}}sequencing") is None
    tags = [etree.QName(c).localname for c in item]
    assert tags == ["title"]


# --------------------------------------------------------------------------- #
# review Important-1 — masteryscore/completionThreshold+sequencing YALNIZ ≥1 puanlı
# ekranı (QUIZ_TYPES) olan kurslarda basılmalı. Aksi halde varsayılan passing_score=80
# ile içerik-only kurslarda masteryscore basılır ama runtime hiç score.raw yazmadığından
# eski 1.2 LMS mastery-override "completed"i "failed"a çevirir (geriye-dönük regresyon).
# --------------------------------------------------------------------------- #
def _content_only_proj(ver: str) -> Project:
    p = Project(id=new_project_id(), title=f"İçerik-only {ver}", scorm_version=ver)
    p.screens = [ContentSlide(id="c1", title="İçerik 1", body_html="<p>Merhaba</p>"),
                 ContentSlide(id="c2", title="İçerik 2", body_html="<p>Devam</p>")]
    # passing_score dokunulmadı → Tracking varsayılanı 80 (bkz. core/project.py Tracking)
    return p


def test_12_no_masteryscore_when_no_scored_screens_default_passing_score():
    from lxml import etree
    p = _content_only_proj("1.2")
    assert p.tracking.passing_score == 80  # varsayılan hâlâ 80 — regresyon buradan doğuyordu
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    assert item.find(f"{{{NS_ADLCP_12}}}masteryscore") is None
    tags = [etree.QName(c).localname for c in item]
    assert tags == ["title"]


def test_2004_no_completion_or_sequencing_when_no_scored_screens_default_passing_score():
    from lxml import etree
    p = _content_only_proj("2004")
    assert p.tracking.passing_score == 80
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    assert item.find(f"{{{NS_ADLCP_2004}}}completionThreshold") is None
    assert item.find(f"{{{NS_IMSSS}}}sequencing") is None
    tags = [etree.QName(c).localname for c in item]
    assert tags == ["title"]


@pytest.mark.parametrize("ver", ["1.2", "2004"])
def test_manifest_xsd_valid_content_only_default_passing_score(ver, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import core.schema_validate as sv
    sv._compiled_schema.cache_clear()
    from core.schema_validate import validate_manifest_xsd, SCHEMA_UNAVAILABLE, CONFORMANCE_ERROR
    p = _content_only_proj(ver)
    xml = build_manifest(p, file_list=["index.html", "runtime/scorm-again.min.js"]).encode()
    errs = validate_manifest_xsd(xml, ver)
    if any(e.code == SCHEMA_UNAVAILABLE for e in errs):
        pytest.skip("SCORM XSD şemaları çevrimdışı — fetch edilemedi")
    conf = [e for e in errs if e.code == CONFORMANCE_ERROR]
    assert conf == [], f"{ver} içerik-only XSD ihlali: {[e.message for e in conf]}"
    sv._compiled_schema.cache_clear()


@pytest.mark.parametrize("passing_score,expected", [(80, "0.8"), (100, "1.0"), (33, "0.33"), (5, "0.05")])
def test_2004_score_ratio_formatting(passing_score, expected):
    p = _proj("2004", passing_score)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    ct = item.find(f"{{{NS_ADLCP_2004}}}completionThreshold")
    mnm = item.find(
        f"{{{NS_IMSSS}}}sequencing/{{{NS_IMSSS}}}objectives/"
        f"{{{NS_IMSSS}}}primaryObjective/{{{NS_IMSSS}}}minNormalizedMeasure"
    )
    assert ct.text == expected
    assert mnm.text == expected


# --------------------------------------------------------------------------- #
# 2.3 (S7) — LOM metadata (imsmd:lom): title/language HER ZAMAN, description/
# keyword/typicalLearningTime yalnız project.metadata doluysa. intended_audience
# LOM'a HİÇ eşlenmez (bkz. core/manifest.py _build_lom docstring).
# --------------------------------------------------------------------------- #
def _lom(xml_bytes: bytes):
    from lxml import etree
    root = etree.fromstring(xml_bytes)
    return root.find(".//{*}metadata/{*}lom")


@pytest.mark.parametrize("ver,ns_imsmd", [("1.2", NS_IMSMD_12), ("2004", NS_IMSMD_2004)])
def test_lom_minimal_when_no_metadata(ver, ns_imsmd):
    from lxml import etree
    p = _proj(ver)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    lom = _lom(xml)
    assert lom is not None
    general = lom.find(f"{{{ns_imsmd}}}general")
    assert general is not None
    tags = [etree.QName(c).localname for c in general]
    assert tags == ["title", "language"], tags
    title_ls = general.find(f"{{{ns_imsmd}}}title/{{{ns_imsmd}}}langstring")
    assert title_ls is not None and title_ls.text == f"Conformance {ver}"
    assert title_ls.get("{http://www.w3.org/XML/1998/namespace}lang") == "tr"
    assert general.find(f"{{{ns_imsmd}}}language").text == "tr"
    # educational hiç basılmaz (typical_learning_time yok) — "alan yoksa eleman yok".
    assert lom.find(f"{{{ns_imsmd}}}educational") is None


@pytest.mark.parametrize("ver,ns_imsmd", [("1.2", NS_IMSMD_12), ("2004", NS_IMSMD_2004)])
def test_lom_full_metadata_populates_general_and_educational(ver, ns_imsmd):
    from lxml import etree
    p = _proj(ver, metadata=_FULL_METADATA)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    lom = _lom(xml)
    general = lom.find(f"{{{ns_imsmd}}}general")
    tags = [etree.QName(c).localname for c in general]
    assert tags == ["title", "language", "description", "keyword", "keyword"], tags

    desc_ls = general.find(f"{{{ns_imsmd}}}description/{{{ns_imsmd}}}langstring")
    assert desc_ls is not None and desc_ls.text == _FULL_METADATA.description

    kw_texts = [
        e.text for e in general.findall(f"{{{ns_imsmd}}}keyword/{{{ns_imsmd}}}langstring")
    ]
    assert kw_texts == _FULL_METADATA.keywords

    educational = lom.find(f"{{{ns_imsmd}}}educational")
    assert educational is not None
    dt = educational.find(f"{{{ns_imsmd}}}typicallearningtime/{{{ns_imsmd}}}datetime")
    assert dt is not None and dt.text == "PT1H30M"

    # intended_audience LOM'a hiç yansımaz (kapalı sözlük gerektiren intendedenduserrole'e
    # serbest metin zorlanmadı) — ne general ne educational altında herhangi bir iz.
    assert "intended" not in etree.tostring(lom).decode().lower()


@pytest.mark.parametrize("ver,ns_imsmd", [("1.2", NS_IMSMD_12), ("2004", NS_IMSMD_2004)])
def test_lom_partial_metadata_only_emits_set_fields(ver, ns_imsmd):
    from lxml import etree
    p = _proj(ver, metadata=CourseMetadata(description="Sadece açıklama"))
    xml = build_manifest(p, file_list=["index.html"]).encode()
    lom = _lom(xml)
    general = lom.find(f"{{{ns_imsmd}}}general")
    tags = [etree.QName(c).localname for c in general]
    assert tags == ["title", "language", "description"], tags
    assert lom.find(f"{{{ns_imsmd}}}educational") is None


# --------------------------------------------------------------------------- #
# 2.4 (S2) — kurs hedefleri manifest'te: 2004'te primaryObjective'den SONRA
# non-primary imsss:objective (yalnız ≥1 puanlı ekrana bağlı hedefler; kurs hedef
# sırasında). passing_score 0 → sequencing hiç yok → hedefler runtime-only.
# 1.2'de manifest'e hedef basılmaz (adlcp 1.2'de karşılığı yok).
# --------------------------------------------------------------------------- #
_OBJS = [Objective(id="obj-kavrama", description="Kavramları açıklar"),
         Objective(id="obj-uygulama", success_criteria="3 soruda 2 doğru"),
         Objective(id="obj-bagsiz")]  # hiçbir ekrana bağlı değil → manifest'e de yazılmaz


def test_2004_nonprimary_objectives_bound_only_in_course_order():
    from lxml import etree
    p = _proj("2004", 80, objectives=_OBJS, bind={"q": ["obj-uygulama", "obj-kavrama"]})
    xml = build_manifest(p, file_list=["index.html"]).encode()
    seq = _item(xml).find(f"{{{NS_IMSSS}}}sequencing")
    objs = seq.find(f"{{{NS_IMSSS}}}objectives")
    tags = [etree.QName(c).localname for c in objs]
    # primaryObjective İLK (imsss objectivesType sırası); bağsız hedef yok
    assert tags == ["primaryObjective", "objective", "objective"], tags
    ids = [o.get("objectiveID") for o in objs.findall(f"{{{NS_IMSSS}}}objective")]
    # ekran bağlama sırası DEĞİL, kurs hedef sırası (determinizm kaynağı tek)
    assert ids == ["obj-kavrama", "obj-uygulama"]


def test_2004_objectives_runtime_only_when_no_passing_score():
    p = _proj("2004", 0, objectives=_OBJS, bind={"q": ["obj-kavrama"]})
    xml = build_manifest(p, file_list=["index.html"]).encode()
    item = _item(xml)
    # 2.1 sözleşmesi korunur: passing_score 0 → sequencing hiç basılmaz (primaryObjective
    # zorunlu-ilk-çocuk olduğundan hedefler runtime-only kalır — karar core/manifest.py'de belgeli)
    assert item.find(f"{{{NS_IMSSS}}}sequencing") is None


def test_12_manifest_has_no_objective_elements():
    p = _proj("1.2", 80, objectives=_OBJS, bind={"q": ["obj-kavrama"]})
    xml = build_manifest(p, file_list=["index.html"])
    assert "objective" not in xml.lower()  # 1.2 manifest'inde hedef karşılığı yok


def test_2004_no_objectives_manifest_unchanged():
    from lxml import etree
    p = _proj("2004", 80)
    xml = build_manifest(p, file_list=["index.html"]).encode()
    objs = _item(xml).find(f"{{{NS_IMSSS}}}sequencing/{{{NS_IMSSS}}}objectives")
    assert [etree.QName(c).localname for c in objs] == ["primaryObjective"]


@pytest.mark.parametrize("ver", ["1.2", "2004"])
def test_manifest_xsd_valid_with_objectives(ver, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import core.schema_validate as sv
    sv._compiled_schema.cache_clear()
    from core.schema_validate import validate_manifest_xsd, SCHEMA_UNAVAILABLE, CONFORMANCE_ERROR
    p = _proj(ver, 80, objectives=_OBJS, bind={"q": ["obj-kavrama", "obj-uygulama"]})
    xml = build_manifest(p, file_list=["index.html", "runtime/scorm-again.min.js"]).encode()
    errs = validate_manifest_xsd(xml, ver)
    if any(e.code == SCHEMA_UNAVAILABLE for e in errs):
        pytest.skip("SCORM XSD şemaları çevrimdışı — fetch edilemedi")
    conf = [e for e in errs if e.code == CONFORMANCE_ERROR]
    assert conf == [], f"{ver} objectives XSD ihlali: {[e.message for e in conf]}"
    sv._compiled_schema.cache_clear()


def test_schema_unavailable_graceful_degrade(monkeypatch):
    """Şema yoksa: conformance_error DEĞİL, bloklamayan schema_unavailable UYARISI (sessiz geçmez)."""
    import core.schema_validate as sv
    sv._compiled_schema.cache_clear()
    monkeypatch.setattr(sv, "_ensure_populated", lambda v: None)
    sv._compiled_schema.cache_clear()
    p = _proj("2004")
    xml = build_manifest(p, file_list=["index.html"]).encode()
    errs = sv.validate_manifest_xsd(xml, "2004")
    assert len(errs) == 1 and errs[0].code == sv.SCHEMA_UNAVAILABLE
    sv._compiled_schema.cache_clear()
