"""get_guide aracı — sözleşme, hatalar, kayma (spec §3, §5.3, §6)."""
import re

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server
from core import guides as g

_NOT_TOOLS = {"fetch", "print", "len", "json", "parse", "set", "get", "map", "open", "range", "str", "int",
              "dict", "list", "postMessage"}


async def _call(**kw):
    async with Client(server.mcp) as c:
        return (await c.call_tool("get_guide", kw)).data


async def test_index_without_topic():
    out = await _call(skill_version="2.4.0")
    assert out["skill_status"] == "current" and out["notice"] is None
    assert out["server_version"] == server._server_version()
    assert {t["name"] for t in out["topics"]} == set(g.load_meta()["topics"])
    assert out["content"] is None and out["topic"] is None


async def test_topic_and_schema_content():
    out = await _call(topic=" Cookbook ")
    assert out["topic"] == "cookbook" and out["content"].startswith("#")
    assert out["skill_status"] == "unknown" and out["notice"]
    sch = await _call(topic="schema:MCQ")
    assert sch["topic"] == "schema:mcq" and sch["content"].startswith("# mcq")


@pytest.mark.parametrize("topic, code", [("nope", "unknown_topic"), ("schema:nope", "unknown_screen_type")])
async def test_unknown_topic_errors_list_options(topic, code):
    with pytest.raises(ToolError, match=code) as e:
        await _call(topic=topic)
    assert "cookbook" in str(e.value) or "mcq" in str(e.value)


async def test_old_skill_gets_notice():
    out = await _call(skill_version="2.3.1")
    assert out["skill_status"] == "incompatible" and "UYUMSUZ" in out["notice"]


async def test_tool_registered_and_instructions_mention_it():
    async with Client(server.mcp) as c:
        names = {t.name for t in await c.list_tools()}
    assert "get_guide" in names and len(names) == 47
    assert "get_guide" in server.mcp.instructions and "2.4.0" in server.mcp.instructions


async def test_guides_only_mention_registered_tools():
    async with Client(server.mcp) as c:
        names = {t.name for t in await c.list_tools()}
    for p in g.GUIDES_DIR.glob("*.md"):
        for m in re.finditer(r"`([a-z_][a-z0-9_]*)\(", p.read_text(encoding="utf-8")):
            n = m.group(1)
            if n in _NOT_TOOLS:
                continue
            assert n in names, (p.name, n)


def test_instructions_follow_meta_version():
    # final inceleme M4: instructions'taki skill sürümü _meta.json'dan gelir (elle yazılmaz → eskimez)
    text = server._guide_instructions({"skill_latest": "9.9.9"})
    assert "9.9.9" in text and "2.4.0" not in text
    assert g.load_meta()["skill_latest"] in server.mcp.instructions
