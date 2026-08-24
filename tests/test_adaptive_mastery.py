"""tests/test_adaptive_mastery.py — W4b-gen: Adaptif Ustalık Döngüsü (opt-in).

Kabul kriterleri:
- Yeni alanlar (loop_mode / scaffold_on_wrong / score_mode / related_retry /
  max_consecutive_wrong) model'de tanımlı ve varsayılanları "sample" davranışını korur.
- _adaptive_cfg bu bayrakları runtime'a (JS s nesnesi) taşır — aksi halde JS hiç görmez.
- Renderer: item.scaffold_html varsa .ap-scaffold slot'u üretir (sanitize edilmiş);
  yoksa üretmez (legacy bozulmaz).
- Antislop: loop_mode='mastery' ama score_mode!='mastery' → WARN.
- Validator: doğru seçenekli geçerli ustalık ekranı hatasız doğrulanır.
"""

from components.renderer import _course_config, render_html
from core.antislop import _lint_adaptive
from core.game_primitives import EloSpec
from core.project import (
    AdaptiveItem,
    AdaptivePracticeScreen,
    Choice,
    Project,
    new_project_id,
)


def _item(i, skill="frac", scaffold=None):
    return AdaptiveItem(
        id=f"q{i}",
        prompt_html=f"<p>Soru {i}</p>",
        options=[
            Choice(id=f"q{i}a", text_html="<p>Yanlış</p>", correct=False),
            Choice(id=f"q{i}b", text_html="<p>Doğru</p>", correct=True),
        ],
        difficulty=0.0 + i * 0.3,
        skill=skill,
        explain_html=f"<p>Soru {i} açıklaması</p>",
        scaffold_html=scaffold,
    )


def _mastery_screen(**kw):
    fields = {
        "id": "ad1",
        "title": "Ustalık döngüsü",
        "items": [_item(0), _item(1), _item(2)],
        "adaptive": EloSpec(),
        "loop_mode": "mastery",
        "scaffold_on_wrong": True,
        "score_mode": "mastery",
        "related_retry": True,
        "max_consecutive_wrong": 5,
    }
    fields.update(kw)
    return AdaptivePracticeScreen(**fields)


def _proj(screens):
    return Project(id=new_project_id(), title="K", screens=screens)


# --------------------------------------------------------------------------- #
# Model + serileştirme
# --------------------------------------------------------------------------- #
def test_mastery_fields_default_to_sample_behavior():
    s = AdaptivePracticeScreen(id="ad0", title="T", items=[_item(0), _item(1), _item(2)], adaptive=EloSpec())
    assert s.loop_mode == "sample"          # Literal varsayılanı
    assert s.scaffold_on_wrong is False
    assert s.score_mode == "ratio"
    assert s.related_retry is True
    assert s.max_consecutive_wrong == 5
    # serileşmede yeni alanlar bulunur
    dump = s.model_dump()
    assert dump["loop_mode"] == "sample"
    assert dump["score_mode"] == "ratio"
    assert "scaffold_html" in dump["items"][0]


def test_mastery_screen_accepts_new_fields():
    s = _mastery_screen()
    assert s.loop_mode == "mastery"
    assert s.score_mode == "mastery"
    assert s.scaffold_on_wrong is True
    assert s.related_retry is True
    assert s.max_consecutive_wrong == 5


# --------------------------------------------------------------------------- #
# _course_config — runtime'a bayrak taşınmalı (JS s nesnesi = bu item)
# --------------------------------------------------------------------------- #
def test_screen_config_carries_mastery_flags():
    s = _mastery_screen()
    cfg = _course_config(_proj([s]))
    item = next(x for x in cfg["screens"] if x["type"] == "adaptive_practice")
    assert item["loop_mode"] == "mastery"
    assert item["scaffold_on_wrong"] is True
    assert item["score_mode"] == "mastery"
    assert item["related_retry"] is True
    assert item["max_consecutive_wrong"] == 5
    # skill bilgisi item.adaptive.items config'te mevcut (JS skillOf bunu kullanır)
    assert item["adaptive"]["items"]["q0"]["skill"] == "frac"


# --------------------------------------------------------------------------- #
# Renderer — .ap-scaffold slot'u
# --------------------------------------------------------------------------- #
def test_renderer_emits_scaffold_slot_when_present():
    s = _mastery_screen(items=[_item(0, scaffold="<p>İpucu: payı ortak paydaya getir</p>"),
                               _item(1), _item(2)])
    html = render_html(_proj([s]), mode="preview", runtime_js="/*rt*/")
    assert "ap-scaffold rich" in html
    assert "İpucu: payı ortak paydaya getir" in html


def test_renderer_omits_scaffold_slot_when_absent():
    s = AdaptivePracticeScreen(id="ad0", title="T", items=[_item(0), _item(1), _item(2)], adaptive=EloSpec())
    html = render_html(_proj([s]), mode="preview", runtime_js="/*rt*/")
    assert "ap-scaffold rich" not in html


# --------------------------------------------------------------------------- #
# Antislop — ustalık döngüsü / skor modu tutarsızlığı
# --------------------------------------------------------------------------- #
def test_lint_warns_mastery_loop_without_mastery_score():
    s = _mastery_screen(score_mode="ratio")
    issues = _lint_adaptive(s, "screens[ad1]")
    codes = {i.code for i in issues}
    assert "mastery_loop_without_mastery_score" in codes


def test_lint_warns_scaffold_enabled_without_content():
    s = _mastery_screen(items=[_item(0), _item(1), _item(2)])  # scaffold_html yok
    issues = _lint_adaptive(s, "screens[ad1]")
    codes = {i.code for i in issues}
    assert "scaffold_enabled_without_content" in codes


def test_lint_clean_for_well_formed_mastery():
    s = _mastery_screen(items=[_item(0, scaffold="<p>ip</p>"), _item(1, scaffold="<p>ip</p>"), _item(2, scaffold="<p>ip</p>")])
    issues = _lint_adaptive(s, "screens[ad1]")
    codes = {i.code for i in issues}
    assert "mastery_loop_without_mastery_score" not in codes
    assert "scaffold_enabled_without_content" not in codes


# --------------------------------------------------------------------------- #
# Validator — geçerli ustalık ekranı hatasız
# --------------------------------------------------------------------------- #
def test_validator_accepts_well_formed_mastery():
    from core.validator import validate_project
    s = _mastery_screen(items=[_item(0, scaffold="<p>ip</p>"), _item(1, scaffold="<p>ip</p>"), _item(2, scaffold="<p>ip</p>")])
    errs = validate_project(_proj([s]))
    # her öğede en az bir doğru seçenek var → W4b doğrulaması geçer
    assert all(not e.code.startswith("validation_error") for e in errs)
