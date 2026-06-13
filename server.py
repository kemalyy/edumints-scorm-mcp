"""scorm-mcp — FastMCP sunucusu (CONTRACTS.md §3, §5, §3.1).

Streamable HTTP transport (transport="http"); stdio yalnız lokal test. ROOT_PATH altında
çalışabilir; tam URL'ler PUBLIC_BASE_URL'den üretilir. Çoklu API-key + kota (auth/).

Mimari ilke: sunucu LLM çağırmaz; yalnız iskele + bileşen + runtime + paketleme.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from pathlib import Path

import nh3
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError as MCPToolError
from fastmcp.server.dependencies import get_access_token, get_http_headers
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

import components.renderer as renderer
from auth import (
    ToolError,
    decode_data_uri,
    enforce_project_quota,
    enforce_size_quota,
    parse_bearer,
    safe_fetch_asset,
    verify_key,
)
from auth.oauth import make_jwt_verifier
from core.packager import Packager
from core.project import (
    AddScreenOut,
    AssetRef,
    BuildFromSpecOut,
    BuildOut,
    CompletionRule,
    CourseSpec,
    CreateProjectOut,
    ListScreensOut,
    OkOut,
    PreviewOut,
    Project,
    Screen,
    ScreenSummary,
    ThemeTokens,
    Tracking,
    ValidateOut,
    new_asset_id,
    new_feedback_id,
    new_key_id,
    new_screen_id,
    utcnow,
)
from core.store import ApiKey, Feedback, create_store
from core.validator import validate_project, validate_zip

import secrets


# --------------------------------------------------------------------------- #
# Ayarlar (CONTRACTS.md §8)
# --------------------------------------------------------------------------- #
class Settings:
    def __init__(self) -> None:
        self.public_base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
        self.root_path = os.environ.get("ROOT_PATH", "")
        self.data_dir = os.environ.get("DATA_DIR", "./data")
        self.port = int(os.environ.get("PORT", "8000"))
        self.host = os.environ.get("HOST", "0.0.0.0")
        self.db_path = os.environ.get("DB_PATH", os.path.join(self.data_dir, "scorm.db"))
        self.package_ttl_days = int(os.environ.get("PACKAGE_TTL_DAYS", "7"))
        self.max_project_mb = int(os.environ.get("MAX_PROJECT_MB", "50"))
        self.max_projects_per_key = int(os.environ.get("MAX_PROJECTS_PER_KEY", "100"))
        self.max_asset_mb = int(os.environ.get("MAX_ASSET_MB", "25"))
        self.build_workers = int(os.environ.get("BUILD_WORKERS", "8"))
        self.scorm_default_version = os.environ.get("SCORM_DEFAULT_VERSION", "1.2")
        self.preview_ttl_min = int(os.environ.get("PREVIEW_TTL_MIN", "60"))
        self.auth_enabled = os.environ.get("SCORM_AUTH_ENABLED", "1") not in ("0", "false", "")
        # OAuth resource-server (INTEGRATION.md) — IdP-agnostik, yalnız standart OIDC.
        # issuer/jwks/audience BİREBİR eşleşmeli (trailing slash / http(s) / /mcp dahil).
        self.logto_issuer = os.environ.get("LOGTO_ISSUER", "").rstrip("/")
        self.logto_jwks = os.environ.get("LOGTO_JWKS", "")
        self.mcp_audience = os.environ.get("MCP_AUDIENCE", "")
        self.logto_alg = os.environ.get("LOGTO_ALG", "ES384")  # Logto EC imzası; RS256 uyuşmaz→401
        # OAuth yalnız issuer+jwks+audience'ın üçü de verildiyse etkin (yoksa sadece API-key).
        self.oauth_enabled = bool(self.logto_issuer and self.logto_jwks and self.mcp_audience)


SETTINGS = Settings()
THEMES_DIR = Path(__file__).resolve().parent / "themes"


# --------------------------------------------------------------------------- #
# Servisler (lazy init — sunucu loop'unda)
# --------------------------------------------------------------------------- #
class Services:
    def __init__(self) -> None:
        self.store = create_store(SETTINGS.db_path, SETTINGS.data_dir)
        self.packager: Packager | None = None
        self._ready = False
        self._lock = asyncio.Lock()

    async def ensure(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            await self.store.init()
            self.packager = Packager(
                self.store,
                SETTINGS.data_dir,
                workers=SETTINGS.build_workers,
                renderer=renderer,
                public_base_url=SETTINGS.public_base_url,
                package_ttl_days=SETTINGS.package_ttl_days,
            )
            await self.packager.start_ttl_cleaner()
            _jwt_verifier()  # C1: JWT doğrulayıcıyı startup'ta warm et (lazy-global race'i önler)
            self._ready = True


SVC = Services()


def _build_auth():
    """Dual-auth sağlayıcısı (OAuth + API-key) — yalnız OAuth env'leri verildiyse.

    Verilmezse None döner: FastMCP auth'suz çalışır, tool'lar API-key'i _owner()'da elle çözer
    (lokal/test ve SCORM_AUTH_ENABLED=0 senaryosu).
    """
    if not SETTINGS.oauth_enabled:
        return None
    from auth.oauth import ApiKeyVerifier, build_auth_provider

    api_key_verifier = ApiKeyVerifier(ensure=SVC.ensure, get_key=lambda raw: SVC.store.get_key(raw))
    return build_auth_provider(
        issuer=SETTINGS.logto_issuer,
        jwks_uri=SETTINGS.logto_jwks,
        audience=SETTINGS.mcp_audience,
        base_url=SETTINGS.public_base_url,
        api_key_verifier=api_key_verifier,
        algorithm=SETTINGS.logto_alg,
    )


mcp = FastMCP(name="scorm-mcp", auth=_build_auth())


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def _wrap(err: ToolError) -> MCPToolError:
    return MCPToolError(f"{err.code}: {err.message}")


async def _owner() -> ApiKey:
    """Auth context'inden owner'ı çözer (dual-auth: OAuth VEYA API-key; CONTRACTS.md §3).

    owner_key_id, kotanın ve proje sahipliğinin anahtarıdır:
      - API-key  → key.id
      - OAuth    → "logto:<sub>" (Logto kullanıcı subject'i)
    """
    if SETTINGS.oauth_enabled:
        # FastMCP MultiAuth token'ı transport katmanında doğruladı (OAuth JWT veya API-key).
        tok = get_access_token()
        if tok is None:
            raise ToolError("unauthorized", "Geçerli OAuth token veya API anahtarı gerekli")
        claims = getattr(tok, "claims", None) or {}
        if claims.get("auth") == "apikey":
            # principal = owner_principal (kimliğe bağlı portal key'i) VEYA eski key'lerde key_id.
            pid = claims.get("owner_principal") or claims["key_id"]
            return ApiKey(
                id=pid, label="apikey", key_hash="",
                max_projects=claims.get("max_projects", SETTINGS.max_projects_per_key),
                max_total_mb=claims.get("max_total_mb", SETTINGS.max_project_mb),
            )
        # OAuth (Logto) kullanıcısı — C5: onay = scorm 'mcp' scope (mcp-user/portal-admin rolü).
        # Scope yoksa kullanıcı onaysız → forbidden (araçlar açılmaz). API-key yolu bu noktaya gelmez
        # (üstte erken döner; ApiKeyVerifier zaten scopes=['mcp'] verir).
        sub = getattr(tok, "subject", None) or claims.get("sub") or "unknown"
        if "mcp" not in (getattr(tok, "scopes", None) or []):
            raise ToolError(
                "forbidden",
                "Hesabın henüz onaylanmadı. Bir yönetici onayladıktan sonra araçlar açılır "
                "(mcp.edumints.com). Onaylandıysan Claude'da connector'ı yeniden bağla.",
            )
        return ApiKey(
            id=f"logto:{sub}", label="logto-user", key_hash="",
            max_projects=SETTINGS.max_projects_per_key, max_total_mb=SETTINGS.max_project_mb,
        )

    # OAuth kapalı (lokal/test veya API-key-only): başlıktan elle çöz.
    headers = get_http_headers(include_all=True) or {}
    raw = parse_bearer(headers)
    if raw is None and not SETTINGS.auth_enabled:
        return ApiKey(
            id="key_local", label="local-dev", key_hash="",
            max_projects=SETTINGS.max_projects_per_key, max_total_mb=SETTINGS.max_project_mb,
        )
    return await verify_key(SVC.store, raw)


_JWT_VERIFIER = None


def _jwt_verifier():
    global _JWT_VERIFIER
    if _JWT_VERIFIER is None and SETTINGS.oauth_enabled:
        _JWT_VERIFIER = make_jwt_verifier(
            issuer=SETTINGS.logto_issuer, jwks_uri=SETTINGS.logto_jwks,
            audience=SETTINGS.mcp_audience, algorithm=SETTINGS.logto_alg,
        )
    return _JWT_VERIFIER


async def _validate_bearer(raw: str | None) -> tuple[ApiKey | None, list[str]]:
    """Custom route'lar (/usage,/projects) için ham Bearer'ı doğrular: OAuth JWT VEYA API-key.

    → (principal | None, scopes). principal None → 401; 'mcp' scope yok → çağıran 403 döner (C5).
    API-key her zaman ['mcp'] taşır (ApiKeyVerifier ile aynı model).
    """
    if not raw:
        return None, []
    if raw.startswith("sk_"):
        try:
            k = await verify_key(SVC.store, raw)
        except ToolError:
            return None, []
        # principal = owner_principal (kimliğe bağlı) VEYA key.id (eski). Route'lar owner.id'yi principal sayar.
        pid = k.owner_principal or k.id
        owner = ApiKey(
            id=pid, label=k.label, key_hash="",
            max_projects=k.max_projects, max_total_mb=k.max_total_mb,
        )
        return owner, ["mcp"]
    v = _jwt_verifier()
    if v is None:
        return None, []
    at = await v.verify_token(raw)
    if at is None:
        return None, []
    sub = getattr(at, "subject", None) or (getattr(at, "claims", None) or {}).get("sub") or "unknown"
    owner = ApiKey(
        id=f"logto:{sub}", label="logto-user", key_hash="",
        max_projects=SETTINGS.max_projects_per_key, max_total_mb=SETTINGS.max_project_mb,
    )
    return owner, list(getattr(at, "scopes", None) or [])


async def _load(project_id: str, owner: ApiKey) -> Project:
    p = await SVC.store.get_project(project_id, owner.id)
    if p is None:
        raise ToolError("not_found", f"Proje bulunamadı: {project_id}")
    return p


def _load_theme(theme: str | ThemeTokens) -> ThemeTokens:
    if isinstance(theme, ThemeTokens):
        return theme
    path = THEMES_DIR / f"{theme}.json"
    if path.exists():
        return ThemeTokens.model_validate_json(path.read_text(encoding="utf-8"))
    return ThemeTokens(name="default")


def _deep_merge_theme(base: ThemeTokens, override: ThemeTokens) -> ThemeTokens:
    """Yalnız override'da AÇIKÇA verilmiş alanları base üstüne uygula (derin merge)."""
    def merge(b: dict, o_model) -> dict:
        out = dict(b)
        for name in o_model.model_fields_set:
            val = getattr(o_model, name)
            if hasattr(val, "model_fields_set"):
                out[name] = merge(out.get(name, {}), val)
            else:
                out[name] = val if not hasattr(val, "model_dump") else val.model_dump()
        return out
    merged = merge(base.model_dump(), override)
    return ThemeTokens.model_validate(merged)


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(name: str, existing: set[str]) -> str:
    base = _SAFE_NAME.sub("_", os.path.basename(name)).strip("._") or "asset"
    rel = f"assets/{base}"
    if rel in existing:
        rel = f"assets/{secrets.token_hex(3)}_{base}"
    return rel


def _summaries(p: Project) -> list[ScreenSummary]:
    return [
        ScreenSummary(id=s.id or f"idx{i}", type=s.type, title=s.title, index=i)
        for i, s in enumerate(p.screens)
    ]


def _build_out(job, pkg_token: str | None, size: int | None, scorm_version: str) -> BuildOut:
    url = SVC.packager.download_url(pkg_token) if pkg_token else None
    return BuildOut(
        job_id=job.id, status=job.status, download_url=url, size=size,
        scorm_version=scorm_version, error=job.error,
    )


async def _job_to_out(job, project: Project) -> BuildOut:
    if job.status == "done" and job.package_id:
        meta = await SVC.store.get_package(job.package_id)
        if meta:
            return _build_out(job, meta.token, meta.size_bytes, meta.scorm_version)
    return _build_out(job, None, None, project.scorm_version)


async def _build_preview(p: Project) -> tuple[str, str]:
    """Tek-dosya self-contained önizleme render eder, diske + DB'ye yazar. → (token, html)."""
    asset_data: dict[str, tuple[str, bytes]] = {}
    for a in p.assets:
        try:
            asset_data[a.id] = (a.mime, await SVC.store.get_asset_bytes(p.id, a.id))
        except FileNotFoundError:
            pass
    html = renderer.render_html(
        p, mode="preview", runtime_js=renderer.load_runtime_js(), asset_data=asset_data
    )
    token = secrets.token_urlsafe(18)
    out = Path(SETTINGS.data_dir) / "previews" / f"{token}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    await SVC.store.put_preview(token, p.id, SETTINGS.preview_ttl_min * 60)
    return token, html


async def _preview_url(p: Project) -> str:
    """Panel listesi için stabil preview URL: geçerli olanı tekrar kullan, yoksa üret."""
    existing = await SVC.store.latest_preview_for_project(p.id)
    if existing:
        path = Path(SETTINGS.data_dir) / "previews" / f"{existing.token}.html"
        if path.exists():
            return f"{SETTINGS.public_base_url}/preview/{existing.token}"
    token, _ = await _build_preview(p)
    return f"{SETTINGS.public_base_url}/preview/{token}"


# --------------------------------------------------------------------------- #
# Tool'lar (CONTRACTS.md §3)
# --------------------------------------------------------------------------- #
@mcp.tool
async def create_project(
    title: str,
    description: str = "",
    scorm_version: str = "1.2",
    theme: str = "default",
    language: str = "tr",
) -> CreateProjectOut:
    """Yeni bir SCORM projesi oluşturur."""
    await SVC.ensure()
    try:
        owner = await _owner()
        await enforce_project_quota(SVC.store, owner)
        from core.project import new_project_id

        p = Project(
            id=new_project_id(),
            title=title,
            description=description,
            scorm_version="2004" if scorm_version == "2004" else "1.2",
            language=language,
            theme=_load_theme(theme),
            owner_key_id=owner.id,
        )
        await SVC.store.create_project(p)
        return CreateProjectOut(project_id=p.id)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def add_screen(project_id: str, screen: Screen) -> AddScreenOut:
    """Projeye tipli bir ekran ekler."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        if not screen.id:
            screen.id = new_screen_id()
        p.screens.append(screen)
        await SVC.store.update_project(p)
        return AddScreenOut(screen_id=screen.id)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def update_screen(project_id: str, screen_id: str, screen: Screen) -> OkOut:
    """Var olan bir ekranı günceller."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        idx = next((i for i, s in enumerate(p.screens) if s.id == screen_id), None)
        if idx is None:
            raise ToolError("not_found", f"Ekran bulunamadı: {screen_id}")
        screen.id = screen_id
        p.screens[idx] = screen
        await SVC.store.update_project(p)
        return OkOut()
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def list_screens(project_id: str) -> ListScreensOut:
    """Projedeki ekranları sıralı listeler."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        return ListScreensOut(screens=_summaries(p))
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def lint_course(project_id: str) -> dict:
    """W6 oyun anti-slop kalite kapısı: game/adaptive_practice ekranlarını araştırma-temelli
    deterministik kurallarla denetler (içsel-bütünleşme, anlamlı seçim, scaffolding dengesi, adaptif
    anlam, a11y). İki şiddet: 'error' (yapısal bug — build'i de bloklar) ve 'warn' (pedagojik koku —
    danışsal, build'i bloklamaz). Yazar bunu yayından ÖNCE çalıştırıp slop'u temizler. Sunucuda LLM YOK."""
    await SVC.ensure()
    try:
        from core.antislop import lint_course as _lint
        owner = await _owner()
        p = await _load(project_id, owner)
        issues = _lint(p)
        items = [{"severity": i.severity, "code": i.code, "message": i.message, "path": i.path}
                 for i in issues]
        return {
            "project_id": project_id,
            "error_count": sum(1 for i in items if i["severity"] == "error"),
            "warn_count": sum(1 for i in items if i["severity"] == "warn"),
            "clean": len(items) == 0,
            "issues": items,
        }
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def remove_screen(project_id: str, screen_id: str) -> OkOut:
    """Bir ekranı siler."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        before = len(p.screens)
        p.screens = [s for s in p.screens if s.id != screen_id]
        if len(p.screens) == before:
            raise ToolError("not_found", f"Ekran bulunamadı: {screen_id}")
        await SVC.store.update_project(p)
        return OkOut()
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def set_theme(project_id: str, theme_tokens: ThemeTokens) -> OkOut:
    """Tema token'larını uygular (kısmi override derin merge edilir)."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        p.theme = _deep_merge_theme(p.theme, theme_tokens)
        await SVC.store.update_project(p)
        return OkOut()
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def set_tracking(project_id: str, completion_rule: CompletionRule, passing_score: int) -> OkOut:
    """Tamamlanma/geçme kriterini ayarlar."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        p.tracking = Tracking(
            completion_rule=completion_rule,
            passing_score=max(0, min(100, passing_score)),
            score_scaling=p.tracking.score_scaling,
        )
        await SVC.store.update_project(p)
        return OkOut()
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def add_asset(project_id: str, source: str, filename: str) -> AssetRef:
    """Dış MCP çıktısını (data: base64 veya https URL) pakete dahil eder (SSRF korumalı)."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        max_bytes = SETTINGS.max_asset_mb * 1024 * 1024
        if source.startswith("data:"):
            data, mime = decode_data_uri(source, max_bytes=max_bytes)
        else:
            data, mime = await safe_fetch_asset(source, max_bytes=max_bytes)
        await enforce_size_quota(SVC.store, owner, len(data))
        existing = {a.rel_path for a in p.assets}
        rel = _safe_filename(filename, existing)
        ref = AssetRef(
            id=new_asset_id(),
            filename=os.path.basename(rel),
            mime=mime,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            rel_path=rel,
        )
        await SVC.store.put_asset(p.id, data, ref)
        p.assets.append(ref)
        await SVC.store.update_project(p)
        return ref
    except ToolError as e:
        raise _wrap(e)


async def _add_processed_asset(p, owner, data: bytes, mime: str, filename: str):
    """ffmpeg çıktısını yeni asset olarak ekler (medya tool'ları için ortak)."""
    await enforce_size_quota(SVC.store, owner, len(data))
    existing = {a.rel_path for a in p.assets}
    rel = _safe_filename(filename, existing)
    ref = AssetRef(
        id=new_asset_id(), filename=os.path.basename(rel), mime=mime,
        size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), rel_path=rel,
    )
    await SVC.store.put_asset(p.id, data, ref)
    p.assets.append(ref)
    await SVC.store.update_project(p)
    return ref


@mcp.tool
async def make_video_from_image_audio(
    project_id: str, image_asset_id: str, audio_asset_id: str, filename: str = "narrated.mp4"
) -> AssetRef:
    """Bir görsel + bir ses asset'ini sabit-görüntülü videoya (mp4, H.264/AAC) birleştirir (ffmpeg).

    E-öğrenme: slayt görseli + TTS seslendirme → seslendirilmiş video. Sonuç yeni asset olur;
    VideoScreen'de video_asset_id ile kullan. Faz 4 — LAZY: yalnız çağrılınca ffmpeg devreye girer.
    """
    await SVC.ensure()
    try:
        from core import media

        owner = await _owner()
        p = await _load(project_id, owner)
        img = p.asset_by_id(image_asset_id)
        aud = p.asset_by_id(audio_asset_id)
        if img is None:
            raise ToolError("not_found", f"Görsel asset yok: {image_asset_id}")
        if aud is None:
            raise ToolError("not_found", f"Ses asset yok: {audio_asset_id}")
        if not media.ffmpeg_available():
            raise ToolError("media_unavailable", "Bu sunucuda ffmpeg yok")
        img_bytes = await SVC.store.get_asset_bytes(p.id, img.id)
        aud_bytes = await SVC.store.get_asset_bytes(p.id, aud.id)
        out = await media.image_audio_to_video(
            img_bytes, aud_bytes,
            img_ext=media._ext(img.filename, "png"), aud_ext=media._ext(aud.filename, "mp3"),
        )
        return await _add_processed_asset(p, owner, out, "video/mp4", filename)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def normalize_audio_asset(
    project_id: str, audio_asset_id: str, filename: str = "audio.mp3"
) -> AssetRef:
    """Bir ses asset'ini tarayıcı-güvenli mp3'e (44.1kHz/128k) normalize/transcode eder (ffmpeg).

    Çapraz-MCP'den gelen wav/ogg/m4a sesleri her tarayıcıda çalışsın diye. Faz 4 — LAZY.
    """
    await SVC.ensure()
    try:
        from core import media

        owner = await _owner()
        p = await _load(project_id, owner)
        aud = p.asset_by_id(audio_asset_id)
        if aud is None:
            raise ToolError("not_found", f"Ses asset yok: {audio_asset_id}")
        if not media.ffmpeg_available():
            raise ToolError("media_unavailable", "Bu sunucuda ffmpeg yok")
        aud_bytes = await SVC.store.get_asset_bytes(p.id, aud.id)
        out = await media.normalize_audio(aud_bytes, ext=media._ext(aud.filename, "mp3"))
        return await _add_processed_asset(p, owner, out, "audio/mpeg", filename)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def synthesize_speech(
    project_id: str, text: str, voice: str | None = None, filename: str = "narration.mp3"
) -> AssetRef:
    """Metni Piper ile Türkçe seslendirmeye çevirir → mp3 narration asset (Faz 11). Ekranlarda
    narration_asset_id ile kullan. LAZY: Piper yoksa net hata. Üst kalite ya da başka dil için
    kendi TTS MCP'ni kullanıp add_asset ile yükle (çapraz-MCP akışı birincildir).
    """
    await SVC.ensure()
    try:
        from core import tts, media

        owner = await _owner()
        p = await _load(project_id, owner)
        if not tts.piper_available(voice):
            raise ToolError("tts_unavailable", "Bu sunucuda Piper/ses modeli yok")
        wav = await tts.synthesize(text, voice=voice)
        mp3 = await media.normalize_audio(wav, ext="wav")
        return await _add_processed_asset(p, owner, mp3, "audio/mpeg", filename)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def render_motion_video(
    project_id: str, video_spec: dict, filename: str = "motion.mp4",
    quality: str = "standard", fps: int | None = None
) -> AssetRef:
    """Sahne-spec'ten programatik motion-graphic / veri-viz MP4 üretir (HyperFrames) ve video
    asset olarak ekler. VideoScreen'de video_asset_id ile kullan. Faz 10 — LAZY/async.

    video_spec = VideoSpec JSON (scenes[].elements: text/shape/image/icon/chart + animation).
    Guardrail: ≤1920x1080, ≤60sn. Sahnede narration_asset_id varsa ses mux'lanır.
    """
    await SVC.ensure()
    try:
        from core.video import VideoSpec
        from core.video_render import render_composition, check_guardrails
        from components.video_compiler import compile_composition
        from core import media

        owner = await _owner()
        p = await _load(project_id, owner)
        spec = VideoSpec.model_validate(video_spec)
        if fps is not None:
            spec.fps = fps           # render hız ayarı: düşük fps = hızlı
        check_guardrails(spec)
        comp = compile_composition(spec, theme=p.theme)
        assets: dict[str, bytes] = {}
        for aid in comp.image_asset_ids:
            ref = p.asset_by_id(aid)
            if ref is None:
                raise ToolError("not_found", f"Görsel asset yok: {aid}")
            assets[aid] = await SVC.store.get_asset_bytes(p.id, ref.id)
        out = await render_composition(comp.html, comp.meta, assets, quality=quality)
        nar = next((s.narration_asset_id for s in spec.scenes if s.narration_asset_id), None)
        if nar:
            ref = p.asset_by_id(nar)
            if ref is not None:
                aud = await SVC.store.get_asset_bytes(p.id, ref.id)
                out = await media.mux_audio(out, aud, aud_ext=media._ext(ref.filename, "mp3"))
        return await _add_processed_asset(p, owner, out, "video/mp4", filename)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def render_screen_video(
    project_id: str, screen_id: str, filename: str = "screen.mp4", duration_sec: float = 8.0,
    quality: str = "standard", fps: int = 30
) -> AssetRef:
    """Mevcut bir stage ekranını (Faz 9 timeline'ıyla) MP4'e döker (HyperFrames). İndirilebilir
    özet / LMS video oynatıcısı için. Faz 10 — LAZY/async. duration_sec ≤ 60.
    quality (draft/standard/high) + fps ile hız/kalite dengesi (Faz 11).
    """
    await SVC.ensure()
    try:
        from core.video_render import render_composition, MAX_DUR
        from components.renderer import render_html

        owner = await _owner()
        p = await _load(project_id, owner)
        s = p.screen_by_id(screen_id)
        if s is None:
            raise ToolError("not_found", f"Ekran yok: {screen_id}")
        if duration_sec <= 0 or duration_sec > MAX_DUR:
            raise ToolError("video_too_long", f"Süre 0–{MAX_DUR:g}sn olmalı")
        html = render_html(p, mode="preview", runtime_js="")
        comp_html = (f'<div class="clip" data-start="0" data-duration="{duration_sec:g}" '
                     f'data-track-index="0">{html}</div>')
        meta = {"width": p.stage_width, "height": p.stage_height, "fps": int(fps),
                "duration": duration_sec}
        out = await render_composition(comp_html, meta, {}, quality=quality)
        return await _add_processed_asset(p, owner, out, "video/mp4", filename)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def preview(project_id: str) -> PreviewOut:
    """Tek-dosya, harici bağımlılıksız önizleme üretir + hosted URL döndürür."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        token, html = await _build_preview(p)
        return PreviewOut(
            inline_html=html,
            hosted_url=f"{SETTINGS.public_base_url}/preview/{token}",
        )
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def build_package(project_id: str) -> BuildOut:
    """Build job tetikler (fast-path §3.1): küçük kurs senkron döner, uzun ise job_id+poll."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        errs = validate_project(p)
        if errs:
            raise ToolError("validation_error", "; ".join(e.message for e in errs[:5]))
        job = await SVC.packager.submit(p)
        timeout = float(os.environ.get("BUILD_SYNC_TIMEOUT_SEC", "4"))
        job = await SVC.packager.wait(job.id, timeout=timeout)
        return await _job_to_out(job, p)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def validate_package(project_id: str) -> ValidateOut:
    """Proje + (varsa) son paketin manifest/yapı doğrulamasını yapar."""
    await SVC.ensure()
    try:
        owner = await _owner()
        p = await _load(project_id, owner)
        errors = validate_project(p)
        meta = await SVC.store.latest_package_for_project(p.id)
        if meta:
            zpath = Path(SETTINGS.data_dir) / meta.rel_path
            if zpath.exists():
                errors += validate_zip(str(zpath), meta.scorm_version)
        # Faz 1 — uyarıları (ör. schema_unavailable) ayır; ok yalnız gerçek hatalara bağlı
        from core.schema_validate import SCHEMA_UNAVAILABLE
        warn_codes = {SCHEMA_UNAVAILABLE}
        warnings = [e for e in errors if e.code in warn_codes]
        errors = [e for e in errors if e.code not in warn_codes]
        return ValidateOut(ok=len(errors) == 0, errors=errors, warnings=warnings)
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def build_from_spec(spec: CourseSpec) -> BuildFromSpecOut:
    """Tüm kursu tek JSON spec ile inşa eder (token-verimli, ÖNERİLİR). Fast-path §3.1."""
    await SVC.ensure()
    try:
        owner = await _owner()
        await enforce_project_quota(SVC.store, owner)
        from core.project import new_project_id

        p = Project(
            id=new_project_id(),
            title=spec.title,
            description=spec.description,
            scorm_version=spec.scorm_version,
            language=spec.language,
            theme=_load_theme(spec.theme),
            tracking=spec.tracking,
            variables=list(spec.variables),
            points_var=spec.points_var,
            levels=list(spec.levels),
            lives_var=spec.lives_var,
            max_lives=spec.max_lives,
            layout_mode=spec.layout_mode,
            stage_width=spec.stage_width,
            stage_height=spec.stage_height,
            xapi=spec.xapi,
            screens=list(spec.screens),
            owner_key_id=owner.id,
        )
        for s in p.screens:
            if not s.id:
                s.id = new_screen_id()
        # asset çekimi server'da (SSRF) → store (CONTRACTS.md §12.6)
        max_bytes = SETTINGS.max_asset_mb * 1024 * 1024
        existing: set[str] = set()
        for ainp in spec.assets:
            if ainp.source.startswith("data:"):
                data, mime = decode_data_uri(ainp.source, max_bytes=max_bytes)
            else:
                data, mime = await safe_fetch_asset(ainp.source, max_bytes=max_bytes)
            await enforce_size_quota(SVC.store, owner, len(data))
            rel = _safe_filename(ainp.filename, existing)
            existing.add(rel)
            ref = AssetRef(
                id=ainp.id or new_asset_id(), filename=os.path.basename(rel), mime=mime,
                size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), rel_path=rel,
            )
            await SVC.store.put_asset(p.id, data, ref)
            p.assets.append(ref)
        await SVC.store.create_project(p)

        errs = validate_project(p)
        if errs:
            raise ToolError("validation_error", "; ".join(e.message for e in errs[:5]))
        job = await SVC.packager.submit(p)
        timeout = float(os.environ.get("BUILD_SYNC_TIMEOUT_SEC", "4"))
        job = await SVC.packager.wait(job.id, timeout=timeout)
        out = await _job_to_out(job, p)
        return BuildFromSpecOut(
            project_id=p.id, job_id=job.id, status=job.status, download_url=out.download_url
        )
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def list_feedback(project_id: str | None = None) -> dict:
    """AÇIK reviewer yorumlarını döndürür (preview annotation; Faz 2).

    - project_id VERİLMEZSE: senin TÜM projelerindeki açık yorumlar (project_id + başlıkla). Hangi
      projede feedback olduğunu bilmiyorsan böyle çağır — keşif için.
    - project_id VERİLİRSE: yalnız o proje.
    Revizyon döngüsü: reviewer preview'da ekrana yorum bırakır → Claude bunu okur → düzeltir →
    `resolve_feedback` ile kapatır. Yalnız projelerin sahibi okuyabilir.
    """
    await SVC.ensure()
    try:
        owner = await _owner()
        if project_id is None:
            items = await SVC.store.list_open_feedback_for_owner(owner.id)
            return {"feedback": items}
        await _load(project_id, owner)  # sahiplik doğrulaması (yoksa not_found)
        items = await SVC.store.list_feedback(project_id, only_open=True)
        return {"feedback": [
            {"id": f.id, "project_id": project_id, "screen_id": f.screen_id, "comment": f.comment,
             "created_at": f.created_at.isoformat()} for f in items
        ]}
    except ToolError as e:
        raise _wrap(e)


