"""components/templates.py — HTML shell + premium CSS + SCORM engine JS.

renderer.py bunları kullanır. SHELL bir str.format() şablonudur; içindeki literal CSS süslü
parantezleri YOKTUR (tüm CSS {base_css} değeri olarak gelir), yalnız :root{{...}} kaçışlıdır.
BASE_CSS / ENGINE_JS / FALLBACK_RUNTIME_SHIM düz string'dir (format edilmez).
REVIEW_MARKUP da SHELL gibi bir str.format() şablonudur (renderer.py ayrıca .format(t=...) eder);
sonucu SHELL'e {review_markup} alanıyla düz metin olarak geçer, o alan SHELL.format() tarafından
tekrar işlenmez (1.1 — review UI, __PREVIEW__'dan bağımsız `review` bayrağına bağlı).
"""

# --------------------------------------------------------------------------- #
# HTML iskeleti (str.format şablonu)
# --------------------------------------------------------------------------- #
SHELL = """<!DOCTYPE html>
<html lang="{lang}" dir="{dir}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{og_tags}
<style>:root{{{css_vars}}}
{base_css}
{font_faces}
{custom_css}</style>
</head>
<body data-bg="{bg_pattern}" data-layout="{layout_mode}">
<a class="skip-link" href="#stage">{t[skip_to_content]}</a>
<div class="app">
  <header class="app-header">
    <div class="brand">{brand_mark}<span class="brand-title">{header_title}</span></div>
    <div class="progress" role="progressbar" aria-label="{t[progress]}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="progress-bar"></div></div>
    <span class="timer-hud" id="timerHud" aria-live="polite" hidden></span>
    <span class="level-hud" id="levelHud" aria-live="polite" hidden></span>
    <span class="lives-hud" id="livesHud" aria-label="{t[hud_lives]}" hidden></span>
    <span class="points-hud" id="pointsHud" aria-live="polite" hidden></span>
    <div class="status-pill" aria-live="polite"></div>{position_strip}
  </header>
  <main class="stage" id="stage" tabindex="-1">
    <div class="stage-scaler" id="stageScaler">
      <div class="stage-frame" id="stageFrame">
        {screens}
      </div>
    </div>
    <div class="cc-bar" id="ccBar" aria-live="polite" hidden></div>
  </main>
  <footer class="app-footer player">
    <button class="btn btn-ghost pl-icon" id="btnPrev" type="button" aria-label="{t[nav_prev]}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg></button>
    <button class="pl-btn" id="btnPlay" type="button" aria-label="{t[player_play_pause]}"><span class="ic-a"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="6 3 20 12 6 21 6 3"/></svg></span><span class="ic-b"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/></svg></span></button>
    <button class="pl-btn" id="btnReplay" type="button" aria-label="{t[player_replay]}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg></button>
    <input class="seekbar" id="seekbar" type="range" min="0" max="1000" value="0" step="1" aria-label="{t[player_seek]}" disabled>
    <span class="pl-time" id="plTime">0:00 / 0:00</span>
    <button class="pl-btn" id="btnMute" type="button" aria-label="{t[player_mute]}"><span class="ic-a"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg></span><span class="ic-b"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/></svg></span></button>
    <button class="pl-btn" id="btnCc" type="button" aria-pressed="false" aria-label="{t[player_captions]}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="14" x="3" y="5" rx="2" ry="2"/><path d="M7 15h4M15 15h2M7 11h2M13 11h4"/></svg></button>
    <button class="pl-btn" id="btnMenu" type="button" aria-haspopup="menu" aria-expanded="false" aria-label="{t[player_menu]}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/></svg></button>
    <div class="dots" id="dots"></div>
    <button class="btn btn-primary pl-icon" id="btnNext" type="button" aria-label="{t[nav_next]}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg></button>
  </footer>
  <nav class="slide-menu" id="slideMenu" aria-label="{t[menu_label]}"><div class="slide-menu-header"><h3>{t[menu_heading]}</h3><button class="slide-menu-close" id="menuClose" type="button" aria-label="{t[menu_close]}"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div><ul id="slideMenuList"{menu_tree_attrs}>{menu_tree_items}</ul></nav>
  <div class="menu-overlay" id="menuOverlay"></div>
</div>
{review_markup}
{runtime_block}
{extra_runtime}
<script>
window.__COURSE__ = {course_json};
window.__ASSETS__ = {asset_json};
window.__SCORM_2004__ = {scorm_2004};
window.__PREVIEW__ = {preview};
window.__REVIEW__ = {review};
window.__I18N__ = {i18n_json};
</script>
<script>
{engine_js}
</script>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# 1.1 — review/annotation FAB'ı bağımsız `review` bayrağına bağlı (str.format şablonu, SHELL'in
# {{t[...]}} kaçışlaması ile aynı desen). review=False iken renderer.py bunu SHELL'e HİÇ vermez
# (gizlemek değil, yoklamak) — /demo yüzeyinde reviewBtn/reviewPanel/reviewFab id'leri hiç yok.
# --------------------------------------------------------------------------- #
REVIEW_MARKUP = """<div class="review-fab" id="reviewFab" hidden>
  <button class="review-btn" id="reviewBtn" type="button" aria-haspopup="dialog"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> {t[review_open]}</button>
  <div class="review-panel" id="reviewPanel" role="dialog" aria-label="{t[review_open]}" hidden>
    <div class="review-head">{t[review_title]}</div>
    <textarea id="reviewText" rows="3" placeholder="{t[review_placeholder]}"></textarea>
    <div class="review-actions">
      <button class="btn btn-ghost" id="reviewCancel" type="button">{t[review_cancel]}</button>
      <button class="btn btn-primary" id="reviewSend" type="button">{t[review_send]}</button>
    </div>
    <div class="review-status" id="reviewStatus" aria-live="polite"></div>
  </div>
</div>"""


# --------------------------------------------------------------------------- #
# Premium CSS (düz string — literal braces)
# --------------------------------------------------------------------------- #
BASE_CSS = r"""
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
/* I2 — RTL: yerleşim logical property'lerle (inset-inline-*, margin-inline-*) aynalanır.
   transform:translateX() aynalanamaz, bu yüzden yön işareti bir değişkenle taşınır.
   NOT: hotspot/diyagram pin koordinatları ve önce/sonra karşılaştırma sürgüsü KASITLI olarak
   fiziksel kalır — bunlar metin akışı değil, uzamsal veridir; aynalamak görseli bozar. */
:root{--dir-x:1}
html[dir="rtl"]{--dir-x:-1}
/* Yönlü ikonlar: ileri/geri chevron'ları ve yeniden-oynat oku RTL'de ters yöne bakmalı.
   Diğer ikonlar (ses, altyazı, menü, geri bildirim) yönsüzdür — aynalanmaz. */
html[dir="rtl"] #btnPrev .ic,html[dir="rtl"] #btnNext .ic,
html[dir="rtl"] #btnReplay .ic{transform:scaleX(-1)}
html{font-size:var(--fs-base);scroll-behavior:smooth}
body{font-family:var(--font-body);font-weight:var(--w-body);line-height:var(--lh-normal);
  color:var(--c-text);background:var(--c-bg);-webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;overflow:hidden;height:100vh;height:100dvh}
body[data-bg="gradient"]{background:
  radial-gradient(ellipse 1400px 700px at 75% -5%, color-mix(in srgb,var(--c-primary) 8%,transparent),transparent),
  radial-gradient(ellipse 1000px 600px at -5% 105%, color-mix(in srgb,var(--c-secondary) 6%,transparent),transparent),
  radial-gradient(ellipse 600px 400px at 50% 50%, color-mix(in srgb,var(--c-accent) 3%,transparent),transparent),var(--c-bg)}
/* subtle noise overlay */
body::after{content:'';position:fixed;inset:0;pointer-events:none;z-index:9999;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.025'/%3E%3C/svg%3E");
  mix-blend-mode:overlay;opacity:.35}
body[data-bg="dots"]{background-image:radial-gradient(color-mix(in srgb,var(--c-border) 60%,transparent) 1px,transparent 1px);
  background-size:24px 24px}
body[data-bg="grid"]{background-image:linear-gradient(color-mix(in srgb,var(--c-border) 50%,transparent) 1px,transparent 1px),
  linear-gradient(90deg,color-mix(in srgb,var(--c-border) 50%,transparent) 1px,transparent 1px);background-size:36px 36px}
.app{height:100vh;height:100dvh;display:flex;flex-direction:column;max-width:1200px;margin:0 auto;overflow:hidden}

/* ===== FOUNDATION: a11y + primitifler ===== */
.skip-link{position:absolute;inset-inline-start:var(--space-4);top:-60px;z-index:100;background:var(--c-primary);
  color:var(--c-primary-contrast);padding:var(--space-3) var(--space-4);border-radius:var(--r-md);
  font-weight:var(--w-strong);transition:top var(--d-fast) var(--ease)}
.skip-link:focus{top:var(--space-4)}
.opt:focus-visible,.branch-choice:focus-visible,.drag-item:focus-visible,.hotspot-region:focus-visible,
.blank input:focus-visible,a:focus-visible{outline:3px solid var(--c-focus);
  outline-offset:2px;border-radius:var(--r-sm)}
.stage:focus{outline:none}
.btn,.opt,.branch-choice{min-height:44px}
.btn,.opt,.branch-choice,.scen-choice,.poll-opt,.pl-btn,.tab,.flashcard,select,input{touch-action:manipulation}
.ui-stack{display:flex;flex-direction:column;gap:var(--space-4)}
.ui-cluster{display:flex;flex-wrap:wrap;gap:var(--space-3);align-items:center}
.ui-grid{display:grid;gap:var(--space-4);grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.ui-card{background:var(--c-bg);border:1px solid var(--c-border);border-radius:var(--r-md);
  padding:var(--space-4);box-shadow:0 1px 3px color-mix(in srgb,var(--c-primary) 6%,transparent)}
.ui-chip{display:inline-flex;align-items:center;gap:var(--space-2);font-size:12px;font-weight:var(--w-strong);
  padding:var(--space-2) var(--space-3);border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--c-primary) 10%,var(--c-surface-alt));color:var(--c-primary)}
.ui-chip[hidden]{display:none}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media(prefers-contrast:more){
  .opt,.branch-choice,.drag-item,.ui-card{border-width:2px}
  .btn:focus-visible,.opt:focus-visible,.branch-choice:focus-visible{outline-width:4px}}

/* ===== HEADER — refined surface ===== */
.app-header{display:flex;align-items:center;gap:var(--space-4);padding:14px var(--gutter);
  background:var(--c-surface);
  border-bottom:none;
  box-shadow:0 1px 3px color-mix(in srgb,var(--c-primary) 5%,transparent),0 1px 0 var(--c-border);
  position:relative;z-index:10;flex:0 0 auto}
.brand{display:flex;align-items:center;gap:var(--space-3);font-family:var(--font-heading);
  font-weight:var(--w-strong);letter-spacing:var(--ls-heading)}
.brand-dot{width:10px;height:10px;border-radius:var(--r-pill);
  background:var(--c-primary);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--c-primary) 15%,transparent);
  animation:dotPulse 4s ease-in-out infinite}
@keyframes dotPulse{0%,100%{box-shadow:0 0 0 3px color-mix(in srgb,var(--c-primary) 12%,transparent)}
  50%{box-shadow:0 0 0 5px color-mix(in srgb,var(--c-primary) 20%,transparent)}}
.chrome-logo{height:22px;width:auto;max-width:120px;display:block;object-fit:contain}
.brand-title{font-size:15px;font-weight:600;color:var(--c-text);
  letter-spacing:-0.01em}
.progress{flex:1;height:6px;background:color-mix(in srgb,var(--c-border) 40%,transparent);
  border-radius:var(--r-pill);overflow:hidden}
.progress-bar{height:100%;width:0;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--c-primary),color-mix(in srgb,var(--c-primary) 70%,var(--c-accent)));
  transition:width .6s cubic-bezier(.22,1,.36,1);
  box-shadow:0 0 6px color-mix(in srgb,var(--c-primary) 20%,transparent)}
/* I2 — sayısal çiftler ("1 / 2", "0:05 / 1:30") RTL'de ters okunur: nötr "/" ayracı yön alır ve
   "1 / 2" ekranda "2 / 1" olur. Bunlar metin değil ÖLÇÜ; kendi yön adacığında LTR kalmalı. */
.status-pill,.pl-time{direction:ltr;unicode-bidi:isolate}
.status-pill{font-size:12px;color:var(--c-muted);min-width:60px;text-align:end;
  font-variant-numeric:tabular-nums;font-weight:500}
/* Faz 4-ek — republish devam bildirimi (dostane; teknik hata degil) */
.resume-notice{position:fixed;inset-block-start:14px;inset-inline-start:50%;transform:translateX(-50%);
  z-index:60;display:flex;align-items:center;gap:10px;max-width:min(92vw,560px);
  background:var(--c-surface);color:var(--c-text);border:1px solid color-mix(in srgb,var(--c-primary) 25%,transparent);
  border-radius:var(--r-md);box-shadow:0 6px 24px rgba(0,0,0,.18);padding:10px 14px;font-size:14px;line-height:1.45}
[dir="rtl"] .resume-notice{transform:translateX(50%)}
.resume-notice-close{flex:none;background:none;border:0;cursor:pointer;color:var(--c-muted);
  font-size:18px;line-height:1;padding:2px 6px;border-radius:var(--r-sm)}
.resume-notice-close:hover{color:var(--c-text)}
.timer-hud{font-family:var(--font-mono);font-weight:var(--w-strong);font-size:13px;color:var(--c-primary);
  background:color-mix(in srgb,var(--c-primary) 6%,var(--c-surface));
  padding:4px 10px;border-radius:var(--r-pill);border:1px solid color-mix(in srgb,var(--c-primary) 12%,transparent)}
.timer-hud.urgent{color:var(--c-error);background:var(--c-error-bg);border-color:var(--c-error)}
.points-hud{font-weight:var(--w-strong);font-size:13px;color:var(--c-warning);
  background:color-mix(in srgb,var(--c-warning) 8%,var(--c-surface));
  padding:4px 10px;border-radius:var(--r-pill);border:1px solid color-mix(in srgb,var(--c-warning) 15%,transparent)}
/* Faz 15 (G1) — birleşik HUD: seviye rozeti + can */
.level-hud{font-weight:var(--w-strong);font-size:13px;color:var(--c-primary);
  background:color-mix(in srgb,var(--c-primary) 8%,var(--c-surface));
  padding:4px 10px;border-radius:var(--r-pill);border:1px solid color-mix(in srgb,var(--c-primary) 15%,transparent)}
.lives-hud{font-size:14px;letter-spacing:1px;color:var(--c-danger,#dc2626)}
.lives-hud.lives-low{animation:badge .9s ease infinite}

/* ===== STAGE + SCREENS — viewport-fit ===== */
.stage{flex:1;position:relative;padding:0;overflow:hidden;min-height:0}
.screen{position:absolute;inset:0;opacity:0;visibility:hidden;
  transform:translateY(6px);
  transition:opacity .35s cubic-bezier(.22,1,.36,1),transform .35s cubic-bezier(.22,1,.36,1);
  pointer-events:none;overflow-y:auto;overflow-x:hidden}
.screen[aria-hidden="false"]{position:relative;opacity:1;visibility:visible;
  transform:none;pointer-events:auto;height:100%}
.screen-inner{max-width:var(--content-max);width:100%;margin:0 auto;
  background:var(--c-surface);
  border:1px solid color-mix(in srgb,var(--c-border) 60%,transparent);
  border-radius:var(--r-lg);box-shadow:0 4px 24px color-mix(in srgb,var(--c-primary) 4%,transparent),0 1px 2px rgba(0,0,0,.03);
  padding:clamp(24px,3vw,44px) clamp(20px,3vw,40px);height:100%;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column}
.screen[data-type="title_slide"] .screen-inner{background:
  linear-gradient(160deg,color-mix(in srgb,var(--c-primary) 4%,var(--c-surface)),var(--c-surface));
  box-shadow:0 8px 32px color-mix(in srgb,var(--c-primary) 6%,transparent);
  justify-content:center}
.screen-title{font-family:var(--font-heading);font-size:var(--fs-h2);font-weight:800;
  letter-spacing:var(--ls-heading);line-height:var(--lh-tight);margin-bottom:var(--space-4);
  text-wrap:balance}

/* ===== VIDEO SCREEN — immersive viewport-fit ===== */
.screen[data-type="video"] .screen-inner{padding:clamp(12px,2vw,24px)}
/* video-only (no narration text) — video-wrap directly in screen-inner flex column */
.screen[data-type="video"] .screen-inner > .video-wrap{flex:1;min-height:0}
.screen[data-type="video"] .split{display:flex;gap:clamp(12px,2vw,24px);align-items:stretch;flex:1;min-height:0}
.screen[data-type="video"] .split .split-text{flex:0 0 auto;max-width:38%;display:flex;flex-direction:column;
  justify-content:center;overflow-y:auto;overflow-x:hidden;padding-inline-end:var(--space-3);min-height:0}
.screen[data-type="video"] .split .split-media{flex:1;min-height:0;min-width:0;display:flex;align-items:center;
  justify-content:center;overflow:hidden}
.screen[data-type="video"] .video-wrap{width:100%;height:100%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;min-height:0;overflow:hidden}
.screen[data-type="video"] .video{max-width:100%;max-height:100%;width:auto;height:auto;
  object-fit:contain;border-radius:var(--r-lg);box-shadow:0 8px 32px rgba(0,0,0,.12);
  pointer-events:none}
/* dik (portrait) videolar — yükseklik sınırıyla alan içinde tut */
.screen[data-type="video"] .video.portrait{max-height:100%;max-width:60%;width:auto;margin:0 auto}
.screen[data-type="video"] figcaption{display:none}
.video-desc{font-size:calc(var(--fs-base) * .95)}
.video-desc p{line-height:1.7;color:var(--c-text)}

/* rich text */
.rich{font-size:var(--fs-base)}
.rich>*+*{margin-top:var(--space-3)}
.rich h1,.rich h2,.rich h3,.rich h4{font-family:var(--font-heading);font-weight:var(--w-heading);
  line-height:var(--lh-tight);letter-spacing:var(--ls-heading)}
.rich h1{font-size:var(--fs-h1)} .rich h2{font-size:var(--fs-h2)}
.rich h3{font-size:var(--fs-h3)} .rich h4{font-size:var(--fs-h4)}
.rich strong{font-weight:var(--w-strong)}
.rich a{color:var(--c-primary);text-underline-offset:3px}
.rich ul,.rich ol{padding-inline-start:1.4em} .rich li+li{margin-top:var(--space-2)}
.rich img{max-width:100%;height:auto;border-radius:var(--r-md);box-shadow:var(--e1)}
.rich blockquote{border-left:3px solid var(--c-primary);padding:var(--space-2) var(--space-4);
  background:var(--c-surface-alt);border-radius:0 var(--r-md) var(--r-md) 0;color:var(--c-muted)}
.rich code{font-family:var(--font-mono);background:var(--c-surface-alt);padding:.15em .4em;
  border-radius:var(--r-sm);font-size:.9em}
.rich table{width:100%;border-collapse:collapse} .rich th,.rich td{border:1px solid var(--c-border);
  padding:var(--space-3);text-align:start} .rich thead th{background:var(--c-surface-alt)}
.prompt{font-size:calc(var(--fs-base) * 1.05);margin-bottom:var(--space-4)}

/* media layouts — all media must fit within the card without scroll */
.media{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;border-radius:var(--r-md);box-shadow:var(--e1)}
.split{display:flex;gap:var(--space-5);align-items:stretch;flex:1;min-height:0}
.split .split-text{flex:0 0 45%;display:flex;flex-direction:column;justify-content:center;
  overflow-y:auto;overflow-x:hidden;min-height:0}
.split .split-media{flex:1;min-height:0;min-width:0;display:flex;align-items:center;
  justify-content:center;overflow:hidden}
.split .split-media .media{max-height:100%;width:auto;height:auto}
.split.text-first{flex-direction:row}
.split.media-first{flex-direction:row-reverse}
.full-media{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;overflow:hidden;
  margin:var(--space-3) auto}
.full-media .media{max-height:100%;width:auto;max-width:100%;height:auto;object-fit:contain}
/* P1/P3/P4 — akış içi (item/blok) görseller: doğal akar, max-width'e sığar, makul tavan.
   Yatay margin auto: display:block görsel geniş ekranda kolonundan darsa sola yapışıyordu
   (2026-07-29 raporu, ölçüm 341/659px); dar ekranda genişlik zaten dolu olduğundan etkisiz. */
.item-media{display:block;max-width:100%;width:auto;height:auto;max-height:340px;object-fit:contain;
  border-radius:var(--r-md);box-shadow:var(--e1);margin:var(--space-3) auto}
.content-blocks{flex:1;min-height:0}
.content-blocks figure.block-media{margin:0}
.content-blocks figcaption{font-size:13px;color:var(--c-muted);text-align:center;margin-top:var(--space-2)}
.acc-body .item-media,.tl-content .item-media,.tab-panel .item-media{max-height:240px}
.fc-face .item-media{max-height:130px;margin:0 auto var(--space-2)}

/* title slide */
.title-slide{text-align:center;padding:var(--space-5) 0;flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center}
.title-kicker{color:var(--c-primary);font-size:11px;letter-spacing:.4em;text-transform:uppercase;
  margin-bottom:var(--space-4)}
.title-main{font-family:var(--font-heading);font-weight:var(--w-heading);font-size:var(--fs-h1);
  line-height:var(--lh-tight);letter-spacing:var(--ls-heading);
  background:linear-gradient(135deg,var(--c-text) 30%,var(--c-primary) 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.title-sub{color:var(--c-muted);font-size:var(--fs-h4);margin-top:var(--space-3)}

/* buttons */
.btn{font-family:var(--font-body);font-weight:var(--w-strong);font-size:14px;cursor:pointer;
  border:1px solid transparent;border-radius:var(--r-md);padding:var(--space-3) var(--space-5);
  transition:all .2s cubic-bezier(.4,0,.2,1)}
.btn:active{transform:translateY(1px)}
.btn:focus-visible{outline:3px solid var(--c-focus);outline-offset:2px}
.btn-primary{background:var(--c-primary);color:var(--c-primary-contrast);
  box-shadow:0 2px 8px color-mix(in srgb,var(--c-primary) 25%,transparent)}
.btn-primary:hover{background:var(--c-primary-hover);
  box-shadow:0 4px 16px color-mix(in srgb,var(--c-primary) 30%,transparent);transform:translateY(-1px)}
.btn-primary:disabled{opacity:.55;cursor:not-allowed;box-shadow:none;transform:none}
.btn-ghost{background:transparent;color:var(--c-muted);border-color:color-mix(in srgb,var(--c-border) 60%,transparent)}
.btn-ghost:hover{color:var(--c-text);background:var(--c-surface-alt)}
.btn-ghost:disabled{opacity:.55;cursor:not-allowed}
.btn-check{background:var(--c-primary);color:var(--c-primary-contrast);
  box-shadow:0 2px 8px color-mix(in srgb,var(--c-primary) 20%,transparent)}
.btn-check:hover{background:var(--c-primary-hover);transform:translateY(-1px)}

/* ===== FOOTER / PLAYER BAR — premium surface ===== */
.app-footer{display:flex;align-items:center;justify-content:center;gap:var(--space-3);
  padding:12px var(--gutter);flex:0 0 auto;
  background:var(--c-surface);
  border-top:none;
  box-shadow:0 -1px 3px color-mix(in srgb,var(--c-primary) 4%,transparent),0 -1px 0 var(--c-border)}
.dots{display:flex;gap:4px;flex-wrap:wrap;justify-content:center}
.dot{width:7px;height:7px;border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--c-border) 50%,transparent);
  transition:all .3s cubic-bezier(.22,1,.36,1)}
.dot.visited{background:var(--c-primary);opacity:.6}
.dot.current{background:var(--c-primary);transform:scale(1.5);opacity:1;
  box-shadow:0 0 6px color-mix(in srgb,var(--c-primary) 40%,transparent)}

/* options (mcq / tf) */
.options{display:flex;flex-direction:column;gap:var(--space-3)}
.options.tf{flex-direction:row}
.opt{display:flex;align-items:center;gap:var(--space-3);text-align:start;cursor:pointer;
  background:var(--c-bg);
  border:1.5px solid var(--c-border);border-radius:var(--r-md);
  padding:var(--space-4);font-size:15px;color:var(--c-text);flex:1;
  transition:all .2s cubic-bezier(.4,0,.2,1)}
.opt:hover{border-color:var(--c-primary);box-shadow:0 2px 12px color-mix(in srgb,var(--c-primary) 12%,transparent);
  transform:translateY(-1px)}
.opt-mark{width:22px;height:22px;border-radius:var(--r-pill);border:2px solid var(--c-border);
  flex:0 0 auto;display:grid;place-items:center;transition:all .2s cubic-bezier(.4,0,.2,1)}
.opt.selected{border-color:var(--c-primary);background:color-mix(in srgb,var(--c-primary) 7%,var(--c-bg))}
.opt.selected .opt-mark{border-color:var(--c-primary);background:var(--c-primary)}
.opt.selected .opt-mark::after{content:"";width:8px;height:8px;border-radius:var(--r-pill);background:#fff}
.opt.correct{border-color:var(--c-success);background:var(--c-success-bg)}
.opt.wrong{border-color:var(--c-error);background:var(--c-error-bg)}
.opt:disabled{cursor:default;transform:none}
.opt-wrap{display:flex;flex-direction:column}
.opt-wrap .opt{flex:1}
.opt-fb{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-primary);background:var(--c-surface);
  border-radius:0 var(--r-sm) var(--r-sm) 0}

/* fill blank */
.blanks{display:flex;flex-direction:column;gap:var(--space-4)}
.blank{display:flex;flex-direction:column;gap:var(--space-2);font-size:13px;color:var(--c-muted)}
::placeholder{color:var(--c-muted);opacity:1}
.blank input{font-family:var(--font-body);font-size:15px;color:var(--c-text);background:var(--c-bg);
  border:1.5px solid var(--c-border);border-radius:var(--r-md);padding:var(--space-3) var(--space-4)}
.blank input:focus{outline:none;border-color:var(--c-primary);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--c-focus) 25%,transparent)}
.blank.correct input{border-color:var(--c-success);background:var(--c-success-bg)}
.blank.wrong input{border-color:var(--c-error);background:var(--c-error-bg)}

