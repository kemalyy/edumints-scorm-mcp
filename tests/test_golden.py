"""tests/test_golden.py — Definition of Done (CONTRACTS.md §11).

Örnek spec → build_from_spec → zip aç → imsmanifest.xml geçerli + index.html var +
scorm-again runtime gömülü + en az bir quiz skorlama hook'u çalışıyor.
"""

import io
import json
import os
import zipfile

import pytest
from fastmcp import Client

import server


def _spec(name: str) -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def _build_and_get_zip(spec: dict) -> bytes:
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        assert res.data.status == "done", f"build status: {res.data.status}"
        assert res.data.download_url
        # token'dan paket meta → diskten zip
        token = res.data.download_url.rstrip("/").split("/")[-1]
    meta = await server.SVC.store.get_package_by_token(token)
    assert meta is not None
    zpath = os.path.join(server.SETTINGS.data_dir, meta.rel_path)
    with open(zpath, "rb") as f:
        return f.read()


@pytest.mark.asyncio
async def test_golden_small_builds_valid_scorm():
    spec = _spec("small.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())

    # 1) index.html var
    assert "index.html" in names
    # 2) imsmanifest.xml var + geçerli
    assert "imsmanifest.xml" in names
    from lxml import etree

    root = etree.fromstring(zf.read("imsmanifest.xml"))
    assert etree.QName(root).localname == "manifest"
    manifest_txt = zf.read("imsmanifest.xml").decode("utf-8")
    assert "schemaversion" in manifest_txt
    assert "index.html" in manifest_txt
    assert 'scormtype="sco"' in manifest_txt.lower() or "scormtype" in manifest_txt.lower()

    # 3) scorm-again runtime gömülü
    assert "runtime/scorm-again.min.js" in names
    runtime = zf.read("runtime/scorm-again.min.js").decode("utf-8", "ignore")
    assert "Scorm12API" in runtime

    # 4) en az bir quiz skorlama hook'u
    index = zf.read("index.html").decode("utf-8")
    assert "cmi.core.score.raw" in index or "cmi.score.raw" in index
    assert "__COURSE__" in index
    course = json.loads(index.split("window.__COURSE__ = ", 1)[1].split(";\n", 1)[0])
    assert course["total_points"] >= 10  # mcq puanı
    assert any(s["is_quiz"] for s in course["screens"])


@pytest.mark.asyncio
async def test_golden_rich_all_screen_types_build():
    spec = _spec("rich.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names and "imsmanifest.xml" in names
    # asset'ler pakete girdi
    assert any(n.startswith("assets/") for n in names)
    index = zf.read("index.html").decode("utf-8")
    for t in ["title_slide", "mcq", "drag_drop", "hotspot", "branching", "video", "summary"]:
        assert f'data-type="{t}"' in index, f"{t} render edilmedi"


@pytest.mark.asyncio
async def test_preview_is_single_file_no_external_deps():
    async with Client(server.mcp) as c:
        proj = await c.call_tool("create_project", {"title": "Önizleme"})
        pid = proj.data.project_id
        await c.call_tool("add_screen", {"project_id": pid,
                                         "screen": {"type": "title_slide", "title": "Merhaba"}})
        pv = await c.call_tool("preview", {"project_id": pid})
    html = pv.data.inline_html
    # harici bağımlılık yok: <script src=...> ve <link href=...> bulunmamalı
    assert "<script src=" not in html
    assert "<link " not in html
    # runtime gömülü
    assert "Scorm12API" in html
    assert pv.data.hosted_url.startswith("https://mcp.test/scorm/preview/")
