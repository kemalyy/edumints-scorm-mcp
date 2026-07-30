"""tests/test_pack_conformance.py — E2 (#111): paket uygunluk denetleyicisi.

Kural kaynağı: skills/authoring-scorm-courses/references/pedagogy/_SCHEMA.md — özellikle
`conflicts_with` kapsamı HEDEFTİR (objective), kurs değil: farklı hedeflerde çelişen paketler
aynı kursta meşru birlikte yaşar; ihlal AYNI ekranın çelişen-paketli iki hedefe bağlanmasıdır.

Tasarım kararları (PR gövdesinde belgeli):
- Beyan birimi: `Objective.method_pack` (additive, opsiyonel). Ekran-düzeyi faz etiketi YOK —
  faz etiketi olmadan doğrulanabilir üç yaklaşık denetim + `unknown_method_pack` sağlamlığı.
- Paket kaynağı: vendored `runtime/pedagogy-packs.json` (tools/gen_packs_manifest.py üretir,
  commit'lenir; sunucu skill reposunu runtime'da OKUMAZ).
- Tüm E2 kodları WARN + strict-terfisiz (danışsal dalga — yeni ekosistem).
- Beyan yoksa SIFIR yeni lint çıktısı (geriye uyumluluk).
"""

import json
import pathlib

from core.antislop import (
    STRICT_PROMOTED_CODES,
    lint_course,
    lint_errors,
)
from core.project import Objective, Project, new_project_id

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "runtime" / "pedagogy-packs.json"
PEDAGOGY = ROOT / "skills" / "authoring-scorm-courses" / "references" / "pedagogy"

E2_CODES = {
    "pack_conflict_on_screen",
    "pack_platform_missing",
    "evidence_type_outside_pack",
    "unknown_method_pack",
}


# --------------------------------------------------------------------------- #
# runtime/pedagogy-packs.json — vendored manifest (üretimi belgeli, commit'li)
# --------------------------------------------------------------------------- #
def test_manifest_exists_and_parses():
    """Manifest commit'li ve geçerli JSON: sunucu skill reposunu runtime'da okumaz."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert isinstance(data["packs"], dict) and len(data["packs"]) >= 12


def test_manifest_in_sync_with_pedagogy_dir():
    """Manifest'teki paket kümesi = pedagogy/ altındaki paket dosyaları (`_` öneklileri hariç).
    Senkron kopuşu = birisi paket ekledi/sildi ama tools/gen_packs_manifest.py çalıştırmadı.
    Kaynak dizin yalnız geliştirme reposunda yaşar (skills/ aynası); public repoda test atlanır."""
    if not PEDAGOGY.exists():
        import pytest

        pytest.skip("pedagogy kaynak dizini bu repoda yok (yalnız geliştirme reposunda)")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = {p.stem for p in PEDAGOGY.glob("*.md") if not p.name.startswith("_")}
    assert set(data["packs"]) == expected


def test_manifest_pack_shape():
    """Her paket E2'nin okuduğu projeksiyon alanlarını taşır; evidence_phases normalize (liste)."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for pid, pk in data["packs"].items():
        assert isinstance(pk["name"], str) and pk["name"]
        assert isinstance(pk["requires_platform"], list)
        assert isinstance(pk["conflicts_with"], list)
        assert isinstance(pk["evidence_phases"], list) and pk["evidence_phases"]
        phase_ids = [ph["id"] for ph in pk["phases"]]
        assert pk["scoring_allowed_from"] in phase_ids
        for eph in pk["evidence_phases"]:
            assert eph in phase_ids
        for ph in pk["phases"]:
            ekr = ph["izinli_ekran_tipleri"]
            assert ekr == "hepsi" or (isinstance(ekr, list) and ekr)
            assert isinstance(ph["skorlanabilir"], bool)


def test_manifest_known_conflict_is_symmetrizable():
    """Gerçek veri denetimi: productive-failure ↔ rosenshine-di çakışması manifest'te görünür."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "rosenshine-di" in data["packs"]["productive-failure"]["conflicts_with"]


# --------------------------------------------------------------------------- #
# yardımcılar
# --------------------------------------------------------------------------- #
def _cs(i, blocks=False):
    """content_slide `objective_ids` TAŞIMAZ (bağ yalnız skorlanabilir/etkileşimli tiplerde) —
    E2'nin ekran-bağı denetimleri bu yüzden mcq/simulation gibi bağlanabilir tiplerle kurulur."""
    d = {"type": "content_slide", "id": f"c{i}", "title": f"Fikir {i}",
         "body_html": f"<p>metin {i}</p>"}
    if blocks:
        d.pop("body_html")
        d["blocks"] = [{"asset_id": f"a{i}", "caption": f"Vaka artefaktı {i}"}]
    return d