/* drag drop */
.dragdrop{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-5)}
.drag-pool{display:flex;flex-direction:column;gap:var(--space-3)}
.drag-item{background:var(--c-bg);border:1.5px solid var(--c-border);border-radius:var(--r-md);
  padding:var(--space-3) var(--space-4);cursor:grab;box-shadow:var(--e1);user-select:none;
  touch-action:none;transition:all .15s ease}
.drag-item.dragging{opacity:.5;transform:scale(.97)}
.drop-list{display:flex;flex-direction:column;gap:var(--space-3)}
.drop-target{border:1.5px dashed var(--c-border);border-radius:var(--r-md);padding:var(--space-3)}
.drop-target.over{border-color:var(--c-primary);background:color-mix(in srgb,var(--c-primary) 6%,var(--c-bg))}
.drop-label{font-size:13px;color:var(--c-muted);margin-bottom:var(--space-2)}
.drop-zone{min-height:44px;display:flex;flex-wrap:wrap;gap:var(--space-2)}
.drop-target.correct{border-style:solid;border-color:var(--c-success);background:var(--c-success-bg)}
.drop-target.wrong{border-style:solid;border-color:var(--c-error);background:var(--c-error-bg)}

/* hotspot */
.hotspot-stage{position:relative;display:inline-block;max-width:100%}
.hotspot-img{max-width:100%;height:auto;border-radius:var(--r-md);display:block;box-shadow:var(--e1)}
.hotspot-region{position:absolute;border:2px solid transparent;border-radius:var(--r-sm);
  background:transparent;cursor:pointer;transition:all .15s ease}
.hotspot-region:hover{border-color:color-mix(in srgb,var(--c-primary) 70%,transparent);
  background:color-mix(in srgb,var(--c-primary) 12%,transparent)}
.hotspot-region.correct{border-color:var(--c-success);background:color-mix(in srgb,var(--c-success) 22%,transparent)}
.hotspot-region.wrong{border-color:var(--c-error);background:color-mix(in srgb,var(--c-error) 22%,transparent)}

/* simulation */
.sim-instruction{font-weight:var(--w-strong);font-size:15px;margin-bottom:var(--space-3);
  padding:var(--space-3) var(--space-4);background:color-mix(in srgb,var(--c-primary) 8%,var(--c-bg));
  border-left:3px solid var(--c-primary);border-radius:0 var(--r-md) var(--r-md) 0}
.sim-progress{margin-bottom:var(--space-3)}
.sim-hint{margin-top:var(--space-3);padding:var(--space-3) var(--space-4);border-radius:var(--r-md);
  background:color-mix(in srgb,var(--c-warning) 14%,var(--c-bg));color:var(--c-warning);
  border:1px solid var(--c-warning);font-size:14px}
.sim-region{cursor:pointer;border-color:color-mix(in srgb,var(--c-primary) 40%,transparent)}
.sim-region.pulse{animation:simpulse 1.6s var(--ease) infinite}
@keyframes simpulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--c-primary) 45%,transparent)}
  50%{box-shadow:0 0 0 7px transparent}}
@media(prefers-reduced-motion:reduce){.sim-region.pulse{animation:none;border-color:var(--c-primary)}}
.sim-input-row{display:flex;gap:var(--space-3);margin-top:var(--space-3);align-items:center}
.sim-input{flex:1;font-family:var(--font-body);font-size:15px;color:var(--c-text);background:var(--c-bg);
  border:1.5px solid var(--c-border);border-radius:var(--r-md);padding:var(--space-3) var(--space-4);min-height:44px}
.sim-input:focus{outline:none;border-color:var(--c-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--c-focus) 22%,transparent)}
.sim-input.wrong{border-color:var(--c-error);background:var(--c-error-bg)}
.sim-submit{flex:0 0 auto}

/* branching */
.branches{display:flex;flex-direction:column;gap:var(--space-3)}
.branch-choice{text-align:start;cursor:pointer;background:var(--c-bg);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);padding:var(--space-4) var(--space-5);font-size:15px;color:var(--c-text);
  display:flex;align-items:center;gap:var(--space-3);
  transition:all .2s cubic-bezier(.4,0,.2,1)}
.branch-choice::before{content:"→";color:var(--c-primary);font-weight:700}
.branch-choice:hover{border-color:var(--c-primary);transform:translateX(calc(4px * var(--dir-x)));
  box-shadow:0 2px 12px color-mix(in srgb,var(--c-primary) 10%,transparent)}

/* karar senaryosu (decision_scenario) */
.scenario{display:flex;flex-direction:column;gap:var(--space-4)}
.scen-hud{align-self:flex-start;font-weight:var(--w-strong);color:var(--c-warning)}
.scen-prompt{font-size:16px}
.scen-img{width:100%;max-height:280px;object-fit:contain;border-radius:var(--r-md);background:var(--c-surface)}
.scen-choices{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:var(--space-3)}
.scen-row{display:flex;flex-direction:column;gap:var(--space-2)}
.scen-choice{text-align:start;cursor:pointer;background:var(--c-bg);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);padding:var(--space-4) var(--space-5);font-size:15px;color:var(--c-text);
  min-height:44px;display:flex;align-items:center;gap:var(--space-3);transition:all .2s cubic-bezier(.4,0,.2,1)}
.scen-choice::before{content:"▸";color:var(--c-primary);font-weight:700}
.scen-choice:hover:not(:disabled){border-color:var(--c-primary);transform:translateX(calc(4px * var(--dir-x)));
  box-shadow:0 2px 12px color-mix(in srgb,var(--c-primary) 10%,transparent)}
.scen-choice:disabled{cursor:default}
.scen-choice.chosen{border-color:var(--c-primary);background:color-mix(in srgb,var(--c-primary) 8%,var(--c-bg))}
.scen-choice.dim{opacity:.5}
.scen-conseq{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-primary);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}
.scen-next{align-self:flex-start}

