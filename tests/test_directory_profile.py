"""Dizin profili (DIRECTORY_PROFILE): model tabanlı TTS kapalı (araç gizli + build_from_spec yolu kapalı);
ChatGPT alan doğrulaması (/.well-known/openai-apps-challenge)."""
import httpx
from fastmcp import Client

import server


async def _get(path):
    transport = httpx.ASGITransport(app=server.mcp.http_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get(path)


async def test_openai_challenge_serves_configured_token(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "openai_apps_challenge", "tok-abc123")
    r = await _get("/.well-known/openai-apps-challenge")
    assert r.status_code == 200 and r.text == "tok-abc123"
    assert r.headers["content-type"].startswith("text/plain")


async def test_openai_challenge_404_when_unset(monkeypatch):
    monkeypatch.setattr(server.SETTINGS, "openai_apps_challenge", "")
    assert (await _get("/.well-known/openai-apps-challenge")).status_code == 404


async def test_directory_profile_hides_tts_tool_and_blocks_spec_tts(monkeypatch):
    called = []
    from core import tts
    monkeypatch.setattr(tts, "piper_available", lambda v=None: True)

    async def fake_synth(text, voice=None):
        called.append(text)
        return b"RIFF"

    monkeypatch.setattr(tts, "synthesize", fake_synth)
    server._apply_directory_profile(True)
    try:
        async with Client(server.mcp) as c:
            names = {t.name for t in await c.list_tools()}
            assert "synthesize_speech" not in names
            spec = {"title": "t", "auto_tts": True,
                    "screens": [{"type": "content_slide", "title": "a", "narration_text": "merhaba"}]}
            out = (await c.call_tool("build_from_spec", {"spec": spec})).data
        assert called == []
        assert any("tts" in w.lower() for w in (out.get("warnings") if isinstance(out, dict)
                                                 else getattr(out, "warnings", []) or []))
    finally:
        server._apply_directory_profile(False)
    async with Client(server.mcp) as c:
        assert "synthesize_speech" in {t.name for t in await c.list_tools()}
