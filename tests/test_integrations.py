"""tests/test_integrations.py — Provenance ve Openverse entegrasyon testleri."""

import pytest
from unittest.mock import patch, MagicMock
from core.integrations.base import validate_provenance
from core.integrations.openverse import OpenverseAdapter
from auth.errors import ToolError

def test_provenance_validation_valid():
    """Geçerli provenance kayıtlarını doğrula."""
    manifest = {
        "assets/img1.png": {
            "source": "cc0",
            "license": "CC0",
            "url": "https://example.com/img1.png",
            "retrieved_at": "2024-01-01"
        },
        "assets/img2.jpg": {
            "source": "ai-generated",
            "license": "Custom",
            "author": "DALL-E 3"
        }
    }
    # Hata fırlatmamalı
    validate_provenance(manifest)

def test_provenance_validation_invalid_source():
    """İzin verilmeyen kaynak hatası."""
    manifest = {
        "assets/bad.png": {
            "source": "found-on-internet",  # Yasak
            "license": "Unknown"
        }
    }
    with pytest.raises(ValueError, match="Geçersiz provenance"):
        validate_provenance(manifest)

def test_provenance_validation_missing():
    """Eksik provenance hatası."""
    manifest = {
        "assets/missing.png": {}
    }
    with pytest.raises(ValueError, match="provenance eksik"):
        validate_provenance(manifest)

@pytest.mark.asyncio
async def test_openverse_adapter_success():
    """Openverse başarılı sonuç dönme senaryosu."""
    mock_api_resp = {
        "results": [{
            "url": "https://safe.com/image.jpg",
            "license": "cc0",
            "creator": "Artist Name",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"
        }]
    }
    
    with patch("core.integrations.openverse.assert_safe_url") as mock_assert, \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("core.integrations.openverse.safe_fetch_asset") as mock_fetch:
        
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)
        mock_fetch.return_value = (b"fake_binary_data", "image/jpeg")
        
        adapter = OpenverseAdapter()
        content, provenance = await adapter.fetch("cats")
        
        assert content == b"fake_binary_data"
        assert provenance.source == "cc0"
        assert provenance.license == "CC0"
        assert provenance.author == "Artist Name"
        assert mock_assert.called
        assert mock_fetch.called

@pytest.mark.asyncio
async def test_openverse_adapter_no_results():
    """Sonuç bulunamadığında graceful degrade."""
    mock_api_resp = {"results": []}
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)
        
        adapter = OpenverseAdapter()
        content, provenance = await adapter.fetch("nothingness")
        
        assert content is None
        assert provenance is None

@pytest.mark.asyncio
async def test_openverse_adapter_ssrf_blocked():
    """SSRF bloklandığında graceful degrade (hata fırlatmaz, None döner)."""
    with patch("core.integrations.openverse.assert_safe_url") as mock_assert:
        mock_assert.side_effect = ToolError("asset_error", "Engelli IP")
        
        adapter = OpenverseAdapter()
        content, provenance = await adapter.fetch("dangerous")
        
        assert content is None
        assert provenance is None

@pytest.mark.asyncio
async def test_openverse_adapter_http_error():
    """HTTP hatasında graceful degrade."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=500)
        
        adapter = OpenverseAdapter()
        content, provenance = await adapter.fetch("error")
        
        assert content is None
        assert provenance is None