/* term_match_race */
.tmr-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-3)}
.tmr-timer.urgent{color:var(--c-danger,#dc2626);font-weight:var(--w-strong)}
.tmr-row.correct .tmr-select{border-color:var(--c-success,#16a34a)}
.tmr-row.wrong .tmr-select{border-color:var(--c-danger,#dc2626)}

/* escape_room */
.esc-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-4)}
.esc-lives{font-size:18px;letter-spacing:2px;color:var(--c-danger,#dc2626)}
.esc-life.lost{opacity:.25}
.esc-input-row{display:flex;gap:var(--space-3);margin-top:var(--space-3)}
.esc-input{flex:1;min-height:44px;padding:0 var(--space-4);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);font-size:15px;background:var(--c-bg);color:var(--c-text)}
.esc-input.wrong{border-color:var(--c-danger,#dc2626);animation:simshake .4s}
@keyframes simshake{0%,100%{transform:translateX(0)}25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}
@media(prefers-reduced-motion:reduce){.esc-input.wrong{animation:none}}
.esc-puzzle.solved{opacity:.6}
.esc-hint{margin-top:var(--space-3);font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-warning,#d97706);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}

/* W3b — kompozisyonel oyun (game) */
.game{display:flex;flex-direction:column;gap:var(--space-4)}
.game-hud{display:flex;flex-wrap:wrap;align-items:center;gap:var(--space-2)}
.game-hud-score b,.game-hud-lives b,.game-hud-timer b{font-variant-numeric:tabular-nums}
.game-hud-lives{color:var(--c-error)}
.game-hint,.game-timer-extend,.game-timer-off{margin-inline-start:auto;font-size:12px;min-height:36px}
.game-timer-extend,.game-timer-off{margin-inline-start:0}
.game-hints{display:flex;flex-direction:column;gap:var(--space-2)}
.game-hint-text{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-warning,#d97706);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}
.game-content{font-size:16px}
.game-img{width:100%;max-height:280px;object-fit:contain;border-radius:var(--r-md);background:var(--c-surface)}
.game-choices{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:var(--space-3)}
.game-row{display:flex;flex-direction:column;gap:var(--space-2)}
.game-choice{text-align:start;cursor:pointer;background:var(--c-bg);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);padding:var(--space-4) var(--space-5);font-size:15px;color:var(--c-text);
  min-height:44px;display:flex;align-items:center;gap:var(--space-3);transition:all .2s cubic-bezier(.4,0,.2,1)}
.game-choice::before{content:"▸";color:var(--c-primary);font-weight:700}
.game-choice:hover:not(:disabled){border-color:var(--c-primary);transform:translateX(calc(4px * var(--dir-x)));
  box-shadow:0 2px 12px color-mix(in srgb,var(--c-primary) 10%,transparent)}
.game-choice:disabled{cursor:default}
.game-choice.chosen{border-color:var(--c-primary);background:color-mix(in srgb,var(--c-primary) 8%,var(--c-bg))}
.game-choice.dim{opacity:.5}
.game-choice.locked{opacity:.45;border-style:dashed;cursor:not-allowed}
.game-conseq{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-primary);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}
.game-next{align-self:flex-start}
@media(prefers-reduced-motion:reduce){.game-choice:hover:not(:disabled){transform:none}}

/* W4b — adaptif pratik (adaptive_practice) */
.adaptive{display:flex;flex-direction:column;gap:var(--space-4)}
.ap-hud{display:flex;flex-wrap:wrap;align-items:center;gap:var(--space-2)}
.ap-level{margin-inline-start:auto;font-variant-numeric:tabular-nums}
.ap-prompt{font-size:16px;margin-bottom:var(--space-3)}
.ap-options{margin-bottom:var(--space-2)}
.ap-explain{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-primary);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}

/* labeled_diagram */
.ld-stage{position:relative;display:inline-block;max-width:100%}
.ld-pin{position:absolute;transform:translate(-50%,-50%);width:28px;height:28px;border-radius:50%;
  background:var(--c-primary);color:var(--c-primary-contrast);border:2px solid #fff;font-weight:var(--w-strong);
  font-size:13px;cursor:pointer;box-shadow:var(--e2);display:grid;place-items:center}
.ld-pin.active{outline:3px solid var(--c-primary);outline-offset:2px;transform:translate(-50%,-50%) scale(1.15)}
.ld-rows{margin-top:var(--space-4)}
.ld-row{display:flex;align-items:center;gap:var(--space-3)}
.ld-num{flex:0 0 28px;height:28px;border-radius:50%;background:var(--c-primary);color:var(--c-primary-contrast);
  font-weight:var(--w-strong);font-size:13px;display:grid;place-items:center}
.ld-select{flex:1;min-height:44px;border:1.5px solid var(--c-border);border-radius:var(--r-md);
  padding:0 var(--space-3);background:var(--c-bg);color:var(--c-text)}
.ld-row.correct .ld-select{border-color:var(--c-success,#16a34a)}
.ld-row.wrong .ld-select{border-color:var(--c-danger,#dc2626)}
/* #126 labeled_diagram display (callout) modu — statik, daima-görünür açıklama kutuları
   görsel ÜSTÜNDE (split-attention exhibit çözümü): yorum görselle BİRLİKTE durur, göz
   gidiş-gelişini elder. num dot @koordinat + leader line + metin kutusu. Renkler yalnız
   gated token'dan: kutu=surface-alt/text (text_on_surface_alt), num=primary/contrast. */
.ld-display .ld-stage{overflow:visible}
.ld-callout{position:absolute;transform:translateY(-50%);display:flex;align-items:center;
  gap:0;max-width:min(48%,320px);z-index:1;pointer-events:none}
.ld-callout-num{flex:0 0 24px;height:24px;border-radius:50%;background:var(--c-primary);
  color:var(--c-primary-contrast);font-weight:var(--w-strong);font-size:12px;display:grid;
  place-items:center;border:2px solid #fff;box-shadow:var(--e2)}
.ld-leader{flex:0 0 18px;height:2px;background:var(--c-primary);align-self:center}
.ld-callout-text{background:var(--c-surface-alt);color:var(--c-text);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);padding:var(--space-2) var(--space-3);font-size:14px;line-height:1.35;
  box-shadow:var(--e1)}
@media(max-width:640px){
  .ld-display .ld-stage{display:block}
  .ld-display .ld-callout{position:static;transform:none;max-width:100%;margin-top:var(--space-2);gap:var(--space-2)}
  .ld-display .ld-leader{display:none}
}

/* data_chart */
.data-chart{margin:0;text-align:center}
.chart-svg{width:100%;max-width:600px;height:auto;color:var(--c-text)}
.chart-cap{color:var(--c-muted);font-size:13px;margin-top:var(--space-2)}

/* results_breakdown (Faz 14) */
.results-breakdown{display:flex;flex-direction:column;gap:var(--space-4)}
.rb-total{font-size:18px;align-self:flex-start;padding:var(--space-2) var(--space-4);
  border-radius:var(--r-md);background:var(--c-surface);border:1px solid var(--c-border)}
.rb-section{display:flex;flex-direction:column;gap:var(--space-2)}
.rb-head{display:flex;justify-content:space-between;font-weight:var(--w-strong);font-size:15px}
.rb-track{height:10px;background:var(--c-surface);border-radius:99px;overflow:hidden}
.rb-fill{height:100%;border-radius:99px;transition:width .6s var(--ease);background:var(--c-success,#16a34a)}
.rb-weak .rb-fill{background:var(--c-warning,#d97706)}
.rb-advice{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-warning,#d97706);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}

/* poll (Faz 14) */
.poll-opts{display:flex;flex-direction:column;gap:var(--space-2);margin-bottom:var(--space-3)}
.poll-opts.poll-nudge{animation:simshake .4s}
.poll-opt{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-3) var(--space-4);
  border:1.5px solid var(--c-border);border-radius:var(--r-md);cursor:pointer;min-height:44px}
.poll-opt:hover{border-color:var(--c-primary)}
.poll-text{width:100%;padding:var(--space-3);border:1.5px solid var(--c-border);border-radius:var(--r-md);
  background:var(--c-bg);color:var(--c-text);font-family:inherit;font-size:15px}
.poll-reflection{margin-top:var(--space-3);padding:var(--space-3) var(--space-4);
  border-left:3px solid var(--c-primary);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}

/* worked_example (F1 #112) — RTL-güvenli: logical property'ler */
.we-steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:var(--space-4)}
.we-step{padding:var(--space-4)}
.we-step-head{display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-2)}
.we-num{flex:0 0 28px;height:28px;border-radius:50%;background:var(--c-primary);color:var(--c-primary-contrast);
  font-weight:var(--w-strong);font-size:13px;display:grid;place-items:center}
.we-step-label{font-weight:var(--w-strong);font-size:14px;color:var(--c-muted)}
.we-rationale{margin-top:var(--space-2);padding:var(--space-2) var(--space-4);font-size:14px;
  border-inline-start:3px solid var(--c-accent);background:var(--c-surface-alt);
  border-radius:var(--r-sm)}
.we-rationale:not([hidden]){animation:pop .3s cubic-bezier(.4,0,.2,1)}
.we-step-body:not([hidden]){animation:pop .3s cubic-bezier(.4,0,.2,1)}
@media(prefers-reduced-motion:reduce){.we-rationale:not([hidden]),.we-step-body:not([hidden]){animation:none}}
.we-artifact{margin:var(--space-3) 0;text-align:center}
.we-artifact figcaption{color:var(--c-muted);font-size:13px;margin-top:var(--space-2)}
.we-reveal{margin-top:var(--space-2);min-height:44px}
.we-reveal[aria-expanded="true"]{color:var(--c-primary)}
.we-selfexp{margin-top:var(--space-5);display:flex;flex-direction:column;gap:var(--space-2);
  align-items:flex-start}
.we-selfexp-text{width:100%;padding:var(--space-3);border:1.5px solid var(--c-border);border-radius:var(--r-md);
  background:var(--c-bg);color:var(--c-text);font-family:inherit;font-size:15px}
.we-unscored{color:var(--c-muted)}

/* exploration (F2 #113) — RTL-güvenli: logical property'ler / yön-bağımsız akış */
.exploration{display:flex;flex-direction:column;gap:var(--space-3);align-items:flex-start}
.xp-label{font-weight:var(--w-strong);font-size:14px}
.xp-text{width:100%;padding:var(--space-3);border:1.5px solid var(--c-border);border-radius:var(--r-md);
  background:var(--c-bg);color:var(--c-text);font-family:inherit;font-size:15px}
.xp-hint{color:var(--c-muted);font-size:13px}
.xp-opts{display:flex;flex-direction:column;gap:var(--space-2);width:100%}
.xp-meta{display:flex;gap:var(--space-2);align-items:center}
.xp-saved{color:var(--c-primary)}
.xp-unscored{color:var(--c-muted)}
[data-exploration-ref]{font-weight:var(--w-strong)}
.xp-ref-empty{color:var(--c-muted);font-style:italic;font-weight:normal}

/* image_compare (Faz 14) */
.img-compare-wrap{margin:0;text-align:center}
.img-compare{position:relative;display:inline-block;max-width:100%;user-select:none;line-height:0}
.ic-img{display:block;width:100%;max-width:600px;height:auto;border-radius:var(--r-md)}
.ic-after-wrap{position:absolute;top:0;left:0;width:50%;height:100%;overflow:hidden}
.ic-after-wrap .ic-img{max-width:none;width:auto;height:100%}
.ic-divider{position:absolute;top:0;left:50%;width:2px;height:100%;background:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.2);pointer-events:none}
.ic-range{position:absolute;top:0;left:0;width:100%;height:100%;margin:0;opacity:0;cursor:ew-resize}
.ic-label{position:absolute;bottom:8px;font-size:12px;font-weight:var(--w-strong);color:#fff;
  background:rgba(0,0,0,.55);padding:2px 8px;border-radius:99px;pointer-events:none}
.ic-before{inset-inline-start:8px}.ic-after{inset-inline-end:8px}

/* video (genel kurallar — ekran-spesifik kurallar yukarıda) */
.video-wrap{margin:0}
.video{width:100%;border-radius:var(--r-md);box-shadow:var(--e2);background:#000;pointer-events:none}
.video-wrap figcaption{color:var(--c-muted);font-size:13px;margin-top:var(--space-2);text-align:center}

/* narration — GİZLİ, programatik playback */
.narration{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);opacity:0;pointer-events:none}

/* quiz feedback */
.quiz-actions{margin-top:var(--space-4)}
.feedback{margin-top:var(--space-3);padding:var(--space-4);border-radius:var(--r-md);font-size:15px;display:none}
.feedback.show{display:block;animation:pop .3s cubic-bezier(.4,0,.2,1)}
.feedback.ok{background:var(--c-success-bg);color:var(--c-success);border:1px solid var(--c-success)}
.feedback.no{background:var(--c-error-bg);color:var(--c-error);border:1px solid var(--c-error)}
@keyframes pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* summary */
.summary{text-align:center;flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
.summary-badge{width:72px;height:72px;border-radius:var(--r-pill);margin:0 auto var(--space-4);
  display:grid;place-items:center;font-size:34px;color:#fff;
  background:linear-gradient(135deg,var(--c-success),color-mix(in srgb,var(--c-success) 60%,var(--c-accent)));
  box-shadow:0 4px 20px color-mix(in srgb,var(--c-success) 30%,transparent);
  animation:badgePop .5s cubic-bezier(.4,0,.2,1)}
@keyframes badgePop{from{transform:scale(.7);opacity:0}to{transform:scale(1);opacity:1}}
.summary-badge .ic{width:38px;height:38px}
.summary-score{font-family:var(--font-heading);font-size:var(--fs-h1);font-weight:var(--w-heading);margin-top:var(--space-4)}
.summary-completion{margin-top:var(--space-3);color:var(--c-muted);font-size:15px}
.summary-completion.passed{color:var(--c-success)}.summary-completion.failed{color:var(--c-error)}

/* accordion */
.accordion summary.acc-head{cursor:pointer;font-weight:var(--w-strong);font-size:15px;list-style:none;
  display:flex;align-items:center;gap:var(--space-3);min-height:44px}
.accordion summary.acc-head::-webkit-details-marker{display:none}
.accordion summary.acc-head::before{content:"+";color:var(--c-primary);font-weight:700;font-size:18px;width:1em;flex:0 0 auto;
  transition:transform .2s ease}
.accordion details[open]>summary.acc-head::before{content:"\2013";transform:rotate(180deg)}
.accordion .acc-body{margin-top:var(--space-3)}
.accordion summary:focus-visible{outline:3px solid var(--c-focus);
  outline-offset:2px;border-radius:var(--r-sm)}

/* tabs */
.tab-list{display:flex;flex-wrap:wrap;gap:var(--space-2);border-bottom:2px solid var(--c-border);margin-bottom:var(--space-4)}
.tab{background:transparent;border:none;cursor:pointer;font-family:var(--font-body);font-weight:var(--w-strong);
  font-size:15px;color:var(--c-muted);padding:var(--space-3) var(--space-4);min-height:44px;
  border-bottom:2px solid transparent;margin-bottom:-2px;
  transition:all .2s cubic-bezier(.4,0,.2,1)}
.tab:hover{color:var(--c-text)}
.tab[aria-selected="true"]{color:var(--c-primary);border-bottom-color:var(--c-primary)}
.tab:focus-visible{outline:3px solid var(--c-focus);outline-offset:-2px;border-radius:var(--r-sm)}

/* flashcards */
.flashcard{background:transparent;border:none;padding:0;cursor:pointer;perspective:1000px;min-height:160px;font:inherit}
.fc-inner{position:relative;display:block;width:100%;min-height:160px;transform-style:preserve-3d;
  transition:transform .5s cubic-bezier(.4,0,.2,1)}
.flashcard.flipped .fc-inner{transform:rotateY(180deg)}
.fc-face{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:var(--space-4);border:1px solid var(--c-border);border-radius:var(--r-md);box-shadow:var(--e1);
  background:var(--c-bg);backface-visibility:hidden;-webkit-backface-visibility:hidden}
.fc-back{transform:rotateY(180deg);background:color-mix(in srgb,var(--c-primary) 7%,var(--c-bg))}
.flashcard:focus-visible{outline:3px solid var(--c-focus);outline-offset:3px;border-radius:var(--r-md)}
@media(prefers-reduced-motion:reduce){.fc-inner{transition:none}}

/* matching */
.match-row{display:grid;grid-template-columns:1fr auto;gap:var(--space-3);align-items:center}
.match-left{padding:var(--space-2) 0}
.match-select{font-family:var(--font-body);font-size:15px;color:var(--c-text);background:var(--c-bg);
  border:1.5px solid var(--c-border);border-radius:var(--r-md);padding:var(--space-3);min-height:44px;min-width:160px;cursor:pointer}
.match-select:focus-visible{outline:3px solid var(--c-focus);outline-offset:2px}
.match-row.correct .match-select{border-color:var(--c-success);background:var(--c-success-bg)}
.match-row.wrong .match-select{border-color:var(--c-error);background:var(--c-error-bg)}

/* sorting */
.sorting{list-style:none;padding:0}
.sort-item{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);cursor:grab;
  transition:all .15s ease}
.sort-item.dragging{opacity:.5;transform:scale(.97)}
.sort-text{flex:1}
.sort-ctrl{display:flex;flex-direction:column;gap:2px;flex:0 0 auto}
.sort-ctrl button{background:var(--c-surface-alt);border:1px solid var(--c-border);border-radius:var(--r-sm);
  width:34px;height:22px;cursor:pointer;color:var(--c-muted);font-size:11px;line-height:1;transition:all .15s ease}
.sort-ctrl button:hover{color:var(--c-primary);border-color:var(--c-primary);background:color-mix(in srgb,var(--c-primary) 6%,var(--c-bg))}
.sort-ctrl button:focus-visible{outline:2px solid var(--c-focus);outline-offset:1px}
.sort-item.correct{border-color:var(--c-success);background:var(--c-success-bg)}
.sort-item.wrong{border-color:var(--c-error);background:var(--c-error-bg)}

/* timeline */
.timeline{list-style:none;padding:0;position:relative;margin-inline-start:var(--space-2)}
.timeline::before{content:"";position:absolute;inset-inline-start:6px;top:8px;bottom:8px;width:2px;background:var(--c-border)}
.tl-event{position:relative;padding-inline-start:var(--space-6);margin-bottom:var(--space-5)}
.tl-marker{position:absolute;inset-inline-start:0;top:6px;width:14px;height:14px;border-radius:var(--r-pill);
  background:var(--c-primary);border:3px solid var(--c-bg);box-shadow:0 0 0 2px var(--c-primary)}
.tl-date{margin-bottom:var(--space-2)}
.tl-title{font-family:var(--font-heading);font-size:var(--fs-h4);font-weight:var(--w-strong);margin-bottom:var(--space-2)}

/* lottie */
.lottie-wrap{display:flex;justify-content:center;margin:var(--space-4) 0;flex:1}
.lottie{width:100%;max-width:480px;aspect-ratio:1/1}

/* review/annotation */
.review-fab{position:fixed;inset-inline-end:18px;bottom:70px;z-index:90}
.review-btn{background:var(--c-primary);color:var(--c-primary-contrast);border:none;border-radius:var(--r-pill);
  padding:var(--space-3) var(--space-4);font-weight:var(--w-strong);font-size:14px;cursor:pointer;
  box-shadow:0 4px 16px color-mix(in srgb,var(--c-primary) 30%,transparent);min-height:44px;
  transition:all .2s ease}
.review-btn:hover{transform:translateY(-2px);box-shadow:0 6px 24px color-mix(in srgb,var(--c-primary) 40%,transparent)}
.review-btn:focus-visible{outline:3px solid var(--c-focus);outline-offset:2px}
.review-panel{position:absolute;inset-inline-end:0;bottom:54px;width:300px;max-width:80vw;
  background:var(--c-surface);
  border:1px solid var(--c-border);
  border-radius:var(--r-lg);box-shadow:0 4px 24px color-mix(in srgb,var(--c-primary) 8%,transparent);padding:var(--space-4)}
.review-head{font-weight:var(--w-strong);font-size:13px;color:var(--c-muted);margin-bottom:var(--space-3)}
.review-panel textarea{width:100%;font-family:var(--font-body);font-size:14px;color:var(--c-text);background:var(--c-bg);
  border:1.5px solid var(--c-border);border-radius:var(--r-sm);padding:var(--space-3);resize:vertical}
.review-panel textarea:focus-visible{outline:none;border-color:var(--c-primary);box-shadow:0 0 0 3px color-mix(in srgb,var(--c-focus) 22%,transparent)}
.review-actions{display:flex;justify-content:flex-end;gap:var(--space-2);margin-top:var(--space-3)}
.review-actions .btn{padding:var(--space-2) var(--space-4);font-size:14px;min-height:auto}
.review-status{font-size:12px;color:var(--c-success);margin-top:var(--space-2);min-height:1em}

@media(prefers-reduced-motion:reduce){
  *{animation-duration:.001ms !important;transition-duration:.001ms !important}
  .screen{transform:none !important}}

/* ===== STAGE MODE ===== */
body[data-layout="stage"] .stage{display:flex;align-items:center;justify-content:center;
  overflow:hidden;padding:0;background:var(--c-surface-alt)}
.stage-scaler{position:relative;margin:0 auto}
body[data-layout="stage"] .stage-frame{
  position:relative;background:transparent;overflow:hidden;transform-origin:top left}
body[data-layout="stage"] .stage-frame .screen{position:absolute;inset:0;overflow-y:auto;overflow-x:hidden;
  padding:clamp(8px,1.5vw,20px)}
body[data-layout="flow"] .stage-scaler,body[data-layout="flow"] .stage-frame{
  width:auto;height:auto;transform:none !important}
/* Faz 17 — JS-tetikli reflow: sabit-tuval ölçeği okunabilirlik eşiğinin (k<0.85) altına
   düşünce fitStage data-fit="flow" set eder → dar/kısa ekran ve LMS iframe'lerde içerik
   küçülmek yerine doğal akışla (≤640px reflow ile aynı) yerleşir, dikey kaydırılır. */
body[data-layout="stage"][data-fit="flow"] .stage{align-items:center;justify-content:flex-start;overflow-y:auto}
body[data-layout="stage"][data-fit="flow"] .stage-scaler{width:100%!important;height:auto!important;margin:0}
body[data-layout="stage"][data-fit="flow"] .stage-frame{width:100%!important;height:auto!important;transform:none!important}
body[data-layout="stage"][data-fit="flow"] .stage-frame .screen[aria-hidden="false"]{position:relative;inset:auto;min-height:100%;overflow:visible}
body[data-layout="stage"][data-fit="flow"] .screen-inner{height:auto;min-height:100%;overflow:visible}
/* altyazı */
.cc-bar{position:absolute;inset-inline:5%;bottom:12px;z-index:6;
  background:rgba(0,0,0,.85);
  color:#fff;padding:8px 16px;border-radius:var(--r-lg);text-align:center;font-size:16px;line-height:1.5;
  box-shadow:0 2px 12px rgba(0,0,0,.25)}
body[data-layout="flow"] .stage{position:relative}
/* player bar */
.app-footer.player{gap:var(--space-3)}
.pl-btn{background:none;border:0;cursor:pointer;line-height:1;padding:8px;
  border-radius:var(--r-md);color:var(--c-muted);display:inline-flex;align-items:center;
  justify-content:center;transition:all .2s cubic-bezier(.22,1,.36,1);
  min-width:36px;min-height:36px}
.pl-btn:hover{background:color-mix(in srgb,var(--c-primary) 8%,transparent);color:var(--c-primary);
  transform:scale(1.06)}
.pl-btn:active{transform:scale(.94);transition-duration:80ms}
.pl-btn[aria-pressed="true"]{background:var(--c-primary);color:var(--c-primary-contrast);
  border-radius:var(--r-pill)}
.ic{width:18px;height:18px;display:block;flex:none}
.pl-btn .ic-a,.pl-btn .ic-b{display:inline-flex}
.pl-btn .ic-b{display:none}
.pl-btn.alt .ic-a{display:none}
.pl-btn.alt .ic-b{display:inline-flex}
.points-hud .ic,.mi-done .ic{width:14px;height:14px;display:inline-block;vertical-align:-2px}
.btn.pl-icon{display:inline-flex;align-items:center;justify-content:center;padding:8px 16px;
  border-radius:var(--r-pill);transition:all .2s cubic-bezier(.22,1,.36,1)}
.btn.pl-icon:hover{transform:scale(1.05)}
.btn.pl-icon:active{transform:scale(.95);transition-duration:80ms}
.review-btn{display:inline-flex;align-items:center;gap:6px}
.review-status{display:inline-flex;align-items:center;gap:5px}
/* seekbar — premium range */
.seekbar{flex:1;min-width:60px;accent-color:var(--c-primary);cursor:pointer;
  -webkit-appearance:none;appearance:none;height:6px;border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--c-border) 50%,transparent);outline:none;
  transition:height .2s ease}
.seekbar::-webkit-slider-runnable-track{height:6px;border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--c-border) 50%,transparent)}
.seekbar::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;
  background:var(--c-primary);border:2px solid var(--c-surface);cursor:pointer;
  box-shadow:0 1px 4px color-mix(in srgb,var(--c-primary) 30%,transparent);
  margin-top:-4px;transition:transform .15s ease}
.seekbar:hover::-webkit-slider-thumb{transform:scale(1.2)}
.seekbar:disabled{opacity:.35;cursor:default}
.seekbar:disabled::-webkit-slider-thumb{opacity:0}
.pl-time{font-variant-numeric:tabular-nums;font-size:12px;font-weight:500;
  color:var(--c-muted);min-width:80px;text-align:center;letter-spacing:.01em}

/* ===== SLIDE MENU — premium drawer ===== */
.menu-overlay{position:fixed;inset:0;z-index:40;background:rgba(0,0,0,.2);
  backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);
  opacity:0;visibility:hidden;transition:all .3s cubic-bezier(.22,1,.36,1)}
.menu-overlay.open{opacity:1;visibility:visible}
.slide-menu{position:fixed;top:0;inset-inline-end:0;bottom:0;z-index:50;width:320px;max-width:85vw;
  background:var(--c-surface);
  border-left:1px solid color-mix(in srgb,var(--c-border) 50%,transparent);
  box-shadow:-8px 0 32px color-mix(in srgb,var(--c-primary) 5%,transparent),-2px 0 8px rgba(0,0,0,.04);
  transform:translateX(calc(100% * var(--dir-x)));transition:transform .35s cubic-bezier(.22,1,.36,1);
  display:flex;flex-direction:column;overflow:hidden}
.slide-menu.open{transform:translateX(0)}
.slide-menu.open li{animation:menuItemIn .3s cubic-bezier(.22,1,.36,1) both}
.slide-menu-header{padding:18px 20px;display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid var(--c-border);flex:0 0 auto}
.slide-menu-header h3{font-family:var(--font-heading);font-size:15px;font-weight:700;
  letter-spacing:var(--ls-heading);color:var(--c-text)}
.slide-menu-close{background:none;border:0;cursor:pointer;padding:6px;border-radius:var(--r-md);
  color:var(--c-muted);display:inline-flex;transition:all .2s cubic-bezier(.22,1,.36,1)}
.slide-menu-close:hover{background:var(--c-surface-alt);color:var(--c-text);transform:rotate(90deg)}
.slide-menu-close .ic{width:18px;height:18px}
.slide-menu ul{list-style:none;margin:0;padding:8px 12px;overflow:auto;flex:1}
.slide-menu li{padding:10px 14px;border-radius:var(--r-md);cursor:pointer;font-size:14px;
  display:flex;gap:10px;align-items:center;transition:all .2s cubic-bezier(.22,1,.36,1);
  margin-bottom:2px;opacity:0}
.slide-menu.open li{opacity:1}
@keyframes menuItemIn{from{opacity:0;transform:translateX(calc(12px * var(--dir-x)))}to{opacity:1;transform:none}}
.slide-menu li:hover{background:color-mix(in srgb,var(--c-primary) 6%,transparent);
  transform:translateX(calc(2px * var(--dir-x)))}
.slide-menu li[aria-current="true"]{font-weight:var(--w-strong);color:var(--c-primary);
  background:color-mix(in srgb,var(--c-primary) 8%,transparent);
  border-inline-start:3px solid var(--c-primary);padding-inline-start:11px;opacity:1}
.slide-menu li .mi-done{color:var(--c-success);margin-inline-start:auto;display:inline-flex}
.slide-menu li.menu-section{font-size:11px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--c-muted);cursor:default;padding:16px 14px 6px;font-weight:var(--w-strong);margin-bottom:0;opacity:1}
.slide-menu li.menu-section:hover{background:none;transform:none}
/* timeline reveal */
.screen[data-reveal="auto"] .tl-block,.screen[data-reveal="click"] .tl-block{opacity:0}
.screen[data-reveal="auto"] .tl-block.tl-in,.screen[data-reveal="click"] .tl-block.tl-in{
  opacity:1;animation:tlFadeUp .45s ease both}
.screen[data-anim="fade"] .tl-block.tl-in{animation-name:tlFade}
.screen[data-anim="zoom"] .tl-block.tl-in{animation-name:tlZoom}
.screen[data-anim="slide-left"] .tl-block.tl-in{animation-name:tlSlideLeft}
@keyframes tlFadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes tlFade{from{opacity:0}to{opacity:1}}
@keyframes tlZoom{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}
@keyframes tlSlideLeft{from{opacity:0;transform:translateX(calc(28px * var(--dir-x)))}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.tl-block{opacity:1 !important}
  .tl-block.tl-in{animation:none !important}}

/* ===== RESPONSIVE — tablet ===== */
@media(max-width:960px){
  .screen[data-type="video"] .split{flex-direction:column}
  .screen[data-type="video"] .split .split-text{flex:0 0 auto;max-height:30%;max-width:100%;padding-inline-end:0;padding-bottom:var(--space-2)}
  .screen[data-type="video"] .split .split-media{flex:1}
  .screen[data-type="video"] .video.portrait{max-width:50%}
  .split{grid-template-columns:1fr}
  .dragdrop{grid-template-columns:1fr}
}
/* ===== RESPONSIVE — mobil ===== */
@media(max-width:640px){
  body{height:100dvh}
  .app{height:100dvh}
  body[data-layout="stage"] .stage{padding:0}
  .app-header{flex-wrap:wrap;gap:6px;row-gap:4px;padding:8px 12px}
  .brand-title{font-size:13px}
  .status-pill{font-size:11px;min-width:44px}
  .app-footer.player{flex-wrap:wrap;gap:4px;padding:8px 10px;justify-content:center}
  .seekbar{order:-1;flex-basis:100%;min-width:0;height:5px}
  .seekbar::-webkit-slider-thumb{width:12px;height:12px;margin-top:-3.5px}
  .dots{display:none}
  .pl-time{font-size:11px;min-width:auto}
  .pl-btn{padding:8px}
  .cc-bar{font-size:13px;bottom:6px;inset-inline:2%;padding:5px 10px}
  .slide-menu{width:280px}
  .review-fab{bottom:56px}
  .screen-inner{padding:14px}
  .screen-title{font-size:calc(var(--fs-h2) * .85)}
  .match-row{grid-template-columns:1fr}
  .match-select{min-width:0;width:100%}
  .options.tf{flex-direction:column}
  /* Faz 16 — mobil/dar ekran: sabit-tuval ölçeklemesini BIRAK, içerik doğal akışla reflow
     + dikey kaydırma (metin okunabilir kalır, tuval küçülmez) */
  body[data-layout="stage"] .stage{align-items:center;justify-content:flex-start;overflow-y:auto}
  body[data-layout="stage"] .stage-scaler{width:100%!important;height:auto!important;margin:0}
  body[data-layout="stage"] .stage-frame{width:100%!important;height:auto!important;transform:none!important}
  body[data-layout="stage"] .stage-frame .screen[aria-hidden="false"]{position:relative;inset:auto;min-height:100%;overflow:visible}
  .screen-inner{height:auto;min-height:100%;overflow:visible}
}
/* ===== RESPONSIVE — küçük mobil ===== */
@media(max-width:380px){
  .app-header{padding:6px 8px}
  .app-footer.player{padding:6px 8px}
  .brand-title{display:none}
  .screen-inner{padding:10px}
}
/* ===== 1.5 — GÖMME MODU (?embed=1) — chromeless varyant, tek dosya/tek önbellek =====
   Sunucu ?embed=1'i asla görmez (render dallanmaz); boot JS location.search'ten okuyup
   body[data-embed="1"] koyar (bkz. ENGINE_JS). Menü butonu + dots + review FAB gizlenir
   (Feedback FAB zaten demolarda yok); dış boşluk azaltılır. prev/next KALIR. */
body[data-embed="1"] #btnMenu{display:none!important}
body[data-embed="1"] .dots{display:none!important}
body[data-embed="1"] .review-fab{display:none!important}
body[data-embed="1"] .app-header{padding:6px var(--gutter,12px)}
body[data-embed="1"] .app-footer{padding:6px var(--gutter,12px)}
"""


# --------------------------------------------------------------------------- #
# SCORM engine JS (düz string)
# --------------------------------------------------------------------------- #
ENGINE_JS = r"""
(function(){
"use strict";
// 1.5 — gömme modu: sunucu ?embed=1'i hiç görmez (aynı önbellekli HTML), yalnız istemci burada
// location.search'ü okuyup body[data-embed="1"] koyar → BASE_CSS chromeless kuralları devreye girer.
if(/(?:^|[?&])embed=1(?:&|$)/.test(location.search||"")) document.body.dataset.embed="1";
var COURSE = window.__COURSE__, ASSETS = window.__ASSETS__, S2004 = window.__SCORM_2004__;
// I1 — çalışma anında üretilen metinler dile göre çözülür (kabuk HTML'i Python tarafında çözüldü).
// Anahtar bulunamazsa anahtarın kendisi döner: sessiz boş metin yerine görünür sinyal.
var I18N = window.__I18N__ || {};
function T(key, params){
  var s = I18N[key]; if(s==null) return key;
  if(params){ for(var k in params){ s = s.split("{"+k+"}").join(String(params[k])); } }
  return s;
}
var byId = {}; COURSE.screens.forEach(function(s){ byId[s.id]=s; });
var order = COURSE.id_order;
var sections = Array.prototype.slice.call(document.querySelectorAll(".screen"));
var secById = {}; sections.forEach(function(el){ secById[el.dataset.screenId]=el; });

// ---- asset çözümle ----
function assetSrc(id){ return ASSETS[id] || ""; }
document.querySelectorAll("[data-asset]").forEach(function(el){
  var src=assetSrc(el.dataset.asset); if(!src) return;
  if(el.tagName==="SOURCE"){ el.src=src; var v=el.parentNode; if(v&&v.load)v.load(); }
  else { el.src=src; }
});
document.querySelectorAll("[data-bg-asset]").forEach(function(el){
  var src=assetSrc(el.dataset.bgAsset); if(src) el.style.backgroundImage="url('"+src+"')";
});
document.querySelectorAll("[data-poster-asset]").forEach(function(el){
  var src=assetSrc(el.dataset.posterAsset); if(src) el.poster=src;
});

// ---- SCORM API ----
var SCORM_NAME = S2004 ? "API_1484_11" : "API";
function findAPI(win){
  var n=0;
  while(win && !win[SCORM_NAME] && win.parent && win.parent!==win && n<12){ win=win.parent; n++; }
  return win ? win[SCORM_NAME] : null;
}
function getAPI(){
  var api=findAPI(window);
  if(!api && window.opener) api=findAPI(window.opener);
  if(!api){
    try {
      var Ctor = S2004 ? window.Scorm2004API : window.Scorm12API;
      if(Ctor){ api=new Ctor({autocommit:false,logLevel:5}); window[SCORM_NAME]=api; }
    } catch(e){}
  }
  return api;
}
var api=getAPI();
function sSet(k,v){ if(!api)return; try{ S2004?api.SetValue(k,String(v)):api.LMSSetValue(k,String(v)); }catch(e){} }
// S5 (2.2c) — suspend_data görünürlüğü: sSet hatayı yutar ama BU yazımın başarısını bilmemiz gerekir.
// API yoksa (preview) true: uyarı spam'i olmasın. Başarı yorumu (CMIBoolean) scorm.js'te (saf, testli).
function sSetChecked(k,v){ if(!api)return true;
  try{ var r=S2004?api.SetValue(k,String(v)):api.LMSSetValue(k,String(v));
    return RT.setResultOk?RT.setResultOk(r):String(r)!=="false"; }catch(e){ return false; } }
function sGet(k){ if(!api)return""; try{ return S2004?api.GetValue(k):api.LMSGetValue(k); }catch(e){ return ""; } }
function sCommit(){ if(!api)return; try{ S2004?api.Commit(""):api.LMSCommit(""); }catch(e){} }
function sInit(){ if(!api)return; try{ S2004?api.Initialize(""):api.LMSInitialize(""); }catch(e){} }
function sFinish(){ if(!api)return; try{ S2004?api.Terminate(""):api.LMSFinish(""); }catch(e){} }
sInit();
// S1/S3/S4 — SCORM veri sözleşmesi yardımcıları (components/engine/scorm.js → koşulsuz inline).
// Yoksa (beklenmedik) tüm yeni yazımlar sessizce atlanır; mevcut davranış bozulmaz.
var RT = window.SCORMRT || {};
if(S2004){ sSet("cmi.score.min","0"); sSet("cmi.score.max","100"); sSet("cmi.completion_status","incomplete"); }
else { sSet("cmi.core.score.min","0"); sSet("cmi.core.score.max","100"); sSet("cmi.core.lesson_status","incomplete"); }

// ---- S3: seat time (oturum süresi) ----
// Sekme GİZLİYKEN geçen süre sayılmaz — açık bırakılan sekme "20 saat eğitim" olarak raporlanmasın.
var _sesMs=0, _sesFrom=Date.now();
function _sesPause(){ if(_sesFrom!=null){ _sesMs+=Date.now()-_sesFrom; _sesFrom=null; } }
function _sesResume(){ if(_sesFrom==null) _sesFrom=Date.now(); }
document.addEventListener("visibilitychange",function(){ document.hidden?_sesPause():_sesResume(); });
function sessionMs(){ return _sesMs + (_sesFrom!=null ? Date.now()-_sesFrom : 0); }
function writeSessionTime(){ if(!RT.sessionTime) return;
  sSet(S2004?"cmi.session_time":"cmi.core.session_time", RT.sessionTime(sessionMs(), S2004)); }

// ---- durum (suspend_data'dan geri yükle) ----
// S4 — entry "ab-initio" ise LMS yeni bir deneme başlatmıştır: eski suspend_data'yı GERİ YÜKLEME.
// Faz 4-ek — republish dayanıklılığı: resumeSuspend okuma merdiveni (scorm.js) orderFp
// uyuşmazlığında pozisyonel alanları atar ama KİMLİK-tabanlı pozisyon kaydından (z) devam
// noktası çıkarır: düğüm yaşıyorsa SESSİZ devam; düğüm gitmiş/ekran yaşıyorsa ya da ikisi de
// gitmişse DOSTANE bildirim (_resumeNotice — showAt sonrası basılır; teknik hata ASLA).
var state={visited:{},results:{},history:[]};
var _resumeNotice=null;
(function restore(){ try{
  var raw=sGet("cmi.suspend_data");
  var entry=sGet(S2004?"cmi.entry":"cmi.core.entry");
  var may = RT.shouldRestore ? RT.shouldRestore(entry, !!raw) : !!raw;
  if(may && raw){
    if(RT.resumeSuspend){
      var sn={}; COURSE.screens.forEach(function(s){ if(s.node_id!=null) sn[s.id]=s.node_id; });
      var rz=RT.resumeSuspend(raw,order,{cv:COURSE.content_version,screenNode:sn});
      if(rz&&rz.state){ state=rz.state;
        state.visited=state.visited||{}; state.results=state.results||{}; state.history=state.history||[];
        if(rz.notice) _resumeNotice={target:rz.target,mode:rz.mode}; }
    } else {
      // S5 — v2 kompakt format + v1 (eski JSON) migrasyonu scorm.js'te; RT yoksa eski yol.
      var d=RT.decodeSuspend?RT.decodeSuspend(raw,order):JSON.parse(raw);
      if(d&&d.visited){ state=d; state.history=state.history||[]; }
    }
  }
}catch(e){} })();

// ---- Faz 5: değişken/durum motoru (state.vars → suspend_data'da persist) ----
if(!state.vars){ state.vars={}; (COURSE.variables||[]).forEach(function(v){ state.vars[v.name]=v.default; }); }
// F2 (#113) — keşif girdileri (store_key → değer); suspend v2 kuyruğunda persist edilir (scorm.js).
if(!state.xp) state.xp={};
function _vnum(x){ var n=parseFloat(x); return isNaN(n)?0:n; }
function applyActions(acts){ if(!acts||!acts.length) return; acts.forEach(function(a){
  if(a.op==="add"){ state.vars[a.var]=_vnum(state.vars[a.var])+_vnum(a.value); }
  else { state.vars[a.var]=a.value; } }); updateHud(); }
function evalCond(c){ if(!c) return true; var v=state.vars[c.var];
  switch(c.cmp){ case "==":return v==c.value; case "!=":return v!=c.value;
    case ">":return _vnum(v)>_vnum(c.value); case "<":return _vnum(v)<_vnum(c.value);
    case ">=":return _vnum(v)>=_vnum(c.value); case "<=":return _vnum(v)<=_vnum(c.value); }
  return true; }
function isVisible(id){ var s=byId[id]; return !s||!s.visible_if||evalCond(s.visible_if); }
function interpolateScreen(el){ if(!(el&&COURSE.variables&&COURSE.variables.length)) return;
  var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT,null),nodes=[],n;
  while(n=w.nextNode()) nodes.push(n);
  nodes.forEach(function(t){ var tpl=(t.__tpl!=null)?t.__tpl:t.nodeValue; if(tpl.indexOf("{{")<0) return;
    t.__tpl=tpl; t.nodeValue=tpl.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g,function(m,k){
      return (state.vars&&state.vars[k]!=null)?String(state.vars[k]):""; }); }); }

// ---- Faz 6: oyunlaştırma (puan HUD + timer) ----
function updatePoints(){ if(!COURSE.points_var) return; var h=document.getElementById("pointsHud");
  if(!h) return; h.hidden=false; var v=state.vars[COURSE.points_var]; h.innerHTML=STAR_SVG+" "+(v!=null?v:0); }
// Faz 15 (G1) — birleşik oyunlaştırma HUD'u: seviye (puan→rozet) + can (kalpler)
function currentLevel(){ if(!COURSE.levels||!COURSE.levels.length||!COURSE.points_var) return null;
  var v=_vnum(state.vars[COURSE.points_var]); var lv=null;
  COURSE.levels.forEach(function(L){ if(v>=L.min_points) lv=L; }); return lv; }
function updateLevel(){ var el=document.getElementById("levelHud"); if(!el) return;
  var L=currentLevel(); if(!L){ el.hidden=true; return; } el.hidden=false; el.textContent="◆ "+L.name; }
function updateLives(){ if(!COURSE.lives_var) return; var el=document.getElementById("livesHud"); if(!el) return;
  el.hidden=false; var v=_vnum(state.vars[COURSE.lives_var]); var max=COURSE.max_lives||0;
  var s=""; for(var i=0;i<max;i++){ s+=(i<v?"●":"○"); } el.textContent=s;
  el.classList.toggle("lives-low", v>0 && v<=1); }
function updateHud(){ updatePoints(); updateLevel(); updateLives(); }
var _timer=null;
function clearTimer(){ if(_timer){ clearInterval(_timer); _timer=null; }
  var h=document.getElementById("timerHud"); if(h){ h.hidden=true; h.classList.remove("urgent"); } }
function _fmtT(t){ var m=Math.floor(t/60),s=t%60; return "⏱ "+m+":"+(s<10?"0":"")+s; }
function startTimer(s){ clearTimer(); if(!s||!s.timer_sec) return;
  var h=document.getElementById("timerHud"); if(!h) return; var sid=s.id, left=s.timer_sec;
  h.hidden=false; h.textContent=_fmtT(left);
  _timer=setInterval(function(){ if(state.cursorId!==sid){ clearTimer(); return; }
    left--; if(left<=10) h.classList.add("urgent"); h.textContent=_fmtT(Math.max(0,left));
    if(left<=0){ clearTimer(); applyActions(s.on_timeout);
      if(s.timeout_goto && byId[s.timeout_goto]) goId(s.timeout_goto,true); else next(); } },1000); }

// ---- Faz 7: lottie animasyon (lazy — ekran gösterilince init; lib yalnız animasyonlu kursta yüklü) ----
var _lottieInit={};
function initLottie(el,s){ if(!window.lottie || !s || _lottieInit[s.id]) return;
  var box=el&&el.querySelector(".lottie"); if(!box) return;
  var src=assetSrc(box.dataset.lottieAsset); if(!src) return;
  try{ window.lottie.loadAnimation({container:box, renderer:"svg",
    loop:box.dataset.loop==="1", autoplay:box.dataset.autoplay==="1", path:src}); _lottieInit[s.id]=true; }catch(e){} }

function persist(){
  // S5 — kompakt v2 kodlama (scorm.js). Faz 4-ek: sınır yerine ÇALIŞMA BÜTÇESİ (1.2'de 3500
  // BAYT; kalan pay LMS kaçışlama ek yüküne rezerv) ve kırpma MERDİVENİ: pozisyon (z: ekran+
  // düğüm+içerik sürümü) asla düşmez; hedef/skor > cevaplar > serbest metin > history sırasıyla
  // korunur. Ölçüm UTF-8 bayttır (Türkçe çok-bayt tuzağı — .length değil byteLen).
  var lim=RT.suspendBudget?RT.suspendBudget(S2004):(RT.suspendLimit?RT.suspendLimit(S2004):(S2004?64000:4096));
  var json, fit=null;
  if(RT.encodeSuspendFit){
    var _cs=byId[state.cursorId];
    fit=RT.encodeSuspendFit(state,order,lim,{node:(_cs&&_cs.node_id!=null)?_cs.node_id:null,
      cv:COURSE.content_version,objIds:OBJ_IDS,objMap:OBJ_MAP});
    json=fit.data;
  }
  else { json=JSON.stringify(state);   // beklenmedik: bundle yok → eski davranış
    if(json.length>4000 && !S2004){ json=JSON.stringify({visited:state.visited,results:state.results,
      history:[],cursorId:state.cursorId,reachedEnd:state.reachedEnd}); } }
  var wok=sSetChecked("cmi.suspend_data",json); sCommit();
  // 2.2c — yazma hatası/kırpma SESSİZ kalmasın: konsol + (varsa) xAPI izi; asla throw yok.
  if(RT.suspendWriteIssues){
    var probs=RT.suspendWriteIssues({ok:wok,size:RT.byteLen?RT.byteLen(json):json.length,limit:lim,
      truncated:!!(fit&&fit.truncated),rung:fit?fit.rung:0});
    for(var pi=0;pi<probs.length;pi++) suspendTrouble(probs[pi]);
  }
}
var _suspendWarned={};
// Faz 4-ek kayıt sözleşmesi: kayıp/hata izi xAPI'ye BAĞIMLI DEĞİLDİR — console.warn HER ZAMAN
// (boyut+bütçe+basamak ile); xAPI suspend.trouble YALNIZ LRS konfigürasyonu varsa EK OLARAK
// (2.2c yolu). SCORM'un öğrenciye görünmeyen ucuz bir LMS hata kanalı YOKTUR (cmi.comments
// öğrenen yorumudur, durum alanları hata taşıyamaz) → konsol+xAPI ile sınırlı (belgeli karar).
// Öğrenciye teknik hata ASLA gösterilmez; yazar tarafı uyarı derleme-zamanı projeksiyondadır
// (antislop taşma WARN'ı — grep etiketi outline runtime'ında).
function suspendTrouble(p){
  if(_suspendWarned[p.kind]) return; _suspendWarned[p.kind]=true;   // olay başına TEK uyarı (spam yok)
  try{ console.warn("[scorm] suspend_data "+p.kind+": "+p.size+" bytes (budget "+p.limit+
    (p.rung?", rung "+p.rung:"")+") - progress data may be incomplete"); }catch(e){}
  try{ if(typeof XAPI!=="undefined"&&XAPI&&XAPI.emit) XAPI.emit("suspend.trouble",{kind:p.kind,size:p.size,limit:p.limit,rung:p.rung||0}); }catch(e){}
}

// ---- skor + tamamlanma ----
// Faz 4-ek: state.e = rung-3 kırpma/republish kurtarma TABANI (toplam kazanılmış puan anlık
// görüntüsü) — canlı toplam tabanın altına düşerse taban kazanır (skor geriye gitmez; öğrenen
// yeniden cevaplayıp geçerse canlı toplam devralır — çifte sayım yok, max alınır).
function earned(){ var e=0; for(var k in state.results){ e+=state.results[k].points||0; }
  if(state.e!=null && Number(state.e)>e) e=Number(state.e);
  return e; }
function scoreValue(){
  var tp=COURSE.total_points||0; var e=earned();
  if(tp<=0) return 0;
  return COURSE.tracking.score_scaling ? Math.round(e/tp*100) : e;
}
function quizPassed(){ return scoreValue() >= COURSE.tracking.passing_score; }
function viewedAll(){
  var need=order.length, seen=0;
  order.forEach(function(id){ if(state.visited[id]) seen++; });
  return seen>=need || !!state.reachedEnd;
}
function isComplete(){
  var rule=COURSE.tracking.completion_rule;
  if(rule==="passed_quiz") return quizPassed();
  if(rule==="viewed_all_and_passed") return viewedAll() && quizPassed();
  return viewedAll();
}
function writeScore(){
  var sc=scoreValue();
  if(S2004){ sSet("cmi.score.raw",sc); sSet("cmi.score.scaled",(sc/100).toFixed(4)); }
  else { sSet("cmi.core.score.raw",sc); }
}
// ---- S2: cmi.objectives.* (hedef başına skor; 1.2↔2004 farkları scorm.js'te) ----
// POLİTİKA: yalnız ≥1 puanlı ekrana bağlı hedefler yazılır (aggregateObjectives filtreler).
var OBJ_IDS=COURSE.objectives||[];
var OBJ_MAP={};
COURSE.screens.forEach(function(s){ if(s.objective_ids&&s.objective_ids.length) OBJ_MAP[s.id]=s.objective_ids; });
var _objIdx=null;   // hedef id → cmi.objectives indeksi (oturum boyunca sabit — deterministik)
function writeObjectives(){
  if(!OBJ_IDS.length||!RT.aggregateObjectives||!RT.objectiveElements||!RT.objectiveIndices) return;
  var aggs=RT.aggregateObjectives(OBJ_IDS,OBJ_MAP,state.results);
  // Faz 4-ek: rung-3/republish tabanı — canlı cevap olmayan hedefte g anlık görüntüsü yazılır
  // (kısmi resume LMS'e SIFIR hedef skoru bastırmasın); canlı cevap gelen hedefte canlı kazanır.
  if(state.g&&RT.mergeObjectiveSnapshot) aggs=RT.mergeObjectiveSnapshot(aggs,OBJ_IDS,state.g);
  if(!aggs.length) return;
  if(_objIdx==null){
    // LMS'te önceden var olan kayıtlar (2004'te manifest imsss:objective pre-populate edebilir)
    // id'ye göre çözülür: mevcut id kendi indeksini korur (.id yeniden YAZILMAZ), yeniler sona.
    var n=parseInt(sGet("cmi.objectives._count"),10)||0, ex=[], i;
    for(i=0;i<n;i++) ex.push(sGet("cmi.objectives."+i+".id"));
    var ids=[]; for(i=0;i<aggs.length;i++) ids.push(aggs[i].id);
    _objIdx={map:RT.objectiveIndices(ex,ids),existing:{}};
    for(i=0;i<ex.length;i++) _objIdx.existing[ex[i]]=true;
  }
  var pr=(COURSE.tracking.passing_score||0)/100;
  for(var k=0;k<aggs.length;k++){
    var a=aggs[k];
    var kv=RT.objectiveElements(a,_objIdx.map[a.id],S2004,pr,!_objIdx.existing[a.id]);
    for(var m=0;m<kv.length;m++) sSet(kv[m][0],kv[m][1]);
  }
}
function evaluate(){
  writeScore();
  writeObjectives();   // S2 — skor commit'iyle AYNI yaşam döngüsü noktası
  var complete=isComplete();
  if(S2004){
    sSet("cmi.completion_status",complete?"completed":"incomplete");
    if(COURSE.total_points>0) sSet("cmi.success_status",quizPassed()?"passed":"failed");
  } else {
    var status;
    if(COURSE.total_points>0 && (COURSE.tracking.completion_rule!=="viewed_all")){
      status = complete ? (quizPassed()?"passed":"failed") : "incomplete";
    } else {
      status = complete ? "completed" : "incomplete";
    }
    sSet("cmi.core.lesson_status",status);
  }
  writeSessionTime();  // S3
  // S4 — exit'i HER değerlendirmede yaz: beforeunload mobilde/bfcache'te kaçırılabilir; boş exit
  // 1.2'de "normal çıkış" demektir ve LMS suspend_data'yı atmakta serbesttir.
  sSet(S2004?"cmi.exit":"cmi.core.exit", RT.exitValue?RT.exitValue(complete):(complete?"normal":"suspend"));
  persist();
}

// ---- gezinme ----
var cursor=0;
function indexOfId(id){ return order.indexOf(id); }
function curScreen(){ return byId[order[cursor]]; }
function updateVideos(activeId){
  sections.forEach(function(el){
    var active = el.dataset.screenId===activeId;
    var v = el.querySelector("video");
    if(v){
      if(active){
        v.currentTime = 0;
        /* portrait/landscape detection — video boyutları gelince class ekle */
        var detectOrientation = function(){
          if(v.videoWidth && v.videoHeight){
            if(v.videoHeight > v.videoWidth){ v.classList.add("portrait"); v.setAttribute("data-portrait",""); }
            else { v.classList.remove("portrait"); v.removeAttribute("data-portrait"); }
          }
        };
        if(v.videoWidth){ detectOrientation(); }
        else { v.addEventListener("loadedmetadata", function hm(){ v.removeEventListener("loadedmetadata",hm); detectOrientation(); }); }
        var doPlay = function(){
          v.play().catch(function(){
            v.muted = true;
            v.play().catch(function(){});
          });
        };
        /* readyState>=2 → yeterli veri yüklendi */
        if(v.readyState >= 2){
          doPlay();
        } else {
          v.addEventListener("canplay", function h(){ v.removeEventListener("canplay",h); doPlay(); });
          /* kaynak henüz atanmamışsa load tetikle */
          var src = v.querySelector("source");
          if(src && src.src) v.load();
        }
      } else {
        try{v.pause(); v.currentTime=0;}catch(e){}
      }
    }
  });
}
function showAt(idx,push){
  if(idx<0||idx>=order.length) return;
  if(push && order[cursor]) state.history.push(order[cursor]);
  cursor=idx;
  var id=order[cursor];
  updateVideos(id);
  sections.forEach(function(el){ el.setAttribute("aria-hidden", el.dataset.screenId===id?"false":"true"); });
  state.visited[id]=true;
  state.cursorId=id;
  if(_shownAt[id]==null) _shownAt[id]=Date.now();  // S1 — latency başlangıcı (ilk gösterim)
  var _sc=byId[id]; if(_sc&&_sc.on_enter) applyActions(_sc.on_enter);  // Faz 5
  interpolateScreen(secById[id]);
  resolveExplorationRefs(secById[id]);  // F2 — saklanan keşif girdilerini geri oynat
  startTimer(_sc); updateHud();  // Faz 6 + Faz 15 (G1)
  if(_sc&&_sc.type==="lottie") initLottie(secById[id],_sc);  // Faz 7
  if(cursor===order.length-1) state.reachedEnd=true;
  applyAnsweredState(secById[id], byId[id]);
  updateChrome();
  renderSummaryIfNeeded(secById[id], byId[id]);
  renderResultsIfNeeded(secById[id], byId[id]);
  evaluate();
  onScreenEnter(secById[id], byId[id]);   // Faz 9 — timeline reveal + player
  fitStage();
  document.getElementById("stage").scrollTop=0;
  if(secById[id]) secById[id].scrollTop=0;
  focusActive(id);
}
function focusActive(id){
  if(!window.__navReady) return;  // ilk render'da focus çalma
  var fi=secById[id] && secById[id].querySelector(".screen-inner");
  if(fi){ fi.setAttribute("tabindex","-1"); fi.focus({preventScroll:true}); }
}
function goId(id,push){ var i=indexOfId(id); if(i>=0) showAt(i,push); }
function next(){ var s=curScreen(); if(s.type==="branching") return;
  var i=cursor+1; while(i<order.length && !isVisible(order[i])) i++;  // Faz 5: koşullu atla
  if(i<order.length) showAt(i,true); }
function prev(){ if(state.history.length){ var id=state.history.pop(); var i=indexOfId(id); if(i>=0){cursor=i;
  state.cursorId=id;
  updateVideos(id);
  sections.forEach(function(el){ el.setAttribute("aria-hidden", el.dataset.screenId===id?"false":"true"); });
  resolveExplorationRefs(secById[id]);  // F2 — geri dönüşte de referanslar taze
  applyAnsweredState(secById[id], byId[id]); updateChrome(); persist(); focusActive(id); return; } } showAt(cursor-1,false); }

function updateChrome(){
  var pct=Math.round((Object.keys(state.visited).length/order.length)*100);
  document.querySelector(".progress-bar").style.width=pct+"%";
  var prog=document.querySelector(".progress"); if(prog) prog.setAttribute("aria-valuenow",pct);
  document.querySelector(".status-pill").textContent=(cursor+1)+" / "+order.length;
  var s=curScreen();
  document.getElementById("btnPrev").disabled=(cursor===0 && state.history.length===0);
  var nextBtn=document.getElementById("btnNext");
  nextBtn.disabled=(s.type==="branching")||(cursor>=order.length-1);
  nextBtn.style.visibility=(cursor>=order.length-1)?"hidden":"visible";
  buildDots();
}
function buildDots(){
  var dots=document.getElementById("dots"); dots.innerHTML="";
  order.forEach(function(id,i){ var d=document.createElement("span"); d.className="dot"+
    (state.visited[id]?" visited":"")+(i===cursor?" current":""); dots.appendChild(d); });
}

// ---- summary ----
function renderSummaryIfNeeded(el,s){
  if(!s||s.type!=="summary") return;
  var sc=el.querySelector(".summary-score"); if(sc){ sc.textContent="%"+scoreValue(); }
  var cp=el.querySelector(".summary-completion");
  if(cp){ var passed=quizPassed(); var hasQuiz=COURSE.total_points>0;
    cp.textContent=hasQuiz?(passed?T("summary_passed"):T("summary_failed"))
      :(isComplete()?T("summary_completed"):T("summary_in_progress"));
    cp.className="summary-completion "+(hasQuiz?(passed?"passed":"failed"):""); }
}

// Faz 14 — özelleştirilmiş sonuç: bölüm bazlı skoru gösterim-zamanında öğrencinin cevaplarından hesapla
function renderResultsIfNeeded(el,s){
  if(!s||s.type!=="results_breakdown") return;
  var root=el.querySelector(".results-breakdown"); if(!root) return;
  var weak=parseInt(root.dataset.weak,10)||60;
  var gTot=0, gMax=0;
  root.querySelectorAll(".rb-section").forEach(function(sec){
    var ids=(sec.dataset.screens||"").split(",").filter(Boolean);
    var pts=0, mx=0;
    ids.forEach(function(id){ var r=state.results[id]; if(r){ pts+=r.points||0; mx+=r.max||0; } });
    var pct=mx>0?Math.round(pts/mx*100):0; gTot+=pts; gMax+=mx;
    var fill=sec.querySelector(".rb-fill"), pctEl=sec.querySelector(".rb-pct");
    if(fill) fill.style.width=pct+"%";
    if(pctEl) pctEl.textContent="%"+pct;
    sec.classList.add(pct>=weak?"rb-ok":"rb-weak");
    var adv=sec.querySelector(".rb-advice"); if(adv && pct<weak) adv.hidden=false;
  });
  var tot=root.querySelector(".rb-total");
  if(tot && tot.dataset.showTotal){ var gp=gMax>0?Math.round(gTot/gMax*100):0;
    tot.hidden=false; tot.innerHTML=T("results_total",{pct:gp}); }
}

// ---- quiz: interaksiyon ----
function recordResult(id,pts,maxpts,ok){ state.results[id]={points:pts,max:maxpts,ok:!!ok,answered:true}; }

// ---- S1: cmi.interactions.* ----
// Ekran → sabit etkileşim indeksi. suspend_data'da taşınır: aynı soru tekrar cevaplanırsa AYNI
// indekse yazılır (LMS'te kopya satır oluşmaz), yeni sorular sıradaki indeksi alır.
if(!state.ix) state.ix={};
if(state.inext==null) state.inext=0;
var _shownAt={};   // ekran id → gösterim zamanı (latency; kalıcı DEĞİL — suspend_data bütçesi)
function _ixOf(id){ var n=state.ix[id]; if(n==null){ n=state.inext++; state.ix[id]=n; } return n; }
// resp/corr verilmezse (bileşik ekranlar) yalnız result/latency yazılır — yanlış cevap uydurulmaz.
function recordInteraction(s,ok,resp,corr,idOverride,typeOverride){
  if(!RT.interactionElements||!s) return;
  try{
    var iid=idOverride||s.id;
    var rec={ id:iid, screenType:typeOverride||s.type, ok:ok, time:Date.now(),
              description:s.title||"", response:(resp==null?"":resp) };
    if(corr!=null) rec.correct=corr;
    if(s.points!=null) rec.weighting=s.points;
    var t0=(_shownAt[iid]!=null)?_shownAt[iid]:_shownAt[s.id];   // varsa öğe-bazlı, yoksa ekran-bazlı
    if(t0!=null) rec.latencyMs=Date.now()-t0;
    var kv=RT.interactionElements(rec,_ixOf(iid),S2004);
    for(var i=0;i<kv.length;i++){ sSet(kv[i][0],kv[i][1]); }
  }catch(e){}
}

// resume: cevaplanmış quiz'i (suspend_data'dan) işaretle — kullanıcı kaldığı yerden cevabı/skoruyla görür
function applyAnsweredState(el,s){
  if(!el||!s||!s.is_quiz) return;
  var r=state.results[s.id]; if(!r||!r.answered) return;
  var btn=el.querySelector(".btn-check"); if(btn) btn.disabled=true;
  el.querySelectorAll(".opt").forEach(function(o){ o.disabled=true; });
  el.querySelectorAll("input[data-blank]").forEach(function(i){ i.disabled=true; });
  el.querySelectorAll(".drag-item").forEach(function(i){ i.setAttribute("draggable","false"); });
  var fb=el.querySelector(".feedback");
  if(fb && s.feedback){ fb.innerHTML=(r.ok?s.feedback.correct:s.feedback.incorrect);
    fb.className="feedback show "+(r.ok?"ok":"no"); }
}

// W5b — xAPI/cmi5 telemetri forwarder: launch'tan LRS bul (cmi5/explicit), ifadeleri EN-İYİ-ÇABA POST et.
// Saf ifade/ayrıştırma mantığı window.SCORMGame'de (vitest); burada YALNIZ DOM/ağ köprüsü (defansif —
// başarısızlık SCORM izlemeyi ASLA bozmaz). Kapalıysa/LRS yoksa sessiz no-op (graceful degrade).
var XAPI=(function(){
  var cfg=(window.__COURSE__&&window.__COURSE__.xapi)||null;
  var enabled=!!(cfg&&cfg.enabled&&window.SCORMGame&&window.SCORMGame.fromEngineEvent);
  var lrs=null, auth=null, actor=null, ready=false, queue=[];
  var base=(cfg&&cfg.activity_base)||"https://edumints.com/xapi/activity";
  function ctx(){ return { actor:actor, activityBase:base, timestamp:new Date().toISOString() }; }
  function post(st){ try{
    var xhr=new XMLHttpRequest(); xhr.open("POST", lrs.replace(/\/$/,"")+"/statements", true);
    xhr.setRequestHeader("Content-Type","application/json");
    xhr.setRequestHeader("X-Experience-API-Version","1.0.3");
    if(auth) xhr.setRequestHeader("Authorization", auth);
    xhr.send(JSON.stringify(st));
  }catch(e){} }
  function flush(){ if(!ready||!lrs) return; while(queue.length) post(queue.shift()); }
  function init(){ if(!enabled) return;
    var lp=window.SCORMGame.parseLaunch(location.search||"");
    lrs=(cfg.mode==="explicit"&&cfg.endpoint)?cfg.endpoint:(lp.endpoint||cfg.endpoint||null);
    actor=lp.actor||window.SCORMGame.normalizeActor(null);
    if(lp.activityId) base=lp.activityId;
    if(lp.auth){ auth=lp.auth; ready=true; return flush(); }
    if(lp.fetch){ try{ var x=new XMLHttpRequest(); x.open("POST",lp.fetch,true);   // cmi5: auth-token al
      x.onreadystatechange=function(){ if(x.readyState===4){ try{ var d=JSON.parse(x.responseText);
        if(d&&d["auth-token"]) auth="Basic "+d["auth-token"]; }catch(e){} ready=true; flush(); } };
      x.send(""); }catch(e){ ready=true; } return; }
    ready=true; flush(); // LRS varsa (auth'suz) gönder; yoksa emit sessizce yutar
  }
  function emit(event,payload){ if(!enabled||!lrs) return;   // LRS yok → hiç ifade üretme (degrade)
    try{ var st=window.SCORMGame.fromEngineEvent(event,payload||{},ctx());
      if(ready) post(st); else queue.push(st); }catch(e){} }
  init();
  return { emit:emit, enabled:enabled };
})();

sections.forEach(function(el){
  var s=byId[el.dataset.screenId]; if(!s) return;
  var t=s.type;
  if(t==="mcq"||t==="true_false"){ bindChoice(el,s); }
  else if(t==="fill_blank"){ bindCheck(el,s,function(){ return checkFill(el,s); }); }
  else if(t==="drag_drop"){ bindDrag(el,s); }
  else if(t==="hotspot"){ bindHotspot(el,s); }
  else if(t==="branching"){ bindBranch(el,s); }
  else if(t==="video"){ bindVideo(el,s); }
  else if(t==="tabs"){ bindTabs(el); }
  else if(t==="flashcards"){ bindFlashcards(el); }
  else if(t==="matching"){ bindCheck(el,s,function(){ return checkMatching(el); }); }
  else if(t==="sorting"){ bindSorting(el,s); }
  else if(t==="simulation"){ bindSimulation(el,s); }
  else if(t==="decision_scenario"){ bindScenario(el,s); }
  else if(t==="term_match_race"){ bindTermRace(el,s); }
  else if(t==="escape_room"){ bindEscape(el,s); }
  else if(t==="labeled_diagram"){ bindLabeledDiagram(el,s); }
  else if(t==="poll"){ bindPoll(el); }
  else if(t==="worked_example"){ bindWorkedExample(el); }
  else if(t==="exploration"){ bindExploration(el); }
  else if(t==="image_compare"){ bindImageCompare(el); }
  else if(t==="game"){ bindGame(el,s); }
  else if(t==="adaptive_practice"){ bindAdaptive(el,s); }
});

function bindChoice(el,s){
  var multi=s.multi; var opts=el.querySelectorAll(".opt");
  opts.forEach(function(b){ b.addEventListener("click",function(){
    if(multi){ b.classList.toggle("selected"); }
    else { opts.forEach(function(o){o.classList.remove("selected");}); b.classList.add("selected"); }
  }); });
  bindCheck(el,s,function(){ return checkChoice(el,s); });
}
function checkChoice(el,s){
  var sel=[]; el.querySelectorAll(".opt.selected").forEach(function(o){ sel.push(o.dataset.opt); });
  var correct = s.type==="true_false" ? [String(s.correct)] : s.correct;
  var ok = sel.length===correct.length && sel.every(function(x){return correct.indexOf(x)>=0;});
    el.querySelectorAll(".opt").forEach(function(o){
      var isC=correct.indexOf(o.dataset.opt)>=0; o.disabled=true;
      if(isC && s.feedback.show_correct) o.classList.add("correct");
      if(o.classList.contains("selected")&&!isC) o.classList.add("wrong");
      // Seçime özel gerekçe (feedback_html) — seçilen şıkkın altında göster (scen-conseq deseni)
      if(o.classList.contains("selected")){
        var ofb=o.parentNode&&o.parentNode.querySelector(".opt-fb"); if(ofb) ofb.hidden=false;
      }
    });
  // true_false → tek boolean; mcq → seçilen şık id'leri (S1 çeldirici analizi bunu kullanır)
  if(s.type==="true_false"){
    return {ok:ok, response:sel.length?sel[0]:"", correct:correct.length?correct[0]:""};
  }
  return {ok:ok, response:sel, correct:correct};
}
function checkFill(el,s){
  var ok=true; var resp=[], corr=[];
  el.querySelectorAll("input[data-blank]").forEach(function(inp){
    var acc=s.blanks[inp.dataset.blank]||[]; var val=inp.value.trim();
    var v=s.case_sensitive?val:val.toLowerCase();
    var hit=acc.some(function(a){ return (s.case_sensitive?a:a.toLowerCase())===v; });
    inp.disabled=true; inp.parentNode.classList.add(hit?"correct":"wrong"); if(!hit) ok=false;
    resp.push(val); corr.push(acc.length?acc[0]:"");
  });
  return {ok:ok, response:resp, correct:corr};
}
function bindDrag(el,s){
  var dragging=null;
  el.querySelectorAll(".drag-item").forEach(function(it){
    it.addEventListener("dragstart",function(){ dragging=it; it.classList.add("dragging"); });
    it.addEventListener("dragend",function(){ it.classList.remove("dragging"); dragging=null; });
    // Faz 16 — dokunma desteği (HTML5 drag dokunmada tetiklenmez): touch ile sürükle-bırak
    it.addEventListener("touchstart",function(){ it.classList.add("dragging"); },{passive:true});
    it.addEventListener("touchmove",function(e){
      var p=e.touches[0]; if(!p) return;
      var over=document.elementFromPoint(p.clientX,p.clientY);
      el.querySelectorAll(".drop-target").forEach(function(z){ z.classList.toggle("over", !!(over&&z.contains(over))); });
      e.preventDefault();
    },{passive:false});
    it.addEventListener("touchend",function(e){
      var p=e.changedTouches&&e.changedTouches[0];
      var over=p?document.elementFromPoint(p.clientX,p.clientY):null;
      var dt=over&&over.closest&&over.closest(".drop-target");
      if(dt){ var z=dt.querySelector(".drop-zone"); if(z) z.appendChild(it); }
      el.querySelectorAll(".drop-target").forEach(function(z){ z.classList.remove("over"); });
      it.classList.remove("dragging");
    });
  });
  el.querySelectorAll(".drop-target").forEach(function(tg){
    var zone=tg.querySelector(".drop-zone");
    tg.addEventListener("dragover",function(e){ e.preventDefault(); tg.classList.add("over"); });
    tg.addEventListener("dragleave",function(){ tg.classList.remove("over"); });
    tg.addEventListener("drop",function(e){ e.preventDefault(); tg.classList.remove("over");
      if(dragging){ zone.appendChild(dragging); } });
  });
  bindCheck(el,s,function(){ return checkDrag(el,s); });
}
function checkDrag(el,s){
  var ok=true; var placed={};   // S1 — matching deseni: {itemId: targetId}
  el.querySelectorAll(".drop-target").forEach(function(tg){
    var tid=tg.dataset.target; var items=tg.querySelectorAll(".drag-item"); var good=true;
    items.forEach(function(it){ placed[it.dataset.item]=tid; });
    items.forEach(function(it){ if(s.correct[it.dataset.item]!==tid) good=false; });
    // hedefte olması gereken tüm item'lar burada mı?
    for(var item in s.correct){ if(s.correct[item]===tid){ var found=false;
      items.forEach(function(it){ if(it.dataset.item===item) found=true; }); if(!found) good=false; } }
    tg.classList.add(good?"correct":"wrong"); if(!good) ok=false;
  });
  el.querySelectorAll(".drag-item").forEach(function(it){ it.setAttribute("draggable","false"); });
  return {ok:ok, response:placed, correct:s.correct};
}
function bindHotspot(el,s){
  var img=el.querySelector(".hotspot-img"); var picked=null;
  function place(){
    var w=img.clientWidth, h=img.clientHeight; if(!w) return;
    el.querySelectorAll(".hotspot-region").forEach(function(r){
      var c=r.dataset.coords.split(",").map(Number); var sh=r.dataset.shape;
      if(sh==="rect"){ r.style.left=(c[0]/img.naturalWidth*w)+"px"; r.style.top=(c[1]/img.naturalHeight*h)+"px";
        r.style.width=(c[2]/img.naturalWidth*w)+"px"; r.style.height=(c[3]/img.naturalHeight*h)+"px"; }
      else if(sh==="circle"){ var d=c[2]*2/img.naturalWidth*w;
        r.style.left=((c[0]-c[2])/img.naturalWidth*w)+"px"; r.style.top=((c[1]-c[2])/img.naturalHeight*h)+"px";
        r.style.width=d+"px"; r.style.height=d+"px"; r.style.borderRadius="50%"; }
    });
  }
  if(img.complete) place(); img.addEventListener("load",place); window.addEventListener("resize",place);
  el.querySelectorAll(".hotspot-region").forEach(function(r){
    r.addEventListener("click",function(){ el.querySelectorAll(".hotspot-region").forEach(function(x){x.classList.remove("selected");});
      r.classList.add("selected"); picked=r.dataset.region; });
  });
  bindCheck(el,s,function(){ var ok=s.correct.indexOf(picked)>=0;
    el.querySelectorAll(".hotspot-region").forEach(function(r){
      if(s.correct.indexOf(r.dataset.region)>=0) r.classList.add("correct");
      else if(r.dataset.region===picked) r.classList.add("wrong"); });
    return {ok:ok, response:picked?[picked]:[], correct:s.correct}; });
}
function bindCheck(el,s,checker){
  var btn=el.querySelector(".btn-check"); var fb=el.querySelector(".feedback");
  btn.addEventListener("click",function(){
    // checker: boolean VEYA {ok,response,correct} — ikincisi S1 için öğrenci cevabını da taşır.
    var r=checker(); var rich=(r&&typeof r==="object");
    var ok=rich?!!r.ok:!!r;
    btn.disabled=true;
    var pts=ok?s.points:0; recordResult(s.id,pts,s.points,ok);
    recordInteraction(s,ok,rich?r.response:null,rich?r.correct:null);
    applyActions(ok?s.on_correct:s.on_wrong);  // Faz 6 — quiz sonucu → değişken (puan vb.)
    fb.innerHTML=ok?s.feedback.correct:s.feedback.incorrect;
    fb.className="feedback show "+(ok?"ok":"no");
    // quiz çözülünce ileri açılır
    var nb=document.getElementById("btnNext"); if(cursor<order.length-1) nb.disabled=false;
    evaluate();
  });
}
function bindBranch(el,s){
  el.querySelectorAll(".branch-choice").forEach(function(b){
    b.addEventListener("click",function(){
      if(s.choice_vars && s.choice_vars[b.dataset.choice]) applyActions(s.choice_vars[b.dataset.choice]);  // Faz 5
      var goto=b.dataset.goto; if(goto&&byId[goto]) goId(goto,true);
      else if(cursor<order.length-1) showAt(cursor+1,true); });
  });
}
function bindVideo(el,s){
  if(!s.require_complete) return;
  var v=el.querySelector("video");
  v.addEventListener("ended",function(){ recordResult(s.id,0,0,true); });
}
// Faz 8 — rehberli çok-adımlı simülasyon (İzle→Uygula→Sıra Sizde'nin "Uygula"sı)
function bindSimulation(el,s){
  var sim=el.querySelector(".simulation"); if(!sim) return;
  var total=parseInt(sim.dataset.steps,10); var cur=0;
  var fb=el.querySelector(".feedback"); var prog=sim.querySelector(".sim-progress");
  function placeStep(step){ var img=step.querySelector(".hotspot-img");
    if(!img||!img.clientWidth||!img.naturalWidth) return; var w=img.clientWidth,h=img.clientHeight;
    step.querySelectorAll(".sim-region").forEach(function(r){ var c=r.dataset.coords.split(",").map(Number); var sh=r.dataset.shape;
      if(sh==="rect"){ r.style.left=(c[0]/img.naturalWidth*w)+"px"; r.style.top=(c[1]/img.naturalHeight*h)+"px";
        r.style.width=(c[2]/img.naturalWidth*w)+"px"; r.style.height=(c[3]/img.naturalHeight*h)+"px"; }
      else if(sh==="circle"){ var d=c[2]*2/img.naturalWidth*w;
        r.style.left=((c[0]-c[2])/img.naturalWidth*w)+"px"; r.style.top=((c[1]-c[2])/img.naturalHeight*h)+"px";
        r.style.width=d+"px"; r.style.height=d+"px"; r.style.borderRadius="50%"; } }); }
  function showStep(i){ sim.querySelectorAll(".sim-step").forEach(function(st){ st.hidden=st.dataset.step!=String(i); });
    if(prog) prog.textContent=(i+1)+" / "+total;
    var step=sim.querySelector('.sim-step[data-step="'+i+'"]'); if(!step) return;
    var img=step.querySelector(".hotspot-img");
    if(img && img.complete) placeStep(step); else if(img) img.addEventListener("load",function(){ placeStep(step); });
    step.querySelectorAll(".sim-region").forEach(function(r){ r.classList.add("pulse"); });
    var inp=step.querySelector(".sim-input"); if(inp) setTimeout(function(){ inp.focus(); },60); }
  window.addEventListener("resize",function(){ var st=sim.querySelector('.sim-step[data-step="'+cur+'"]'); if(st) placeStep(st); });
  function wrong(step){ var hint=step.querySelector(".sim-hint"); if(hint) hint.hidden=false; }
  function advance(step){ var hint=step.querySelector(".sim-hint"); if(hint) hint.hidden=true; cur++;
    if(cur>=total){ recordResult(s.id,s.points,s.points,true); recordInteraction(s,true,"steps:"+total,null); applyActions(s.on_correct);
      if(fb&&s.feedback){ fb.innerHTML=s.feedback.correct; fb.className="feedback show ok"; } evaluate();
    } else showStep(cur); }
  // TIKLAMA adımları
  sim.querySelectorAll(".sim-region").forEach(function(r){
    r.addEventListener("click",function(){ var step=r.closest(".sim-step"); if(parseInt(step.dataset.step,10)!==cur) return;
      if(r.dataset.correct==="1"){ advance(step); }
      else { wrong(step); r.classList.add("wrong"); setTimeout(function(){ r.classList.remove("wrong"); },600); } }); });
  // YAZMA adımları (Wooclap deseni)
  sim.querySelectorAll(".sim-step").forEach(function(step){
    var inp=step.querySelector(".sim-input"); var sub=step.querySelector(".sim-submit"); if(!inp||!sub) return;
    function check(){ if(parseInt(step.dataset.step,10)!==cur) return; var acc;
      try{ acc=JSON.parse(inp.dataset.accepted); }catch(e){ acc=[]; }
      var v=inp.value.trim().toLowerCase();
      if(acc.some(function(a){ return String(a).trim().toLowerCase()===v; })){ inp.disabled=true; sub.disabled=true; advance(step); }
      else { wrong(step); inp.classList.add("wrong"); setTimeout(function(){ inp.classList.remove("wrong"); },600); } }
    sub.addEventListener("click",check);
    inp.addEventListener("keydown",function(e){ if(e.key==="Enter"){ e.preventDefault(); check(); } }); });
  showStep(0);
}
// Faz 12 (G2) — dallanan karar senaryosu (durum/skor taşır, uç düğümde skorlanır)
function bindScenario(el,s){
  var root=el.querySelector(".scenario"); if(!root) return;
  var score=0, finished=false, path=[];   // path: S1 — öğrencinin izlediği karar yolu
  var hud=root.querySelector(".scen-score");
  var fb=el.querySelector(".feedback");
  var pass=(root.dataset.pass!==undefined&&root.dataset.pass!=="")?parseInt(root.dataset.pass,10):null;
  var points=parseInt(root.dataset.points,10)||0;
  function show(id){ root.querySelectorAll(".scen-node").forEach(function(n){ n.hidden=(n.dataset.node!==id); }); }
  function finalize(){ if(finished) return; finished=true;
    var ok = (pass!=null) ? (score>=pass) : (score>0);
    recordResult(s.id, ok?points:0, points, ok);
    recordInteraction(s, ok, path, null);
    applyActions(ok?s.on_correct:s.on_wrong);
    if(fb){ var msg=ok?(s.feedback&&s.feedback.correct||""):(s.feedback&&s.feedback.incorrect||"");
      fb.innerHTML=msg+' <b>'+T("scenario_result_score",{score:score})+'</b>'; fb.className="feedback show "+(ok?"ok":"no"); }
    var nb=document.getElementById("btnNext"); if(cursor<order.length-1) nb.disabled=false;
    evaluate();
  }
  root.querySelectorAll(".scen-node").forEach(function(node){
    var nextBtn=node.querySelector(".scen-next"); var goTo="";
    node.querySelectorAll(".scen-choice").forEach(function(b){
      b.addEventListener("click",function(){
        if(node.dataset.done) return; node.dataset.done="1";
        score+=parseInt(b.dataset.delta,10)||0; if(hud) hud.textContent=score;
        path.push(node.dataset.node);
        node.querySelectorAll(".scen-choice").forEach(function(x){ x.disabled=true; if(x!==b) x.classList.add("dim"); });
        b.classList.add("chosen");
        var cf=b.parentNode.querySelector(".scen-conseq"); if(cf) cf.hidden=false;
        goTo=b.dataset.goto||"";
        if(nextBtn) nextBtn.hidden=false;
      });
    });
    if(nextBtn) nextBtn.addEventListener("click",function(){
      if(goTo && root.querySelector('.scen-node[data-node="'+goTo+'"]')){ show(goTo); }
      else { finalize(); }
    });
  });
  show(root.dataset.start);
}
// Faz 13 (G3) — süreli terim↔tanım eşleştirme oyunu
function bindTermRace(el,s){
  var root=el.querySelector(".term-race"); if(!root) return;
  var total=root.querySelectorAll(".tmr-row").length, done=false;
  var left=parseInt(root.dataset.time,10)||60;
  var tEl=root.querySelector(".tmr-timer"), scEl=root.querySelector(".tmr-score");
  var fb=el.querySelector(".feedback"), finish=root.querySelector(".tmr-finish");
  // tanım <option>'larını her select içinde karıştır (sıra ipucu vermesin)
  root.querySelectorAll(".tmr-select").forEach(function(sel){
    var opts=Array.prototype.slice.call(sel.querySelectorAll("option")).slice(1);
    for(var i=opts.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); sel.appendChild(opts[j]); opts.splice(j,1); }
  });
  function correctCount(){ var c=0; root.querySelectorAll(".tmr-row").forEach(function(r){
    if(r.querySelector(".tmr-select").value===r.dataset.pair) c++; }); return c; }
  function update(){ if(scEl) scEl.textContent=correctCount()+" / "+total; }
  root.querySelectorAll(".tmr-select").forEach(function(sel){ sel.addEventListener("change",update); });
  function grade(){ if(done) return; done=true; if(_tmrTimer) clearInterval(_tmrTimer);
    var c=correctCount(); var bonus=(c===total)?Math.round(left/5):0;
    var earned=Math.min(s.points, Math.round(s.points*c/total)+bonus); var ok=c===total;
    var resp={}, corr={};   // S1 — matching deseni
    root.querySelectorAll(".tmr-row").forEach(function(r,i){ var sel=r.querySelector(".tmr-select"); sel.disabled=true;
      r.classList.add(sel.value===r.dataset.pair?"correct":"wrong");
      var key=r.dataset.row||String(i); resp[key]=sel.value; corr[key]=r.dataset.pair; });
    finish.disabled=true; recordResult(s.id, earned, s.points, ok);
    recordInteraction(s, ok, resp, corr);
    applyActions(ok?s.on_correct:s.on_wrong);
    if(fb){ var m=ok?(s.feedback.correct||""):(s.feedback.incorrect||"");
      fb.innerHTML=m+" <b>"+T("term_race_result",{correct:c,total:total})+(bonus?T("term_race_bonus",{bonus:bonus}):"")+"</b>"; fb.className="feedback show "+(ok?"ok":"no"); }
    var nb=document.getElementById("btnNext"); if(cursor<order.length-1) nb.disabled=false; evaluate(); }
  finish.addEventListener("click",grade);
  var _tmrTimer=setInterval(function(){ if(state.cursorId!==s.id){ clearInterval(_tmrTimer); return; }
    left--; if(tEl){ tEl.textContent="⏱ "+Math.max(0,left); if(left<=10) tEl.classList.add("urgent"); }
    if(left<=0){ clearInterval(_tmrTimer); grade(); } },1000);
}
// Faz 13 (G3) — kilitli bulmaca zinciri (escape room)
function bindEscape(el,s){
  var root=el.querySelector(".escape"); if(!root) return;
  var total=parseInt(root.dataset.puzzles,10), lives=parseInt(root.dataset.lives,10), cur=0, done=false;
  var prog=root.querySelector(".esc-progress"), fb=el.querySelector(".feedback");
  var acc=s.accepted||[], cs=s.case_sensitive||[];
  function norm(v,i){ return cs[i]?String(v).trim():String(v).trim().toLowerCase(); }
  function loseLife(){ lives--; var hearts=root.querySelectorAll(".esc-life");
    if(hearts[lives]) hearts[lives].classList.add("lost");
    if(lives<=0){ finish(false); } }
  function finish(win){ if(done) return; done=true;
    var resp=[], corr=[];   // S1 — bulmaca başına girilen cevap / ilk kabul edilen cevap
    root.querySelectorAll(".esc-input").forEach(function(x,i){ resp.push(x.value); corr.push((acc[i]||[])[0]||""); });
    root.querySelectorAll(".esc-input,.esc-submit").forEach(function(x){ x.disabled=true; });
    recordResult(s.id, win?s.points:0, s.points, win);
    recordInteraction(s, win, resp, corr);
    applyActions(win?s.on_correct:s.on_wrong);
    if(fb){ fb.innerHTML=win?(s.feedback.correct||T("escape_win")):(s.feedback.incorrect||T("escape_lose"));
      fb.className="feedback show "+(win?"ok":"no"); }
    var nb=document.getElementById("btnNext"); if(cursor<order.length-1) nb.disabled=false; evaluate(); }
  function showPuzzle(i){ root.querySelectorAll(".esc-puzzle").forEach(function(p){ p.hidden=p.dataset.puzzle!=String(i); });
    if(prog) prog.textContent=(i+1)+" / "+total;
    var inp=root.querySelector('.esc-puzzle[data-puzzle="'+i+'"] .esc-input'); if(inp) setTimeout(function(){ inp.focus(); },60); }
  root.querySelectorAll(".esc-puzzle").forEach(function(pz){
    var i=parseInt(pz.dataset.puzzle,10); var inp=pz.querySelector(".esc-input"); var sub=pz.querySelector(".esc-submit");
    function check(){ if(done||i!==cur) return; var v=norm(inp.value,i);
      var hit=(acc[i]||[]).some(function(a){ return norm(a,i)===v; });
      if(hit){ pz.classList.add("solved"); cur++;
        if(cur>=total){ finish(true); } else showPuzzle(cur); }
      else { inp.classList.add("wrong"); setTimeout(function(){ inp.classList.remove("wrong"); },500);
        var hint=pz.querySelector(".esc-hint"); if(hint) hint.hidden=false; loseLife(); } }
    sub.addEventListener("click",check);
    inp.addEventListener("keydown",function(e){ if(e.key==="Enter"){ e.preventDefault(); check(); } });
  });
  showPuzzle(0);
}
// W3b — kompozisyonel oyun: engine bundle'dan (window.SCORMGame) primitifleri spec'ten kur,
// kuralları olay veriyoluna bağla, dallanan düğümleri DOM'da yürüt. Mantık tek-kaynak components/engine.
function bindGame(el,s){
  var root=el.querySelector(".game"); if(!root) return;
  var cfg=s.game, G=window.SCORMGame;
  var fb=el.querySelector(".feedback");
  if(!cfg||!G){ // motor bundle yoksa: içerik statik HTML'de görünür kalır (progresif geliştirme)
    if(fb){ fb.textContent=T("game_engine_failed"); } return; }
  var bus=G.createEventBus();
  var rng=G.createRng(G.seedFromString(cfg.seed||s.id||"game"));
  var m=cfg.mechanics||{}, mech={};
  if(m.score) mech.score=G.createScore(m.score,bus);
  if(m.lives) mech.lives=G.createLives(m.lives,bus);
  if(m.timer) mech.timer=G.createTimer(m.timer,bus);
  if(m.hints) mech.hints=G.createHintLadder(m.hints,bus);
  var ctx={bus:bus,vars:{},mechanics:mech,rng:rng};
  G.attachRules(cfg.rules||[],ctx);
  var logic=cfg.logic||{}, pass=cfg.pass_score, points=cfg.points||0, finished=false, clock=null;
  // HUD elemanları (gizli render edildi — mevcut mekaniğe göre aç)
  var scW=root.querySelector(".game-hud-score"), scB=scW&&scW.querySelector("b");
  var lvW=root.querySelector(".game-hud-lives"), lvB=lvW&&lvW.querySelector("b");
  var tmW=root.querySelector(".game-hud-timer"), tmB=tmW&&tmW.querySelector("b");
  var hintBtn=root.querySelector(".game-hint"), hintsBox=root.querySelector(".game-hints");
  var extBtn=root.querySelector(".game-timer-extend"), offBtn=root.querySelector(".game-timer-off");
  function updHud(){
    if(mech.score){ scW.hidden=false; scB.textContent=mech.score.value; }
    if(mech.lives){ lvW.hidden=false; lvB.textContent=mech.lives.current; }
    if(mech.timer){ tmW.hidden=false; tmB.textContent=mech.timer.value; }
  }
  bus.on("score.changed",updHud); bus.on("lives.changed",updHud);
  bus.on("timer.tick",function(){ if(tmB&&mech.timer) tmB.textContent=mech.timer.value; });
  if(mech.hints){ hintBtn.hidden=false;
    bus.on("hint.revealed",function(h){ var d=document.createElement("div"); d.className="game-hint-text rich";
      d.textContent=h.text+(h.cost?(" (−"+h.cost+")"):""); hintsBox.appendChild(d); });
    hintBtn.addEventListener("click",function(){ if(finished) return; var hh=mech.hints.reveal();
      if(hh) XAPI.emit("hint.revealed",{index:hh.index,cost:hh.cost});                              // telemetri (W5b)
      if(!mech.hints.hasMore()) hintBtn.disabled=true; updHud(); });
  }
  if(mech.timer){ extBtn.hidden=false; offBtn.hidden=false;          // a11y WCAG 2.2.1: süre uzat/kapat
    extBtn.addEventListener("click",function(){ if(finished) return; mech.timer.extend(30); if(tmB) tmB.textContent=mech.timer.value; });
    offBtn.addEventListener("click",function(){ mech.timer.disable(); if(tmB) tmB.textContent="∞"; if(clock){ clearInterval(clock); clock=null; } });
    bus.on("timer.expired",function(){ if(clock){ clearInterval(clock); clock=null; } finalize(); });
    clock=setInterval(function(){ if(finished){ clearInterval(clock); return; } if(state.cursorId!==s.id) return; mech.timer.tick(1000); },1000);
  }
  if(mech.lives){ bus.on("lives.depleted",function(){ finalize(); }); }
  function condOk(c){ return G.evalCond?G.evalCond(c,ctx.vars):true; }
  function applyLocks(node){ node.querySelectorAll(".game-choice").forEach(function(b){
    var L=logic[b.dataset.node+"/"+b.dataset.choice];
    if(L&&L.cond){ var ok=condOk(L.cond); b.disabled=!ok; b.classList.toggle("locked",!ok); } }); }
  function show(id){ root.querySelectorAll(".game-node").forEach(function(n){ n.hidden=(n.dataset.node!==id); });
    var node=root.querySelector('.game-node[data-node="'+id+'"]'); if(node) applyLocks(node); }
  function finalize(){ if(finished) return; finished=true; if(clock){ clearInterval(clock); clock=null; }
    var sc=mech.score?mech.score.value:0; var ok;
    if(mech.lives&&mech.lives.depleted) ok=false;       // can bitti → kaybetti
    else if(pass!=null) ok=sc>=pass; else ok=sc>0;
    recordResult(s.id, ok?points:0, points, ok);
    recordInteraction(s, ok, "skor:"+sc, null);
    XAPI.emit("finalize",{ok:ok,score:sc,max:points});                                            // telemetri (W5b)
    applyActions(ok?s.on_correct:s.on_wrong);
    root.querySelectorAll(".game-choice,.game-hint,.game-next").forEach(function(x){ x.disabled=true; });
    if(fb){ var msg=ok?(s.feedback&&s.feedback.correct||""):(s.feedback&&s.feedback.incorrect||"");
      fb.innerHTML=msg+' <b>'+T("game_result_score",{score:sc})+'</b>'; fb.className="feedback show "+(ok?"ok":"no"); }
    var nb=document.getElementById("btnNext"); if(nb&&cursor<order.length-1) nb.disabled=false;
    evaluate();
  }
  root.querySelectorAll(".game-node").forEach(function(node){
    var nextBtn=node.querySelector(".game-next"), goTo="";
    node.querySelectorAll(".game-choice").forEach(function(b){
      b.addEventListener("click",function(){
        if(finished||node.dataset.done||b.disabled) return; node.dataset.done="1";
        var L=logic[b.dataset.node+"/"+b.dataset.choice]||{};
        (L.on||[]).forEach(function(a){ var fn=G.ACTIONS&&G.ACTIONS[a.do]; if(fn) fn(a,ctx); });  // seçime özel aksiyonlar
        ctx.vars._choice=b.dataset.choice;
        bus.emit("choice.taken",{node:node.dataset.node,choice:b.dataset.choice});                // global kurallar
        XAPI.emit("choice.taken",{node:node.dataset.node,choice:b.dataset.choice});                // telemetri (W5b)
        node.querySelectorAll(".game-choice").forEach(function(x){ x.disabled=true; if(x!==b) x.classList.add("dim"); });
        b.classList.add("chosen");
        var cf=b.parentNode.querySelector(".game-conseq"); if(cf) cf.hidden=false;
        goTo=(L.to||b.dataset.goto||"");
        updHud();
        if(finished) return;                            // can bitince depletion handler bitirdi
        if(nextBtn) nextBtn.hidden=false;
      });
    });
    if(nextBtn) nextBtn.addEventListener("click",function(){ if(finished) return;
      if(goTo && root.querySelector('.game-node[data-node="'+goTo+'"]')) show(goTo); else finalize(); });
  });
  updHud(); show(cfg.start);
}
// W4b — adaptif pratik: engine bundle'dan tahminciyi (Elo/BKT) kur; her cevaptan sonra observe edip
// sıradaki öğeyi seç — Elo: ZPD/akış (hedef başarıya en yakın zorluk), BKT: ustalık (kolaydan zora +
// erken-bitir). Mantık tek-kaynak components/engine/adaptive.js. SUNUCUDA LLM YOK; seed'li tie-break.
function bindAdaptive(el,s){
  var root=el.querySelector(".adaptive"); if(!root) return;
  var cfg=s.adaptive, G=window.SCORMGame, fb=el.querySelector(".feedback");
  if(!cfg||!G){ if(fb) fb.textContent=T("adaptive_engine_failed"); return; }
  var strategy=(cfg.adaptive&&cfg.adaptive.strategy)||"elo";
  var est=G.createEstimator(cfg.adaptive||{});
  var rng=G.createRng(G.seedFromString(cfg.seed||s.id||"adaptive"));
  var itemsCfg=cfg.items||{}, target=cfg.target_success||0.7;
  var pool=[]; root.querySelectorAll(".ap-item").forEach(function(node){
    pool.push({id:node.dataset.item, d:parseFloat(node.dataset.difficulty)||0, node:node, done:false}); });
  var cap=(cfg.max_items&&cfg.max_items>0)?Math.min(cfg.max_items,pool.length):pool.length;
  var answered=0, correctN=0, finished=false, current=null;
  var prog=root.querySelector(".ap-progress"), lvl=root.querySelector(".ap-level");
  function levelText(){ return strategy==="bkt" ? T("adaptive_mastery",{pct:Math.round(est.mastery*100)})
                                                : T("adaptive_ability",{value:est.ability.toFixed(2)}); }
  function updHud(){ if(prog) prog.textContent=answered+" / "+cap; if(lvl) lvl.textContent=levelText(); }
  function show(p){ current=p; pool.forEach(function(x){ x.node.hidden=(x!==p); });
    var o=p.node.querySelector(".opt"); if(o) setTimeout(function(){ o.focus(); },50); }
  function next(){
    if(finished) return;
    if(answered>=cap) return finalize();
    if(cfg.mastery_stop!=null && strategy==="bkt" && est.mastery>=cfg.mastery_stop) return finalize();
    var avail=pool.filter(function(p){ return !p.done; });
    if(!avail.length) return finalize();
    var pick;
    if(strategy==="bkt"){ avail.sort(function(a,b){ return a.d-b.d; }); pick=avail[0]; }   // ustalık: kolaydan zora
    else { pick=G.pickByTargetSuccess(function(p){ return est.pCorrect(p.d); }, avail, {target:target}, rng); } // akış: ZPD
    if(pick) _shownAt[s.id+"."+pick.id]=Date.now();   // S1 — öğe-bazlı latency başlangıcı
    show(pick);
  }
  function finalize(){ if(finished) return; finished=true;
    pool.forEach(function(x){ x.node.hidden=true; });
    var ratio=answered?correctN/answered:0, ok=ratio>=(cfg.pass_ratio||0.6);
    recordResult(s.id, ok?cfg.points:0, cfg.points, ok);
    XAPI.emit("finalize",{ok:ok,score:correctN,max:answered});                                    // telemetri (W5b)
    applyActions(ok?s.on_correct:s.on_wrong);
    if(fb){ var msg=ok?(s.feedback&&s.feedback.correct||""):(s.feedback&&s.feedback.incorrect||"");
      fb.innerHTML=msg+' <b>'+T("adaptive_result",{correct:correctN,answered:answered,level:levelText()})+'</b>';
      fb.className="feedback show "+(ok?"ok":"no"); }
    var nb=document.getElementById("btnNext"); if(nb&&cursor<order.length-1) nb.disabled=false; evaluate();
  }
  pool.forEach(function(p){
    var node=p.node, opts=node.querySelectorAll(".opt"), check=node.querySelector(".ap-check");
    opts.forEach(function(b){ b.addEventListener("click",function(){ if(p.done) return;
      opts.forEach(function(o){ o.classList.remove("selected"); }); b.classList.add("selected"); }); });
    check.addEventListener("click",function(){
      if(p.done||finished||p!==current) return;
      var sel=node.querySelector(".opt.selected"); if(!sel) return;
      p.done=true; check.disabled=true;
      var correct=(itemsCfg[p.id]&&itemsCfg[p.id].correct)||[];
      var ok=correct.indexOf(sel.dataset.opt)>=0;
      opts.forEach(function(o){ o.disabled=true;
        if(correct.indexOf(o.dataset.opt)>=0 && s.feedback && s.feedback.show_correct) o.classList.add("correct");
        if(o.classList.contains("selected")&&!ok) o.classList.add("wrong"); });
      // S1 — adaptif havuz SORU BAZINDA raporlanır: her öğe ayrı bir cmi.interactions kaydı.
      recordInteraction(s, ok, [sel.dataset.opt], correct, s.id+"."+p.id, "mcq");
      if(strategy==="bkt") est.observe(ok); else est.observe(p.d, ok);   // yeterliliği güncelle
      XAPI.emit("adaptive.observe", strategy==="bkt"                       // telemetri (W5b): ability VEYA mastery
        ? {itemId:p.id,correct:ok,mastery:est.mastery}
        : {itemId:p.id,correct:ok,ability:est.ability,difficulty:p.d});
      answered++; if(ok) correctN++;
      var ex=node.querySelector(".ap-explain"); if(ex) ex.hidden=false;
      updHud(); setTimeout(next,60);
    });
  });
  updHud(); next();
}
// Faz 13 — etiketli diyagram (görsel öğrenme; select == pin id ise doğru)
function bindLabeledDiagram(el,s){
  var ld=el.querySelector(".labeled-diagram"); if(!ld) return;
  // #126 — display (callout) modu: statik, etkileşimsiz. Select/check yok → hiç bağlama.
  if(ld.classList.contains("ld-display")) return;
  // pin <-> select karşılıklı vurgulama
  ld.querySelectorAll(".ld-select").forEach(function(sel){
    var id=sel.dataset.label; var pin=ld.querySelector('.ld-pin[data-label="'+id+'"]');
    function hl(on){ if(pin) pin.classList.toggle("active",on); }
    sel.addEventListener("focus",function(){ hl(true); }); sel.addEventListener("blur",function(){ hl(false); });
    if(pin) pin.addEventListener("click",function(){ sel.focus(); sel.scrollIntoView({block:"nearest"}); });
  });
  bindCheck(el,s,function(){ var ok=true; var resp={}, corr={};
    ld.querySelectorAll(".ld-select").forEach(function(sel){ var hit=sel.value===sel.dataset.label;
      sel.disabled=true; sel.closest(".ld-row").classList.add(hit?"correct":"wrong"); if(!hit) ok=false;
      resp[sel.dataset.label]=sel.value; corr[sel.dataset.label]=sel.dataset.label; });
    return {ok:ok, response:resp, correct:corr}; });
}
// Faz 14 — anket/yansıma (skorlanmaz; gönderince yansıma belirir)
function bindPoll(el){
  var poll=el.querySelector(".poll"); if(!poll) return;
  var btn=poll.querySelector(".poll-submit"), refl=poll.querySelector(".poll-reflection");
  btn.addEventListener("click",function(){
    var picked=poll.querySelector(".poll-opts input:checked");
    var txt=poll.querySelector(".poll-text");
    if(!picked && !(txt && txt.value.trim())){ var o=poll.querySelector(".poll-opts"); o.classList.add("poll-nudge");
      setTimeout(function(){ o.classList.remove("poll-nudge"); },600); return; }
    poll.querySelectorAll(".poll-opts input, .poll-text").forEach(function(i){ i.disabled=true; });
    btn.disabled=true; if(refl) refl.hidden=false;
  });
}
// F2 (#113) — keşif: girdi saklama + geri oynatma. Değer HER ZAMAN textContent olarak
// enjekte edilir (innerHTML ASLA — saklanan metin HTML olarak yorumlanamaz, XSS-güvenli).
// Boş değer i18n yer tutucusuna düşer ("henüz cevaplamadın"). Skora/LMS puanına yazım YOK.
function resolveExplorationRefs(root){ if(!root||!root.querySelectorAll) return;
  root.querySelectorAll("[data-exploration-ref]").forEach(function(n){
    var k=n.getAttribute("data-exploration-ref");
    var v=RT.getExploration?RT.getExploration(state,k):((state.xp&&state.xp[k])||"");
    n.textContent = v || T("xp_not_answered");
    n.classList.toggle("xp-ref-empty", !v);
  });
}
var _xpWarned={};
function bindExploration(el){
  var box=el.querySelector("[data-exploration]"); if(!box) return;
  var key=box.dataset.storeKey, min=parseInt(box.dataset.min||"0",10)||0;
  var saved=box.querySelector(".xp-saved");
  function cur(){ return RT.getExploration?RT.getExploration(state,key):((state.xp&&state.xp[key])||""); }
  function store(v,doPersist){
    var r; if(RT.setExploration){ r=RT.setExploration(state,key,v); }
    else { r={value:String(v==null?"":v).slice(0,500),truncated:false}; state.xp=state.xp||{}; state.xp[key]=r.value; }
    if(r.truncated && !_xpWarned[key]){ _xpWarned[key]=true;
      try{ console.warn("[exploration] '"+key+"' value truncated at 500 chars (suspend budget)"); }catch(e){} }
    // aynı ekrandaki VE önceden gösterilmiş ekranlardaki referanslar canlı güncellenir
    document.querySelectorAll('[data-exploration-ref="'+key+'"]').forEach(function(n){
      n.textContent = r.value || T("xp_not_answered"); n.classList.toggle("xp-ref-empty", !r.value); });
    if(saved) saved.hidden = !r.value || (min>0 && r.value.length<min);
    if(doPersist) persist();
  }
  var ta=box.querySelector(".xp-text");
  if(ta){
    var v0=cur(); if(v0){ ta.value=v0; if(saved) saved.hidden=(min>0 && v0.length<min); }
    ta.addEventListener("input",function(){ store(ta.value,false); });   // canlı state + referans
    ta.addEventListener("change",function(){ store(ta.value,true); });   // blur'da persist (commit spam'i yok)
  }
  box.querySelectorAll('.xp-opts input[type="radio"]').forEach(function(r){
    var lbl=r.closest("label");
    var txt=lbl?lbl.textContent.replace(/\s+/g," ").trim():r.value;   // saklanan = görünen etiket metni
    if(cur() && cur()===txt) r.checked=true;                          // resume: seçimi geri kur
    r.addEventListener("change",function(){ if(r.checked) store(txt,true); });
  });
}
// F1 (#112) — çözümlü örnek: fading reveal butonları (aria-expanded toggle; klavye = native buton).
// Skora/LMS'e HİÇBİR yazma yok — öz-açıklama alanı dahil (poll gibi skorsuz).
function bindWorkedExample(el){
  el.querySelectorAll(".we-reveal").forEach(function(b){
    b.addEventListener("click",function(){
      var t=document.getElementById(b.getAttribute("aria-controls")); if(!t) return;
      var open=b.getAttribute("aria-expanded")==="true";
      b.setAttribute("aria-expanded", open?"false":"true");
      t.hidden=open;
    });
  });
}
// Faz 14 — önce/sonra görsel karşılaştırma (sürüklenebilir slider)
function bindImageCompare(el){
  var ic=el.querySelector(".img-compare"); if(!ic) return;
  var range=ic.querySelector(".ic-range"), after=ic.querySelector(".ic-after-wrap"), div=ic.querySelector(".ic-divider");
  function set(v){ if(after) after.style.width=v+"%"; if(div) div.style.left=v+"%"; }
  range.addEventListener("input",function(){ set(range.value); });
  set(range.value);
}
function bindTabs(el){
  var tabs=Array.prototype.slice.call(el.querySelectorAll(".tab"));
  function select(idx){
    tabs.forEach(function(x,i){ x.setAttribute("aria-selected", i===idx?"true":"false"); });
    el.querySelectorAll(".tab-panel").forEach(function(p){ p.hidden = (p.dataset.panel!=String(idx)); });
  }
  tabs.forEach(function(tb,i){
    tb.addEventListener("click",function(){ select(i); });
    tb.addEventListener("keydown",function(e){  // ok tuşlarıyla gezinme (ARIA)
      var n=null; if(e.key==="ArrowRight") n=(i+1)%tabs.length;
      else if(e.key==="ArrowLeft") n=(i-1+tabs.length)%tabs.length;
      if(n!==null){ e.preventDefault(); select(n); tabs[n].focus(); }
    });
  });
}
function bindFlashcards(el){
  el.querySelectorAll(".flashcard").forEach(function(c){
    c.addEventListener("click",function(){ c.classList.toggle("flipped"); });
  });
}
function checkMatching(el){
  var ok=true; var resp={}, corr={};   // S1 — {satır: seçilen} / {satır: doğru}
  el.querySelectorAll(".match-row").forEach(function(row,i){
    var sel=row.querySelector(".match-select"); var hit=sel.value===row.dataset.pair;
    sel.disabled=true; row.classList.add(hit?"correct":"wrong"); if(!hit) ok=false;
    var key=row.dataset.row||String(i);
    resp[key]=sel.value; corr[key]=row.dataset.pair;
  });
  return {ok:ok, response:resp, correct:corr};
}
function bindSorting(el,s){
  var list=el.querySelector(".sorting");
  // Fisher-Yates karıştır (görev anlamlı olsun)
  var arr=Array.prototype.slice.call(list.children);
  for(var i=arr.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var tmp=arr[i];arr[i]=arr[j];arr[j]=tmp; }
  arr.forEach(function(li){ list.appendChild(li); });
  // up/down (klavye-erişilebilir)
  list.querySelectorAll(".sort-up").forEach(function(b){ b.addEventListener("click",function(){
    var li=b.closest(".sort-item"); if(li.previousElementSibling) list.insertBefore(li,li.previousElementSibling); }); });
  list.querySelectorAll(".sort-down").forEach(function(b){ b.addEventListener("click",function(){
    var li=b.closest(".sort-item"); if(li.nextElementSibling) list.insertBefore(li.nextElementSibling,li); }); });
  // drag
  var drag=null;
  list.querySelectorAll(".sort-item").forEach(function(it){
    it.addEventListener("dragstart",function(){ drag=it; it.classList.add("dragging"); });
    it.addEventListener("dragend",function(){ it.classList.remove("dragging"); drag=null; });
    it.addEventListener("dragover",function(e){ e.preventDefault(); if(!drag||drag===it) return;
      var r=it.getBoundingClientRect(); var after=(e.clientY-r.top)/r.height>0.5;
      list.insertBefore(drag, after?it.nextElementSibling:it); });
  });
  bindCheck(el,s,function(){ return checkSorting(el,s); });
}
function checkSorting(el,s){
  var cur=Array.prototype.slice.call(el.querySelectorAll(".sort-item")).map(function(li){return li.dataset.item;});
  var c=s.correct_order; var ok=cur.length===c.length && cur.every(function(x,i){return x===c[i];});
  el.querySelectorAll(".sort-item").forEach(function(li,i){ li.classList.add(cur[i]===c[i]?"correct":"wrong");
    li.setAttribute("draggable","false"); li.querySelectorAll("button").forEach(function(b){b.disabled=true;}); });
  return {ok:ok, response:cur, correct:c};
}

/* ===== Faz 9 — stage ölçekleme + player + timeline reveal ===== */
var STAR_SVG='<svg class="ic" viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
var CHECK_SVG='<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
function fitStage(){
  if(document.body.dataset.layout!=="stage") return;
  var sc=document.getElementById("stageScaler"), fr=document.getElementById("stageFrame"),
      st=document.getElementById("stage");
  if(!fr||!st||!sc) return;
  var W=(COURSE&&COURSE.stage_width)||960, H=(COURSE&&COURSE.stage_height)||540;
  var k=Math.min(st.clientWidth/W, st.clientHeight/H);
  if(!isFinite(k)||k<=0) k=1;
  /* Faz 16/17 — mobil breakpoint VEYA ölçek okunabilirlik eşiğinin altına düşerse
     (dar/kısa ekran, LMS iframe) sabit-tuvali BIRAK → CSS reflow devralır; inline temizle. */
  var mobileMQ=window.matchMedia && window.matchMedia("(max-width:640px)").matches;
  if(mobileMQ || k<0.85){
    document.body.dataset.fit="flow";
    fr.style.transform=""; fr.style.width=""; fr.style.height="";
    sc.style.width=""; sc.style.height=""; return;
  }
  document.body.dataset.fit="stage";
  /* frame sabit boyut — scale ile ölçeklenecek */
  fr.style.width=W+"px"; fr.style.height=H+"px";
  fr.style.transform="scale("+k+")";
  var scaledW=W*k, scaledH=H*k;
  sc.style.width=scaledW+"px"; sc.style.height=scaledH+"px";
}
window.addEventListener("resize",fitStage);
/* Faz 17 — döndürme + mobil tarayıcı çubuğu (visualViewport) değişiminde yeniden ölçekle */
window.addEventListener("orientationchange",function(){ setTimeout(fitStage,150); });
if(window.visualViewport){ window.visualViewport.addEventListener("resize",fitStage); }

function distributeCues(n,duration){
  if(n<=0) return [];
  var cues=[]; for(var i=0;i<n;i++) cues.push((i*duration)/(n+1)); return cues;
}
function fmtTime(s){ s=Math.max(0,s||0); var m=Math.floor(s/60), x=Math.floor(s%60);
  return m+":"+(x<10?"0":"")+x; }

var TL=null;  // aktif ekranın timeline durumu
function clearTL(){
  if(!TL) return;
  if(TL.audio){ try{TL.audio.pause();}catch(e){}
    TL.audio.ontimeupdate=TL.audio.onended=TL.audio.onloadedmetadata=null; }
  if(TL.timer){ clearInterval(TL.timer); TL.timer=0; }
  if(TL.clickH && TL.section){ TL.section.removeEventListener("click",TL.clickH); }
}
function ccOn(){ var b=document.getElementById("btnCc"); return b&&b.getAttribute("aria-pressed")==="true"; }
function updateCaptions(section,on){
  var bar=document.getElementById("ccBar"); if(!bar) return;
  var cap=section?section.querySelector(".cc-text"):null;
  if(on && cap){ bar.textContent=cap.textContent; bar.hidden=false; }
  else { bar.hidden=true; bar.textContent=""; }
}
function setSeekEnabled(on){
  var sk=document.getElementById("seekbar"); if(sk) sk.disabled=!on;
  var pb=document.getElementById("btnPlay"); if(pb) pb.disabled=!on;
}
function checkLock(){
  if(!TL||!TL.cfg) return;
  var nb=document.getElementById("btnNext");
  if(TL.cfg.lock_until_complete && !TL.done) nb.disabled=true;
  else updateChrome();
}
function startPaced(){
  if(!TL||!TL.paced) return;
  var seek=document.getElementById("seekbar"), plTime=document.getElementById("plTime");
  document.getElementById("btnPlay").classList.add("alt");
  TL.timer=setInterval(function(){
    TL.elapsed+=0.1; TL.showUpTo(TL.elapsed);
    seek.value=Math.round((TL.elapsed/TL.duration)*1000);
    plTime.textContent=fmtTime(TL.elapsed)+" / "+fmtTime(TL.duration);
    if(TL.elapsed>=TL.duration) stopPaced();
  },100);
}
function stopPaced(){ if(TL&&TL.timer){ clearInterval(TL.timer); TL.timer=0; }
  var p=document.getElementById("btnPlay"); if(p) p.classList.remove("alt"); }
function pacedSeek(t){ if(!TL) return; TL.elapsed=Math.max(0,Math.min(t,TL.duration));
  TL.showUpTo(TL.elapsed);
  document.getElementById("plTime").textContent=fmtTime(TL.elapsed)+" / "+fmtTime(TL.duration); }

function onScreenEnter(section, cfg){
  clearTL();
  var play=document.getElementById("btnPlay"), seek=document.getElementById("seekbar"),
      plTime=document.getElementById("plTime"), mute=document.getElementById("btnMute");
  if(play) play.classList.remove("alt"); if(mute) mute.classList.remove("alt");
  var reveal=section?section.dataset.reveal:"none";
  var blocks=section?Array.prototype.slice.call(section.querySelectorAll(".tl-block")):[];
  blocks.forEach(function(b){ b.classList.remove("tl-in"); });
  TL={section:section, cfg:cfg, reveal:reveal, blocks:blocks, cues:[], audio:null,
      duration:0, timer:0, idx:0, elapsed:0, done:false, paced:false, clickH:null, showUpTo:null};
  updateCaptions(section, ccOn());
  if(reveal==="none" || blocks.length===0){
    blocks.forEach(function(b){ b.classList.add("tl-in"); });
    setSeekEnabled(false); if(seek) seek.value=0;
    if(plTime) plTime.textContent="0:00 / 0:00"; TL.done=true; return;
  }
  TL.showUpTo=function(t){
    var last=-1;
    for(var i=0;i<blocks.length;i++){
      if(TL.cues[i]<=t){ blocks[i].classList.add("tl-in"); last=i; }
      else blocks[i].classList.remove("tl-in");
    }
    if(last>=blocks.length-1 && !TL.done){ TL.done=true; checkLock(); }
  };
  var audio=section.querySelector("audio.narration");
  // audio.src veya data-asset kontrolü (asset çözülmüş olabilir)
  var hasAudio = audio && (audio.src || audio.dataset.asset || (audio.querySelector && audio.querySelector("source")));
  if(reveal==="auto" && hasAudio){
    TL.audio=audio; setSeekEnabled(true);
    TL.cues=distributeCues(blocks.length, blocks.length*2.5); TL.showUpTo(0);
    audio.onloadedmetadata=function(){
      TL.duration=audio.duration||(blocks.length*2.5);
      TL.cues=distributeCues(blocks.length, TL.duration); TL.showUpTo(audio.currentTime||0);
      plTime.textContent=fmtTime(audio.currentTime)+" / "+fmtTime(TL.duration);
    };
    audio.ontimeupdate=function(){
      if(!TL.cues.length) return;
      TL.showUpTo(audio.currentTime);
      seek.value=Math.round((audio.currentTime/(audio.duration||1))*1000);
      plTime.textContent=fmtTime(audio.currentTime)+" / "+fmtTime(audio.duration);
    };
    audio.onended=function(){ play.classList.remove("alt"); TL.done=true; checkLock(); };
    // Otomatik başlat — video varsa onu bekle, yoksa hemen
    try{
      audio.load();
      var autoStartAudio = function(){
        audio.play().then(function(){ play.classList.add("alt"); }).catch(function(err){
          console.log("Narration autoplay blocked, waiting for user click", err.message);
        });
      };
      /* ekranda video varsa → video hazır olunca sesi başlat */
      var screenVideo = section ? section.querySelector("video") : null;
      if(screenVideo){
        var startWhenVideoReady = function(){
          if(audio.readyState >= 2){ autoStartAudio(); }
          else { audio.addEventListener("canplay", function h(){ audio.removeEventListener("canplay",h); autoStartAudio(); }); }
        };
        if(screenVideo.readyState >= 2){ startWhenVideoReady(); }
        else { screenVideo.addEventListener("canplay", function hv(){ screenVideo.removeEventListener("canplay",hv); startWhenVideoReady(); }); }
      } else {
        /* video yoksa direkt ses başlat */
        if(audio.readyState >= 2){ autoStartAudio(); }
        else { audio.addEventListener("canplay", function h(){ audio.removeEventListener("canplay",h); autoStartAudio(); }); }
      }
    }catch(e){}
  } else if(reveal==="click"){
    setSeekEnabled(false);
    TL.cues=distributeCues(blocks.length, blocks.length); // sıra için yer tutucu
    blocks[0].classList.add("tl-in"); TL.idx=1;
    plTime.textContent=TL.idx+" / "+blocks.length;
    TL.clickH=function(ev){
      if(ev.target.closest("button,a,input,select,textarea,details,.tl-block .match-select")) return;
      if(TL.idx<blocks.length){ blocks[TL.idx].classList.add("tl-in"); TL.idx++;
        plTime.textContent=TL.idx+" / "+blocks.length;
        if(TL.idx>=blocks.length && !TL.done){ TL.done=true; checkLock(); } }
    };
    section.addEventListener("click", TL.clickH);
  } else {
    // paced auto (ses yok) — timeline kendiliğinden akar
    var bs=(cfg&&cfg.block_sec)||2.5;
    TL.paced=true; TL.duration=blocks.length*bs;
    TL.cues=distributeCues(blocks.length, TL.duration);
    TL.elapsed=0; setSeekEnabled(true); TL.showUpTo(0);
    plTime.textContent="0:00 / "+fmtTime(TL.duration);
    startPaced();
  }
}

function buildMenu(){
  var ul=document.getElementById("slideMenuList"); if(!ul) return; ul.innerHTML="";
  var curSection=null;
  order.forEach(function(id,i){
    var c=byId[id];
    // Faz 9.1 — bölüm başlığı (section değişince ekle)
    if(c.section && c.section!==curSection){
      curSection=c.section;
      var hd=document.createElement("li"); hd.className="menu-section";
      hd.setAttribute("role","presentation"); hd.textContent=c.section;
      ul.appendChild(hd);
    }
    var li=document.createElement("li");
    li.setAttribute("role","menuitem"); li.tabIndex=0;
    if(i===cursor) li.setAttribute("aria-current","true");
    var t=secById[id]&&secById[id].querySelector(".screen-title,.title-main");
    li.innerHTML="<span>"+(i+1)+". "+((t&&t.textContent)||c.type)+"</span>"+
      (state.visited[id]?"<span class='mi-done'>"+CHECK_SVG+"</span>":"");
    li.addEventListener("click",function(){ closeMenu(); goId(id,true); });
    li.addEventListener("keydown",function(e){ if(e.key==="Enter"){ closeMenu(); goId(id,true); } });
    ul.appendChild(li);
  });
}
function openMenu(){ buildMenu(); var m=document.getElementById("slideMenu"), o=document.getElementById("menuOverlay");
  if(m){ m.classList.add("open");
    /* staggered entry */
    var items=m.querySelectorAll("li:not(.menu-section)");
    items.forEach(function(li,i){ li.style.animationDelay=(i*30)+"ms"; }); }
  if(o) o.classList.add("open");
  document.getElementById("btnMenu").setAttribute("aria-expanded","true"); }
function closeMenu(){ var m=document.getElementById("slideMenu"), o=document.getElementById("menuOverlay");
  if(m) m.classList.remove("open"); if(o) o.classList.remove("open");
  var b=document.getElementById("btnMenu"); if(b) b.setAttribute("aria-expanded","false"); }

(function bindPlayer(){
  var play=document.getElementById("btnPlay"), seek=document.getElementById("seekbar"),
      mute=document.getElementById("btnMute"), cc=document.getElementById("btnCc"),
      menu=document.getElementById("btnMenu"), replay=document.getElementById("btnReplay"),
      menuCloseBtn=document.getElementById("menuClose"), overlay=document.getElementById("menuOverlay");
  if(play) play.addEventListener("click",function(){
    if(!TL) return;
    if(TL.audio){ if(TL.audio.paused){ TL.audio.play(); play.classList.add("alt"); }
      else { TL.audio.pause(); play.classList.remove("alt"); } }
    else if(TL.paced){ if(TL.timer) stopPaced(); else startPaced(); }
  });
  if(seek) seek.addEventListener("input",function(){
    if(!TL) return; var frac=(seek.value||0)/1000;
    if(TL.audio && TL.audio.duration){ TL.audio.currentTime=frac*TL.audio.duration; }
    else if(TL.paced){ pacedSeek(frac*TL.duration); }
  });
  if(replay) replay.addEventListener("click",function(){
    if(!TL||!TL.section) return;
    if(TL.audio){ TL.audio.currentTime=0; TL.audio.play(); play.classList.add("alt"); }
    else { onScreenEnter(TL.section, TL.cfg); }
  });
  if(mute) mute.addEventListener("click",function(){
    if(TL&&TL.audio){ TL.audio.muted=!TL.audio.muted; mute.classList.toggle("alt", TL.audio.muted); } });
  if(cc) cc.addEventListener("click",function(){
    var on=cc.getAttribute("aria-pressed")!=="true"; cc.setAttribute("aria-pressed",on?"true":"false");
    updateCaptions(TL?TL.section:null, on); });
  if(menu) menu.addEventListener("click",function(e){ e.stopPropagation();
    var m=document.getElementById("slideMenu"); if(!m.classList.contains("open")) openMenu(); else closeMenu(); });
  if(menuCloseBtn) menuCloseBtn.addEventListener("click",closeMenu);
  if(overlay) overlay.addEventListener("click",closeMenu);
})();

document.getElementById("btnNext").addEventListener("click",next);
document.getElementById("btnPrev").addEventListener("click",prev);
// S3/S4 — kapanış: beforeunload mobilde/bfcache'te tetiklenmeyebilir, pagehide daha güvenilir.
// _finished bayrağı çift Terminate'i (LMS hatası) engeller.
var _finished=false;
function finishNow(){ if(_finished) return; _finished=true; _sesPause(); evaluate(); sFinish(); }
window.addEventListener("beforeunload",finishNow);
window.addEventListener("pagehide",finishNow);

// başla — suspend_data'dan kaldığı ekrana devam (yoksa baştan)
var startIdx=0;
if(state.cursorId && indexOfId(state.cursorId)>=0) startIdx=indexOfId(state.cursorId);
showAt(startIdx,false);
// Faz 4-ek — republish devam BİLDİRİMİ: dostane, teknik olmayan, i18n (tr/en), aria-live=polite.
// Yalnız fallback modlarında görünür (screen: düğüm gitmiş; start: ikisi de gitmiş); sessiz
// modlarda (full/node) hiç oluşturulmaz. Kapatılabilir + 12 sn'de kendiliğinden kalkar.
if(_resumeNotice){ try{ (function(){
  var rn=document.createElement("div"); rn.className="resume-notice";
  rn.setAttribute("role","status"); rn.setAttribute("aria-live","polite");
  var msg=T("resume_restart");
  if(_resumeNotice.mode!=="start" && _resumeNotice.target){
    var tEl=secById[_resumeNotice.target]&&secById[_resumeNotice.target].querySelector(".screen-title");
    var ttl=tEl?tEl.textContent.trim():"";
    if(ttl) msg=T("resume_updated",{name:ttl});
  }
  var sp=document.createElement("span"); sp.textContent=msg; rn.appendChild(sp);
  var cb=document.createElement("button"); cb.type="button"; cb.className="resume-notice-close";
  cb.setAttribute("aria-label",T("notice_close")); cb.textContent="×";
  cb.addEventListener("click",function(){ if(rn.parentNode) rn.parentNode.removeChild(rn); });
  rn.appendChild(cb);
  document.body.appendChild(rn);
  setTimeout(function(){ if(rn.parentNode) rn.parentNode.removeChild(rn); },12000);
})(); }catch(e){} }
fitStage();  // Faz 9 — ilk ölçekleme (layout görseli oturduktan sonra)
window.__navReady=true;  // ilk render bitti → sonraki gezinmelerde focus aktif ekrana taşınır

/*__REVIEW_JS_SLOT__*/
})();
"""

# --------------------------------------------------------------------------- #
# 1.1 — review/annotation JS'i ENGINE_JS'ten AYRILDI: renderer.py yalnız review=True iken
# ENGINE_JS içindeki /*__REVIEW_JS_SLOT__*/ sentinelini bununla değiştirir (düz .replace(),
# ENGINE_JS zaten .format() edilmediği için {{}} kaçışlama derdi yok). review=False'ta sentinel
# boş dizgeyle değişir → çıktı HTML/JS'de "reviewBtn" vb. hiçbir iz kalmaz (yalnız markup değil,
# JS de HİÇ basılmaz). T()/curScreen()/CHECK_SVG dış IIFE kapsamından geldiği için bu blok
# ENGINE_JS'in ana IIFE'sinin İÇİNDE (kapanış })();'den önce) kalmak ZORUNDA.
# ---- review/annotation: yalnız review=true render'da (örn. /preview); /demo ve pakette hiç yok ----
REVIEW_JS = r"""if(window.__REVIEW__){
  var rFab=document.getElementById("reviewFab"); if(rFab) rFab.hidden=false;
  var rPanel=document.getElementById("reviewPanel"), rBtn=document.getElementById("reviewBtn"),
      rTxt=document.getElementById("reviewText"), rSend=document.getElementById("reviewSend"),
      rCancel=document.getElementById("reviewCancel"), rSt=document.getElementById("reviewStatus");
  function rToken(){ var m=location.pathname.match(/\/preview\/([^\/]+)/); return m?m[1]:""; }
  if(rBtn) rBtn.addEventListener("click",function(){ rPanel.hidden=!rPanel.hidden; if(!rPanel.hidden) rTxt.focus(); });
  if(rCancel) rCancel.addEventListener("click",function(){ rPanel.hidden=true; });
  if(rSend) rSend.addEventListener("click",function(){
    var c=(rTxt.value||"").trim(); if(!c){ rTxt.focus(); return; }
    rSt.textContent=T("review_sending"); rSend.disabled=true;
    fetch("/feedback",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({preview_token:rToken(),screen_id:(curScreen()&&curScreen().id)||null,comment:c})})
    .then(function(r){ return r.ok?r.json():Promise.reject(); })
    .then(function(){ rSt.innerHTML=CHECK_SVG+" "+T("review_sent"); rTxt.value=""; rSend.disabled=false;
      setTimeout(function(){ rPanel.hidden=true; rSt.textContent=""; },1200); })
    .catch(function(){ rSt.textContent=T("review_error"); rSend.disabled=false; });
  });
}"""


# --------------------------------------------------------------------------- #
# Vendor henüz yapılmadıysa no-op SCORM shim (yalnız fallback; gerçek paket runtime'ı gerektirir)
# --------------------------------------------------------------------------- #
FALLBACK_RUNTIME_SHIM = r"""
(function(){
  function NoopAPI(){ this.data={}; }
  var p=NoopAPI.prototype;
  p.LMSInitialize=p.Initialize=function(){return "true";};
  p.LMSFinish=p.Terminate=function(){return "true";};
  p.LMSGetValue=p.GetValue=function(k){return this.data[k]||"";};
  p.LMSSetValue=p.SetValue=function(k,v){this.data[k]=v;return "true";};
  p.LMSCommit=p.Commit=function(){return "true";};
  p.LMSGetLastError=p.GetLastError=function(){return "0";};
  p.LMSGetErrorString=p.GetErrorString=function(){return "No error";};
  p.LMSGetDiagnostic=p.GetDiagnostic=function(){return "";};
  window.Scorm12API=window.Scorm2004API=NoopAPI;
})();
"""


# --------------------------------------------------------------------------- #
# Senaryo hattı Faz 1 — outline tree menü (CSS + JS). İKİSİ DE yalnız outline'lı kursta
# basılır: CSS renderer'da BASE_CSS'e eklenir, JS review-slot deseniyle ENGINE_JS'in ana
# IIFE'sine gömülür (yeni sentinel YOK — outline boşken çıktı BAYT-BAYT eski hâliyle aynı,
# tests/test_outline_menu.py fixture testi bunu kilitler). Ağacın MARKUP'ı sunucuda render
# edilir (components/renderer.py _render_menu_tree) — JS yalnız davranış: katlama, klavye
# (APG tree deseni), aria-current/ziyaret tazeleme. Dizgeler i18n'den sunucuda çözülür;
# bu JS'te kullanıcıya görünen sabit metin YOK.
# --------------------------------------------------------------------------- #
OUTLINE_CSS = r"""
/* ===== OUTLINE TREE MENU (senaryo hatti Faz 1 — yalniz outline'li kurslarda) ===== */
.slide-menu ul[role="group"]{list-style:none;margin:0;padding:0;padding-inline-start:16px}
.slide-menu li.mtree-li{padding:0}
.slide-menu li.mtree-li:hover{background:none;transform:none}
.mtree-btn{display:flex;align-items:center;gap:8px;width:100%;background:none;border:0;
  cursor:pointer;padding:9px 12px;border-radius:var(--r-md);font-family:inherit;
  font-size:14px;line-height:1.4;color:var(--c-text);text-align:start}
