"""auth/ssrf.py — SSRF guard + güvenli asset çekimi (CONTRACTS.md §6, §6.1).

add_asset / build_from_spec dış URL çektiği için bağlayıcı kurallar:
  - yalnız https://, userinfo reddi
  - DNS çözümle, ÇÖZÜLEN tüm IP'leri blok listesine göre denetle (DNS rebinding'e karşı)
  - yönlendirmeleri takip ETME; her hop'u yeniden denetle
  - stream sırasında MAX_ASSET_MB kes (Content-Length'e güvenme)
  - mime izinli listede olmalı
Blok: loopback/private/link-local/CGNAT(100.64/10)/ULA(fc00::/7)/metadata
(169.254.169.254 + fd00:ec2::254)/unspecified/multicast/reserved + IPv4-mapped yeniden denetim.
"""

from __future__ import annotations

import base64
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from .errors import ToolError

DEFAULT_ALLOWED_MIMES = (
    "image/",
    # video — tarayıcı-oynatabilir; çapraz-MCP/ffmpeg çıktıları (Faz 3)
    "video/mp4",
    "video/webm",
    "video/ogg",
    # audio — TTS/seslendirme MCP çıktıları (mp3/m4a/aac/ogg/wav/webm)
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "application/pdf",
    "application/json",  # Lottie animasyon verisi (Faz 7)
    # #145 — WebVTT altyazı hattı. Düz metin biçimi; oynatıcıya <track> olarak girer, ASLA
    # HTML olarak yürütülmez. Bazı sunucular .vtt'yi text/plain ile servis ediyor, o yüzden
    # ikisi de kabul edilir (uzantı/kullanım yeri belirleyici, mime tek başına değil).
    "text/vtt",
    "text/plain",
    "font/",
)

# Açık ek blok listesi (ipaddress bayraklarının kaçırabildikleri)
_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
}
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_ULA = ipaddress.ip_network("fc00::/7")


def _is_blocked_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    # IPv4-mapped IPv6 → eşlenen IPv4'e göre yeniden denetle
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    if ip in _METADATA_IPS:
        return True
    if ip.version == 4 and ip in _CGNAT:
        return True
    if ip.version == 6 and ip in _ULA:
        return True
    return False


def _resolve_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ToolError("asset_error", f"DNS çözümlenemedi: {host} ({e})")
    return list({info[4][0] for info in infos})


def assert_safe_url(url: str) -> list[str]:
    """URL güvenli mi? Değilse ToolError. Güvenliyse çözülen IP listesini döndürür."""
    p = urlparse(url)
    if p.scheme != "https":
        raise ToolError("asset_error", "Yalnız https:// desteklenir")
    if "@" in (p.netloc or "") or p.username or p.password:
        raise ToolError("asset_error", "URL'de kullanıcı bilgisi (userinfo) yasak")
    host = p.hostname
    if not host:
        raise ToolError("asset_error", "Geçersiz host")
    ips = _resolve_ips(host)
    for ip in ips:
        if _is_blocked_ip(ip):
            raise ToolError("asset_error", f"Engelli IP aralığı: {ip} ({host})")
    return ips


def _mime_allowed(mime: str, allowed=DEFAULT_ALLOWED_MIMES) -> bool:
    mime = (mime or "").split(";")[0].strip().lower()
    return any(mime.startswith(a) if a.endswith("/") else mime == a for a in allowed)


async def safe_fetch_asset(
    url: str,
    *,
    max_bytes: int,
    allowed_mimes=DEFAULT_ALLOWED_MIMES,
    connect_timeout: float = 5.0,
    total_timeout: float = 30.0,
    max_redirects: int = 3,
) -> tuple[bytes, str]:
    """Güvenli https asset çekimi. (bytes, mime) döndürür."""
    timeout = httpx.Timeout(total_timeout, connect=connect_timeout)
    hops = 0
    current = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
        while True:
            assert_safe_url(current)  # her hop yeniden denetlenir
            async with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    hops += 1
                    if hops > max_redirects:
                        raise ToolError("asset_error", "Çok fazla yönlendirme")
                    loc = resp.headers.get("location")
                    if not loc:
                        raise ToolError("asset_error", "Yönlendirmede Location yok")
                    current = str(httpx.URL(current).join(loc))
                    continue
                if resp.status_code >= 400:
                    raise ToolError("asset_error", f"HTTP {resp.status_code}")
                mime = resp.headers.get("content-type", "application/octet-stream")
                if not _mime_allowed(mime, allowed_mimes):
                    raise ToolError("asset_error", f"İzin verilmeyen mime: {mime}")
                chunks = bytearray()
                async for chunk in resp.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > max_bytes:  # stream sırasında kes
                        raise ToolError("asset_error", f"Asset {max_bytes} bayt sınırını aşıyor")
                return bytes(chunks), mime.split(";")[0].strip()


def decode_data_uri(source: str, *, max_bytes: int) -> tuple[bytes, str]:
    """data:<mime>;base64,... → (bytes, mime). Ağ yok."""
    if not source.startswith("data:"):
        raise ToolError("asset_error", "Geçersiz data URI")
    try:
        header, b64 = source[5:].split(",", 1)
        mime = header.split(";")[0] or "application/octet-stream"
        data = base64.b64decode(b64)
    except Exception as e:  # noqa: BLE001
        raise ToolError("asset_error", f"data URI çözülemedi: {e}")
    if len(data) > max_bytes:
        raise ToolError("asset_error", f"Asset {max_bytes} bayt sınırını aşıyor")
    return data, mime
