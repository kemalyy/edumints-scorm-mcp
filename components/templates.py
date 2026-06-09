"""components/templates.py — HTML shell + premium CSS + SCORM engine JS.

renderer.py bunları kullanır. SHELL bir str.format() şablonudur; içindeki literal CSS süslü
parantezleri YOKTUR (tüm CSS {base_css} değeri olarak gelir), yalnız :root{{...}} kaçışlıdır.
BASE_CSS / ENGINE_JS / FALLBACK_RUNTIME_SHIM düz string'dir (format edilmez).
"""

# --------------------------------------------------------------------------- #
# HTML iskeleti (str.format şablonu)
# --------------------------------------------------------------------------- #
SHELL = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>:root{{{css_vars}}}
{base_css}
{custom_css}</style>
</head>
<body data-bg="{bg_pattern}" data-layout="{layout_mode}">
<a class="skip-link" href="#stage">İçeriğe geç</a>
<div class="app">
  <header class="app-header">
    <div class="brand"><span class="brand-dot"></span><span class="brand-title">{header_title}</span></div>
    <div class="progress" role="progressbar" aria-label="İlerleme" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="progress-bar"></div></div>
    <span class="timer-hud" id="timerHud" aria-live="polite" hidden></span>
    <span class="points-hud" id="pointsHud" aria-live="polite" hidden></span>
    <div class="status-pill" aria-live="polite"></div>
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
    <button class="btn btn-ghost pl-icon" id="btnPrev" type="button" aria-label="Önceki"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg></button>
    <button class="pl-btn" id="btnPlay" type="button" aria-label="Oynat / Duraklat"><span class="ic-a"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="6 3 20 12 6 21 6 3"/></svg></span><span class="ic-b"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/></svg></span></button>
    <button class="pl-btn" id="btnReplay" type="button" aria-label="Baştan oynat"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg></button>
    <input class="seekbar" id="seekbar" type="range" min="0" max="1000" value="0" step="1" aria-label="İlerleme çubuğu" disabled>
    <span class="pl-time" id="plTime">0:00 / 0:00</span>
    <button class="pl-btn" id="btnMute" type="button" aria-label="Sesi aç / kapat"><span class="ic-a"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg></span><span class="ic-b"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/></svg></span></button>
    <button class="pl-btn" id="btnCc" type="button" aria-pressed="false" aria-label="Altyazı"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="14" x="3" y="5" rx="2" ry="2"/><path d="M7 15h4M15 15h2M7 11h2M13 11h4"/></svg></button>
    <button class="pl-btn" id="btnMenu" type="button" aria-haspopup="menu" aria-expanded="false" aria-label="Bölüm menüsü"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/></svg></button>
    <div class="dots" id="dots"></div>
    <button class="btn btn-primary pl-icon" id="btnNext" type="button" aria-label="Sonraki"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg></button>
  </footer>
  <nav class="slide-menu" id="slideMenu" aria-label="Slayt menüsü"><div class="slide-menu-header"><h3>İçerik</h3><button class="slide-menu-close" id="menuClose" type="button" aria-label="Menüyü kapat"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div><ul id="slideMenuList"></ul></nav>
  <div class="menu-overlay" id="menuOverlay"></div>
</div>
<div class="review-fab" id="reviewFab" hidden>
  <button class="review-btn" id="reviewBtn" type="button" aria-haspopup="dialog"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> Geri bildirim</button>
  <div class="review-panel" id="reviewPanel" role="dialog" aria-label="Geri bildirim" hidden>
    <div class="review-head">Bu ekran için yorum bırak</div>
    <textarea id="reviewText" rows="3" placeholder="Ne değişmeli?"></textarea>
    <div class="review-actions">
      <button class="btn btn-ghost" id="reviewCancel" type="button">İptal</button>
      <button class="btn btn-primary" id="reviewSend" type="button">Gönder</button>
    </div>
    <div class="review-status" id="reviewStatus" aria-live="polite"></div>
  </div>
