"""components/renderer.py — spec → HTML (CONTRACTS.md §9, §12.5).

ÖNİZLEME ve PAKET aynı renderer'ı paylaşır:
  - mode="preview": TEK dosya, harici bağımlılık YOK (runtime_js + tema + CSS + JS gömülü)
  - mode="package": index.html; assets/ ve runtime/scorm-again.min.js'e referans verir

Premium görünüm: ThemeTokens → CSS custom property; modüler tipografi, katmanlı elevation,
akıcı motion (prefers-reduced-motion'a uyar). Tüm *_html alanları nh3 ile sanitize edilir.

SCORM köprüsü: içerik standart API keşfi yapar (parent/opener'da window.API /
window.API_1484_11 arar). LMS bulunursa onu kullanır (gerçek izleme); bulunmazsa
scorm-again'in Scorm12API/Scorm2004API'sini yerel fallback olarak kurar (önizleme = no-op).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import nh3

from core.project import Project, QUIZ_TYPES, ScreenType, ThemeTokens

from .templates import BASE_CSS, ENGINE_JS, FALLBACK_RUNTIME_SHIM, SHELL

_RUNTIME_PATH = Path(__file__).resolve().parent.parent / "runtime" / "scorm-again.min.js"
_LOTTIE_PATH = Path(__file__).resolve().parent.parent / "runtime" / "lottie_light.min.js"
_LOTTIE_REL = "runtime/lottie_light.min.js"

# CONTRACTS.md §1.3 — izinli HTML alt kümesi
_ALLOWED_TAGS = {
    "p", "h1", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "a", "br",
    "img", "figure", "figcaption", "code", "pre", "blockquote",
    "table", "thead", "tbody", "tr", "td", "th", "span", "div",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "width", "height"},
    "span": {"class"},
    "div": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}


def sanitize(html: str | None) -> str:
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )


@lru_cache(maxsize=1)
def load_runtime_js() -> str:
    """runtime/scorm-again.min.js içeriğini döndürür (yoksa no-op fallback shim). Önbellekli (O4)."""
    if _RUNTIME_PATH.exists():
        return _RUNTIME_PATH.read_text(encoding="utf-8")
    return FALLBACK_RUNTIME_SHIM


@lru_cache(maxsize=1)
def _load_lottie_js() -> str:
    return _LOTTIE_PATH.read_text(encoding="utf-8") if _LOTTIE_PATH.exists() else ""


def _uses_lottie(project: Project) -> bool:
    return any(s.type == ScreenType.lottie for s in project.screens)


def extra_runtime_files(project: Project) -> list[tuple[str, str]]:
    """Paket için gereken EK runtime dosyaları (rel_path, içerik). Opt-in/lazy: animasyonsuz
    kurs → boş liste → pakette lottie YOK (zero-load)."""
    out: list[tuple[str, str]] = []
    if _uses_lottie(project):
        out.append((_LOTTIE_REL, _load_lottie_js()))
    return out


# --------------------------------------------------------------------------- #
# Public API (CONTRACTS.md §12.5)
# --------------------------------------------------------------------------- #
def render_html(
    project: Project,
    *,
    mode: Literal["preview", "package"],
    runtime_js: str,
    asset_data: dict[str, tuple[str, bytes]] | None = None,
) -> str:
    """spec → HTML. asset_data (preview için): {asset_id: (mime, bytes)} → data-URI gömme."""
    theme = project.theme
    css_vars = _css_vars(theme)
    # Faz 9.1 — ayarlanabilir tuval ölçüsü → CSS değişkeni (stage modu bunları kullanır)
    css_vars += f"\n  --stage-w:{int(project.stage_width)}px; --stage-h:{int(project.stage_height)}px;"
    screens_html = "\n".join(_render_screen(s, i) for i, s in enumerate(project.screens))
    course_cfg = _course_config(project)

    if mode == "preview":
        runtime_block = f"<script>{runtime_js}</script>"
    else:
        runtime_block = '<script src="runtime/scorm-again.min.js"></script>'

    # Faz 7 — opt-in/lazy: lottie lib YALNIZ animasyon kullanılırsa eklenir (zero-load)
    if _uses_lottie(project):
        extra_runtime = (f"<script>{_load_lottie_js()}</script>" if mode == "preview"
                         else f'<script src="{_LOTTIE_REL}"></script>')
    else:
        extra_runtime = ""

    if mode == "preview" and asset_data:
        # Tek-dosya self-contained önizleme: asset'leri data-URI olarak göm
        import base64

        asset_map = {}
        for a in project.assets:
            if a.id in asset_data:
                mime, data = asset_data[a.id]
                asset_map[a.id] = f"data:{mime};base64,{base64.b64encode(data).decode()}"
            else:
                asset_map[a.id] = a.rel_path
    else:
        asset_map = {a.id: a.rel_path for a in project.assets}

    return SHELL.format(
        lang=_attr(project.language),
        title=_text(project.title),
        css_vars=css_vars,
        base_css=BASE_CSS,
        custom_css=theme.custom_css or "",
        bg_pattern=theme.background_pattern,
        layout_mode=project.layout_mode,
        header_title=_text(project.title),
        screens=screens_html,
        runtime_block=runtime_block,
        course_json=json.dumps(course_cfg, ensure_ascii=False),
        asset_json=json.dumps(asset_map, ensure_ascii=False),
        scorm_2004="true" if project.scorm_version == "2004" else "false",
        preview="true" if mode == "preview" else "false",
        extra_runtime=extra_runtime,
        engine_js=ENGINE_JS,
    )


# --------------------------------------------------------------------------- #
# Tema → CSS değişkenleri
# --------------------------------------------------------------------------- #
def _css_vars(t: ThemeTokens) -> str:
    c, ty, sp, r, e, m = t.color, t.typography, t.spacing, t.radii, t.elevation, t.motion
    base = ty.base_size_px
    ratio = ty.scale_ratio
    h1 = round(base * ratio ** 3)
    h2 = round(base * ratio ** 2)
    h3 = round(base * ratio)
    h4 = base
    space = "".join(f"--space-{i}:{v}px;" for i, v in enumerate(sp.scale))
    return f"""
  --c-primary:{c.primary}; --c-primary-hover:{c.primary_hover}; --c-primary-contrast:{c.primary_contrast};
  --c-secondary:{c.secondary}; --c-accent:{c.accent};
  --c-bg:{c.bg}; --c-surface:{c.surface}; --c-surface-alt:{c.surface_alt}; --c-border:{c.border};
  --c-text:{c.text}; --c-muted:{c.text_muted}; --c-on-dark:{c.text_on_dark};
  --c-success:{c.success}; --c-success-bg:{c.success_bg};
  --c-error:{c.error}; --c-error-bg:{c.error_bg};
  --c-warning:{c.warning}; --c-info:{c.info}; --c-focus:{c.focus_ring};
  --font-heading:{ty.font_heading}; --font-body:{ty.font_body}; --font-mono:{ty.font_mono};
  --fs-base:{base}px; --fs-h1:{h1}px; --fs-h2:{h2}px; --fs-h3:{h3}px; --fs-h4:{h4}px;
  --w-heading:{ty.weight_heading}; --w-body:{ty.weight_body}; --w-strong:{ty.weight_strong};
  --lh-tight:{ty.line_height_tight}; --lh-normal:{ty.line_height_normal};
  --ls-heading:{ty.letter_spacing_heading};
  {space}
  --content-max:{sp.content_max_width}; --gutter:{sp.gutter};
  --r-sm:{r.sm}; --r-md:{r.md}; --r-lg:{r.lg}; --r-pill:{r.pill};
  --e1:{e.e1}; --e2:{e.e2}; --e3:{e.e3}; --e4:{e.e4};
  --d-fast:{m.duration_fast}; --d-base:{m.duration_base}; --d-slow:{m.duration_slow};
  --ease:{m.easing_standard}; --ease-emph:{m.easing_emphasized};