@mcp.tool
async def resolve_feedback(project_id: str, feedback_id: str) -> OkOut:
    """Bir reviewer yorumunu 'çözüldü' işaretler (Claude düzeltmeyi uyguladıktan sonra)."""
    await SVC.ensure()
    try:
        owner = await _owner()
        await _load(project_id, owner)
        ok = await SVC.store.resolve_feedback(feedback_id, project_id)
        return OkOut(ok=ok)
    except ToolError as e:
        raise _wrap(e)


# --------------------------------------------------------------------------- #
# Keşif tool'ları (discovery) — statik katalog; proje/auth gerektirmez.
# Claude'un mevcut yetenekleri (ekran tipleri, temalar) programatik görmesi için.
# --------------------------------------------------------------------------- #
_SCREEN_TYPE_DESC: dict[str, str] = {
    "title_slide": "Açılış/başlık ekranı — relevansla aç.",
    "content_slide": "Tek-fikir içerik slaytı (metin/medya düzenleri).",
    "mcq": "Çoktan seçmeli (tek/çok seçim).",
    "true_false": "Doğru/yanlış hızlı yoklama.",
    "fill_blank": "Boşluk doldurma (kabul edilen cevaplar).",
    "drag_drop": "Öğeleri hedeflere sürükle (dokunma destekli).",
    "hotspot": "Görsel üzerinde doğru bölgeyi bul.",
    "branching": "Ekranlar-arası dallanma (seçim → gidilecek ekran).",
    "video": "Video (asset/URL); require_complete ile kapı.",
    "summary": "Kapanış — skor/tamamlanma/özet.",
    "accordion": "Yoğun referans/SSS (genişleyen).",
    "tabs": "Bir konunun paralel yönleri.",
    "flashcards": "Terim ↔ tanım; kendini-test.",
    "matching": "İki sütunu eşleştir (erişilebilir select).",
    "sorting": "Adım/sıralama (doğru sırayı ver; runtime karıştırır).",
    "timeline": "Kronoloji/süreç adımları.",
    "lottie": "Tasarımcı animasyonu (opt-in/lazy).",
    "simulation": "Rehberli yazılım simülasyonu (Uygula/try-mode).",
    "decision_scenario": "Dallanan karar oyunu — durum/skor taşır (anlatı try-mode).",
    "term_match_race": "Süreli terim↔tanım eşleştirme oyunu.",
    "escape_room": "Kilitli bulmaca zinciri (ipucu/can).",
    "labeled_diagram": "Görseldeki işaretçilere etiket ata (görsel öğrenme).",
    "data_chart": "Veri-görseli (bar/line/pie; sunucu-SVG; içerik).",
    "results_breakdown": "Özelleştirilmiş sonuç — hedef-bazlı skor dökümü + adaptif öneri.",
    "poll": "Puanlanmayan anket/yansıma (katılım).",
    "image_compare": "Önce/sonra sürüklenebilir görsel karşılaştırma.",
    "game": "Kompozisyonel oyun — mekanik primitifler (skor/can/süre/ipucu) + 'when olay if koşul "
            "then aksiyon' kuralları + dallanan içerik düğümleri (case_sim / escape_room şablonları).",
    "adaptive_practice": "Adaptif pratik — yeterlilik tahmini (Elo/BKT) ile her cevaptan sonra ZPD/akış "
                         "hedefine en yakın zorlukta sıradaki öğeyi seçer (öğrenciye kalibre).",
}