</div>
{runtime_block}
{extra_runtime}
<script>
window.__COURSE__ = {course_json};
window.__ASSETS__ = {asset_json};
window.__SCORM_2004__ = {scorm_2004};
window.__PREVIEW__ = {preview};
</script>
<script>
{engine_js}
</script>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# Premium CSS (düz string — literal braces)
# --------------------------------------------------------------------------- #
BASE_CSS = r"""
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:var(--fs-base);scroll-behavior:smooth}
body{font-family:var(--font-body);font-weight:var(--w-body);line-height:var(--lh-normal);
  color:var(--c-text);background:var(--c-bg);-webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;overflow:hidden;height:100vh}
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
.app{height:100vh;display:flex;flex-direction:column;max-width:1200px;margin:0 auto;overflow:hidden}

/* ===== FOUNDATION: a11y + primitifler ===== */
.skip-link{position:absolute;left:var(--space-4);top:-60px;z-index:100;background:var(--c-primary);
  color:var(--c-primary-contrast);padding:var(--space-3) var(--space-4);border-radius:var(--r-md);
  font-weight:var(--w-strong);transition:top var(--d-fast) var(--ease)}
.skip-link:focus{top:var(--space-4)}
.opt:focus-visible,.branch-choice:focus-visible,.drag-item:focus-visible,.hotspot-region:focus-visible,
.blank input:focus-visible,a:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 50%,transparent);
  outline-offset:2px;border-radius:var(--r-sm)}
.stage:focus{outline:none}
.btn,.opt,.branch-choice{min-height:44px}
.ui-stack{display:flex;flex-direction:column;gap:var(--space-4)}
.ui-cluster{display:flex;flex-wrap:wrap;gap:var(--space-3);align-items:center}
.ui-grid{display:grid;gap:var(--space-4);grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.ui-card{background:var(--c-bg);border:1px solid var(--c-border);border-radius:var(--r-md);
  padding:var(--space-4);box-shadow:0 1px 3px color-mix(in srgb,var(--c-primary) 6%,transparent)}
.ui-chip{display:inline-flex;align-items:center;gap:var(--space-2);font-size:12px;font-weight:var(--w-strong);
  padding:var(--space-2) var(--space-3);border-radius:var(--r-pill);
  background:color-mix(in srgb,var(--c-primary) 10%,var(--c-surface-alt));color:var(--c-primary)}
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
.brand-title{font-size:15px;font-weight:600;color:var(--c-text);
  letter-spacing:-0.01em}
.progress{flex:1;height:6px;background:color-mix(in srgb,var(--c-border) 40%,transparent);
  border-radius:var(--r-pill);overflow:hidden}
.progress-bar{height:100%;width:0;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--c-primary),color-mix(in srgb,var(--c-primary) 70%,var(--c-accent)));
  transition:width .6s cubic-bezier(.22,1,.36,1);
  box-shadow:0 0 6px color-mix(in srgb,var(--c-primary) 20%,transparent)}
.status-pill{font-size:12px;color:var(--c-muted);min-width:60px;text-align:right;
  font-variant-numeric:tabular-nums;font-weight:500}
.timer-hud{font-family:var(--font-mono);font-weight:var(--w-strong);font-size:13px;color:var(--c-primary);
  background:color-mix(in srgb,var(--c-primary) 6%,var(--c-surface));
  padding:4px 10px;border-radius:var(--r-pill);border:1px solid color-mix(in srgb,var(--c-primary) 12%,transparent)}
.timer-hud.urgent{color:var(--c-error);background:var(--c-error-bg);border-color:var(--c-error)}
.points-hud{font-weight:var(--w-strong);font-size:13px;color:var(--c-warning);
  background:color-mix(in srgb,var(--c-warning) 8%,var(--c-surface));
  padding:4px 10px;border-radius:var(--r-pill);border:1px solid color-mix(in srgb,var(--c-warning) 15%,transparent)}

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
  padding:clamp(24px,3vw,44px) clamp(20px,3vw,40px);height:100%;overflow:hidden;display:flex;flex-direction:column}
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
  justify-content:center;overflow-y:auto;overflow-x:hidden;padding-right:var(--space-3);min-height:0}
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
.rich ul,.rich ol{padding-left:1.4em} .rich li+li{margin-top:var(--space-2)}
.rich img{max-width:100%;height:auto;border-radius:var(--r-md);box-shadow:var(--e1)}
.rich blockquote{border-left:3px solid var(--c-primary);padding:var(--space-2) var(--space-4);
  background:var(--c-surface-alt);border-radius:0 var(--r-md) var(--r-md) 0;color:var(--c-muted)}
.rich code{font-family:var(--font-mono);background:var(--c-surface-alt);padding:.15em .4em;
  border-radius:var(--r-sm);font-size:.9em}
.rich table{width:100%;border-collapse:collapse} .rich th,.rich td{border:1px solid var(--c-border);
  padding:var(--space-3);text-align:left} .rich thead th{background:var(--c-surface-alt)}
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
  margin:var(--space-3) 0}
.full-media .media{max-height:100%;width:auto;max-width:100%;height:auto;object-fit:contain}

/* title slide */
.title-slide{text-align:center;padding:var(--space-5) 0;flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center}
.title-kicker{color:var(--c-primary);font-size:11px;letter-spacing:.4em;text-transform:uppercase;
  margin-bottom:var(--space-4);opacity:.7}
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
.btn:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 45%,transparent);outline-offset:2px}
.btn-primary{background:var(--c-primary);color:var(--c-primary-contrast);
  box-shadow:0 2px 8px color-mix(in srgb,var(--c-primary) 25%,transparent)}
.btn-primary:hover{background:var(--c-primary-hover);
  box-shadow:0 4px 16px color-mix(in srgb,var(--c-primary) 30%,transparent);transform:translateY(-1px)}
.btn-primary:disabled{opacity:.45;cursor:not-allowed;box-shadow:none;transform:none}
.btn-ghost{background:transparent;color:var(--c-muted);border-color:color-mix(in srgb,var(--c-border) 60%,transparent)}
.btn-ghost:hover{color:var(--c-text);background:var(--c-surface-alt)}
.btn-ghost:disabled{opacity:.4;cursor:not-allowed}
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
.opt{display:flex;align-items:center;gap:var(--space-3);text-align:left;cursor:pointer;
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

/* fill blank */
.blanks{display:flex;flex-direction:column;gap:var(--space-4)}
.blank{display:flex;flex-direction:column;gap:var(--space-2);font-size:13px;color:var(--c-muted)}
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
  transition:all .15s ease}
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
.branch-choice{text-align:left;cursor:pointer;background:var(--c-bg);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);padding:var(--space-4) var(--space-5);font-size:15px;color:var(--c-text);
  display:flex;align-items:center;gap:var(--space-3);
  transition:all .2s cubic-bezier(.4,0,.2,1)}
.branch-choice::before{content:"→";color:var(--c-primary);font-weight:700}
.branch-choice:hover{border-color:var(--c-primary);transform:translateX(4px);
  box-shadow:0 2px 12px color-mix(in srgb,var(--c-primary) 10%,transparent)}

/* karar senaryosu (decision_scenario) */
.scenario{display:flex;flex-direction:column;gap:var(--space-4)}
.scen-hud{align-self:flex-start;font-weight:var(--w-strong);color:var(--c-warning)}
.scen-prompt{font-size:16px}
.scen-img{width:100%;max-height:280px;object-fit:contain;border-radius:var(--r-md);background:var(--c-surface)}
.scen-choices{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:var(--space-3)}
.scen-row{display:flex;flex-direction:column;gap:var(--space-2)}
.scen-choice{text-align:left;cursor:pointer;background:var(--c-bg);border:1.5px solid var(--c-border);
  border-radius:var(--r-md);padding:var(--space-4) var(--space-5);font-size:15px;color:var(--c-text);
  min-height:44px;display:flex;align-items:center;gap:var(--space-3);transition:all .2s cubic-bezier(.4,0,.2,1)}
.scen-choice::before{content:"▸";color:var(--c-primary);font-weight:700}
.scen-choice:hover:not(:disabled){border-color:var(--c-primary);transform:translateX(4px);
  box-shadow:0 2px 12px color-mix(in srgb,var(--c-primary) 10%,transparent)}
.scen-choice:disabled{cursor:default}
.scen-choice.chosen{border-color:var(--c-primary);background:color-mix(in srgb,var(--c-primary) 8%,var(--c-bg))}
.scen-choice.dim{opacity:.5}
.scen-conseq{font-size:14px;color:var(--c-muted);padding:var(--space-2) var(--space-4);
  border-left:3px solid var(--c-primary);background:var(--c-surface);border-radius:0 var(--r-sm) var(--r-sm) 0}
.scen-next{align-self:flex-start}

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
.accordion summary:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 50%,transparent);
  outline-offset:2px;border-radius:var(--r-sm)}

/* tabs */
.tab-list{display:flex;flex-wrap:wrap;gap:var(--space-2);border-bottom:2px solid var(--c-border);margin-bottom:var(--space-4)}
.tab{background:transparent;border:none;cursor:pointer;font-family:var(--font-body);font-weight:var(--w-strong);
  font-size:15px;color:var(--c-muted);padding:var(--space-3) var(--space-4);min-height:44px;
  border-bottom:2px solid transparent;margin-bottom:-2px;
  transition:all .2s cubic-bezier(.4,0,.2,1)}
.tab:hover{color:var(--c-text)}
.tab[aria-selected="true"]{color:var(--c-primary);border-bottom-color:var(--c-primary)}
.tab:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 50%,transparent);outline-offset:-2px;border-radius:var(--r-sm)}

/* flashcards */
.flashcard{background:transparent;border:none;padding:0;cursor:pointer;perspective:1000px;min-height:160px;font:inherit}
.fc-inner{position:relative;display:block;width:100%;min-height:160px;transform-style:preserve-3d;
  transition:transform .5s cubic-bezier(.4,0,.2,1)}
.flashcard.flipped .fc-inner{transform:rotateY(180deg)}
.fc-face{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;
  padding:var(--space-4);border:1px solid var(--c-border);border-radius:var(--r-md);box-shadow:var(--e1);
  background:var(--c-bg);backface-visibility:hidden;-webkit-backface-visibility:hidden}
.fc-back{transform:rotateY(180deg);background:color-mix(in srgb,var(--c-primary) 7%,var(--c-bg))}
.flashcard:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 50%,transparent);outline-offset:3px;border-radius:var(--r-md)}
@media(prefers-reduced-motion:reduce){.fc-inner{transition:none}}

/* matching */
.match-row{display:grid;grid-template-columns:1fr auto;gap:var(--space-3);align-items:center}
.match-left{padding:var(--space-2) 0}
.match-select{font-family:var(--font-body);font-size:15px;color:var(--c-text);background:var(--c-bg);
  border:1.5px solid var(--c-border);border-radius:var(--r-md);padding:var(--space-3);min-height:44px;min-width:160px;cursor:pointer}
.match-select:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 50%,transparent);outline-offset:2px}
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
.timeline{list-style:none;padding:0;position:relative;margin-left:var(--space-2)}
.timeline::before{content:"";position:absolute;left:6px;top:8px;bottom:8px;width:2px;background:var(--c-border)}
.tl-event{position:relative;padding-left:var(--space-6);margin-bottom:var(--space-5)}
.tl-marker{position:absolute;left:0;top:6px;width:14px;height:14px;border-radius:var(--r-pill);
  background:var(--c-primary);border:3px solid var(--c-bg);box-shadow:0 0 0 2px var(--c-primary)}
.tl-date{margin-bottom:var(--space-2)}
.tl-title{font-family:var(--font-heading);font-size:var(--fs-h4);font-weight:var(--w-strong);margin-bottom:var(--space-2)}

/* lottie */
.lottie-wrap{display:flex;justify-content:center;margin:var(--space-4) 0;flex:1}
.lottie{width:100%;max-width:480px;aspect-ratio:1/1}

/* review/annotation */
.review-fab{position:fixed;right:18px;bottom:70px;z-index:90}
.review-btn{background:var(--c-primary);color:var(--c-primary-contrast);border:none;border-radius:var(--r-pill);
  padding:var(--space-3) var(--space-4);font-weight:var(--w-strong);font-size:14px;cursor:pointer;
  box-shadow:0 4px 16px color-mix(in srgb,var(--c-primary) 30%,transparent);min-height:44px;
  transition:all .2s ease}
.review-btn:hover{transform:translateY(-2px);box-shadow:0 6px 24px color-mix(in srgb,var(--c-primary) 40%,transparent)}
.review-btn:focus-visible{outline:3px solid color-mix(in srgb,var(--c-focus) 50%,transparent);outline-offset:2px}
.review-panel{position:absolute;right:0;bottom:54px;width:300px;max-width:80vw;
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
/* altyazı */
.cc-bar{position:absolute;left:5%;right:5%;bottom:12px;z-index:6;
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
.slide-menu{position:fixed;top:0;right:0;bottom:0;z-index:50;width:320px;max-width:85vw;
  background:var(--c-surface);
  border-left:1px solid color-mix(in srgb,var(--c-border) 50%,transparent);
  box-shadow:-8px 0 32px color-mix(in srgb,var(--c-primary) 5%,transparent),-2px 0 8px rgba(0,0,0,.04);
  transform:translateX(100%);transition:transform .35s cubic-bezier(.22,1,.36,1);
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
@keyframes menuItemIn{from{opacity:0;transform:translateX(12px)}to{opacity:1;transform:none}}
.slide-menu li:hover{background:color-mix(in srgb,var(--c-primary) 6%,transparent);
  transform:translateX(2px)}
.slide-menu li[aria-current="true"]{font-weight:var(--w-strong);color:var(--c-primary);
  background:color-mix(in srgb,var(--c-primary) 8%,transparent);
  border-left:3px solid var(--c-primary);padding-left:11px;opacity:1}
.slide-menu li .mi-done{color:var(--c-success);margin-left:auto;display:inline-flex}
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
@keyframes tlSlideLeft{from{opacity:0;transform:translateX(28px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.tl-block{opacity:1 !important}
  .tl-block.tl-in{animation:none !important}}

/* ===== RESPONSIVE — tablet ===== */
@media(max-width:960px){
  .screen[data-type="video"] .split{flex-direction:column}
  .screen[data-type="video"] .split .split-text{flex:0 0 auto;max-height:30%;max-width:100%;padding-right:0;padding-bottom:var(--space-2)}
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
  .cc-bar{font-size:13px;bottom:6px;left:2%;right:2%;padding:5px 10px}
  .slide-menu{width:280px}
  .review-fab{bottom:56px}
  .screen-inner{padding:14px}
  .screen-title{font-size:calc(var(--fs-h2) * .85)}
  .match-row{grid-template-columns:1fr}
  .match-select{min-width:0;width:100%}
  .options.tf{flex-direction:column}
}
/* ===== RESPONSIVE — küçük mobil ===== */
@media(max-width:380px){
  .app-header{padding:6px 8px}
  .app-footer.player{padding:6px 8px}
  .brand-title{display:none}
  .screen-inner{padding:10px}
}
"""


