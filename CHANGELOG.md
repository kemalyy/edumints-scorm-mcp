# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — opt-in strict anti-slop mode (SP-5 / B4-strict)
- New optional `strict` parameter on `lint_course`, `build_package` and `build_from_spec`
  (`bool | None`, default `None` = server default). When strict is on, a curated set of advisory
  WARN rules is promoted to blocking: `penalty_without_rationale` (the fake-choice-adjacent rule —
  `fake_choice` itself is already error tier), `text_only_run`, `visual_poverty`,
  `missing_alt_text` and `decorative_score` (`core/antislop.py` `STRICT_PROMOTED_CODES`).
  `lint_course(strict=True)` reports these as `error` severity in the counts/issues (plus a
  `strict` flag in the output); strict builds refuse the course with the existing
  `validation_error` ToolError, each promoted message prefixed `[strict:<code>]` for an actionable
  payload. `ANTISLOP_STRICT=1` flips the server-wide default to strict; an explicit
  `strict=True/False` always wins. Default behavior is unchanged — regression tests prove a
  warn-laden course still builds non-strict (`tests/test_strict_and_zipcheck.py`).

### Added — build-time artifact zip validation (SP-5 / B1 delta)
- The packager now runs `core/validator.validate_zip` on the produced zip *before* marking a build
  job done. The gate lives at job completion (`Packager._run`) — the single point both the
  fast-path and the async path go through — so `build_status`/download can never serve an
  unvalidated package. On structural errors the package is not registered, the corrupt zip is
  deleted from disk and the job fails (`ArtifactValidationError`); in the fast-path the failure
  additionally surfaces as a hard `ToolError("build_error", ...)`. `schema_unavailable` stays
  non-blocking and rides the response in a new additive `warnings: list[str]` field on
  `BuildOut`/`BuildFromSpecOut` (in-process, advisory — empty after a server restart).

### Added — build_status tool (#94)
- New `build_status(project_id)` MCP tool (30th tool): polls the newest build job for a project
  after `build_package`/`build_from_spec` returned `job_id`+`status` past the fast-path window.
  Ownership-checked like every other tool; the read is store-backed (`active_job_for_project`,
  newest job) so polling keeps working across server restarts. Returns `BuildOut` — `download_url`
  and `size` are populated only when `status="done"`; a project with no build job at all raises a
  clear `not_found` ToolError. Never triggers a new build.

### Added — WWW-Authenticate on custom-route 401s (#98)
- The five bare-JSON 401 responses of the custom Starlette routes (`GET /usage`, `POST /keys`,
  `GET /keys`, `DELETE /keys/{key_id}`, `GET /projects`) now carry a `WWW-Authenticate` header per
  the MCP 2026-07-28 authorization spec (RFC 9728). With OAuth enabled the challenge points at the
  protected-resource metadata URL exactly as RemoteAuthProvider mounts it
  (`/.well-known/oauth-protected-resource` inserted between host and resource path, resource path =
  `PUBLIC_BASE_URL` path + `/mcp` — derived, not guessed; a test cross-checks against the SDK's
  `build_resource_metadata_url`). In API-key-only mode the header is a plain `Bearer`. 200 paths
  are unchanged.

## [1.6.0] — 2026-07-26

Demo surface hardening + SCORM contract completion + evidence & process. The permanent `/demo`
pages gain a real lifecycle (store-backed metadata, quota, caching, OG tags, embedding); the
generated packages gain mastery score in the manifest, overflow-safe suspend data, LOM metadata
and per-objective LMS reporting; the runtime probe now gates CI. All additive — existing specs
build unchanged.

### Fixed — suspend_data v2 order fingerprint (Batch 3 / S5)
- `components/engine/scorm.js` `encodeSuspend`/`_decodeV2`: the v2 suspend_data envelope now embeds
  a deterministic djb2 fingerprint of the screen `order` array. Previously, if a course package was
  republished with screens reordered, inserted, or deleted, an old v2 payload would decode its
  positional cursor/visited/results/ix indices against the *new* order and silently misattribute
  progress to the wrong screens (wrong scores, wrong resume position). On decode, a fingerprint
  mismatch (including append — decided as the simplest safe policy) now returns a fresh-start state
  instead of corrupted data; v1 (legacy id-keyed JSON) migration is unaffected since it was already
  immune to reorder by design.

