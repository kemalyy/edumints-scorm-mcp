"""tests/test_integrations_sources.py — Wikimedia ve GenerativeSVG testleri."""

import pytest
from unittest.mock import patch, MagicMock
from core.integrations.wikimedia import WikimediaAdapter
from core.integrations.generative_svg import GenerativeSVGAdapter
from auth.errors import ToolError

@pytest.mark.asyncio
async def test_wikimedia_adapter_success():
    """Wikimedia başarılı sonuç dönme senaryosu."""
    mock_api_resp = {
        "query": {
            "pages": {
                "123": {
                    "imageinfo": [{
                        "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:test.jpg",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC0"},
                            "Artist": {"value": "Wikimedia Artist"}
                        }
                    }]
                }
            }
        }
    }
    
    with patch("core.integrations.wikimedia.assert_safe_url") as mock_assert, \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("core.integrations.wikimedia.safe_fetch_asset") as mock_fetch:
        
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)
        mock_fetch.return_value = (b"wikimedia_data", "image/jpeg")
        
        adapter = WikimediaAdapter()
        content, provenance = await adapter.fetch("test")
        
        assert content == b"wikimedia_data"
        assert provenance.source == "cc0"
        assert provenance.license == "CC0"
        assert provenance.author == "Wikimedia Artist"
        assert mock_assert.called
        assert mock_fetch.called

@pytest.mark.asyncio
async def test_wikimedia_adapter_license_filtering():
    """İzin verilmeyen lisanslı görselleri atlamalı."""
    mock_api_resp = {
        "query": {
            "pages": {
                "123": {
                    "imageinfo": [{
                        "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC-BY-SA-4.0"} # Yasak
                        }
                    }]
                }
            }
        }
    }
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)
        
        adapter = WikimediaAdapter()
        content, provenance = await adapter.fetch("test")
        
        assert content is None
        assert provenance is None

@pytest.mark.asyncio
async def test_wikimedia_adapter_ssrf_blocked():
    """SSRF bloklandığında graceful degrade."""
    with patch("core.integrations.wikimedia.assert_safe_url") as mock_assert:
        mock_assert.side_effect = ToolError("asset_error", "Engelli IP")
        
        adapter = WikimediaAdapter()
        content, provenance = await adapter.fetch("dangerous")
        
        assert content is None
        assert provenance is None

@pytest.mark.asyncio
async def test_generative_svg_adapter():
    """SVG üretimi ve provenance doğrulaması."""
    adapter = GenerativeSVGAdapter()
    content, provenance = await adapter.fetch("hello")
    
    assert content.startswith(b"<svg")
    assert b"hello" in content
    assert provenance.source == "ai-generated"
    assert provenance.license == "CC0"
    assert provenance.author == "GenerativeSVGAdapter"

@pytest.mark.asyncio
async def test_wikimedia_adapter_no_results():
    """Sonuç bulunamadığında graceful degrade."""
    mock_api_resp = {"query": {"pages": {}}}
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)
        
        adapter = WikimediaAdapter()
        content, provenance = await adapter.fetch("nothing")
        
        assert content is None
        assert provenance is None
