"""data-URI ve URL yolu aynı içerik politikası: MIME izin listesi, decode öncesi boyut, katı base64,
image/* içerik imzası."""
import base64

import httpx
import pytest

import auth.ssrf as ssrf
from auth.errors import ToolError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
HTML = b"<!doctype html><script>alert(1)</script>"


def _uri(mime: str, data: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


async def _via_url(mime: str, data: bytes, monkeypatch, **kw):
    async def resolve(host, port):
        return ["93.184.216.34"]

    monkeypatch.setattr(ssrf, "_resolve_ips_async", resolve)
    t = httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": mime}, content=data))
    return await ssrf.safe_fetch_asset("https://cdn.test/f", max_bytes=1024, _transport=t, **kw)


async def test_forbidden_mime_rejected_alike_on_both_paths(monkeypatch):
    with pytest.raises(ToolError) as a:
        ssrf.decode_data_uri(_uri("text/html", HTML), max_bytes=1024)
    with pytest.raises(ToolError) as b:
        await _via_url("text/html", HTML, monkeypatch)
    assert a.value.code == b.value.code == "asset_error"
    assert "İzin verilmeyen mime" in str(a.value) and "İzin verilmeyen mime" in str(b.value)


def test_html_profile_allows_html_on_data_uri():
    data, mime = ssrf.decode_data_uri(_uri("text/html", HTML), max_bytes=1024,
                                      allowed_mimes=ssrf.DEFAULT_ALLOWED_MIMES + ssrf.HTML_MIMES)
    assert data == HTML and mime == "text/html"


def test_oversized_input_rejected_before_decoding(monkeypatch):
    called = []
    monkeypatch.setattr(ssrf.base64, "b64decode", lambda *a, **k: called.append(1) or b"")
    with pytest.raises(ToolError, match="sınırını aşıyor"):
        ssrf.decode_data_uri("data:image/png;base64," + "A" * 8000, max_bytes=1024)
    assert called == []


def test_strict_base64():
    with pytest.raises(ToolError, match="data URI çözülemedi"):
        ssrf.decode_data_uri("data:image/png;base64,iVBOR@@@##", max_bytes=1024)
    # satır sonlu (MIME tarzı) base64 kabul edilir
    b64 = base64.encodebytes(PNG).decode()
    assert ssrf.decode_data_uri("data:image/png;base64," + b64, max_bytes=1024)[0] == PNG


@pytest.mark.parametrize("data", [HTML, b"hello", b""])
async def test_image_signature_must_match(data, monkeypatch):
    with pytest.raises(ToolError, match="imza"):
        ssrf.decode_data_uri(_uri("image/png", data), max_bytes=1024)
    with pytest.raises(ToolError, match="imza"):
        await _via_url("image/png", data, monkeypatch)


@pytest.mark.parametrize("mime, data", [("image/png", PNG), ("image/jpeg", JPEG), ("image/jpeg", PNG),
                                        ("image/svg+xml", b"<svg xmlns='http://www.w3.org/2000/svg'/>"),
                                        ("audio/mpeg", b"ID3\x03"), ("application/pdf", b"%PDF-1.7")])
def test_valid_content_accepted(mime, data):
    out, m = ssrf.decode_data_uri(_uri(mime, data), max_bytes=1024)
    assert out == data and m == mime
