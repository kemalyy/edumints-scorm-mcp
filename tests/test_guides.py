"""get_guide — rehber yükleme, sürüm karşılaştırma, notice (spec §3–§5)."""
import json
from pathlib import Path

import pytest

from core import guides as g

META = {"skill_latest": "2.4.0", "skill_min_compatible": "2.4.0",
        "download_url": "https://example.test/skill",
        "changes": {"2.3.0": "eski", "2.4.0": "yeni sürüm özeti"}, "topics": {}}


def test_topics_match_files_and_size_limit():
    meta = g.load_meta()
    files = sorted(p.stem for p in g.GUIDES_DIR.glob("*.md"))
    assert files == sorted(meta["topics"])
    assert files == sorted(["cookbook", "composition", "screen-types", "artifact", "media", "themes", "video"])
    for t in g.topics():
        assert 0 < t["size_bytes"] <= g.MAX_GUIDE_BYTES, t
        assert t["summary"]


def test_read_topic_normalizes_and_rejects_unknown():
    assert g.read_topic(g.normalize_topic(" Cookbook ")).startswith("#")
    with pytest.raises(KeyError):
        g.read_topic("nope")


def test_guides_do_not_link_moved_skill_files():
    moved = ("mcp-cookbook", "composition", "screen-types", "artifact-to-scorm", "media", "themes",
             "video-generation")
    for p in g.GUIDES_DIR.glob("*.md"):
        s = p.read_text(encoding="utf-8")
        for m in moved:
            assert f"references/{m}.md" not in s, (p.name, m)
        assert "scorm.edumints.com" not in s, p.name


@pytest.mark.parametrize("raw, want", [("2.4.0", (2, 4, 0)), ("v2.4.0", (2, 4, 0)), (" 2.4 ", (2, 4, 0)),
                                       ("2.10.1", (2, 10, 1)), ("abc", None), ("", None), (None, None)])
def test_parse_version(raw, want):
    assert g.parse_version(raw) == want


@pytest.mark.parametrize("v, status", [("2.4.0", "current"), ("2.5.0", "current"), ("v2.4", "current"),
                                       ("2.3.1", "incompatible"), (None, "unknown"), ("abc", "unknown")])
def test_skill_status(v, status):
    st, notice = g.skill_status(v, META)
    assert st == status
    assert (notice is None) == (status == "current")
    if notice:
        assert "https://example.test/skill" in notice


def test_outdated_lists_changes_since_version():
    meta = dict(META, skill_min_compatible="2.3.0")
    st, notice = g.skill_status("2.3.0", meta)
    assert st == "outdated" and "yeni sürüm özeti" in notice and "eski" not in notice


def test_download_url_env_override(monkeypatch):
    monkeypatch.setenv("SKILL_DOWNLOAD_URL", "https://self.host/skill.zip")
    assert g.download_url(META) == "https://self.host/skill.zip"
    monkeypatch.setenv("SKILL_DOWNLOAD_URL", "  ")
    assert g.download_url(META) == "https://example.test/skill"


def test_dockerfile_copies_guides():
    assert "COPY guides ./guides" in Path("Dockerfile").read_text()


def test_meta_is_valid_json():
    json.loads((g.GUIDES_DIR / "_meta.json").read_text(encoding="utf-8"))
