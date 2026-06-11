"""tests/responsive/test_responsive.py — Responsive and touch compatibility tests (Phase 16)."""

import pytest
from core.project import (
    Project, new_project_id, ContentSlide, MCQScreen, Choice,
    DragDropScreen, DragItem, DropTarget, HotspotScreen, HotspotRegion,
    VideoScreen,
)
from components.renderer import render_html

def test_responsive_meta_and_css_structural_assertions():
    """
    Test structural and CSS assertions for responsive design as required:
    (1) Viewport meta exists.
    (2) .screen-inner overflow rules.
    (3) Mobile breakpoint and stage reflow.
    (4) matchMedia check in engine.
    (5) Touch drag attributes and engine logic.
    (6) Button touch-action.
    """
    p = Project(
        id=new_project_id(),
        title="Responsive Test",
        scorm_version="2004",
        screens=[
            ContentSlide(id="s1", title="Content", body_html="<p>Hello</p>"),
            MCQScreen(id="s2", title="Quiz", prompt_html="<p>Q</p>", 
                      options=[Choice(id="o1", text_html="A", correct=True), Choice(id="o2", text_html="B")]),
            DragDropScreen(id="s3", title="Drag", prompt_html="<p>D</p>",
                          items=[DragItem(id="i1", text_html="Item", correct_target_id="t1")],
                          targets=[DropTarget(id="t1", label_html="Target")]),
            HotspotScreen(id="s4", title="Hotspot", image_asset_id="img1", prompt_html="<p>H</p>",
                          regions=[HotspotRegion(id="r1", shape="rect", coords=[0, 0, 10, 10], correct=True)]),
            VideoScreen(id="s5", title="Video", video_url="https://example.com/v.mp4")
        ]
    )
    
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    
    # (1) Viewport meta exists
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    
    # (2) .screen-inner: overflow-y:auto var, overflow:hidden YOK
    # BASE_CSS contains: .screen-inner{...;height:100%;overflow-y:auto;overflow-x:hidden;...}
    assert ".screen-inner" in html
    assert "overflow-y:auto" in html
    # Ensure no 'overflow:hidden' is applied to .screen-inner specifically in a way that blocks scrolling
    # In BASE_CSS, body has overflow:hidden, but .screen-inner must have overflow-y:auto.
    # We check that .screen-inner style block doesn't have overflow:hidden.
    assert ".screen-inner{" in html
    # Find the block for .screen-inner and check it
    import re
    inner_style = re.search(r"\.screen-inner\{([^}]+)\}", html)
    if inner_style:
        style_content = inner_style.group(1)
        assert "overflow-y:auto" in style_content
        assert "overflow:hidden" not in style_content
        
    # (3) Mobil breakpoint '@media(max-width:640px)' var ve stage reflow kuralı
    assert "@media(max-width:640px)" in html
    assert "transform:none!important" in html
    
    # (4) fitStage mobil erken-çıkışı: matchMedia("(max-width:640px)") engine'de geçiyor
    assert 'matchMedia("(max-width:640px)")' in html
    
    # (5) Dokunma drag: touchmove + elementFromPoint + .drag-item için touch-action:none
    assert "touchmove" in html
    assert "elementFromPoint" in html
    assert ".drag-item" in html
    drag_style = re.search(r"\.drag-item\{([^}]+)\}", html)
    if drag_style:
        assert "touch-action:none" in drag_style.group(1)
        
    # (6) Butonlarda touch-action:manipulation
    # .btn,.opt,.branch-choice,.scen-choice,.poll-opt,.pl-btn,.tab,.flashcard,select,input{touch-action:manipulation}
    assert "touch-action:manipulation" in html

def test_responsive_engine_js_presence():
    """Verify engine JS contains the necessary touch event listeners."""
    p = Project(id=new_project_id(), title="JS Test")
    # Even with no screens, the ENGINE_JS is included in SHELL
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    
    assert "addEventListener(\"touchstart\"" in html
    assert "addEventListener(\"touchmove\"" in html
    assert "addEventListener(\"touchend\"" in html
    assert "document.elementFromPoint" in html

if __name__ == "__main__":
    pytest.main([__file__])