# --------------------------------------------------------------------------- #
# SCORM engine JS (düz string)
# --------------------------------------------------------------------------- #
ENGINE_JS = r"""
(function(){
"use strict";
var COURSE = window.__COURSE__, ASSETS = window.__ASSETS__, S2004 = window.__SCORM_2004__;
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
function sGet(k){ if(!api)return""; try{ return S2004?api.GetValue(k):api.LMSGetValue(k); }catch(e){ return ""; } }
function sCommit(){ if(!api)return; try{ S2004?api.Commit(""):api.LMSCommit(""); }catch(e){} }
function sInit(){ if(!api)return; try{ S2004?api.Initialize(""):api.LMSInitialize(""); }catch(e){} }
function sFinish(){ if(!api)return; try{ S2004?api.Terminate(""):api.LMSFinish(""); }catch(e){} }
sInit();
if(S2004){ sSet("cmi.score.min","0"); sSet("cmi.score.max","100"); sSet("cmi.completion_status","incomplete"); }
else { sSet("cmi.core.score.min","0"); sSet("cmi.core.score.max","100"); sSet("cmi.core.lesson_status","incomplete"); }

// ---- durum (suspend_data'dan geri yükle) ----
var state={visited:{},results:{},history:[]};
(function restore(){ try{ var raw=sGet(S2004?"cmi.suspend_data":"cmi.suspend_data");
  if(raw){ var d=JSON.parse(raw); if(d&&d.visited){ state=d; state.history=state.history||[]; } } }catch(e){} })();

// ---- Faz 5: değişken/durum motoru (state.vars → suspend_data'da persist) ----
if(!state.vars){ state.vars={}; (COURSE.variables||[]).forEach(function(v){ state.vars[v.name]=v.default; }); }
function _vnum(x){ var n=parseFloat(x); return isNaN(n)?0:n; }
function applyActions(acts){ if(!acts||!acts.length) return; acts.forEach(function(a){
  if(a.op==="add"){ state.vars[a.var]=_vnum(state.vars[a.var])+_vnum(a.value); }
  else { state.vars[a.var]=a.value; } }); updatePoints(); }
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
  var json=JSON.stringify(state);
  if(json.length>4000 && !S2004){ json=JSON.stringify({visited:state.visited,results:state.results,
    history:[],cursorId:state.cursorId,reachedEnd:state.reachedEnd}); }
  sSet("cmi.suspend_data",json); sCommit();
}

// ---- skor + tamamlanma ----
function earned(){ var e=0; for(var k in state.results){ e+=state.results[k].points||0; } return e; }
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
function evaluate(){
  writeScore();
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
  var _sc=byId[id]; if(_sc&&_sc.on_enter) applyActions(_sc.on_enter);  // Faz 5
  interpolateScreen(secById[id]);
  startTimer(_sc); updatePoints();  // Faz 6
  if(_sc&&_sc.type==="lottie") initLottie(secById[id],_sc);  // Faz 7
  if(cursor===order.length-1) state.reachedEnd=true;
  applyAnsweredState(secById[id], byId[id]);
  updateChrome();
  renderSummaryIfNeeded(secById[id], byId[id]);
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
    cp.textContent=hasQuiz?(passed?"Başarıyla tamamladınız":"Geçme notuna ulaşılamadı")
      :(isComplete()?"Tamamlandı":"Devam ediyor");
    cp.className="summary-completion "+(hasQuiz?(passed?"passed":"failed"):""); }
}

// ---- quiz: interaksiyon ----
function recordResult(id,pts,maxpts,ok){ state.results[id]={points:pts,max:maxpts,ok:!!ok,answered:true}; }

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
  });
  return ok;
}
function checkFill(el,s){
  var ok=true;
  el.querySelectorAll("input[data-blank]").forEach(function(inp){
    var acc=s.blanks[inp.dataset.blank]||[]; var val=inp.value.trim();
    var v=s.case_sensitive?val:val.toLowerCase();
    var hit=acc.some(function(a){ return (s.case_sensitive?a:a.toLowerCase())===v; });
    inp.disabled=true; inp.parentNode.classList.add(hit?"correct":"wrong"); if(!hit) ok=false;
  });
  return ok;
}
function bindDrag(el,s){
  var dragging=null;
  el.querySelectorAll(".drag-item").forEach(function(it){
    it.addEventListener("dragstart",function(){ dragging=it; it.classList.add("dragging"); });
    it.addEventListener("dragend",function(){ it.classList.remove("dragging"); dragging=null; });
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
  var ok=true;
  el.querySelectorAll(".drop-target").forEach(function(tg){
    var tid=tg.dataset.target; var items=tg.querySelectorAll(".drag-item"); var good=true;
    items.forEach(function(it){ if(s.correct[it.dataset.item]!==tid) good=false; });
    // hedefte olması gereken tüm item'lar burada mı?
    for(var item in s.correct){ if(s.correct[item]===tid){ var found=false;
      items.forEach(function(it){ if(it.dataset.item===item) found=true; }); if(!found) good=false; } }
    tg.classList.add(good?"correct":"wrong"); if(!good) ok=false;
  });
  el.querySelectorAll(".drag-item").forEach(function(it){ it.setAttribute("draggable","false"); });
  return ok;
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
      else if(r.dataset.region===picked) r.classList.add("wrong"); }); return ok; });
}
function bindCheck(el,s,checker){
  var btn=el.querySelector(".btn-check"); var fb=el.querySelector(".feedback");
  btn.addEventListener("click",function(){
    var ok=checker(); btn.disabled=true;
    var pts=ok?s.points:0; recordResult(s.id,pts,s.points,ok);
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
    if(cur>=total){ recordResult(s.id,s.points,s.points,true); applyActions(s.on_correct);
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
  var score=0, finished=false;
  var hud=root.querySelector(".scen-score");
  var fb=el.querySelector(".feedback");
  var pass=(root.dataset.pass!==undefined&&root.dataset.pass!=="")?parseInt(root.dataset.pass,10):null;
  var points=parseInt(root.dataset.points,10)||0;
  function show(id){ root.querySelectorAll(".scen-node").forEach(function(n){ n.hidden=(n.dataset.node!==id); }); }
  function finalize(){ if(finished) return; finished=true;
    var ok = (pass!=null) ? (score>=pass) : (score>0);
    recordResult(s.id, ok?points:0, points, ok);
    applyActions(ok?s.on_correct:s.on_wrong);
    if(fb){ var msg=ok?(s.feedback&&s.feedback.correct||""):(s.feedback&&s.feedback.incorrect||"");
      fb.innerHTML=msg+' <b>Skor: '+score+'</b>'; fb.className="feedback show "+(ok?"ok":"no"); }
    var nb=document.getElementById("btnNext"); if(cursor<order.length-1) nb.disabled=false;
    evaluate();
  }
  root.querySelectorAll(".scen-node").forEach(function(node){
    var nextBtn=node.querySelector(".scen-next"); var goTo="";
    node.querySelectorAll(".scen-choice").forEach(function(b){
      b.addEventListener("click",function(){
        if(node.dataset.done) return; node.dataset.done="1";
        score+=parseInt(b.dataset.delta,10)||0; if(hud) hud.textContent=score;
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
  var ok=true;
  el.querySelectorAll(".match-row").forEach(function(row){
    var sel=row.querySelector(".match-select"); var hit=sel.value===row.dataset.pair;
    sel.disabled=true; row.classList.add(hit?"correct":"wrong"); if(!hit) ok=false;
  });
  return ok;
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
  return ok;
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
  /* frame sabit boyut — scale ile ölçeklenecek */
  fr.style.width=W+"px"; fr.style.height=H+"px";
  var k=Math.min(st.clientWidth/W, st.clientHeight/H);
  if(!isFinite(k)||k<=0) k=1;
  fr.style.transform="scale("+k+")";
  var scaledW=W*k, scaledH=H*k;
  sc.style.width=scaledW+"px"; sc.style.height=scaledH+"px";
}
window.addEventListener("resize",fitStage);

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
window.addEventListener("beforeunload",function(){ evaluate(); sFinish(); });

// başla — suspend_data'dan kaldığı ekrana devam (yoksa baştan)
var startIdx=0;
if(state.cursorId && indexOfId(state.cursorId)>=0) startIdx=indexOfId(state.cursorId);
showAt(startIdx,false);
fitStage();  // Faz 9 — ilk ölçekleme (layout görseli oturduktan sonra)
window.__navReady=true;  // ilk render bitti → sonraki gezinmelerde focus aktif ekrana taşınır

// ---- review/annotation: yalnız preview'da; paket modunda hiç çalışmaz ----
if(window.__PREVIEW__){
  var rFab=document.getElementById("reviewFab"); if(rFab) rFab.hidden=false;
  var rPanel=document.getElementById("reviewPanel"), rBtn=document.getElementById("reviewBtn"),
      rTxt=document.getElementById("reviewText"), rSend=document.getElementById("reviewSend"),
      rCancel=document.getElementById("reviewCancel"), rSt=document.getElementById("reviewStatus");
  function rToken(){ var m=location.pathname.match(/\/preview\/([^\/]+)/); return m?m[1]:""; }
  if(rBtn) rBtn.addEventListener("click",function(){ rPanel.hidden=!rPanel.hidden; if(!rPanel.hidden) rTxt.focus(); });
  if(rCancel) rCancel.addEventListener("click",function(){ rPanel.hidden=true; });
  if(rSend) rSend.addEventListener("click",function(){
    var c=(rTxt.value||"").trim(); if(!c){ rTxt.focus(); return; }
    rSt.textContent="Gönderiliyor…"; rSend.disabled=true;
    fetch("/feedback",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({preview_token:rToken(),screen_id:(curScreen()&&curScreen().id)||null,comment:c})})
    .then(function(r){ return r.ok?r.json():Promise.reject(); })
    .then(function(){ rSt.innerHTML=CHECK_SVG+" Gönderildi"; rTxt.value=""; rSend.disabled=false;
      setTimeout(function(){ rPanel.hidden=true; rSt.textContent=""; },1200); })
    .catch(function(){ rSt.textContent="Hata — tekrar dene"; rSend.disabled=false; });
  });
}
})();
"""


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