_THEME_DESC: dict[str, str] = {
    "default": "Temiz mavi, beyaz zemin — güvenli kurumsal varsayılan.",
    "modern-light": "Teal vurgu, crisp — modern/ürün eğitimi.",
    "academic": "Serif başlık, lacivert/altın — akademik.",
    "high-contrast": "WCAG AA+, erişilebilirlik-kritik.",
    "agency": "Cesur indigo — pazarlama/yaratıcı.",
    "dark": "Ölçülü koyu — yalnız bilinçli (dev/IT).",
    "clinical-calm": "Teal, sakin — sağlık/klinik CPD.",
    "warm-education": "Sıcak turuncu, dostane — ilkokul/dil.",
    "quest-bright": "Canlı mor-pembe — oyun/oyunlaştırma.",
    "editorial": "Serif + düz çift-çizgi kart + drop-cap — beşeri/akademik.",
    "playground": "Yuvarlak + canlı + zıplayan butonlar — çocuk/oyun.",
    "boardroom-clinic": "Rafine, güven, sıkı radii — kurumsal/sağlık.",
}


@mcp.tool
async def list_screen_types() -> dict:
    """Mevcut TÜM ekran tiplerini (build_from_spec/add_screen `screen.type` değerleri) ve kısa
    açıklamalarını listeler. Skorlanan tipler `scored:true` ile işaretlenir. Yeni bir kurs
    tasarlarken hangi ekran tiplerinin mevcut olduğunu görmek için çağır (keşif; proje gerektirmez)."""
    from core.project import QUIZ_TYPES, ScreenType
    items = [
        {"type": t.value, "scored": t in QUIZ_TYPES, "description": _SCREEN_TYPE_DESC.get(t.value, "")}
        for t in ScreenType
    ]
    return {"count": len(items), "screen_types": items}


