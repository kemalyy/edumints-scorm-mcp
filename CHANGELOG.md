# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
