"""K1 / #160 — tema fontları (Inter, Outfit, JetBrains Mono) auto projelerde pakete gömülür."""
from pathlib import Path

import server
from components.renderer import extra_runtime_files, render_html
from core.project import Project, TitleSlide

FONTS = Path(__file__).resolve().parent.parent / "runtime" / "fonts"


def P(comp):
    return Project(id="p", title="t", composition=comp, theme=server._load_theme("mint"),
                   screens=[TitleSlide(title="t")])


def test_vendored_files_present():
    for fam in ("inter", "outfit", "jetbrains-mono"):
        for sub in ("latin", "latin-ext"):
            assert (FONTS / f"{fam}-{sub}.woff2").stat().st_size > 1000


def test_auto_preview_inlines_fonts_classic_does_not():
    auto = render_html(P("auto"), mode="preview", runtime_js="")
    classic = render_html(P("classic"), mode="preview", runtime_js="")
    assert 'font-family:"Inter"' in auto and "data:font/woff2;base64," in auto
    assert "data:font/woff2" not in classic


def test_auto_package_references_relative_files():
    html = render_html(P("auto"), mode="package", runtime_js="")
    assert 'url("runtime/fonts/inter-latin.woff2")' in html
    rels = [r for r, _ in extra_runtime_files(P("auto"))]
    assert "runtime/fonts/inter-latin-ext.woff2" in rels
    assert not [r for r, _ in extra_runtime_files(P("classic")) if r.startswith("runtime/fonts")]


def test_unicode_range_covers_turkish():
    html = render_html(P("auto"), mode="package", runtime_js="")
    assert "U+0100-02BA" in html  # latin-ext: ş ğ ı İ


async def test_built_package_contains_fonts_and_validates():
    import io
    import os
    import zipfile

    from fastmcp import Client

    spec = {"title": "Font", "screens": [{"type": "title_slide", "title": "Şimdi ığ"}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
        val = (await c.call_tool("validate_package", {"project_id": pid})).data
    assert val.ok, val
    pkg = await server.SVC.store.latest_package_for_project(pid)
    data = open(os.path.join(os.environ["DATA_DIR"], pkg.rel_path), "rb").read()
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "runtime/fonts/inter-latin-ext.woff2" in names
    assert "runtime/fonts/outfit-latin.woff2" in names