@mcp.tool
async def list_themes() -> dict:
    """Mevcut tema preset'lerini (build_from_spec/set_theme `theme` adı) ve konularına uygunluğunu
    listeler. Arayüzü konuya göre farklılaştırmak için uygun temayı seçmek üzere çağır (keşif)."""
    names = sorted(p.stem for p in THEMES_DIR.glob("*.json"))
    items = [{"name": n, "description": _THEME_DESC.get(n, "")} for n in names]
    return {"count": len(items), "themes": items}


# --------------------------------------------------------------------------- #
# HTTP route'ları (CONTRACTS.md §5)
# --------------------------------------------------------------------------- #
@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/usage", methods=["GET"])
async def usage(request: Request) -> JSONResponse:
    """Principal-bazlı kullanım (PORTAL_SPEC §6.2). Dual-auth: OAuth JWT VEYA API-key.

    → { principal, tier, projects:{used,limit}, storage_mb:{used,limit} }
    Portal UsageProvider bunu çağırır; çoklu-MCP'de her MCP aynı şekli sunar.
    """
    await SVC.ensure()
    owner, scopes = await _validate_bearer(parse_bearer(dict(request.headers)))
    if owner is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if "mcp" not in scopes:
        return JSONResponse({"error": "forbidden", "detail": "account not approved"}, status_code=403)
    tier = await SVC.store.get_or_create_principal(owner.id)
    used_projects = await SVC.store.count_projects(owner.id)
    used_bytes = await SVC.store.total_bytes(owner.id)
    return JSONResponse({
        "principal": owner.id,
        "tier": tier,
        "projects": {"used": used_projects, "limit": owner.max_projects},
        "storage_mb": {"used": round(used_bytes / (1024 * 1024), 2), "limit": owner.max_total_mb},
    })


