"""tests/test_integrations.py — Köken (provenance) ve entegrasyon testleri."""

import pytest
from unittest.mock import AsyncMock, patch

from core.integrations.provenance.base import validate_provenance, Provenance
from core.integrations.provenance.openverse import OpenverseAdapter
from auth.errors import ToolError

def test_validate_provenance_success():
    manifest = {
        "img/test.png": {
            "source": "cc0",
            "license": "CC0-1.0",
            "url": "https://example.com/img.png",
            "retrieved_at": "2023-10-27"
        },
        "img/ai.png": Provenance(
            source="ai-generated",
            license="Custom",
            retrieved_at="2023-10-27"
        )
    }
    # Hata fırlatmamalı
    validate_provenance(manifest)

def test_validate_provenance_invalid_source():
    manifest = {
        "img/stolen.png": {
            "source": "copyrighted",  # Yasaklı
            "license": "None",
            "retrieved_at": "2023-10-27"
        }
    }
    with pytest.raises(ToolError) as exc:
        validate_provenance(manifest)
    assert "provenance_error" in str(exc.value.code)

def test_validate_provenance_missing_field():
    manifest = {
        "img/bad.png": {
            "source": "cc0"
            # retrieved_at eksik
        }
    }
    with pytest.raises(ToolError):
        validate_provenance(manifest)

@pytest.mark.asyncio
async def test_openverse_adapter_success():
    adapter = OpenverseAdapter()
    
    mock_api_resp = {
        "results": [{
            "url": "https://images.openverse.org/test.jpg",
            "license": "cc0",
            "license_version": "1.0",
            "foreign_landing_url": "https://example.com/test",
            "creator": "Artist",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"
        }]
    }

    with patch("httpx.AsyncClient.get") as mock_get, \
         patch("core.integrations.provenance.openverse.safe_fetch_asset") as mock_fetch:
        
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_api_resp,
            raise_for_status=lambda: None
        )
        mock_fetch.return_value = (b"fake_image_data", "image/jpeg")

        img_bytes, prov = await adapter.fetch("cat")

        assert img_bytes == b"fake_image_data"
        assert prov.source == "cc0"
        assert prov.author == "Artist"
        assert prov.license == "1.0"

@pytest.mark.asyncio
async def test_openverse_adapter_no_results():
    adapter = OpenverseAdapter()
    
    mock_api_resp = {"results": []}

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_api_resp,
            raise_for_status=lambda: None
        )
        
        with pytest.raises(ToolError) as exc:
            await adapter.fetch("nonexistent_thing")
        assert exc.value.code == "asset_not_found"
