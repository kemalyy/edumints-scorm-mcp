import io
import json
import os
import zipfile
import pytest
from fastmcp import Client
import server

def _spec(name: str) -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "games", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

async def _build_and_get_zip(spec: dict) -> bytes:
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        assert res.data.status == "done", f"build status: {res.data.status}"
        assert res.data.download_url
        token = res.data.download_url.rstrip("/").split("/")[-1]
    meta = await server.SVC.store.get_package_by_token(token)
    assert meta is not None
    zpath = os.path.join(server.SETTINGS.data_dir, meta.rel_path)
    with open(zpath, "rb") as f:
        return f.read()

@pytest.mark.asyncio
async def test_phishing_decision_builds():
    spec = _spec("phishing-decision.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="decision_scenario"' in index

@pytest.mark.asyncio
async def test_customer_deescalation_builds():
    spec = _spec("customer-deescalation.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="decision_scenario"' in index