@mcp.custom_route("/keys", methods=["POST"])
async def create_key(request: Request) -> JSONResponse:
    """Çağıran kullanıcı adına kimliğe-bağlı API-key üretir (Antigravity/terminal statik Bearer için).

    Auth: OAuth JWT VEYA API-key ('mcp' scope = onaylı). Üretilen key owner_principal=çağıranın
    principal'ı ("logto:<sub>") taşır → Claude (OAuth) ve bu key (Antigravity) AYNI projeleri görür.
    Ham key BİR KEZ döner (sadece hash saklanır). Mevcut dual-auth korunur; eski key'ler etkilenmez.
    """
    await SVC.ensure()
    owner, scopes = await _validate_bearer(parse_bearer(dict(request.headers)))
    if owner is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if "mcp" not in scopes:
        return JSONResponse({"error": "forbidden", "detail": "account not approved"}, status_code=403)
    raw = "sk_" + secrets.token_urlsafe(32)
    key = ApiKey(
        id=new_key_id(), label="portal", key_hash="",
        max_projects=owner.max_projects, max_total_mb=owner.max_total_mb,
        owner_principal=owner.id, created_at=utcnow(),
        preview=raw[:10] + "…" + raw[-4:],  # maskeli gösterim; ham key saklanmaz
    )
    await SVC.store.upsert_key(key, raw_key=raw)
    return JSONResponse({"api_key": raw, "key_id": key.id, "principal": owner.id})