### Added — Accessibility conformance statement (Batch 3.2 / A1)
- `docs/ACCESSIBILITY-CONFORMANCE.md`: WCAG 2.2 AA partial-conformance statement for produced course players — a 28-screen-type matrix (keyboard / screen reader / motion / time limits) grounded in verified code behavior, honest known limitations (no video captions/WebVTT, pointer-only `drag_drop`, non-adjustable `term_match_race`/`timer_sec` countdowns, Lottie ignoring reduced-motion), test methodology (non-blocking axe CI audit, validator timer gate, alt-text lint), and RTL/language notes.

### Added — CI: scorm-probe gate (Batch 3.1 / Y1)
- `tests/runtime/scorm-probe.mjs` (the real-browser S1/S2/S3/S4 behavioural probe) is now wired into
  CI via a new blocking `scorm-probe` job in `.github/workflows/ci.yml` — previously it existed only
  as a local `npm run scorm-probe` script and ran in nobody's CI. Unlike `a11y-audit`, this job is
  NOT `continue-on-error`: a broken `cmi.interactions`/`cmi.objectives` write now fails the build.
- The probe script itself exits 0 both on "all checks passed" and on "environment unavailable"
  (missing browser/Python) so local runs never fail spuriously. Since that skip must never happen
  silently in CI, the workflow step greps the probe's own log for the skip marker and turns it into
  an explicit `::error::`-annotated job failure if the environment came up unexpectedly broken —
  verified locally by simulating both a broken interactions write (probe fails as expected) and a
  forced environment-skip (job now fails loudly instead of passing green).
- `.github/workflows/ci.yml` itself was newly added to this repo (it previously only existed in the
  public mirror) with the same `test`/`lint`/`js-test`/`a11y-audit` jobs, so the private dev repo now
  gets the same push/PR gate as the public one, plus the new `scorm-probe` job.

### Added — contribution & language policy (Batch 3.3 / Y4)
- New `CONTRIBUTING.md`: dev setup + guidelines, plus a one-sentence language policy — code,
  comments, commits, and `CHANGELOG.md` are English; `docs/` and READMEs are multilingual, with
  `README.tr.md` treated as first-class.
- `CHANGELOG.md` converted to a single language (English), including history: the previously
  Turkish `[Unreleased]` entries (Batches 1 and 2) and the Turkish W10 subsection under `[1.5.0]`
  were translated in place (structure, entries, and version headings preserved faithfully; no
  content summarized or dropped). Quoted literal default strings that are actual runtime values
  (e.g. `"Doğru!"`) were intentionally left untranslated since they document real code behavior.
  Bulk translation of existing code comments is explicitly out of scope for this change.

### Added — cmi.objectives goal reporting (Batch 2.4 / S2)
- Optional `objectives: list[Objective]` on `CourseSpec`/`Project` (id required + machine-friendly
  `[A-Za-z0-9_.-]{1,255}`; `description`/`success_criteria` optional, authoring-only — no text is
  printed into the package). Optional `objective_ids: list[str]` on ALL graded screen types
  (14 QUIZ_TYPES). Unknown objective references and duplicate course objective ids are a HARD error
  in `validate_project`.
- Single-source objective aggregation in `components/engine/scorm.js` (S1 pattern: pure, DOM-free,
  deterministic; vitest): `aggregateObjectives` (screen results + screen→objective map → per-objective
  correct/total/scaled over the course), `objectiveElements` (1.2↔2004 element/vocabulary differences
  in ONE place), `objectiveIndices` (collision-free, id-based indexing against records the LMS may
  already hold).
- The runtime writes at the SAME lifecycle point as the score commit (`evaluate()`) —
  1.2: `cmi.objectives.n.id` + `.score.raw/min/max` (0–100) + `.status`;
  2004: `.id` + `.score.scaled` (0–1) + `.success_status` + `.completion_status`.
  Score is only written once ≥1 answer exists; status vocabulary: never attempted →
  `not attempted`/`unknown`, partially attempted → `incomplete`, fully attempted → `passed`/`failed`
  (threshold = course `passing_score`, consistent with the S6 primaryObjective/minNormalizedMeasure).
- POLICY: a cmi record is written only for objectives bound to ≥1 graded screen — an unbound
  objective is an authoring error, caught by the new `unbound_objective` WARN in `lint_course`
  (does not block the build).
- Manifest (2004 only): course objectives are emitted after `imsss:primaryObjective` as non-primary
  `imsss:objective/@objectiveID` entries (bound ones, in course order; no rollup/rule → inert on the
  leaf, `controlMode` still absent). When `passing_score` is 0, sequencing is not emitted at all
  (2.1 contract) → objectives become runtime-only. Both versions validated against the official XSDs
  (0 errors). If a 2004 LMS pre-populates these records, the runtime resolves indices by id and never
  rewrites an existing `.id` (proven in scorm-probe with a fake-LMS pre-populate scenario).