def _mcq(qid="q1", **kw):
    d = {"type": "mcq", "id": qid, "title": "Soru", "prompt_html": "<p>?</p>",
         "points": 10,
         "options": [{"id": "a", "text_html": "A", "correct": True},
                     {"id": "b", "text_html": "B"}],
         "feedback": {"correct_html": "Doğru — kanıt ekranındaki artefakt bunu gösteriyor.",
                      "incorrect_html": "Kanıt ekranına dön, artefaktı yeniden incele."}}
    d.update(kw)
    return d


def _proj(screens, objectives=None, **kw):
    return Project(id=new_project_id(), title="K", screens=screens,
                   objectives=objectives or [], **kw)


def _e2(p):
    return [i for i in lint_course(p) if i.code in E2_CODES]


# --------------------------------------------------------------------------- #
# Objective.method_pack — additive beyan alanı
# --------------------------------------------------------------------------- #
def test_objective_method_pack_field_optional():
    o = Objective(id="ob1")
    assert o.method_pack is None
    o2 = Objective(id="ob2", method_pack="gagne-9")
    assert o2.method_pack == "gagne-9"


# --------------------------------------------------------------------------- #
# Geriye uyumluluk: beyan yok → SIFIR yeni lint çıktısı
# --------------------------------------------------------------------------- #
def test_no_declaration_zero_e2_output():
    p = _proj(
        [_cs(0), _mcq(objective_ids=["ob1", "ob2"])],
        objectives=[Objective(id="ob1"), Objective(id="ob2")],
    )
    assert _e2(p) == []


def test_e2_codes_not_strict_promoted():
    """Danışsal dalga: E2 kodları strict'te bloklamaya TERFİ ETMEZ."""
    assert not (E2_CODES & STRICT_PROMOTED_CODES)