@mcp.custom_route("/keys", methods=["GET"])
async def keys_list(request: Request) -> JSONResponse:
    """Çağıranın kendi API-key'leri (maskeli; ham key dönmez). Portal /app yönetimi."""
    await SVC.ensure()
    owner, scopes = await _validate_bearer(parse_bearer(dict(request.headers)))
    if owner is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if "mcp" not in scopes:
        return JSONResponse({"error": "forbidden", "detail": "account not approved"}, status_code=403)
    keys = await SVC.store.list_keys_for_principal(owner.id)
    return JSONResponse({"keys": [{
        "key_id": k.id, "label": k.label, "preview": k.preview,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "disabled": k.disabled,
    } for k in keys]})


@mcp.custom_route("/keys/{key_id}", methods=["DELETE"])
async def keys_delete(request: Request) -> JSONResponse:
    """Çağıranın bir API-key'ini siler (rotate = yeni üret + eskiyi sil). Yalnız kendi key'i."""
    await SVC.ensure()
    owner, scopes = await _validate_bearer(parse_bearer(dict(request.headers)))
    if owner is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if "mcp" not in scopes:
        return JSONResponse({"error": "forbidden", "detail": "account not approved"}, status_code=403)
    kid = request.path_params["key_id"]
    k = await SVC.store.get_key_by_id(kid)
    # sahiplik: key'in principal'ı çağıranınkiyle eşleşmeli (başkasının key'i 404)
    if k is None or (k.owner_principal or k.id) != owner.id:
        return JSONResponse({"error": "not_found"}, status_code=404)
    await SVC.store.delete_key(kid)
    return JSONResponse({"ok": True})