- `tests/runtime/scorm-probe.mjs`: a 3-objective / 9-question course — verifies in a real browser
  (1.2 + 2004) that 3 SEPARATE objective records reach the fake LMS, with correct scores
  (`33`/`0.3333`) and correct vocabulary differences.

### Added — LOM metadata (Batch 2.3 / S7)
- Optional `metadata: CourseMetadata | None = None` field on `CourseSpec`/`Project` (additive):
  `description`, `keywords: list[str]`, `intended_audience`, `typical_learning_time` (an ISO 8601
  duration string, e.g. `"PT1H30M"` — light regex validation; passed through
  `build_from_spec` → `Project.metadata`).
- Optional `imsmd:lom` block inside `<metadata>`: `general/title` (localized `langstring`, from
  `project.title`) + `general/language` are ALWAYS emitted (required/defaulted fields on `Project` —
  a minimal-but-real LOM was preferred over an LOM-less manifest). `general/description`,
  `general/keyword` (one per entry), and `educational/typicalLearningTime/datetime` are emitted ONLY
  when the corresponding `project.metadata` field is set (no field → no element). `intended_audience`
  was not mapped to LOM — forcing free text into `imsmd:intendedenduserrole`, which requires a closed
  vocabulary, would be the wrong semantics.
- Both SCORM versions use the IMS Meta-data **1.2.4** binding (`imsmd_v1p2p4.xsd`, namespace
  `http://www.imsglobal.org/xsd/imsmd_v1p2`) — the "expected" official 1.2.1 binding for SCORM 1.2
  (`imsmd_rootv1p2p1.xsd`) was DELIBERATELY not used: that schema defines `grp.any` inside
  `generalType`/`educationalType`/… with `namespace="##any"` (which also covers its own namespace) →
  a UPA (Unique Particle Attribution) violation with neighbouring optional elements; libxml2 cannot
  COMPILE that schema at all (it silently falls back to `schema_unavailable`, so XSD validation never
  runs). The 1.2.4 binding (`##other`) is UPA-clean and actually compiles and validates.
  `runtime/schemas/ims_sources.json` + `driver_12.xsd`/`driver_2004.xsd` updated
  (fetch+sha256-pinned, imsglobal.org — IMS/W3C schemas are not vendored).
- `core/schema_validate.py`: the `xml.xsd` import-URL rewrite rule was extended (besides
  `/2001/xml.xsd`, the `/2001/03/xml.xsd` variant is now also mapped to the local `xml.xsd` — the
  form used by `imsmd_v1p2p4.xsd`). Both cases validated against the official IMS XSDs (0 errors).

### Added — suspend_data overflow safety (Batch 2.2 / S5)
- Compact v2 suspend_data encoding (`components/engine/scorm.js`): base36 indices instead of screen
  ids, a `visited` hex bitfield, minimal results/ix — on a synthetic 64-screen / 30-graded-item
  course the payload stays well under the SCORM 1.2 limit (4096). The old (v1 flat JSON) format is
  recognized and migrated: courses already in production survive a resume after a package update.
  On limit overflow, navigation history is dropped first; `vars` and interaction indices (`ix`) are
  now PRESERVED (the v1 fallback used to drop both → re-answered questions could produce duplicate
  interactions on the LMS).