.mtree-btn:hover{background:color-mix(in srgb,var(--c-primary) 6%,transparent)}
.mtree-btn:focus-visible{outline:3px solid var(--c-focus);
  outline-offset:-2px}
.mtree-node{font-weight:var(--w-strong)}
.mtree-num{color:var(--c-muted);flex:none}
.mtree-title{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mtree-chevron{width:14px;height:14px;flex:none;transition:transform .15s ease}
.mtree-btn[aria-expanded="false"] .mtree-chevron{transform:rotate(calc(-90deg * var(--dir-x)))}
.mtree-btn[aria-expanded="false"]+ul[role="group"]{display:none}
.mtree-bullet{width:14px;flex:none}
.mtree-btn[aria-current="page"]{color:var(--c-primary);font-weight:var(--w-strong)}
.mtree-btn .mi-done{color:var(--c-success);margin-inline-start:auto;display:inline-flex}
@media(prefers-reduced-motion:reduce){.mtree-chevron{transition:none}}
/* ===== Faz 4: konum seridi + dugum ilerlemesi + kilit (yalniz outline'li kurslarda) ===== */
.pos-strip{font-size:12px;color:var(--c-muted);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;max-width:34ch;margin-inline-start:var(--space-2,8px);flex:0 1 auto}
@media(max-width:640px){.pos-strip{display:none}}
.mtree-progress{margin-inline-start:auto;flex:none;font-size:12px;color:var(--c-muted);
  font-weight:var(--w-body);font-variant-numeric:tabular-nums}
.mtree-node{flex-wrap:wrap}
.mtree-lockreason{flex-basis:100%;font-size:11px;color:var(--c-muted);
  font-weight:var(--w-body);text-align:start;padding-inline-start:22px}
.mtree-btn[aria-disabled="true"]{opacity:.55;cursor:not-allowed}
.mtree-btn[aria-disabled="true"]:hover{background:none}
"""

OUTLINE_JS = r"""
/* ---- outline tree menü (senaryo hattı Faz 1): sunucu markup'ı statik, burada yalnız davranış ---- */
(function mtreeInit(){
  var tree=document.getElementById("slideMenuList");
  if(!tree||tree.getAttribute("role")!=="tree") return;
  function items(){ return Array.prototype.slice.call(tree.querySelectorAll(".mtree-btn")); }
  function isVisible(b){
    // yapısal görünürlük: kapalı (aria-expanded=false) bir atanın grubunda mı?
    var el=b.parentElement;
    while(el&&el!==tree){
      if(el.tagName==="UL"&&el.getAttribute("role")==="group"){
        var t=el.previousElementSibling;
        if(t&&t.getAttribute("aria-expanded")==="false") return false;
      }
      el=el.parentElement;
    }
    return true;
  }
  function visible(){ return items().filter(isVisible); }
  function setFocus(b){ items().forEach(function(x){ x.tabIndex=-1; }); b.tabIndex=0; b.focus(); }
  function toggle(b){
    if(b.getAttribute("aria-disabled")==="true") return;   // Faz 4 kilit: aç/kapa da etkinleştirmedir
    b.setAttribute("aria-expanded", b.getAttribute("aria-expanded")==="false"?"true":"false"); }
  tree.addEventListener("click",function(e){
    var b=e.target.closest(".mtree-btn"); if(!b) return;
    // Faz 4 kilit (§6.1): kilitli öğe ODAKLANILIR (sebep SR'a okunur) ama ETKİNLEŞTİRİLEMEZ.
    // Ok tuşları/Tab serbest kalır — klavye tuzağı YOK (yalnız aktivasyon engellenir).
    if(b.getAttribute("aria-disabled")==="true") return;
    var id=b.getAttribute("data-goto");
    if(id){ closeMenu(); goId(id,true); }
    else if(b.hasAttribute("aria-expanded")) toggle(b);
  });
  // APG tree klavye deseni; RTL'de sağ/sol anlamı aynalanır. Enter/Space native button'da.
  var rtl=document.documentElement.getAttribute("dir")==="rtl";
  var K_EXPAND=rtl?"ArrowLeft":"ArrowRight", K_COLLAPSE=rtl?"ArrowRight":"ArrowLeft";
  tree.addEventListener("keydown",function(e){
    var b=e.target.closest(".mtree-btn"); if(!b||e.altKey||e.ctrlKey||e.metaKey) return;
    var k=e.key, vis=visible(), i=vis.indexOf(b);
    if(k===K_EXPAND){
      if(b.getAttribute("aria-expanded")==="false") toggle(b);
      else if(b.hasAttribute("aria-expanded")){
        var g=b.nextElementSibling, f=g&&g.querySelector(".mtree-btn"); if(f) setFocus(f); }
    } else if(k===K_COLLAPSE){
      if(b.getAttribute("aria-expanded")==="true") toggle(b);
      else{ var pg=b.parentElement&&b.parentElement.parentElement,
            pb=pg&&pg!==tree&&pg.previousElementSibling;
        if(pb&&pb.classList&&pb.classList.contains("mtree-btn")) setFocus(pb); }
    } else if(k==="ArrowDown"){ if(i<vis.length-1) setFocus(vis[i+1]); }
    else if(k==="ArrowUp"){ if(i>0) setFocus(vis[i-1]); }
    else if(k==="Home"){ if(vis.length) setFocus(vis[0]); }
    else if(k==="End"){ if(vis.length) setFocus(vis[vis.length-1]); }
    else if(k.length===1&&k!==" "&&/\S/.test(k)){
      // type-ahead: geçerli öğeden İLERİYE, başlığı bu harfle başlayan ilk görünür öğe
      var q=k.toLowerCase();
      for(var s=1;s<=vis.length;s++){
        var cand=vis[(i+s)%vis.length], tt=cand.querySelector(".mtree-title");
        if(tt&&tt.textContent.trim().toLowerCase().indexOf(q)===0){ setFocus(cand); break; } }
      return;
    } else return;
    e.preventDefault();
  });
  // ---- Faz 4 (§6.2-6.3): konum şeridi + düğüm ilerlemesi + kilit + düğüme devam ----
  // Saf mantık window.SCORMP'ta (components/engine/progress.js, vitest'li); burada YALNIZ DOM.
  var RTP=window.SCORMP||{};
  var OUT=COURSE.outline||[];
  var SN={}; COURSE.screens.forEach(function(s){ if(s.node_id!=null) SN[s.id]=s.node_id; });
  var NBID={}; OUT.forEach(function(n){ NBID[n.id]=n; });
  function chainOf(nid){ var c=[],seen={},n=nid!=null?NBID[nid]:null;
    while(n&&!seen[n.id]){ seen[n.id]=1; c.unshift(n.id); n=n.parent_id!=null?NBID[n.parent_id]:null; }
    return c; }
  // Konum şeridi: "Ünite 1 · Bölüm 1.1 · 2/4". aria-live=polite yalnız metin DEĞİŞİNCE
  // duyursun diye önceki içerik karşılaştırılır. n/m parçası dir=ltr span'da (RTL'de "4/7"
  // ayracının yönü bozulmaz); düğümsüz ekranların başlığı sunucudan data özniteliğiyle gelir.
  var strip=document.getElementById("posStrip"), _stripKey=null;
  function refreshStrip(){
    if(!strip||!RTP.positionInfo) return;
    var info=RTP.positionInfo(OUT,SN,order,order[cursor]); if(!info) return;
    var path=info.chain.length?info.chain.join(" · "):(strip.getAttribute("data-ungrouped-label")||"");
    var key=path+"|"+info.index+"/"+info.total;
    if(key===_stripKey) return;
    _stripKey=key;
    strip.textContent="";
    var t=document.createElement("span"); t.textContent=path+" · "; strip.appendChild(t);
    var c=document.createElement("span"); c.dir="ltr";
    c.textContent=info.index+"/"+info.total; strip.appendChild(c);
  }
  // Ağaç tazeleme: aria-current + ziyaret işaretleri (Faz 1) + n/m ilerleme + kilit + zincir
  // açma (Faz 4). Kilitli düğüm GÖRÜNÜR + aria-disabled + sebep görünür (buton adının parçası
  // → SR odakta okur) + KATLI (içerik kilit açılmadan gezilmez); ok tuşları/Tab serbest —
  // odaklanılır ama etkinleştirilemez, klavye tuzağı yok. Kullanıcının el katlaması korunur:
  // yalnız AKTİF ekranın düğüm zinciri açılır, başka dal kapatılmaz.
  function refreshTree(){
    var prog=RTP.nodeProgress?RTP.nodeProgress(OUT,SN,state.visited):{};
    var locked=RTP.lockedNodes?RTP.lockedNodes(OUT,SN,state.visited):{};
    var cur=order[cursor], curChain=chainOf(SN[cur]);
    items().forEach(function(bt){
      var nid=bt.getAttribute("data-node-id");
      if(nid){
        var pr=prog[nid];
        if(pr&&pr.total>0){
          var pe=bt.querySelector(".mtree-progress");
          if(!pe){ pe=document.createElement("span"); pe.className="mtree-progress"; pe.dir="ltr";
            bt.insertBefore(pe, bt.querySelector(".mtree-lockreason")); }
          pe.textContent=pr.done+"/"+pr.total;
        }
        var rs=bt.querySelector(".mtree-lockreason");
        if(locked[nid]){
          bt.setAttribute("aria-disabled","true"); if(rs) rs.hidden=false;
          if(bt.getAttribute("aria-expanded")==="true") bt.setAttribute("aria-expanded","false");
        } else {
          bt.removeAttribute("aria-disabled"); if(rs) rs.hidden=true;
          if(curChain.indexOf(nid)>=0 && bt.hasAttribute("aria-expanded"))
            bt.setAttribute("aria-expanded","true");   // düğüme devam: zincir açılır
        }
        return;
      }
      var id=bt.getAttribute("data-goto"); if(!id) return;
      if(locked[SN[id]]) bt.setAttribute("aria-disabled","true");
      else bt.removeAttribute("aria-disabled");
      if(id===cur) bt.setAttribute("aria-current","page"); else bt.removeAttribute("aria-current");
      var done=state.visited[id], has=bt.querySelector(".mi-done");
      if(done&&!has){ var sp=document.createElement("span"); sp.className="mi-done";
        sp.innerHTML=CHECK_SVG; bt.appendChild(sp); }
      else if(!done&&has){ has.parentNode.removeChild(has); }
    });
    refreshStrip();
  }
  // buildMenu'yü geçersiz kıl: ağaç yapısı statik — yalnız dinamik durum tazelenir. Düz
  // menünün innerHTML-yeniden-kurma yolu hiç çalışmaz.
  buildMenu=function(){ refreshTree(); };
  // Her gezinmede tazele (showAt/prev → updateChrome): konum şeridi + kilit durumu güncel kalır.
  var _updateChrome0=updateChrome;
  updateChrome=function(){ _updateChrome0(); refreshTree(); };
  // results_breakdown bölüm TAMAMLANMASI: skorla AYNI data-screens mekanizması (paralel hedef-
  // ilerleme makinesi YOK) — sectionCompletion saf, burada yalnız .rb-comp basımı. ENGINE_JS'e
  // konmadı: outline'sız kursun çıktısı bayt-bayt eski hâlinde kalmalı (3.3).
  var _rr0=renderResultsIfNeeded;
  renderResultsIfNeeded=function(el,s){
    _rr0(el,s);
    if(!s||s.type!=="results_breakdown"||!RTP.sectionCompletion) return;
    var root=el.querySelector(".results-breakdown"); if(!root) return;
    root.querySelectorAll(".rb-section").forEach(function(sec){
      var ids=(sec.dataset.screens||"").split(",").filter(Boolean);
      var comp=RTP.sectionCompletion(ids,state.visited);
      var ce=sec.querySelector(".rb-comp");
      if(!ce){ ce=document.createElement("span"); ce.className="rb-comp";
        var hd=sec.querySelector(".rb-head"), pe=hd&&hd.querySelector(".rb-pct");
        if(hd) hd.insertBefore(ce,pe||null); }
      ce.textContent=T("results_completion",{done:comp.done,total:comp.total});
    });
  };
  // 3.11 — hiyerarşik kursta suspend taşması SESSİZ kırpılmaz: grep'lenebilir SUSPEND_OVERFLOW
  // etiketi (+ mevcut xAPI suspend.trouble izi). Faz 4-ek: merdiven kırpması (trimmed) da aynı
  // etiketi taşır; boyut/bütçe BAYT, basamak (rung) rapora eklenir. Konum kaydı (z) artık zarfta
  // — republish devamının temeli (scorm.js resumeSuspend); türetilen düğüm gösterimi progress.js'te.
  suspendTrouble=function(p){
    if(_suspendWarned[p.kind]) return; _suspendWarned[p.kind]=true;
    var tag=(p.kind==="truncated"||p.kind==="trimmed")?"SUSPEND_OVERFLOW":p.kind;
    try{ console.warn("[scorm] suspend_data "+tag+" ("+p.kind+"): "+p.size+" bytes (budget "+p.limit+
      (p.rung?", rung "+p.rung:"")+") - progress data may be incomplete"); }catch(e){}
    try{ if(typeof XAPI!=="undefined"&&XAPI&&XAPI.emit) XAPI.emit("suspend.trouble",{kind:p.kind,size:p.size,limit:p.limit,rung:p.rung||0}); }catch(e){}
  };
  // İlk tazeleme: ENGINE_JS'in açılış showAt'ı bu blok tanımlanmadan koştu — resume'da konum
  // şeridi/zincir açımı/kilitler burada oturur; results ekranına devam edildiyse tamamlanma da.
  refreshTree();
  var _cs=byId[order[cursor]];
  if(_cs&&_cs.type==="results_breakdown") renderResultsIfNeeded(secById[order[cursor]],_cs);
})();
"""