@mcp.custom_route("/projects", methods=["GET"])
async def projects_list(request: Request) -> JSONResponse:
    """Principal'ın projeleri + preview/indirme linkleri (portal panel listesi).

    → { projects: [ { id, title, screens, scorm_version, updated_at,
                      preview_url, download_url|null, size_bytes|null } ] }
    Dual-auth: OAuth JWT VEYA API-key (aynı _validate_bearer).
    """
    await SVC.ensure()
    owner, scopes = await _validate_bearer(parse_bearer(dict(request.headers)))
    if owner is None:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if "mcp" not in scopes:
        return JSONResponse({"error": "forbidden", "detail": "account not approved"}, status_code=403)
    out = []
    for p in await SVC.store.list_projects(owner.id):
        download_url = None
        size_bytes = None
        pkg = await SVC.store.latest_package_for_project(p.id)
        if pkg is not None:
            exp = pkg.expires_at
            if exp.tzinfo is None:
                from datetime import timezone

                exp = exp.replace(tzinfo=timezone.utc)
            if exp >= utcnow():
                download_url = SVC.packager.download_url(pkg.token)
                size_bytes = pkg.size_bytes
        out.append({
            "id": p.id,
            "title": p.title,
            "screens": len(p.screens),
            "scorm_version": p.scorm_version,
            "updated_at": p.updated_at.isoformat(),
            "preview_url": await _preview_url(p),
            "download_url": download_url,
            "size_bytes": size_bytes,
            "open_feedback": await SVC.store.count_open_feedback(p.id),
        })
    return JSONResponse({"projects": out})


