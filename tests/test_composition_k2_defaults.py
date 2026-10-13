import pytest
from fastmcp import Client
from pydantic import ValidationError

import server
from core.project import CompositionDefaults, CourseSpec, Project


def test_defaults_none_by_default_and_validated():
    assert Project(id="p", title="t").composition_defaults is None
    assert CourseSpec(title="t", screens=[]).composition_defaults is None
    with pytest.raises(ValidationError):
        CompositionDefaults(visual="wide")


async def _project(pid):
    return await server._load(pid, await server._owner())


async def test_build_from_spec_carries_defaults():
    spec = {"title": "x", "composition_defaults": {"visual": "stack"},
            "screens": [{"type": "title_slide", "title": "a"}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
    assert (await _project(pid)).composition_defaults.visual == "stack"


async def test_set_composition_visual():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
        await c.call_tool("set_composition", {"project_id": pid, "mode": "auto",
                                              "visual": "split"})
    p = await _project(pid)
    assert p.composition == "auto" and p.composition_defaults.visual == "split"


async def test_set_composition_without_visual_keeps_defaults():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
        await c.call_tool("set_composition", {"project_id": pid, "mode": "auto",
                                              "visual": "stack"})
        await c.call_tool("set_composition", {"project_id": pid, "mode": "auto"})
    assert (await _project(pid)).composition_defaults.visual == "stack"