"""


# --------------------------------------------------------------------------- #
# JS engine için kurs konfigürasyonu (cevaplar + skor + dallanma)
# --------------------------------------------------------------------------- #
def _course_config(project: Project) -> dict:
    screens = []
    total_points = 0
    for idx, s in enumerate(project.screens):
        item: dict = {"id": s.id or f"idx{idx}", "type": s.type.value, "index": idx,
                      "is_quiz": s.type in QUIZ_TYPES}
        if s.type == ScreenType.mcq:
            item["points"] = s.points
            item["multi"] = s.multi_select
            item["correct"] = [o.id for o in s.options if o.correct]
            total_points += s.points
        elif s.type == ScreenType.true_false:
            item["points"] = s.points
            item["correct"] = bool(s.correct)
            total_points += s.points
        elif s.type == ScreenType.fill_blank:
            item["points"] = s.points
            item["case_sensitive"] = s.case_sensitive
            item["blanks"] = {b.id: list(b.accepted) for b in s.blanks}
            total_points += s.points
        elif s.type == ScreenType.drag_drop:
            item["points"] = s.points
            item["correct"] = {it.id: it.correct_target_id for it in s.items}
            total_points += s.points
        elif s.type == ScreenType.hotspot:
            item["points"] = s.points
            item["correct"] = [rg.id for rg in s.regions if rg.correct]
            total_points += s.points
        elif s.type == ScreenType.matching:
            item["points"] = s.points
            total_points += s.points  # doğru = select value === satır pair id (DOM'da kontrol)
        elif s.type == ScreenType.sorting:
            item["points"] = s.points
            item["correct_order"] = [it.id for it in s.items]
            total_points += s.points
        elif s.type == ScreenType.simulation:
            item["points"] = s.points
            total_points += s.points  # doğru = tüm adımlar doğru tıklamayla tamamlandı (DOM'da)
        elif s.type == ScreenType.decision_scenario:
            item["points"] = s.points
            item["pass_score"] = s.pass_score  # None → skor>0 geçer; sayı → skor≥pass geçer
            total_points += s.points  # skor, seçim score_delta'larının toplamı (DOM'da yürütülür)
        elif s.type == ScreenType.term_match_race:
            item["points"] = s.points
            item["time_limit_sec"] = s.time_limit_sec
            item["correct"] = {p.id: p.id for p in s.pairs}  # select value === pair id
            total_points += s.points
        elif s.type == ScreenType.escape_room:
            item["points"] = s.points
            item["lives"] = s.lives
            item["case_sensitive"] = [p.case_sensitive for p in s.puzzles]
            item["accepted"] = [list(p.accepted) for p in s.puzzles]  # adım sırasıyla
            total_points += s.points
        elif s.type == ScreenType.labeled_diagram:
            item["points"] = s.points
            total_points += s.points  # doğru = her işaretçinin select'i kendi label id'si (DOM)
        elif s.type == ScreenType.branching:
            item["routes"] = {c.id: c.goto_screen_id for c in s.choices}
            item["default_goto"] = s.default_goto
            cv = {c.id: [_act(a) for a in c.set_vars] for c in s.choices if c.set_vars}
            if cv:
                item["choice_vars"] = cv
        elif s.type == ScreenType.video:
            item["require_complete"] = s.require_complete
        if s.type in QUIZ_TYPES:
            item["feedback"] = {
                "correct": sanitize(s.feedback.correct_html),
                "incorrect": sanitize(s.feedback.incorrect_html),
                "show_correct": s.feedback.show_correct_answer,
            }
        # Faz 5: koşullu görünürlük + girişte değişken atama (her ekran tipi)
        if getattr(s, "visible_if", None):
            item["visible_if"] = _cond(s.visible_if)
        if getattr(s, "on_enter", None):
            item["on_enter"] = [_act(a) for a in s.on_enter]
        # Faz 6: oyunlaştırma — timer + quiz doğru/yanlış aksiyonları
        if getattr(s, "timer_sec", None):
            item["timer_sec"] = s.timer_sec
            if s.on_timeout:
                item["on_timeout"] = [_act(a) for a in s.on_timeout]
            if s.timeout_goto:
                item["timeout_goto"] = s.timeout_goto
        if getattr(s, "on_correct", None):
            item["on_correct"] = [_act(a) for a in s.on_correct]
        if getattr(s, "on_wrong", None):
            item["on_wrong"] = [_act(a) for a in s.on_wrong]
        # Faz 9: timeline reveal modu + kilit + paced aralığı + altyazı bayrağı
        item["reveal"] = _effective_reveal(s)
        if getattr(s, "lock_until_complete", False):
            item["lock_until_complete"] = True
        if getattr(s, "block_sec", None):
            item["block_sec"] = s.block_sec
        if getattr(s, "narration_text", None):
            item["has_captions"] = True
        if getattr(s, "section", None):
            item["section"] = s.section
        screens.append(item)
    return {
        "title": project.title,
        "language": project.language,
        "scorm_version": project.scorm_version,
        "total_points": total_points,
        "tracking": {
            "completion_rule": project.tracking.completion_rule.value,
            "passing_score": project.tracking.passing_score,
            "score_scaling": project.tracking.score_scaling,
        },
        "variables": [{"name": v.name, "type": v.type, "default": v.default}
                      for v in project.variables],
        "points_var": project.points_var,
        "layout_mode": project.layout_mode,
        "stage_width": project.stage_width,
        "stage_height": project.stage_height,
        "screens": screens,
        "id_order": [s.id or f"idx{i}" for i, s in enumerate(project.screens)],
    }


def _act(a) -> dict:
    return {"var": a.var, "op": a.op, "value": a.value}


def _cond(c) -> dict:
    return {"var": c.var, "cmp": c.cmp, "value": c.value}


# --------------------------------------------------------------------------- #
# Ekran HTML render
# --------------------------------------------------------------------------- #
# Faz 9 — bu ekran tipleri varsayılan olarak timeline reveal'a girer (içerik/anlatım).
# Etkileşimliler (mcq/drag/hotspot/simulation/matching/sorting/branching) reveal:"none".
_AUTO_REVEAL_TYPES = {
    ScreenType.title_slide, ScreenType.content_slide, ScreenType.video,
    ScreenType.timeline, ScreenType.lottie, ScreenType.summary,
    ScreenType.data_chart,  # içerik (skorlanmaz)
    ScreenType.results_breakdown, ScreenType.poll, ScreenType.image_compare,  # Faz 14 içerik
}


def _effective_reveal(s) -> str:
    """Ekranın etkin reveal modu: açık override yoksa tipten türetilir."""
    r = getattr(s, "reveal", None)
    if r:
        return r
    return "auto" if s.type in _AUTO_REVEAL_TYPES else "none"


_VOID_TAGS = {"img", "br", "hr", "input", "meta", "link", "source", "area", "col", "wbr"}
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*?)(/?)>")
_RICH_RE = re.compile(r'^<div class="rich"[^>]*>(.*)</div>$', re.DOTALL)


def _top_level_elements(html: str) -> list[str]:
    """HTML parçasındaki en üst seviye (depth-0) elemanları döndürür. Dengeli etiket
    sayımı; void/self-closing elemanlar tek blok. Etiketler arası serbest metin yok sayılır
    (dispatch çıktısı tag-yoğundur). Bozuk/dengesiz girişte tüm parçayı tek eleman döndürür."""
    elems: list[str] = []
    depth = 0
    start: int | None = None
    for m in _TAG_RE.finditer(html):
        closing, tag, selfclose = m.group(1), m.group(2).lower(), m.group(4)
        if closing:
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    elems.append(html[start:m.end()])
                    start = None
        elif tag in _VOID_TAGS or selfclose == "/":
            if depth == 0:
                elems.append(html[m.start():m.end()])
        else:
            if depth == 0 and start is None:
                start = m.start()
            depth += 1
    if depth != 0 or not elems:
        return [html]
    return elems


def _wrap_blocks(body: str) -> str:
    """Üst-düzey blokları .tl-block'a sarar (timeline reveal birimleri). Bir .rich gövdesi
    varsa ONUN üst-düzey çocukları ayrı bloklar olur (paragraf/liste düzeyinde reveal)."""
    counter = [0]

    def wrap(html_el: str) -> str:
        i = counter[0]
        counter[0] += 1
        return f'<div class="tl-block" data-block="{i}">{html_el}</div>'

    out: list[str] = []
    for el in _top_level_elements(body):
        m = _RICH_RE.match(el.strip())
        if m:
            children = _top_level_elements(m.group(1))
            wrapped = "".join(wrap(c) for c in children)
            out.append(f'<div class="rich">{wrapped}</div>')
        else:
            out.append(wrap(el))
    return "".join(out)


def _render_screen(s, idx: int) -> str:
    sid = s.id or f"idx{idx}"
    body = _SCREEN_DISPATCH.get(s.type, _render_unknown)(s)
    reveal = _effective_reveal(s)
    if reveal != "none":
        body = _wrap_blocks(body)
    narration = ""
    nid = getattr(s, "narration_asset_id", None)
    if nid:
        narration = (f'<audio class="narration" preload="none" '
                     f'data-asset="{_attr(nid)}" aria-label="Seslendirme"></audio>')
    cap = ""
    ntext = getattr(s, "narration_text", None)
    if ntext:
        cap = f'<div class="cc-text" data-captions hidden>{_text(ntext)}</div>'
    anim = _attr(getattr(s, "animation", None) or "fade-up")
    return (
        f'<section class="screen" data-screen-id="{_attr(sid)}" data-type="{s.type.value}"'
        f' data-index="{idx}" data-reveal="{reveal}" data-anim="{anim}" aria-hidden="true">'
        f'<div class="screen-inner">{narration}{body}{cap}</div></section>'
    )


def _media(asset_id: str | None, cls: str = "media") -> str:
    if not asset_id:
        return ""
    return f'<img class="{cls}" data-asset="{_attr(asset_id)}" alt="">'


def _r_title(s) -> str:
    bg = f' data-bg-asset="{_attr(s.background_asset_id)}"' if s.background_asset_id else ""
    sub = f'<p class="title-sub">{_text(s.subtitle)}</p>' if s.subtitle else ""
    body = f'<div class="rich">{sanitize(s.body_html)}</div>' if s.body_html else ""
    return (
        f'<div class="title-slide"{bg}>'
        f'<div class="title-kicker">●</div>'
        f'<h1 class="title-main">{_text(s.title)}</h1>{sub}{body}</div>'
    )


def _r_content(s) -> str:
    media = _media(s.media_asset_id)
    rich = f'<div class="rich">{sanitize(s.body_html)}</div>'
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.layout in ("text_media", "media_text") and media:
        order = "media-first" if s.layout == "media_text" else "text-first"
        return (f'{head}<div class="split {order}"><div class="split-text">{rich}</div>'
                f'<div class="split-media">{media}</div></div>')
    if s.layout == "full_media" and media:
        return f'{head}<div class="full-media">{media}</div>'
    return f"{head}{rich}"


def _r_mcq(s) -> str:
    opts = "".join(
        f'<button class="opt" data-opt="{_attr(o.id)}" type="button">'
        f'<span class="opt-mark"></span><span class="opt-text">{sanitize(o.text_html)}</span></button>'
        for o in s.options
    )
    multi = ' data-multi="1"' if s.multi_select else ""
    return _quiz_shell(s, f'<div class="options"{multi}>{opts}</div>')


def _r_true_false(s) -> str:
    opts = (
        '<div class="options tf">'
        '<button class="opt" data-opt="true" type="button"><span class="opt-mark"></span>'
        '<span class="opt-text">Doğru</span></button>'
        '<button class="opt" data-opt="false" type="button"><span class="opt-mark"></span>'
        '<span class="opt-text">Yanlış</span></button></div>'
    )
    return _quiz_shell(s, opts)


def _r_fill(s) -> str:
    inputs = "".join(
        f'<label class="blank"><span>{_text(b.id)}</span>'
        f'<input type="text" data-blank="{_attr(b.id)}" autocomplete="off"></label>'
        for b in s.blanks
    )
    return _quiz_shell(s, f'<div class="blanks">{inputs}</div>')


def _r_drag(s) -> str:
    items = "".join(
        f'<div class="drag-item" draggable="true" data-item="{_attr(it.id)}">{sanitize(it.text_html)}</div>'
        for it in s.items
    )
    targets = "".join(
        f'<div class="drop-target" data-target="{_attr(t.id)}">'
        f'<div class="drop-label">{sanitize(t.label_html)}</div><div class="drop-zone"></div></div>'
        for t in s.targets
    )
    return _quiz_shell(
        s,
        f'<div class="dragdrop"><div class="drag-pool">{items}</div>'
        f'<div class="drop-list">{targets}</div></div>',
    )


def _r_hotspot(s) -> str:
    regions = "".join(
        f'<button class="hotspot-region" type="button" data-region="{_attr(rg.id)}"'
        f' data-shape="{rg.shape}" data-coords="{_attr(",".join(str(c) for c in rg.coords))}"'
        f' title="{_attr(rg.label_html or "")}"></button>'
        for rg in s.regions
    )
    img = f'<img class="hotspot-img" data-asset="{_attr(s.image_asset_id)}" alt="">'
    return _quiz_shell(s, f'<div class="hotspot"><div class="hotspot-stage">{img}{regions}</div></div>')


def _r_branching(s) -> str:
    choices = "".join(
        f'<button class="branch-choice" type="button" data-choice="{_attr(c.id)}"'
        f' data-goto="{_attr(c.goto_screen_id)}">{sanitize(c.text_html)}</button>'
        for c in s.choices
    )
    return (
        f'<h2 class="screen-title">{_text(s.title)}</h2>'
        f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
        f'<div class="branches">{choices}</div>'
    )


def _r_video(s) -> str:
    if s.video_asset_id:
        src = f'<source data-asset="{_attr(s.video_asset_id)}">'
    else:
        src = f'<source src="{_attr(s.video_url or "")}">'
    poster = f' data-poster-asset="{_attr(s.poster_asset_id)}"' if s.poster_asset_id else ""
    cap = f'<figcaption>{_text(s.caption)}</figcaption>' if s.caption else ""
    req = ' data-require-complete="1"' if s.require_complete else ""
    # a11y: controls (öğrenci duraklat/seek edebilmeli — WCAG). loop YALNIZ require_complete YOKKEN
    # (loop'ta 'ended' tetiklenmez → tamamlanma yazılmaz; dekoratif video için loop serbest).
    loop = "" if s.require_complete else " loop"
    video_html = (
        f'<figure class="video-wrap"><video class="video" preload="auto" autoplay{loop} muted '
        f'playsinline controls{poster}{req}>{src}</video>{cap}</figure>'
    )
    if getattr(s, "narration_text", None):
        desc = f'<div class="video-desc rich"><p>{_text(s.narration_text)}</p></div>'
        body = f'<div class="split text-first"><div class="split-text">{desc}</div><div class="split-media">{video_html}</div></div>'
    else:
        body = video_html
    return (
        f'<h2 class="screen-title">{_text(s.title)}</h2>'
        f'{body}'
    )


def _r_summary(s) -> str:
    body = f'<div class="rich">{sanitize(s.body_html)}</div>' if s.body_html else ""
    score = '<div class="summary-score" data-show-score="1"></div>' if s.show_score else ""
    comp = '<div class="summary-completion" data-show-completion="1"></div>' if s.show_completion else ""
    return (
        f'<div class="summary"><div class="summary-badge">'
        f'<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>'
        f'</div><h2 class="screen-title">{_text(s.title)}</h2>{body}{score}{comp}</div>'
    )


def _content_head(s) -> str:
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if getattr(s, "prompt_html", None):
        head += f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
    return head


def _r_accordion(s) -> str:
    # native <details> → JS'siz, klavye-erişilebilir
    items = "".join(
        f'<details class="acc-item ui-card"><summary class="acc-head">{_text(it.title)}</summary>'
        f'<div class="acc-body rich">{sanitize(it.body_html)}</div></details>'
        for it in s.items
    )
    return f'{_content_head(s)}<div class="accordion ui-stack">{items}</div>'


def _r_tabs(s) -> str:
    tabs = "".join(
        f'<button class="tab" type="button" role="tab" data-tab="{i}"'
        f' aria-selected="{"true" if i == 0 else "false"}">{_text(t.label)}</button>'
        for i, t in enumerate(s.tabs)
    )
    panels = "".join(
        f'<div class="tab-panel rich" role="tabpanel" data-panel="{i}"{"" if i == 0 else " hidden"}>'
        f'{sanitize(t.body_html)}</div>'
        for i, t in enumerate(s.tabs)
    )
    return (
        f'{_content_head(s)}<div class="tabs" data-tabs>'
        f'<div class="tab-list" role="tablist">{tabs}</div>{panels}</div>'
    )


def _r_flashcards(s) -> str:
    cards = "".join(
        f'<button class="flashcard" type="button" data-card aria-label="Kartı çevir">'
        f'<span class="fc-inner"><span class="fc-face fc-front rich">{sanitize(c.front_html)}</span>'
        f'<span class="fc-face fc-back rich">{sanitize(c.back_html)}</span></span></button>'
        for c in s.cards
    )
    return f'{_content_head(s)}<div class="flashcards ui-grid">{cards}</div>'


def _strip_html(html: str | None) -> str:
    return nh3.clean(html or "", tags=set(), attributes={}).strip()


def _r_matching(s) -> str:
    # her sol için <select> (klavye-erişilebilir); seçenekler = tüm sağ taraflar
    opts = "".join(
        f'<option value="{_attr(p.id)}">{_text(_strip_html(p.right_html))}</option>' for p in s.pairs
    )
    rows = "".join(
        f'<div class="match-row" data-pair="{_attr(p.id)}">'
        f'<div class="match-left rich">{sanitize(p.left_html)}</div>'
        f'<select class="match-select" data-pair="{_attr(p.id)}" aria-label="Eşleştir">'
        f'<option value="">— seç —</option>{opts}</select></div>'
        for p in s.pairs
    )
    return _quiz_shell(s, f'<div class="matching ui-stack">{rows}</div>')


def _r_sorting(s) -> str:
    items = "".join(
        f'<li class="sort-item ui-card" data-item="{_attr(it.id)}" draggable="true">'
        f'<span class="sort-text rich">{sanitize(it.text_html)}</span>'
        f'<span class="sort-ctrl"><button type="button" class="sort-up" aria-label="Yukarı taşı">▲</button>'
        f'<button type="button" class="sort-down" aria-label="Aşağı taşı">▼</button></span></li>'
        for it in s.items
    )
    return _quiz_shell(s, f'<ol class="sorting ui-stack" data-sorting>{items}</ol>')


def _r_timeline(s) -> str:
    events = "".join(
        f'<li class="tl-event"><span class="tl-marker"></span>'
        f'<div class="tl-content ui-card"><span class="tl-date ui-chip">{_text(e.date)}</span>'
        f'<h3 class="tl-title">{_text(e.title)}</h3>'
        + (f'<div class="rich">{sanitize(e.body_html)}</div>' if e.body_html else "")
        + "</div></li>"
        for e in s.events
    )
    return f'{_content_head(s)}<ol class="timeline">{events}</ol>'


def _r_lottie(s) -> str:
    attrs = (f'data-lottie-asset="{_attr(s.lottie_asset_id)}" '
             f'data-loop="{"1" if s.loop else "0"}" data-autoplay="{"1" if s.autoplay else "0"}"')
    return (f"{_content_head(s)}"
            f'<div class="lottie-wrap"><div class="lottie" {attrs} role="img"'
            f' aria-label="{_attr(s.title)}"></div></div>')


def _r_simulation(s) -> str:
    steps = ""
    for i, st in enumerate(s.steps):
        img = f'<img class="hotspot-img" data-asset="{_attr(st.image_asset_id)}" alt="">'
        if st.input_accepted is not None:  # YAZMA adımı
            acc = _attr(json.dumps(st.input_accepted, ensure_ascii=False))
            label = _attr(st.input_label or "Cevabını yaz")
            stage = (f'<div class="hotspot-stage">{img}</div>'
                     f'<div class="sim-input-row"><input class="sim-input" type="text" data-accepted="{acc}"'
                     f' placeholder="{label}" aria-label="{label}" autocomplete="off">'
                     f'<button class="btn btn-primary sim-submit" type="button">Tamam</button></div>')
        else:  # TIKLAMA adımı
            regions = "".join(
                f'<button class="hotspot-region sim-region" type="button" data-shape="{rg.shape}"'
                f' data-coords="{_attr(",".join(str(c) for c in rg.coords))}"'
                f' data-correct="{"1" if rg.correct else "0"}" title="{_attr(rg.label_html or "")}"></button>'
                for rg in st.regions
            )
            stage = f'<div class="hotspot-stage">{img}{regions}</div>'
        hint = f'<div class="sim-hint" hidden>{sanitize(st.hint_html or "")}</div>'
        hidden = "" if i == 0 else " hidden"
        steps += (f'<div class="sim-step" data-step="{i}"{hidden}>'
                  f'<div class="sim-instruction rich">{sanitize(st.instruction_html)}</div>'
                  f'{stage}{hint}</div>')
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.prompt_html:
        head += f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
    return (f'{head}<div class="simulation" data-sim data-steps="{len(s.steps)}">'
            f'<div class="sim-progress ui-chip">1 / {len(s.steps)}</div>{steps}</div>'
            f'<div class="feedback" role="status" aria-live="polite"></div>')


def _r_decision_scenario(s) -> str:
    start = s.start_node_id or s.nodes[0].id
    nodes_html = ""
    for node in s.nodes:
        img = (f'<img class="scen-img" data-asset="{_attr(node.image_asset_id)}" alt="">'
               if node.image_asset_id else "")
        rows = ""
        for c in node.choices:
            rows += (
                f'<li class="scen-row">'
                f'<button class="scen-choice" type="button" data-choice="{_attr(c.id)}"'
                f' data-delta="{int(c.score_delta)}" data-goto="{_attr(c.goto_node_id or "")}">'
                f'{sanitize(c.text_html)}</button>'
                f'<div class="scen-conseq rich" hidden>{sanitize(c.feedback_html)}</div></li>'
            )
        hidden = "" if node.id == start else " hidden"
        nodes_html += (
            f'<div class="scen-node" data-node="{_attr(node.id)}"{hidden}>'
            f'<div class="scen-prompt rich">{sanitize(node.prompt_html)}</div>{img}'
            f'<ul class="scen-choices">{rows}</ul>'
            f'<button class="btn btn-primary scen-next" type="button" hidden>Devam &rarr;</button>'
            f'</div>'
        )
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.intro_html:
        head += f'<div class="rich prompt">{sanitize(s.intro_html)}</div>'
    passattr = f' data-pass="{int(s.pass_score)}"' if s.pass_score is not None else ""
    return (
        f'{head}<div class="scenario" data-scenario data-points="{int(s.points)}"{passattr}'
        f' data-start="{_attr(start)}">'
        f'<div class="scen-hud ui-chip">Skor: <span class="scen-score">0</span></div>'
        f'{nodes_html}</div>'
        f'<div class="feedback" role="status" aria-live="polite"></div>'
    )


def _r_term_match_race(s) -> str:
    # her terim için <select> (klavye-erişilebilir); seçenekler = tüm tanımlar (DOM'da karıştırılır)
    opts = "".join(
        f'<option value="{_attr(p.id)}">{_text(_strip_html(p.definition_html))}</option>' for p in s.pairs
    )
    rows = "".join(
        f'<div class="match-row tmr-row" data-pair="{_attr(p.id)}">'
        f'<div class="match-left rich">{sanitize(p.term_html)}</div>'
        f'<select class="match-select tmr-select" data-pair="{_attr(p.id)}" aria-label="Eşleştir">'
        f'<option value="">— seç —</option>{opts}</select></div>'
        for p in s.pairs
    )
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.prompt_html:
        head += f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
    return (
        f'{head}<div class="term-race" data-tmr data-time="{int(s.time_limit_sec)}">'
        f'<div class="tmr-bar"><span class="tmr-timer ui-chip">⏱ {int(s.time_limit_sec)}</span>'
        f'<span class="tmr-score ui-chip">0 / {len(s.pairs)}</span></div>'
        f'<div class="matching ui-stack">{rows}</div>'
        f'<div class="quiz-actions"><button class="btn btn-check tmr-finish" type="button">Bitir</button></div>'
        f'</div><div class="feedback" role="status" aria-live="polite"></div>'
    )


def _r_escape_room(s) -> str:
    puzzles = ""
    for i, p in enumerate(s.puzzles):
        hint = f'<div class="esc-hint rich" hidden>{sanitize(p.hint_html or "")}</div>' if p.hint_html else ""
        hidden = "" if i == 0 else " hidden"
        puzzles += (
            f'<div class="esc-puzzle" data-puzzle="{i}"{hidden}>'
            f'<div class="esc-prompt rich">{sanitize(p.prompt_html)}</div>'
            f'<div class="esc-input-row"><input class="esc-input" type="text" autocomplete="off"'
            f' aria-label="Cevabını yaz" placeholder="Cevabını yaz">'
            f'<button class="btn btn-primary esc-submit" type="button">Aç</button></div>{hint}</div>'
        )
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.intro_html:
        head += f'<div class="rich prompt">{sanitize(s.intro_html)}</div>'
    hearts = "".join('<span class="esc-life">&#9829;</span>' for _ in range(s.lives))
    return (
        f'{head}<div class="escape" data-escape data-puzzles="{len(s.puzzles)}" data-lives="{int(s.lives)}">'
        f'<div class="esc-bar"><span class="esc-progress ui-chip">1 / {len(s.puzzles)}</span>'
        f'<span class="esc-lives">{hearts}</span></div>{puzzles}</div>'
        f'<div class="feedback" role="status" aria-live="polite"></div>'
    )


def _r_labeled_diagram(s) -> str:
    pins = "".join(
        f'<button class="ld-pin" type="button" data-label="{_attr(lb.id)}"'
        f' style="left:{lb.x / 10:.2f}%;top:{lb.y / 10:.2f}%" aria-label="İşaretçi {i + 1}">{i + 1}</button>'
        for i, lb in enumerate(s.labels)
    )
    opts = "".join(f'<option value="{_attr(lb.id)}">{_text(lb.text)}</option>' for lb in s.labels)
    rows = "".join(
        f'<div class="ld-row"><span class="ld-num">{i + 1}</span>'
        f'<select class="ld-select" data-label="{_attr(lb.id)}" aria-label="İşaretçi {i + 1} etiketi">'
        f'<option value="">— etiket seç —</option>{opts}</select></div>'
        for i, lb in enumerate(s.labels)
    )
    img = f'<img class="hotspot-img" data-asset="{_attr(s.image_asset_id)}" alt="">'
    inner = (
        f'<div class="labeled-diagram"><div class="ld-stage hotspot-stage">{img}{pins}</div>'
        f'<div class="ld-rows ui-stack">{rows}</div></div>'
    )
    return _quiz_shell(s, inner)


_CHART_COLORS = ["#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed", "#0891b2", "#dc2626", "#65a30d"]


def _r_data_chart(s) -> str:
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.prompt_html:
        head += f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
    svg = _build_chart_svg(s)
    cap = f'<figcaption class="chart-cap">{_text(s.caption)}</figcaption>' if s.caption else ""
    return f'{head}<figure class="data-chart">{svg}{cap}</figure>'


def _build_chart_svg(s) -> str:
    """Deterministik inline-SVG grafik (bar/line/pie) — dış lib/ağ yok."""
    data = s.data
    W, H, PAD = 600, 340, 40
    vmax = max((d.value for d in data), default=0) or 1
    if s.chart_type == "pie":
        total = sum(d.value for d in data) or 1
        cx, cy, r = 300, 170, 130
        import math
        a0 = -math.pi / 2
        parts, legend = [], []
        for i, d in enumerate(data):
            frac = d.value / total
            a1 = a0 + frac * 2 * math.pi
            large = 1 if frac > 0.5 else 0
            x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            col = _CHART_COLORS[i % len(_CHART_COLORS)]
            parts.append(f'<path d="M{cx},{cy} L{x0:.1f},{y0:.1f} A{r},{r} 0 {large},1 {x1:.1f},{y1:.1f} Z" fill="{col}"/>')
            legend.append(f'<tspan x="470" dy="22"><tspan fill="{col}">&#9632;</tspan> {_text(d.label)} ({frac * 100:.0f}%)</tspan>')
            a0 = a1
        return (f'<svg viewBox="0 0 {W} {H}" role="img" class="chart-svg">{"".join(parts)}'
                f'<text x="470" y="40" font-size="13" fill="currentColor">{"".join(legend)}</text></svg>')
    n = len(data)
    bw = (W - 2 * PAD) / max(n, 1)
    if s.chart_type == "line":
        pts = []
        for i, d in enumerate(data):
            x = PAD + bw * (i + 0.5)
            y = H - PAD - (d.value / vmax) * (H - 2 * PAD)
            pts.append(f"{x:.1f},{y:.1f}")
        dots = "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="4" fill="#2563eb"/>' for p in pts)
        labels = "".join(
            f'<text x="{PAD + bw * (i + 0.5):.1f}" y="{H - PAD + 18}" font-size="11" text-anchor="middle" fill="currentColor">{_text(d.label)}</text>'
            for i, d in enumerate(data))
        return (f'<svg viewBox="0 0 {W} {H}" role="img" class="chart-svg">'
                f'<line x1="{PAD}" y1="{H - PAD}" x2="{W - PAD}" y2="{H - PAD}" stroke="currentColor" opacity=".3"/>'
                f'<polyline points="{" ".join(pts)}" fill="none" stroke="#2563eb" stroke-width="2.5"/>{dots}{labels}</svg>')
    # bar (varsayılan)
    bars = ""
    for i, d in enumerate(data):
        bh = (d.value / vmax) * (H - 2 * PAD)
        x = PAD + bw * i + bw * 0.15
        y = H - PAD - bh
        col = _CHART_COLORS[i % len(_CHART_COLORS)]
        bars += (f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw * 0.7:.1f}" height="{bh:.1f}" rx="3" fill="{col}"/>'
                 f'<text x="{x + bw * 0.35:.1f}" y="{H - PAD + 18}" font-size="11" text-anchor="middle" fill="currentColor">{_text(d.label)}</text>'
                 f'<text x="{x + bw * 0.35:.1f}" y="{y - 6:.1f}" font-size="11" text-anchor="middle" fill="currentColor">{_num(d.value)}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" role="img" class="chart-svg">'
            f'<line x1="{PAD}" y1="{H - PAD}" x2="{W - PAD}" y2="{H - PAD}" stroke="currentColor" opacity=".3"/>{bars}</svg>')


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _r_results_breakdown(s) -> str:
    rows = ""
    for sec in s.sections:
        ids = _attr(",".join(sec.screen_ids))
        advice = (f'<div class="rb-advice rich" hidden>{sanitize(sec.advice_html)}</div>'
                  if sec.advice_html else "")
        rows += (
            f'<div class="rb-section" data-screens="{ids}">'
            f'<div class="rb-head"><span class="rb-title">{_text(sec.title)}</span>'
            f'<span class="rb-pct">—</span></div>'
            f'<div class="rb-track"><div class="rb-fill" style="width:0%"></div></div>{advice}</div>'
        )
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.body_html:
        head += f'<div class="rich">{sanitize(s.body_html)}</div>'
    total = ('<div class="rb-total" data-show-total="1" hidden></div>' if s.show_total else "")
    return (
        f'{head}<div class="results-breakdown" data-results data-weak="{int(s.weak_threshold)}">'
        f'{total}{rows}</div>'
    )


def _r_poll(s) -> str:
    head = f'<h2 class="screen-title">{_text(s.title)}</h2><div class="rich prompt">{sanitize(s.prompt_html)}</div>'
    inp_type = "checkbox" if s.multi else "radio"
    opts = "".join(
        f'<label class="poll-opt"><input type="{inp_type}" name="poll-{_attr(s.id or "p")}"'
        f' value="{_attr(o.id)}"><span class="rich">{sanitize(o.text_html)}</span></label>'
        for o in s.options
    )
    text = ('<textarea class="poll-text" rows="3" aria-label="Yansımanı yaz" '
            'placeholder="Düşünceni yaz…"></textarea>' if s.allow_text else "")
    reflection = (f'<div class="poll-reflection rich" hidden>{sanitize(s.reflection_html)}</div>'
                  if s.reflection_html else '<div class="poll-reflection rich" hidden>Paylaştığın için teşekkürler.</div>')
    return (
        f'{head}<div class="poll" data-poll>'
        f'<div class="poll-opts">{opts}</div>{text}'
        f'<div class="quiz-actions"><button class="btn btn-primary poll-submit" type="button">Gönder</button></div>'
        f'{reflection}</div>'
    )


def _r_image_compare(s) -> str:
    bl = f'<span class="ic-label ic-before">{_text(s.before_label)}</span>' if s.before_label else ""
    al = f'<span class="ic-label ic-after">{_text(s.after_label)}</span>' if s.after_label else ""
    cap = f'<figcaption class="chart-cap">{_text(s.caption)}</figcaption>' if s.caption else ""
    head = f'<h2 class="screen-title">{_text(s.title)}</h2>'
    if s.prompt_html:
        head += f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
    return (
        f'{head}<figure class="img-compare-wrap"><div class="img-compare" data-compare>'
        f'<img class="ic-img ic-img-before" data-asset="{_attr(s.before_asset_id)}" alt="">{bl}'
        f'<div class="ic-after-wrap"><img class="ic-img ic-img-after" data-asset="{_attr(s.after_asset_id)}" alt="">{al}</div>'
        f'<input class="ic-range" type="range" min="0" max="100" value="50" aria-label="Önce/sonra karşılaştır">'
        f'<div class="ic-divider"></div></div>{cap}</figure>'
    )


def _render_unknown(s) -> str:
    return f'<h2 class="screen-title">{_text(getattr(s, "title", "?"))}</h2>'


def _quiz_shell(s, inner: str) -> str:
    return (
        f'<h2 class="screen-title">{_text(s.title)}</h2>'
        f'<div class="rich prompt">{sanitize(s.prompt_html)}</div>'
        f'{inner}'
        f'<div class="quiz-actions"><button class="btn btn-check" type="button">Kontrol Et</button></div>'
        f'<div class="feedback" role="status" aria-live="polite"></div>'
    )


_SCREEN_DISPATCH = {
    ScreenType.title_slide: _r_title,
    ScreenType.content_slide: _r_content,
    ScreenType.mcq: _r_mcq,
    ScreenType.true_false: _r_true_false,
    ScreenType.fill_blank: _r_fill,
    ScreenType.drag_drop: _r_drag,
    ScreenType.hotspot: _r_hotspot,
    ScreenType.branching: _r_branching,
    ScreenType.video: _r_video,
    ScreenType.summary: _r_summary,
    ScreenType.accordion: _r_accordion,
    ScreenType.tabs: _r_tabs,
    ScreenType.flashcards: _r_flashcards,
    ScreenType.matching: _r_matching,
    ScreenType.sorting: _r_sorting,
    ScreenType.timeline: _r_timeline,
    ScreenType.lottie: _r_lottie,
    ScreenType.simulation: _r_simulation,
    ScreenType.decision_scenario: _r_decision_scenario,
    ScreenType.term_match_race: _r_term_match_race,
    ScreenType.escape_room: _r_escape_room,
    ScreenType.labeled_diagram: _r_labeled_diagram,
    ScreenType.data_chart: _r_data_chart,
    ScreenType.results_breakdown: _r_results_breakdown,
    ScreenType.poll: _r_poll,
    ScreenType.image_compare: _r_image_compare,
}


# --------------------------------------------------------------------------- #
# Küçük yardımcılar
# --------------------------------------------------------------------------- #
def _attr(s: str | None) -> str:
    return (s or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _text(s: str | None) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
