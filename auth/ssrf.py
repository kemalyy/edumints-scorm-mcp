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

import asyncio
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

# v1.9.1 — bilinçli HTML asset'leri (embed_html; yalnız sandbox'lı iframe'de çalışır) için AYRI profil.
# Varsayılan listeye girmez; yalnız çağrı yeri açıkça isterse (build_from_spec assets) eklenir — o zaman
# data-URI ve URL yolu aynı listeyi kullanır.
HTML_MIMES = ("text/html", "application/xhtml+xml")

# image/* (svg hariç) içerik imzaları — bildirilen MIME'a değil baytlara bakılır (HTML'i "image/png" diye
# sokmayı engeller). Tam tür eşleşmesi aranmaz: sunucular jpeg/webp'yi sıkça yanlış etiketler.
_IMAGE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM",
                     b"\x00\x00\x01\x00", b"\x00\x00\x02\x00", b"II*\x00", b"MM\x00*")


def check_signature(data: bytes, mime: str) -> None:
    """image/* (svg hariç) bildirilen içerik bilinen bir görsel imzası taşımalı; değilse ToolError."""
    m = (mime or "").split(";")[0].strip().lower()
    if not m.startswith("image/") or m == "image/svg+xml":
        return
    ok = (data.startswith(_IMAGE_SIGNATURES)
          or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
          or data[4:8] == b"ftyp")  # avif / heic
    if not ok:
        raise ToolError("asset_error", f"İçerik {m} imzası taşımıyor (bildirilen tür ile baytlar uyuşmuyor)")


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
    elif isinstance(ip, ipaddress.IPv6Address) and ip.sixtofour is not None:  # 6to4 (2002::/16)
        if _is_blocked_ip(str(ip.sixtofour)):
            return True
    elif isinstance(ip, ipaddress.IPv6Address) and ip.teredo is not None:  # Teredo: (sunucu, istemci)
        if any(_is_blocked_ip(str(x)) for x in ip.teredo):
            return True
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


def _url_rules(url: str):
    """Şema / userinfo / host kuralları (DNS'siz). → urlparse sonucu."""
    p = urlparse(url)
    if p.scheme != "https":
        raise ToolError("asset_error", "Yalnız https:// desteklenir")
    if "@" in (p.netloc or "") or p.username or p.password:
        raise ToolError("asset_error", "URL'de kullanıcı bilgisi (userinfo) yasak")
    if not p.hostname:
        raise ToolError("asset_error", "Geçersiz host")
    return p


def _check_ips(host: str, ips: list[str]) -> None:
    if not ips:
        raise ToolError("asset_error", f"DNS çözümlenemedi: {host}")
    for ip in ips:
        if _is_blocked_ip(ip):
            raise ToolError("asset_error", f"Engelli IP aralığı: {ip} ({host})")


def assert_safe_url(url: str) -> list[str]:
    """URL güvenli mi? Değilse ToolError. Güvenliyse çözülen IP listesini döndürür.
    Senkron ön-kontrol (arama entegrasyonları); asıl çekim `safe_fetch_asset` IP'yi sabitler."""
    p = _url_rules(url)
    ips = _resolve_ips(p.hostname)
    _check_ips(p.hostname, ips)
    return ips


async def _resolve_ips_async(host: str, port: int) -> list[str]:
    """v1.9.1 (P1) — event loop'u bloklamayan DNS çözümlemesi."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ToolError("asset_error", f"DNS çözümlenemedi: {host} ({e})")
    return list(dict.fromkeys(info[4][0] for info in infos))


async def _pin(url: str) -> tuple[list[httpx.URL], str, str]:
    """v1.9.1 — URL'yi denetle ve bağlantıyı denetlenen IP'lere sabitle.
    → (IP'li hedef URL'ler — çözümleme sırasıyla, hepsi denetlenmiş; Host başlığı; SNI adı). Bağlantı
    sırasında ikinci bir DNS çözümlemesi olmaz; TLS SNI + sertifika doğrulaması orijinal ada göre yapılır
    (httpx `sni_hostname` eklentisi)."""
    p = _url_rules(url)
    host, port = p.hostname, p.port or 443
    try:
        ipaddress.ip_address(host)
        ips = [host]  # IP literal: çözümleme yok
    except ValueError:
        ips = await _resolve_ips_async(host, port)
    _check_ips(host, ips)
    base = httpx.URL(url)
    shown = f"[{host}]" if ":" in host else host  # IPv6 literal Host başlığında köşeli parantezli
    host_header = shown if p.port in (None, 443) else f"{shown}:{p.port}"
    return [base.copy_with(host=ip) for ip in ips], host_header, host


async def assert_safe_url_async(url: str) -> list[str]:
    """`assert_safe_url`'ün event loop'u bloklamayan sürümü (arama entegrasyonları)."""
    p = _url_rules(url)
    ips = await _resolve_ips_async(p.hostname, p.port or 443)
    _check_ips(p.hostname, ips)
    return ips


_HTML_EXTS = (".html", ".htm", ".xhtml", ".xht")


def check_extension(filename: str | None, mime: str, *, html_ok: bool = False) -> None:
    """v1.9.1 — dosya uzantısı ↔ MIME: HTML uzantısı yalnız HTML profili açık çağrı yerinde ve HTML MIME
    ile; .svg yalnız image/svg+xml ile (LMS dosyayı uzantısına göre servis eder → etiket atlatılmasın)."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if filename and "." in filename else ""
    m = (mime or "").split(";")[0].strip().lower()
    if ext in _HTML_EXTS and not (html_ok and m in HTML_MIMES):
        raise ToolError("asset_error", f"'{ext}' uzantısı bu çağrıda / {m} türüyle kullanılamaz")
    if ext == ".svg" and m != "image/svg+xml":
        raise ToolError("asset_error", f"'.svg' uzantısı {m} türüyle kullanılamaz")


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
    _transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bytes, str]:
    """Güvenli https asset çekimi. (bytes, mime) döndürür. v1.9.1: her hop denetlenen IP'ye
    sabitlenir; DNS asenkron; `total_timeout` yönlendirmeler + gövde akışı dahil gerçek üst sınırdır."""
    try:
        async with asyncio.timeout(total_timeout):
            return await _fetch(url, max_bytes=max_bytes, allowed_mimes=allowed_mimes,
                                connect_timeout=connect_timeout, max_redirects=max_redirects,
                                transport=_transport)
    except TimeoutError:
        raise ToolError("asset_error", f"Asset çekimi zaman aşımı ({total_timeout:g} sn)")


