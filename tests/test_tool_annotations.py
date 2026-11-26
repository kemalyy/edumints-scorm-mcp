"""Dizin başvurusu: her araç gerçek tools/list çıktısında title + readOnlyHint/destructiveHint taşır;
sınıflandırma gerçek yan etkilere göre."""
import pytest
from fastmcp import Client

import server

READ_ONLY = {"list_screens", "lint_course", "export_qti", "list_demos", "build_status", "validate_package",
             "list_feedback", "list_screen_types", "list_themes", "list_compositions", "get_guide",
             "search_images", "scenario_tree", "scenario_gaps", "scenario_compile", "match_media_manifest"}
DESTRUCTIVE = {"remove_screen", "update_screen", "unpublish_demo", "scenario_delete_node", "scenario_delete_page",
               "revoke_links", "publish_demo"}
OPEN_WORLD = {"add_asset", "build_from_spec", "wrap_artifact", "search_images", "publish_demo", "fill_media_slot"}


async def _tools():
    async with Client(server.mcp) as c:
        return {t.name: t for t in await c.list_tools()}


async def test_every_tool_has_title_and_hints():
    tools = await _tools()
    assert len(tools) == 48
    for name, t in tools.items():
        a = t.annotations
        assert a is not None and a.title, name
        assert a.readOnlyHint is not None, name
        if not a.readOnlyHint:
            assert a.destructiveHint is not None, name
        assert a.openWorldHint is not None, name


async def test_classification_matches_side_effects():
    tools = await _tools()
    for name, t in tools.items():
        a = t.annotations
        assert a.readOnlyHint is (name in READ_ONLY), name
        if name not in READ_ONLY:
            assert a.destructiveHint is (name in DESTRUCTIVE), name
        assert a.openWorldHint is (name in OPEN_WORLD), name


@pytest.mark.parametrize("name", sorted(READ_ONLY | DESTRUCTIVE | OPEN_WORLD))
async def test_classified_names_exist(name):
    assert name in await _tools()
