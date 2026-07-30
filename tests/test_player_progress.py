"""tests/test_player_progress.py — Senaryo hattı Faz 4: konum, hedef-bazlı ilerleme,
düğüme devam, kilit (plan Kol C §6.1-6.3 + 3.11).

Kapsam:
  1) Şema: `OutlineNode.unlock_rule: Literal["free","sequential"]="free"` (additive).
  2) Validator: `UNREACHABLE_NODE` SERT hata — sequential düğümün önceki kardeşinin
     alt-ağacında tamamlanabilir (bağlı) ekran yoksa düğüm asla açılamaz.
     AD SAPMASI (bilinçli, PR'da belgeli): plan'ın hata enum'undaki NO_KEYBOARD_PATH
     klavye-erişim sınıfıdır; erişilemez-İÇERİK durumu ayrı adla anılır.
  3) Markup: konum şeridi (#posStrip, aria-live=polite) YALNIZ outline'lı kursta;
     kilitli düğüm sebebi sunucuda i18n ile render edilir (engelleyen düğümün ADI geçer).
  4) Runtime konfig: unlock_rule yalnız "sequential" iken serileşir (bayt tasarrufu).
  5) Geriye uyum: outline'sız çıktıda Faz 4 izi (posStrip/kilit/mtree) YOKTUR;
     estimate_suspend_size outline eklemekle DEĞİŞMEZ (suspend'e yeni alan girmedi kanıtı).
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from components.renderer import render_html
from core.antislop import estimate_suspend_size
from core.project import (
    ContentSlide,
    MCQScreen,
    Choice,
    OutlineNode,
    Project,
    ResultsBreakdownScreen,
    ResultSection,
    SummaryScreen,
    TitleSlide,
)
from core.validator import validate_project


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _project(**kw) -> Project:
    base = dict(id="proj_T", title="T", screens=[
        TitleSlide(id="t1", title="Başlık"),
        ContentSlide(id="c1", title="İçerik", body_html="<p>x</p>"),
        SummaryScreen(id="s1", title="Özet"),
    ])
    base.update(kw)
    return Project(**base)


def _locked_outline_project(lang: str = "tr") -> Project:
    """u1 (2 ekran) → u2 sequential (1 ekran): u2, u1 bitmeden kilitli."""
    return Project(
        id="proj_T", title="Kilit", language=lang,
        outline=[
            OutlineNode(id="u1", kind="unit", title="Ünite 1"),
            OutlineNode(id="u2", kind="unit", title="Ünite 2", unlock_rule="sequential"),
        ],
        screens=[
            TitleSlide(id="t1", title="Giriş", node_id="u1"),
            ContentSlide(id="c1", title="Konu", body_html="<p>a</p>", node_id="u1"),
            ContentSlide(id="c2", title="İleri konu", body_html="<p>b</p>", node_id="u2"),
        ],
    )


def _render(p: Project) -> str:
    return render_html(p, mode="preview", runtime_js="/*RUNTIME_STUB*/")


# --------------------------------------------------------------------------- #
# 1) Şema — unlock_rule
# --------------------------------------------------------------------------- #
def test_unlock_rule_default_free_and_additive():
    n = OutlineNode(id="u1", kind="unit", title="Ü")
    assert n.unlock_rule == "free"
    n2 = OutlineNode(id="u2", kind="unit", title="Ü2", unlock_rule="sequential")
    assert n2.unlock_rule == "sequential"


def test_unlock_rule_rejects_unknown_value():
    with pytest.raises(PydanticValidationError):
        OutlineNode(id="u1", kind="unit", title="Ü", unlock_rule="skorla")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 2) Validator — UNREACHABLE_NODE
# --------------------------------------------------------------------------- #
def _unreachable(project: Project):
    return [e for e in validate_project(project) if "UNREACHABLE_NODE" in e.message]


def test_unreachable_node_when_prev_sibling_has_no_screens():
    p = _project(
        outline=[
            OutlineNode(id="bos", kind="unit", title="Boş ünite"),  # alt-ağaçta ekran yok
            OutlineNode(id="u2", kind="unit", title="Ünite 2", unlock_rule="sequential"),
        ],
        screens=[TitleSlide(id="t1", title="Giriş", node_id="u2")],
    )
    errs = _unreachable(p)
    assert len(errs) == 1
    assert "u2" in errs[0].message and "bos" in errs[0].message


def test_unreachable_node_prev_sibling_screens_in_descendants_count():
    # önceki kardeşin ekranı TORUN düğümde → alt-ağaç sayımı ile tamamlanabilir → hata yok
    p = _project(
        outline=[
            OutlineNode(id="u1", kind="unit", title="Ünite 1"),
            OutlineNode(id="b1", parent_id="u1", kind="section", title="Bölüm"),
            OutlineNode(id="u2", kind="unit", title="Ünite 2", unlock_rule="sequential"),
        ],
        screens=[
            TitleSlide(id="t1", title="Giriş", node_id="b1"),
            ContentSlide(id="c2", title="X", body_html="<p>b</p>", node_id="u2"),
            SummaryScreen(id="s1", title="Özet"),
        ],
    )
    assert _unreachable(p) == []


def test_sequential_on_first_sibling_is_open_no_error():
    p = _project(
        outline=[OutlineNode(id="u1", kind="unit", title="Ü", unlock_rule="sequential")],
        screens=[TitleSlide(id="t1", title="Giriş", node_id="u1")],
    )
    assert _unreachable(p) == []


def test_free_nodes_never_raise_unreachable():
    p = _locked_outline_project()
    assert _unreachable(p) == []


# --------------------------------------------------------------------------- #
# 3) Markup — konum şeridi + kilit sebebi
# --------------------------------------------------------------------------- #
def test_position_strip_only_for_outline_courses():
    tree = _render(_locked_outline_project())
    flat = _render(_project())
    assert 'id="posStrip"' in tree
    assert 'aria-live="polite"' in tree.split('id="posStrip"')[1][:80]
    assert "posStrip" not in flat
    assert "pos-strip" not in flat


def test_position_strip_carries_ungrouped_label_i18n():
    tr = _render(_locked_outline_project())
    en = _render(_locked_outline_project(lang="en"))
    assert 'data-ungrouped-label="Düğümsüz ekranlar"' in tr
    assert 'data-ungrouped-label="Ungrouped screens"' in en


_REASON_SPAN = '<span class="mtree-lockreason"'  # markup öğesi (CSS'teki .mtree-lockreason sınıf
                                                 # tanımıyla karışmasın — OUTLINE_CSS her outline'lı
                                                 # kursta durur, öğe yalnız sequential düğümde)


def test_lock_reason_rendered_server_side_with_blocking_node_name():
    tr = _render(_locked_outline_project())
    en = _render(_locked_outline_project(lang="en"))
    # sebep metni GÖRÜNÜR olacak öğede (JS kilitliyken hidden kaldırır), engelleyeni ADIYLA anar
    assert _REASON_SPAN in tr
    assert "Ünite 1" in tr and "tamamlanınca açılır" in tr
    assert "Unlocks after completing" in en
    # free düğümde sebep öğesi YOK
    free = _render(_locked_outline_project())
    assert free.count(_REASON_SPAN) == 1  # yalnız u2


def test_lock_reason_absent_without_sequential():
    p = _locked_outline_project()
    p.outline[1].unlock_rule = "free"
    assert _REASON_SPAN not in _render(p)


# --------------------------------------------------------------------------- #
# 4) Runtime konfig
# --------------------------------------------------------------------------- #
def _course_cfg(html: str) -> dict:
    import json
    import re
    m = re.search(r"window\.__COURSE__ = (\{.*?\});\n", html, re.S)
    return json.loads(m.group(1))


def test_unlock_rule_serialized_only_when_sequential():
    cfg = _course_cfg(_render(_locked_outline_project()))
    by_id = {n["id"]: n for n in cfg["outline"]}
    assert by_id["u2"]["unlock_rule"] == "sequential"
    assert "unlock_rule" not in by_id["u1"]


# --------------------------------------------------------------------------- #
# 5) Geriye uyum + suspend maliyet modeli
# --------------------------------------------------------------------------- #
def test_flat_output_has_no_phase4_artifacts():
    flat = _render(_project())
    for marker in ("posStrip", "mtree", "lockreason", 'role="tree"'):
        assert marker not in flat


def test_overflow_tag_only_in_outline_runtime():
    """3.11 — SUSPEND_OVERFLOW etiketi (grep'lenebilir taşma izi) hiyerarşik suspend işinin
    parçası: yalnız outline'lı kursun runtime'ında; düz kurs eski 'truncated' iziyle bayt-bayt
    aynı kalır (3.3)."""
    assert "SUSPEND_OVERFLOW" in _render(_locked_outline_project())
    assert "SUSPEND_OVERFLOW" not in _render(_project())


def test_estimate_suspend_size_unchanged_by_outline():
    """Faz 4 suspend zarfına yeni alan eklemedi (türetme kararı, 3.11) — outline/kilit
    eklemek sunucu maliyet tahminini DEĞİŞTİRMEZ."""
    screens = [
        TitleSlide(id="t1", title="Giriş"),
        MCQScreen(id="q1", title="Soru", prompt_html="<p>?</p>", points=10,
                  options=[Choice(id="a", text_html="A", correct=True),
                           Choice(id="b", text_html="B")]),
    ]
    plain = _project(screens=[s.model_copy(deep=True) for s in screens])
    outlined = _project(
        outline=[OutlineNode(id="u1", kind="unit", title="Ünite 1"),
                 OutlineNode(id="u2", kind="unit", title="Ünite 2", unlock_rule="sequential")],
        screens=[s.model_copy(deep=True) for s in screens],
    )
    outlined.screens[0].node_id = "u1"
    outlined.screens[1].node_id = "u2"
    assert estimate_suspend_size(outlined) == estimate_suspend_size(plain)


def test_results_breakdown_completion_hook_present():
    """results_breakdown hizası: bölüm tamamlanması AYNI data-screens mekanizmasıyla,
    runtime'da .rb-comp olarak basılır (OUTLINE_JS sarmalayıcısı). YALNIZ outline'lı kursta:
    kancayı ENGINE_JS'e koymak outline'sız kursların çıktısını değiştirirdi (3.3 bayt-parite,
    fixture kilidi) — düz kursların results ekranı Faz 4 ÖNCESİYLE bayt-bayt aynı kalır."""
    results = [
        MCQScreen(id="q1", title="Soru", prompt_html="<p>?</p>", points=10,
                  node_id="u1",
                  options=[Choice(id="a", text_html="A", correct=True),
                           Choice(id="b", text_html="B")]),
        ResultsBreakdownScreen(id="r1", title="Sonuç", sections=[
            ResultSection(title="Hedef 1", screen_ids=["q1"]),
        ]),
    ]
    outlined = _project(
        outline=[OutlineNode(id="u1", kind="unit", title="Ünite 1")],
        screens=[s.model_copy(deep=True) for s in results],
    )
    html = _render(outlined)
    assert 'data-screens="q1"' in html          # Faz 14 mekanizması aynen (paralel makine yok)
    assert "rb-comp" in html                     # tamamlanma runtime kancası (OUTLINE_JS)
    assert "sectionCompletion" in html           # saf yardımcı (progress bundle) kullanılıyor
    flat_results = [s.model_copy(deep=True) for s in results]
    flat_results[0].node_id = None
    flat = _render(_project(screens=flat_results))
    assert 'data-screens="q1"' in flat           # mekanizmanın kendisi her kursta
    assert "rb-comp" not in flat                 # Faz 4 izi düz kursa SIZMAZ
    assert "sectionCompletion" not in flat
