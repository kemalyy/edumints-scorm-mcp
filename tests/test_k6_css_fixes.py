"""K6 — release öncesi CSS düzeltmeleri: kurallar çıktıda (davranış probe'da doğrulanır)."""
from components.renderer import render_html
from core.project import ContentSlide, FlashcardsScreen, Flashcard, Project


def _html(comp="classic"):
    s = FlashcardsScreen(id="f", title="F", cards=[Flashcard(front_html="a", back_html="b")])
    return render_html(Project(id="p", title="t", composition=comp,
                               screens=[ContentSlide(id="c", title="T", body_html="<p>x</p>"), s]),
                       mode="preview", runtime_js="")


def test_flow_stage_uses_safe_center_desktop_and_mobile():
    html = _html()
    assert html.count("align-items:safe center;justify-content:flex-start;overflow-y:auto") == 2
    assert "align-items:center;justify-content:flex-start;overflow-y:auto" not in html


def test_flashcard_faces_stack_in_one_cell_as_column():
    html = _html()
    assert ".fc-inner{position:relative;display:grid;" in html
    assert ".fc-face{grid-area:1 / 1;display:flex;flex-direction:column;" in html
    assert "position:absolute;inset:0;display:flex;align-items:center" not in html


def test_slots_use_safe_alignment_in_auto():
    html = _html("auto")
    assert ".slot{min-width:0;min-height:0;display:flex;flex-direction:column;justify-content:safe center}" in html
    assert '.screen[data-comp="visual-stack"] .slot-support{justify-content:safe flex-end}' in html