@mcp.custom_route("/files/{token}", methods=["GET"])
async def files(request: Request):
    await SVC.ensure()
    token = request.path_params["token"]
    meta = await SVC.store.get_package_by_token(token)
    if meta is None:
        return PlainTextResponse("not found", status_code=404)
    exp = meta.expires_at
    if exp.tzinfo is None:
        from datetime import timezone

        exp = exp.replace(tzinfo=timezone.utc)
    if exp < utcnow():
        return PlainTextResponse("expired", status_code=410)
    path = Path(SETTINGS.data_dir) / meta.rel_path
    if not path.exists():
        return PlainTextResponse("gone", status_code=410)
    return FileResponse(
        str(path), media_type="application/zip",
        filename=f"{meta.project_id}.zip",
    )


@mcp.custom_route("/preview/{token}", methods=["GET"])
async def preview_route(request: Request):
    await SVC.ensure()
    token = request.path_params["token"]
    meta = await SVC.store.get_preview(token)
    if meta is None:
        return PlainTextResponse("not found", status_code=404)
    exp = meta.expires_at
    if exp.tzinfo is None:
        from datetime import timezone

        exp = exp.replace(tzinfo=timezone.utc)
    if exp < utcnow():
        return PlainTextResponse("expired", status_code=410)
    path = Path(SETTINGS.data_dir) / "previews" / f"{token}.html"
    if not path.exists():
        return PlainTextResponse("gone", status_code=410)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@mcp.custom_route("/feedback", methods=["POST"])
async def feedback_submit(request: Request) -> JSONResponse:
    """Preview annotation (Faz 2): reviewer ekrana yorum bırakır. Yetki = preview_token (capability);
    token → project_id çözülür. Claude yorumları `list_feedback` aracıyla okuyup uygular."""
    await SVC.ensure()
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "bad_request"}, status_code=400)
    token = str(body.get("preview_token") or "").strip()
    # C2: yorumu sanitize et — HTML/tag strip (stored-XSS + Claude'a giden ham içerik savunması).
    # Yorum güvenilmeyen kullanıcı verisidir; Claude onu talimat değil VERİ olarak ele almalı.
    comment = nh3.clean(str(body.get("comment") or "").strip(), tags=set(), attributes={}).strip()
    screen_id = body.get("screen_id") or None
    if not token or not comment:
        return JSONResponse({"error": "preview_token ve comment gerekli"}, status_code=400)
    meta = await SVC.store.get_preview(token)
    if meta is None:
        return JSONResponse({"error": "geçersiz preview token"}, status_code=404)
    fb = Feedback(id=new_feedback_id(), project_id=meta.project_id,
                  screen_id=str(screen_id)[:128] if screen_id else None, comment=comment[:2000])
    await SVC.store.add_feedback(fb)
    return JSONResponse({"ok": True, "id": fb.id})


# --------------------------------------------------------------------------- #
# Giriş noktası
# --------------------------------------------------------------------------- #
def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "http")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # json_response=True → POST yanıtları SSE (text/event-stream) yerine düz application/json.
        # Bazı istemciler (örn. Antigravity Go transport) SSE-akışlı initialize'da "context canceled"
        # verir; JSON yanıt bunu çözer. Oturum semantiği korunur. Sorun olursa MCP_JSON_RESPONSE=0.
        json_response = os.environ.get("MCP_JSON_RESPONSE", "1") == "1"
        mcp.run(
            transport="http", host=SETTINGS.host, port=SETTINGS.port,
            json_response=json_response,
        )


if __name__ == "__main__":
    main()