async def _fetch(url, *, max_bytes, allowed_mimes, connect_timeout, max_redirects, transport):
    hops = 0
    current = url
    while True:
        targets, host_header, sni = await _pin(current)  # her hop yeniden denetlenir + sabitlenir
        result = await _fetch_hop(targets, host_header, sni, max_bytes=max_bytes, allowed_mimes=allowed_mimes,
                                  connect_timeout=connect_timeout, transport=transport)
        if isinstance(result, str):  # yönlendirme
            hops += 1
            if hops > max_redirects:
                raise ToolError("asset_error", "Çok fazla yönlendirme")
            current = str(httpx.URL(current).join(result))
            continue
        return result


async def _fetch_hop(targets, host_header, sni, *, max_bytes, allowed_mimes, connect_timeout, transport):
    """Tek hop: denetlenen IP'leri sırayla dener (bağlanamazsa sonraki — çift yığınlı host'lar). Her deneme
    YENİ istemci: bağlantı havuzu hop'lar arasında paylaşılmaz (aynı IP'deki başka ad, önceki hop'un TLS
    oturumunu kullanıp sertifika denetimini atlayamaz). trust_env=False: proxy env değişkenleri sabitlemeyi
    ve SNI'yi devre dışı bırakamaz. → yönlendirme ise Location (str), değilse (bytes, mime)."""
    timeout = httpx.Timeout(None, connect=connect_timeout)
    last: Exception | None = None
    for target in targets:
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, transport=transport,
                                         trust_env=False) as client:
                return await _read(client, target, host_header, sni, max_bytes, allowed_mimes)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:  # sessizce düşen adres → sonraki IP
            last = e
    raise ToolError("asset_error", f"Bağlanılamadı: {sni} ({last})")


async def _read(client, target, host_header, sni, max_bytes, allowed_mimes):
    async with client.stream("GET", target, headers={"Host": host_header},
                     extensions={"sni_hostname": sni}) as resp:
        if resp.is_redirect:
            loc = resp.headers.get("location")
            if not loc:
                raise ToolError("asset_error", "Yönlendirmede Location yok")
            return loc
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
        check_signature(bytes(chunks), mime)
        return bytes(chunks), mime.split(";")[0].strip()


def decode_data_uri(source: str, *, max_bytes: int,
                    allowed_mimes=DEFAULT_ALLOWED_MIMES) -> tuple[bytes, str]:
    """data:<mime>;base64,... → (bytes, mime). Ağ yok. v1.9.1: URL yolu ile AYNI politika —
    MIME izin listesi, decode ÖNCESİ boyut sınırı, katı base64, image/* içerik imzası."""
    if not source.startswith("data:") or "," not in source:
        raise ToolError("asset_error", "Geçersiz data URI")
    header, b64 = source[5:].split(",", 1)
    mime = header.split(";")[0].strip().lower() or "application/octet-stream"
    if not _mime_allowed(mime, allowed_mimes):
        raise ToolError("asset_error", f"İzin verilmeyen mime: {mime}")
    b64 = "".join(b64.split())  # MIME tarzı satır sonları/boşluklar
    if len(b64) * 3 // 4 > max_bytes + 2:  # kodlanmış uzunluk → belleğe açmadan red
        raise ToolError("asset_error", f"Asset {max_bytes} bayt sınırını aşıyor")
    try:
        data = base64.b64decode(b64, validate=True)
    except Exception as e:  # noqa: BLE001
        raise ToolError("asset_error", f"data URI çözülemedi: {e}")
    if len(data) > max_bytes:
        raise ToolError("asset_error", f"Asset {max_bytes} bayt sınırını aşıyor")
    check_signature(data, mime)
    return data, mime
