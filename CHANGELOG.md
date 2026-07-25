# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — kalıcı demo linkleri (W12)
- Yeni `publish_demo` MCP tool'u (27. araç) + `GET /demo/{slug}` rotası: projeyi TTL'siz, kalıcı
  bir herkese-açık URL'e yayınlar (README/vitrin linkleri artık kırılmaz). Upsert; slug sahibine
  kilitli; slug regex'i path-traversal'ı engeller.

### Added — görsel anlatı sistemleştirmesi (W11)
- `lint_course`'a iki yeni görsel-yoğunluk kuralı (WARN): `text_only_run` (≥4 ardışık görselsiz
  ekran) ve `visual_poverty` (≥8 ekranlı kursta <%25 görsel ekran) — "metin duvarı" artık makine-
  denetimli.
- Yeni `search_images` MCP tool'u (26. araç): Openverse/Wikimedia üzerinden CC0/Public-Domain
  görsel arama; sonuçlar lisans/yazar/kaynak bilgisiyle döner, indirme mevcut `add_asset` üzerinden.
  Sorgu URL-encode edilir (CC0 filtre bypass'ı kapalı), per-item lisans aile kontrolü var, tüm API
  istekleri SSRF korumasından geçer.

### Added — `search_images` (W11 Bölüm 2)
- New `search_images(query, source="openverse", limit=5)` MCP tool wires the previously-dormant
  Openverse/Wikimedia adapters into a real CC0/Public-Domain image search (26th MCP tool).
  Candidate-only (no download); pick a result's `url` and pass it to the existing
  `add_asset(project_id, source=url, filename=...)` to attach it (download + SSRF checks happen
  there). Each result carries license/creator/source-page for attribution.
- `OpenverseAdapter.search()` / `WikimediaAdapter.search()` — new candidate-listing methods
  alongside the existing `fetch()` (untouched); Wikimedia results are filtered to the PD/CC0
  license family; both go through `assert_safe_url` and degrade gracefully (`[]`) on error.

## [1.5.0] — 2026-07-25

Standards fidelity + internationalisation + theme composability. The player now reports
question-level data to the LMS, speaks the course's language, and supports RTL scripts;
themes decouple structural style from brand identity. All additive — existing specs unchanged.

### Added — SCORM data contract (S1/S3/S4)
- `cmi.interactions.*` — every graded answer now reaches the LMS with id, type, learner response,
  result, correct-response pattern, latency and timestamp (1.2/2004 element-name and format
  differences handled in one place: `components/engine/scorm.js`, exposed as `window.SCORMRT`).
- Seat time — `cmi.core.session_time` (1.2) / `cmi.session_time` (2004) written in the
  version-correct duration format on every evaluate and on unload.
- `exit`/`entry` — `exit="suspend"` while incomplete, `"normal"` on completion; restore honours
  `entry` so "continue where you left off" is guaranteed across LMSs, not incidental.

### Added — player internationalisation (I1/I2)
- `components/i18n.py` string table — all ~47 previously hard-coded Turkish shell strings
  (aria-labels, buttons, runtime messages) now resolve from `project.language`; `tr` and `en`
  fully maintained in-repo, missing keys fall back to `en` (never to `tr`).
- RTL support — `<html dir>` derived from language; Arabic, Persian, Hebrew and other RTL
  scripts render correctly.
- `Feedback.correct_html`/`incorrect_html` defaults are now `None` and resolve to the course
  language at render time (a German course no longer shows "Doğru!"); the `default_feedback`
  lint rule checks for unfilled feedback directly instead of comparing Turkish strings.

### Added — tema stil/marka katmanlaştırması (W10)
- 3 yeni "stil varyantı" tema preset'i (`style-minimal`, `style-playful`, `style-premium`) — yapısal
  kişilik (gölge, kenarlık, buton davranışı) `custom_css` içinde yalnız `var(--c-*)` token'larına
  dayanır, sabit marka rengi içermez; herhangi bir marka paletiyle `set_theme` üzerinden serbestçe
  birleştirilebilir.
- Tema preset yüklemesine yeni bir `extends` yönergesi — bir preset başka birini miras alıp yalnız
  farkını override edebilir (`style-playful.json`, `playground`'ı extends eder — CSS mantığı tek
  kaynakta yaşar, kopyalanmaz). Döngüsel miras tespit edilip reddedilir.
- `ThemeTokens.logo_asset_id` artık gerçekten render ediliyor — player chrome'undaki marka noktasının
  yerine paketlenmiş logo görseli geçiyor (`ThemeTokens.logo_alt` ile erişilebilir alt-text).
- Yeni `ThemeTokens.custom_fonts` — paketlenmiş bir `.woff2` asset'inden otomatik `@font-face` üretimi,
  kurumsal fontların harici CDN bağımlılığı olmadan (SCORM paketleri offline/LMS-içi çalışabilsin diye)
  gömülmesini sağlar.
- `lint_course` yeni bir `missing_alt_text` dalı kazandı — tema logosu var ama `logo_alt` boşsa WARN.

### Fixed
- Mobile viewports: content is now vertically centred and hidden screens no longer stack into
  the layout (the flow-mode `.screen` rule is scoped to the visible screen; `.stage` uses
  `align-items:center`) — previously a real course inflated the stage to ~10,000px on phones.

## [1.4.0] — 2026-07-23

Institutional-readiness hardening (W9 P0+P1): accessibility alt-text, rate limiting, audit logging,
dependency scanning, mechanized anti-slop rules, SCORM Cloud CI conformance gate, WCAG game a11y
audit tooling. All additive — existing specs unchanged, no server-side LLM. Still 25 MCP tools.

### Added — accessibility (alt text)
- Opsiyonel `*_alt` fields on 10 screen/item classes carrying images (`HotspotScreen.image_alt`,
  `LabeledDiagramScreen.image_alt`, `SimStep.image_alt`, `ScenarioNode.image_alt`,
  `GameNode.image_alt`, `ContentSlide.media_alt`, `AccordionItem.image_alt`, `TabItem.image_alt`,
  `Flashcard.front_alt`/`back_alt`, `TimelineEvent.image_alt`) — renderer now emits the real value
  instead of a hardcoded empty `alt=""`.
- `lint_course` gained a `missing_alt_text` WARN — flags any image-bearing field left without alt
  text, across every screen type that carries one (including `ContentSlide.blocks[]`).

### Added — security
- Per-principal rate limiting (`RATE_LIMIT_PER_MIN`, default 60/min) — an in-process token bucket
  wraps the internal owner-resolution path used by 23 of 25 MCP tools; the previously-unused
  `rate_limited` error code now actually fires.
- Basic structured audit logging (`scorm_mcp.audit` logger) for project creation, package builds,
  and API-key create/delete.
- CI: Dependabot (pip + github-actions) + a real `pip-audit --strict` gate on every push/PR
  (previously only a non-blocking weekly report).

### Added — anti-slop mechanization
- Four more anti-slop rules from `references/anti-slop.md` are now mechanically enforced (WARN) via
  `lint_course` instead of relying on the authoring model to self-count: `consecutive_content_slides`
  (A1, >2 in a row), `too_many_list_items` (A2, >4 `<li>` per screen), `generic_title` (A3, e.g.
  "Modül 1: Giriş"), `default_feedback` (B3, schema-default `"Doğru!"`/`"Tekrar deneyin."` left
  unedited).

### Added — conformance & a11y tooling
- `tools/scorm_cloud.py` + `tools/scorm_cloud_ci_check.py` + a private-repo CI workflow
  (`scorm-cloud-conformance.yml`): every push to master imports 4 real package combinations
  (small/rich × SCORM 1.2/2004) into SCORM Cloud and verifies 0 parser warnings + a launchable
  registration — a genuine, repeating conformance gate (previously a one-time manual check).
  `docs/CONFORMANCE.md` now also lists Moodle/Canvas/Blackboard/TalentLMS/Docebo as an honest,
  unfilled manual checklist (no access to automate these).
- `tests/a11y/generate_fixtures.py` + `tests/a11y/audit.mjs` (`npm run a11y-audit`) — renders the 8
  `examples/games/*.json` courses and runs `@axe-core/playwright` against them, reporting WCAG
  violations. Non-blocking for this first pass (baseline: 8 fixtures, 8 moderate `heading-order`
  violations) — a new public-repo CI job (`a11y-audit`) runs this on every push/PR.

### Known gaps carried forward (see `docs/superpowers/plans/2026-07-22-institutional-production-readiness.md`)
- 10 known third-party dependency CVEs (cryptography, mcp, pydantic-settings, python-multipart,
  setuptools, starlette) — pinned via `--ignore-vuln` with a dated tracking note, not yet fixed.
- No organization/multi-tenant model, no backup/DR automation, no billing — still open P1/P2 items.

## [1.3.0] — 2026-06-26

SVG diagram pipeline + block sizing + opt-in narration. **25 MCP tools.** All additive — existing
specs unchanged, no server-side LLM.

### Added
- **`svg_to_asset` tool** (25th tool) — turn a Claude-generated SVG string into a packaged asset without
  base64 (raw `svg_content`); validates `<svg>`, returns an `AssetRef` (`id`) to use in
  `media_asset_id` / `image_asset_id` / block `asset_id`. Optional `rasterize=true` → PNG (needs
  `cairosvg`; clear `rasterize_unavailable` error otherwise). Fixes the "inline `<svg>` in `body_html`
  gets sanitized away" pitfall — use the asset pipeline (rendered as `<img src=…svg>`).
- **`content_slide` `blocks[]` per-block `width`** (e.g. `"60%"`) — image blocks can be sized + centered
  (`margin-inline:auto`); omitted → full width.
- **`build_from_spec` `auto_tts`** (opt-in, default `false`) + `tts_voice` — auto-generates Piper
  narration for screens that have `narration_text` and no `narration_asset_id`, setting
  `narration_asset_id`. Silently skipped when Piper is unavailable (build never breaks).

### Changed
- `render_motion_video`: when the render subprocess fails because Chromium is missing, return a clear
  `render_unavailable` error with workarounds (PNG+TTS video, static SVG/PNG asset, or local render)
  instead of a raw HyperFrames stderr dump.

## [1.2.0] — 2026-06-24

Richer media authoring (content_slide blocks, per-item images, inline assets), screen reorder, and
QTI 2.1 export. **24 MCP tools.** All additive — existing specs unchanged, no server-side LLM.

### Added — richer media authoring + screen reorder (W9)
- **`content_slide` multi-block (`blocks[]`)** — optional ordered list of `{html}` / `{asset_id, caption?}`
  blocks → interleave `paragraph → image → paragraph → image` in one screen (no more 3-consecutive-slide
  workaround). Falls back to `body_html`/`media_asset_id` when `blocks` is absent; `body_html` is now optional.
- **Per-item images** — optional `image_asset_id` on `accordion` and `tabs` items, on `timeline`
  events; `front_asset_id`/`back_asset_id` on `flashcards`. All optional/backward-compatible.
- **`reorder_screens` tool** (24th MCP tool) — reorder a project's screens to an explicit id order
  (validates the set matches all existing screens). `add_screen` still appends.
- **Inline images in `*_html`** — sanitizer now allows `data:` URIs on `<img>` (inline base64
  icons), and `{{asset:<id>}}` tokens in any `*_html` interpolate to the packaged asset (self-contained,
  unlike external `<img src>`). Validator extended to check per-item / block asset references.

### Added — QTI 2.1 export (W8a)
- **`export_qti` tool** (23rd MCP tool) + `core/qti.py`: quiz screens → IMS QTI 2.1 `assessmentItem`
  XML. `mcq`/`true_false` → `choiceInteraction`, `fill_blank` → `textEntryInteraction`, with
  `correctResponse` + standard `match_correct` response processing. Deterministic XML (lxml), so
  content becomes portable to QTI-compatible systems. Unmappable types are silently skipped (no fake
  conversion); no server-side LLM. Returns `{count, items:[{filename, xml}]}`. See `docs/QTI.md`.

## [1.1.0] — 2026-06-15

Composable game engine + adaptive learning + telemetry. 22 MCP tools. All additive — existing
screen types untouched, no server-side LLM (intelligence is in the spec + deterministic runtime).

### Added — composable game layer
- **`game` screen type** — a composition of mechanic primitives (`score`/`lives`/`timer`/`hints`) +
  declarative `when <event> if <cond> then <action>` rules + branching content nodes, rather than a
  fixed game type. Logic single-sourced in vitest-tested `components/engine/*.js`, lazy-inlined into the
  package at runtime via `core/engine_bundle.py`. Templates: case simulation, escape room. Game
  accessibility enforced (hint text, timer extend/disable — WCAG 2.2.1). See `docs/GAME-ECD.md`
  (Evidence-Centered Design), `docs/GAME-A11Y.md`.
- **`adaptive_practice` screen type** — competency estimation → ZPD/flow difficulty calibration.
  Two estimators behind one interface: **Elo** (Rasch-like, closest-to-target difficulty) and **BKT**
  (Bayesian Knowledge Tracing, mastery tracking + early stop). Tiny state (SCORM 1.2 4096B budget).
  See `docs/GAME-ADAPTIVE.md`.
- **`game`/`adaptive_practice`** are now in `list_screen_types` (28 screen types total).

### Added — telemetry (xAPI / cmi5)
- Course-level `xapi` config (default **off**). Engine events (choice/answer/adaptive observe/hint/
  finalize) become xAPI statements; W4 ability/mastery flow to the LRS as result extensions. cmi5
  launch parsing + explicit-LRS mode, best-effort POST with offline buffer; **no LRS → silent no-op,
  SCORM tracking never breaks**. See `docs/GAME-XAPI.md`.

### Added — anti-slop quality gate
- **`lint_course` tool** + `core/antislop.py`: research-based deterministic checks for game/adaptive
  specs (intrinsic integration, meaningful choice, scaffolding balance, adaptive spread, a11y).
  Structural bugs (unreachable node, fake choice) **block the build** via `validate_project`;
  pedagogical smells are advisory warnings. See `docs/GAME-ANTISLOP.md`.

### Added — examples & docs
- `examples/games/`: `clinic-triage-game`, `escape-cipher-game` (cmi5), `adaptive-statistics` (Elo),
  `adaptive-fractions-bkt` (BKT), `lab-safety-game.en` (i18n). All pass the anti-slop gate.
- `docs/GAME-ECD.md`, `docs/GAME-ADAPTIVE.md`, `docs/GAME-XAPI.md`, `docs/GAME-ANTISLOP.md`,
  `docs/GAME-TEMPLATES.md`.

### Added — SCORM conformance
- `validate_package` validates the generated `imsmanifest.xml` against the official ADL/IMS XSD
  schemas for SCORM 1.2 and 2004 4th Edition. ADL schemas are vendored (`runtime/schemas/adl/`);
  IMS/W3C schemas are fetched at runtime + cached (not redistributed), pinned by sha256. Validation
  is fully offline (`no_network`); `SCORM_SCHEMA_DIR` enables air-gapped use; missing schemas degrade
  gracefully to a non-blocking `schema_unavailable` warning. `ValidateOut` gains an additive
  `warnings` field. `docs/CONFORMANCE.md` — SCORM Cloud round-trip is the gating proof, XSD supporting
  (all example packages import with 0 errors and 0 warnings).

### Fixed
- **Manifest (2004):** removed `imsss:controlMode flow/choice` from the single-SCO leaf `<item>`
  (SCORM Cloud parser flags it as only applicable to cluster nodes, [6022]).

## [1.0.0] — 2026-06-11

First stable release. 19 MCP tools, production-deployed.

### Added — authoring surface
- **26 screen types**, incl. games (`decision_scenario`, `escape_room`, `term_match_race`),
  customized results (`results_breakdown`), participation (`poll`), and visuals
  (`labeled_diagram`, `data_chart`, `image_compare`).
- **G1 gamification HUD** — unified header showing levels (points→level badge), lives, and points
  (`levels`, `lives_var`, `max_lives`); intrinsic-mastery oriented.
- **Cross-device compatibility** — content overflow scrolls (no clipping), mobile/≤640px reflow
  (drop the fixed-canvas scale → natural flow + readable fonts + vertical scroll), touch drag-and-drop
  fallback, `touch-action` on controls. See `docs/DEVICE-COMPATIBILITY.md`.
- **Topic-distinct themes** — `editorial`, `playground`, `boardroom-clinic` (plus existing presets);
  themes exploit heading fonts, radii, patterns and `custom_css` so the interface differs by subject.
- Curated example courses (`examples/games/`, `examples/visual/`, `examples/showcase/`,
  `examples/themed/`); game-design guide (`docs/GAME-PATTERNS.md`); `docs/SCREEN_TYPES.md` for all 26.

### Tooling
- Real lint-gate pre-commit (ruff on all files) + weekly dependency report (deduped).

### Added — initial release
- Initial public release of the edumints SCORM MCP server.
- 18+ screen types (content, quizzes, drag & drop, hotspot, branching, accordion, tabs, flashcards,
  matching, sorting, timeline, lottie, guided simulation, video, summary).
- Slide-stage player: fixed-aspect scalable stage, player bar (play/seek/captions/menu/replay),
  narration-synced timeline reveal, section-grouped menu, adjustable stage size, mobile/responsive,
  inline SVG icons.
- Variables/state, conditional visibility, branching, points & timer gamification.
- Cross-MCP media ingestion (`add_asset`), ffmpeg processing, programmatic video (HyperFrames),
  built-in offline Turkish TTS (Piper), and a local media helper.
- Themes/accessibility, SCORM 1.2 & 2004 packaging, opt-in/lazy heavy features.