# --------------------------------------------------------------------------- #
# pack_conflict_on_screen — çelişen paketli iki hedef AYNI ekranda
# --------------------------------------------------------------------------- #
def test_conflict_on_shared_screen_warns():
    p = _proj(
        [_mcq(objective_ids=["ob_pf", "ob_di"])],
        objectives=[Objective(id="ob_pf", method_pack="productive-failure"),
                    Objective(id="ob_di", method_pack="rosenshine-di")],
    )
    issues = [i for i in _e2(p) if i.code == "pack_conflict_on_screen"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert issues[0].path == "screens[0]"
    assert "productive-failure" in issues[0].message
    assert "rosenshine-di" in issues[0].message


def test_conflicting_packs_on_separate_screens_clean():
    """_SCHEMA.md B2: kapsam HEDEFTİR — çelişen paketler ayrı hedef+ayrı ekranlarda meşru."""
    p = _proj(
        [_mcq(qid="q1", objective_ids=["ob_pf"]), _mcq(qid="q2", objective_ids=["ob_di"])],
        objectives=[Objective(id="ob_pf", method_pack="productive-failure"),
                    Objective(id="ob_di", method_pack="rosenshine-di")],
    )
    assert [i for i in _e2(p) if i.code == "pack_conflict_on_screen"] == []


def test_non_conflicting_packs_on_shared_screen_clean():
    p = _proj(
        [_mcq(objective_ids=["ob_g", "ob_r"])],
        objectives=[Objective(id="ob_g", method_pack="gagne-9"),
                    Objective(id="ob_r", method_pack="retrieval-spaced")],
    )
    assert [i for i in _e2(p) if i.code == "pack_conflict_on_screen"] == []


def test_conflict_fires_once_per_screen_pair():
    """Aynı çift, aynı ekranda tek WARN (yön simetrik: A↔B çifte rapor üretmez)."""
    p = _proj(
        [_mcq(objective_ids=["ob_5e", "ob_ca"])],
        objectives=[Objective(id="ob_5e", method_pack="5e-inquiry"),
                    Objective(id="ob_ca", method_pack="cognitive-apprenticeship")],
    )
    issues = [i for i in _e2(p) if i.code == "pack_conflict_on_screen"]
    assert len(issues) == 1


# --------------------------------------------------------------------------- #
# pack_platform_missing — requires_platform tipi hedefin kullanımında yok
# --------------------------------------------------------------------------- #
# Karşılanma kuralları (bağ modeli gerçeği: objective_ids YALNIZ skorlanabilir/etkileşimli
# tiplerde var — content_slide/worked_example/exploration/branching bağlanamaz):
# 1. gerekli tipte ekran hedefe BAĞLI (objective_ids), YA DA
# 2. gerekli tipte ekran, hedefin skorlu ekranlarının `evidence_screen_ids` hedefi, YA DA
# 3. tip HİÇ bağlanamıyorsa (objective_ids alanı yok) kurs genelinde ≥1 ekran yeter.
def test_platform_missing_warns_per_missing_type():
    """sim-drill requires_platform: [simulation, worked_example, exploration] — hiçbiri yok."""
    p = _proj(
        [_cs(0), _mcq(objective_ids=["ob_sim"], evidence_screen_ids=["c0"])],
        objectives=[Objective(id="ob_sim", method_pack="sim-drill")],
    )
    issues = [i for i in _e2(p) if i.code == "pack_platform_missing"]
    missing = {t for i in issues for t in ("simulation", "worked_example", "exploration")
               if t in i.message}
    assert len(issues) == 3
    assert missing == {"simulation", "worked_example", "exploration"}
    assert all(i.severity == "warn" for i in issues)


def test_platform_unbindable_type_satisfied_course_wide():
    """productive-failure requires_platform: [exploration] — exploration `objective_ids`
    TAŞIYAMAZ (kural 3): kurs genelinde varlığı yeter."""
    p = _proj(
        [{"type": "exploration", "id": "x0", "title": "Tahmin",
          "prompt_html": "<p>Tahminini yaz</p>", "store_key": "tahmin1"}],
        objectives=[Objective(id="ob_pf", method_pack="productive-failure")],
    )
    assert [i for i in _e2(p) if i.code == "pack_platform_missing"] == []


def test_platform_bindable_type_requires_binding():
    """mastery-learning requires [branching, adaptive_practice]: branching bağlanamaz + kursta
    var → karşılandı (kural 3); adaptive_practice BAĞLANABİLİR ama hedefe bağlı değil ve kanıt
    hedefi de değil → WARN (hedef-kapsamlı semantik: bağlanabilir tipte kurs-geneli yetmez)."""
    p = _proj(
        [{"type": "branching", "id": "b0", "title": "Yol ayrımı",
          "prompt_html": "<p>Nereden devam?</p>",
          "choices": [{"id": "a", "text_html": "Tekrar", "goto_screen_id": "ap0"},
                      {"id": "b", "text_html": "İleri", "goto_screen_id": "ap0"}]},
         {"type": "adaptive_practice", "id": "ap0", "title": "Pratik",
          "items": [{"id": f"i{k}", "prompt_html": "<p>?</p>",
                     "options": [{"id": "a", "text_html": "A", "correct": True},
                                 {"id": "b", "text_html": "B"}],
                     "difficulty": float(k),
                     "explain_html": "<p>çünkü</p>"} for k in range(4)],
          "adaptive": {"strategy": "elo"}}],
        objectives=[Objective(id="ob_m", method_pack="mastery-learning")],
    )
    issues = [i for i in _e2(p) if i.code == "pack_platform_missing"]
    assert len(issues) == 1
    assert "adaptive_practice" in issues[0].message
    assert "branching" not in issues[0].message


def test_platform_evidence_reference_satisfies():
    """Kural 2: bağlanabilir tip (simulation) hedefe objective_ids ile bağlı DEĞİL ama hedefin
    skorlu ekranının kanıt hedefi → simülasyon şartı karşılandı (worked_example/exploration
    hâlâ eksik → 2 WARN)."""
    p = _proj(
        [{"type": "simulation", "id": "sim0", "title": "Gösterim",
          "steps": [{"image_asset_id": "a1", "image_alt": "ekran",
                     "instruction_html": "<p>tıkla</p>"}]},
         _mcq(objective_ids=["ob_sim"], evidence_screen_ids=["sim0"])],
        objectives=[Objective(id="ob_sim", method_pack="sim-drill")],
    )
    issues = [i for i in _e2(p) if i.code == "pack_platform_missing"]
    assert len(issues) == 2
    joined = " ".join(i.message for i in issues)
    assert "simulation" not in joined
    assert "worked_example" in joined and "exploration" in joined


def test_empty_requires_platform_clean():
    p = _proj(
        [_mcq(objective_ids=["ob_g"])],
        objectives=[Objective(id="ob_g", method_pack="gagne-9")],
    )
    assert [i for i in _e2(p) if i.code == "pack_platform_missing"] == []


# --------------------------------------------------------------------------- #
# evidence_type_outside_pack — kanıt hedefi paketin kanıt fazlarının tipi dışında
# --------------------------------------------------------------------------- #
def test_evidence_type_outside_pack_warns():
    """productive-failure kanıt fazları (kesfif_denemesi vb.) exploration/worked_example gibi
    tipleri izinler; timeline kanıt fazlarında izinli DEĞİLSE WARN. Fikstür manifest'ten
    dinamik okur: pakette timeline izinliyse test başka tip seçer."""
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pk = data["packs"]["productive-failure"]
    allowed = set()
    for ph in pk["phases"]:
        if ph["id"] in pk["evidence_phases"]:
            ekr = ph["izinli_ekran_tipleri"]
            assert ekr != "hepsi", "fikstür varsayımı: pf kanıt fazı kısıtlı"
            allowed |= set(ekr)
    assert "timeline" not in allowed, "fikstür varsayımı: timeline pf kanıt fazlarında izinsiz"

    p = _proj(
        [{"type": "timeline", "id": "t0", "title": "Zaman çizelgesi",
          "events": [{"date": "1900", "title": "A", "body_html": "<p>a</p>"},
                     {"date": "1950", "title": "B", "body_html": "<p>b</p>"}]},
         _mcq(objective_ids=["ob_pf"], evidence_screen_ids=["t0"])],
        objectives=[Objective(id="ob_pf", method_pack="productive-failure")],
    )
    issues = [i for i in _e2(p) if i.code == "evidence_type_outside_pack"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "timeline" in issues[0].message
    assert "productive-failure" in issues[0].message


def test_evidence_type_inside_pack_clean():
    """gagne-9 kanıt fazları data_chart'ı izinler → uyum, sıfır E2 çıktısı."""
    p = _proj(
        [{"type": "data_chart", "id": "d0", "title": "Veri", "chart_type": "bar",
          "data": [{"label": "a", "value": 1}, {"label": "b", "value": 2}]},
         _mcq(objective_ids=["ob_g"], evidence_screen_ids=["d0"])],
        objectives=[Objective(id="ob_g", method_pack="gagne-9")],
    )
    assert [i for i in _e2(p) if i.code == "evidence_type_outside_pack"] == []


def test_evidence_check_skips_dangling_and_undeclared():
    """Sarkan kanıt id'si E1'in işi (evidence_screen_missing ERROR) — E2 çifte raporlamaz;
    beyansız hedefe bağlı skorlu ekran da E2 kapsamı dışında."""
    p = _proj(
        [_mcq(objective_ids=["ob_pf"], evidence_screen_ids=["yok"]),
         _mcq(qid="q2", objective_ids=["ob_plain"], evidence_screen_ids=["yok2"])],
        objectives=[Objective(id="ob_pf", method_pack="productive-failure"),
                    Objective(id="ob_plain")],
    )
    assert [i for i in _e2(p) if i.code == "evidence_type_outside_pack"] == []


# --------------------------------------------------------------------------- #
# unknown_method_pack — manifest'te olmayan paket beyanı
# --------------------------------------------------------------------------- #
def test_unknown_pack_warns():
    p = _proj(
        [_mcq(objective_ids=["ob_x"])],
        objectives=[Objective(id="ob_x", method_pack="boyle-bir-paket-yok")],
    )
    issues = [i for i in _e2(p) if i.code == "unknown_method_pack"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "boyle-bir-paket-yok" in issues[0].message
    assert issues[0].path == "objectives[ob_x]"


def test_unknown_pack_skips_other_checks_for_that_objective():
    """Bilinmeyen paket için platform/kanıt denetimi çalıştırılamaz — yalnız unknown WARN."""
    p = _proj(
        [_mcq(objective_ids=["ob_x"], evidence_screen_ids=["c9"])],
        objectives=[Objective(id="ob_x", method_pack="boyle-bir-paket-yok")],
    )
    codes = {i.code for i in _e2(p)}
    assert codes == {"unknown_method_pack"}


# --------------------------------------------------------------------------- #
# temiz fikstür — beyanlı, uyumlu kurs: 0 E2 çıktısı
# --------------------------------------------------------------------------- #
def test_clean_declared_course_zero_e2():
    """#111 kabul: temiz fikstür 0 FAIL / 0 WARN (E2 kapsamında)."""
    p = _proj(
        [_cs(0, blocks=True),
         _mcq(objective_ids=["ob_g"], evidence_screen_ids=["c0"])],
        objectives=[Objective(id="ob_g", method_pack="gagne-9")],
    )
    assert _e2(p) == []


def test_e2_never_blocks_build():
    """Danışsal dalga: E2 bulguları lint_errors'ta (strict dahil) görünmez."""
    p = _proj(
        [_mcq(objective_ids=["ob_pf", "ob_di"])],
        objectives=[Objective(id="ob_pf", method_pack="productive-failure"),
                    Objective(id="ob_di", method_pack="rosenshine-di")],
    )
    assert not (E2_CODES & {i.code for i in lint_errors(p)})
    assert not (E2_CODES & {i.code for i in lint_errors(p, strict=True)})
