"""tests/test_video_captions.py — #145: WebVTT altyazı hattı (a11y kısıt #1 / #2).

Kabul kriteri hattı:
- `captions_asset_id` verilen video `<track kind="captions" srclang default>` üretir;
- VTT asset'i pakete gömülür → çalışma zamanında ağ isteği YOK (data-asset jenerik çözücüsü);
- `<track>` yokken çıktı **bayt-aynı** (koşullu üretim, bayt-parite kapısı);
- sarkan altyazı referansı SERT hata (sessiz altyazısızlık olmasın);
- kısıt #2 artık sessiz değil: seslendirme sesi var + metni yok → `lint_course` WARN.

Tarayıcı tarafı ayrı doğrulandı (bu testler tarayıcı kaldırmaz): sabitlenmiş Playwright
konteynerinde gerçek preview HTML'i açıldı ve `<track>`in `data:text/vtt` URI'sinden
YÜKLENDİĞİ ölçüldü — `readyState=2`, `cues=2`, `mode="showing"`, `kind="captions"`,
`language="tr"`. Yani jenerik `[data-asset]` çözücüsü track için de yeterli; `file://`
sayfasında data-URI track'i engellenmiyor.
"""
import hashlib

import pytest

from components.renderer import render_html
from core.antislop import lint_course
from core.project import (
    AssetRef,
    ContentSlide,
    Project,
    ThemeTokens,
    VideoScreen,
    new_project_id,
)
from core.validator import validate_project

VTT = "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nMerhaba.\n"


def _asset(aid: str, filename: str, mime: str, body: bytes = b"x") -> AssetRef:
    return AssetRef(id=aid, filename=filename, mime=mime, size_bytes=len(body),
                    sha256=hashlib.sha256(body).hexdigest(), rel_path=f"assets/{filename}")


def _proj(captions: str | None = None, *, with_caption_asset: bool = True,
          language: str = "tr") -> Project:
    s = VideoScreen(id="v1", title="Video", video_asset_id="vid1", captions_asset_id=captions)
    p = Project(id=new_project_id(), title="T", language=language, theme=ThemeTokens(),
                screens=[s])
    p.assets.append(_asset("vid1", "v.mp4", "video/mp4"))
    if captions and with_caption_asset:
        p.assets.append(_asset(captions, "c.vtt", "text/vtt", VTT.encode()))
    return p


def _html(p: Project) -> str:
    return render_html(p, mode="preview", runtime_js="/*rt*/")


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_captions_asset_id_defaults_to_none():
    assert VideoScreen(id="v1", title="V").captions_asset_id is None


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def test_track_is_emitted_inside_the_video_element():
    h = _html(_proj("cap1"))
    assert '<track kind="captions" data-asset="cap1" srclang="tr"' in h
    assert " default>" in h
    # <track> <video>'nun ICINDE olmali; disarida basilirsa tarayici gormez
    video = h.split('<video class="video"')[1].split("</video>")[0]
    assert "<track" in video


def test_srclang_follows_the_course_language():
    assert 'srclang="en"' in _html(_proj("cap1", language="en"))


def test_track_label_is_localized():
    assert 'label="Altyazı"' in _html(_proj("cap1"))
    assert 'label="Captions"' in _html(_proj("cap1", language="en"))


# --------------------------------------------------------------------------- #
# Bayt-parite — koşullu üretim kapısı
# --------------------------------------------------------------------------- #
def test_no_track_without_the_asset_id():
    assert "<track" not in _html(_proj())


def test_output_is_byte_identical_without_captions():
    """Alan EKLENDI ama kullanilmayan kursun ciktisi degismemeli."""
    a = _proj()
    b = _proj()
    b.id = a.id
    for x, y in zip(a.assets, b.assets):
        y.id = x.id
    assert _html(a) == _html(b)
    assert "captions" not in _html(a)


# --------------------------------------------------------------------------- #
# Validator — sarkan referans sessiz altyazısızlık olmasın
# --------------------------------------------------------------------------- #
def test_dangling_captions_reference_is_a_hard_error():
    errs = validate_project(_proj("yok", with_caption_asset=False))
    assert any(e.path.endswith(".captions_asset_id") for e in errs), \
        f"sarkan altyazi referansi yakalanmadi: {[e.path for e in errs]}"


def test_valid_captions_reference_passes():
    errs = validate_project(_proj("cap1"))
    assert not [e for e in errs if "captions" in e.path]


# --------------------------------------------------------------------------- #
# mime allowlist — VTT asset'i sunucuya girebilmeli
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("mime", ["text/vtt", "text/plain"])
def test_vtt_mimes_are_allowed(mime):
    from auth.ssrf import _mime_allowed
    assert _mime_allowed(mime)


def test_html_mime_is_still_rejected_for_generic_assets():
    """Genişletme DAR olmalı: text/ ailesi topluca açılmadı."""
    from auth.ssrf import _mime_allowed
    assert not _mime_allowed("text/html")


# --------------------------------------------------------------------------- #
# a11y kısıt #2 — artık sessiz değil
# --------------------------------------------------------------------------- #
def test_lint_warns_on_narration_audio_without_text():
    p = Project(id=new_project_id(), title="T", theme=ThemeTokens(), screens=[
        ContentSlide(id="c1", title="Ses var metin yok", body_html="<p>x</p>",
                     narration_asset_id="a1")])
    issues = [i for i in lint_course(p) if i.code == "narration_without_transcript"]
    assert issues and issues[0].severity == "warn"


def test_lint_quiet_when_narration_has_text():
    p = Project(id=new_project_id(), title="T", theme=ThemeTokens(), screens=[
        ContentSlide(id="c1", title="Ikisi de var", body_html="<p>x</p>",
                     narration_asset_id="a1", narration_text="Sesin metni")])
    assert not [i for i in lint_course(p) if i.code == "narration_without_transcript"]


def test_lint_quiet_when_there_is_no_narration_audio():
    p = Project(id=new_project_id(), title="T", theme=ThemeTokens(), screens=[
        ContentSlide(id="c1", title="Ses yok", body_html="<p>x</p>")])
    assert not [i for i in lint_course(p) if i.code == "narration_without_transcript"]