- `lint_course`: `suspend_size_risk` WARN — for a 1.2 target, if the estimated suspend size (via a
  conservative mirror of the encoder's cost model) exceeds the 4096×0.9 threshold, the author is
  warned IN ADVANCE (to decide whether to split the course / move to 2004; not a FAIL).
- Runtime visibility: suspend_data writes are now checked (`sSetChecked`); on a write error or
  truncation, a `console.warn` (once per event) +, if an xAPI forwarder is configured, a
  `suspend.trouble` statement (suspend-kind/size/limit extensions). Never throws.

### Added — passing grade in the manifest (Batch 2.1 / S6)
- SCORM 1.2: if the course `passing_score` is non-zero, `adlcp:masteryscore` (0–100 integer scale)
  is emitted under `<item>`, right after `title` (per the imscp `itemType`:
  `title?, item*, metadata?, ##other`).
- SCORM 2004: `<adlcp:completionThreshold>` + `imsss:sequencing → imsss:objectives →
  imsss:primaryObjective → imsss:minNormalizedMeasure` (0–1 scale, `passing_score/100`, e.g. `0.8`).
  `imsss:controlMode` was NOT added ([6022] rationale still applies — flow/choice is meaningless on
  a leaf item).
- When `passing_score` is 0 (or unset) → none of these elements are emitted in either version
  (additive, backward compatible). Both cases validated against the official ADL/IMS XSDs (0 errors).
- **Fix (review Important-1):** in both versions, emission was ADDITIONALLY gated on the course
  having ≥1 graded screen (QUIZ_TYPES) — otherwise, with the default `passing_score=80`,
  content-only courses emitted `masteryscore`/`completionThreshold`/sequencing even though the
  runtime never wrote `score.raw`, which on older 1.2 LMSs turned the mastery override from
  "completed" into "failed".

### Fixed — demo surface (Batch 1.1)
- The review UI (FAB/panel) is no longer rendered at all on `/demo/{slug}` pages — previously it was
  both visible AND broken (`rToken()` only resolved `/preview/` paths). Added an independent
  `review: bool = False` flag to `render_html`; the two roles of `__PREVIEW__` (asset embedding vs.
  review UI) were split apart. `/preview` behaviour is unchanged. Note: the package HTML changed at
  the byte level — the dead (hidden, JS-disabled) review markup it used to contain is no longer
  emitted at all; no behavioural difference.

### Added — demo lifecycle (Batch 1.2)
- Demo metadata now lives in the store (`DemoMeta`: slug, project, owner, title, language, size,
  timestamps) — ownership is checked against the store, not the `.owner` file (legacy files are
  honoured once and migrated). Demo HTML size is now included in the owner's quota accounting.
- New `list_demos()` (28th) and `unpublish_demo(slug)` (29th) MCP tools: inventory + removal
  (ownership-checked; after removal `/demo/{slug}` → 404).

### Added — demo caching + sharing + embedding (Batch 1.3–1.5)
- `/demo` responses now carry `ETag` + `Cache-Control: public, max-age, must-revalidate`; on a
  matching `If-None-Match`, an empty-bodied `304`. `/preview` (TTL-based) was deliberately left out
  of scope.
- OG/twitter meta tags (`og:title/description/type/url` + `twitter:card`) — if a field is empty, the
  tag is not emitted at all; an optional `canonical_url` parameter was added to `render_html`
  (additive).
- `/demo/{slug}?embed=1` chromeless embed mode — the same cached HTML, driven client-side via
  `body[data-embed="1"]` CSS; a `Content-Security-Policy: frame-ancestors` header sourced from the
  `DEMO_FRAME_ANCESTORS` env var (default `'self'`), documented in `.env.example`.

### Added — permanent demo links (W12)
- New `publish_demo` MCP tool (27th tool) + `GET /demo/{slug}` route: publishes a project to a
  TTL-free, permanent public URL (README/showcase links no longer break). Upsert; slug is locked to
  its owner; the slug regex prevents path traversal.

### Added — systematized visual storytelling (W11)
- Two new visual-density rules (WARN) in `lint_course`: `text_only_run` (≥4 consecutive screens with
  no visual) and `visual_poverty` (<25% visual screens in an ≥8-screen course) — "walls of text" are
  now machine-checked.
- New `search_images` MCP tool (26th tool): CC0/Public-Domain image search via Openverse/Wikimedia;
  results carry license/author/source info, downloaded via the existing `add_asset`. The query is
  URL-encoded (no CC0 filter bypass), each result gets a per-item license-family check, and all API
  requests go through SSRF protection.

### Added — `search_images` (W11 part 2)
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

### Added — theme style/brand layering (W10)
- 3 new "style variant" theme presets (`style-minimal`, `style-playful`, `style-premium`) — the
  structural personality (shadow, border, button behaviour) lives entirely in `custom_css` and only
  references `var(--c-*)` tokens, with no hardcoded brand colour; freely composable with any brand
  palette via `set_theme`.
- New `extends` directive for theme preset loading — a preset can inherit from another and override
  only the difference (`style-playful.json` extends `playground` — the CSS logic lives in a single
  source, not copied). Circular inheritance is detected and rejected.
- `ThemeTokens.logo_asset_id` is now actually rendered — the packaged logo image replaces the brand
  spot in the player chrome (with accessible alt text via `ThemeTokens.logo_alt`).
- New `ThemeTokens.custom_fonts` — auto-generates an `@font-face` from a packaged `.woff2` asset,
  letting corporate fonts be embedded without an external CDN dependency (so SCORM packages can run
  offline/in-LMS).
- `lint_course` gained a new `missing_alt_text` branch — WARNs when a theme has a logo but no
  `logo_alt`.

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
