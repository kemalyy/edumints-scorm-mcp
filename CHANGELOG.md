# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added — artifact→SCORM: `embed_html` ekran tipi + `wrap_artifact` / `html_to_asset`
Keyfi kendine-yeten HTML'i (Claude artifact, tek dosyalık uygulama) sandbox'lı iframe'de
çalıştırıp LMS'e izlenebilir hâle getirir.
- **`embed_html` ekran tipi.** `html_asset_id` (zorunlu), `completion` = `on_view` |
  `on_message` | `time_threshold`, `min_seconds` (≥0; `time_threshold`'da >0 zorunlu),
  `aspect` = `fill` | `16:9` | `4:3`. QUIZ_TYPES dışı — skorsuz; skor yalnız köprüyle gelir.
- **postMessage köprüsü** (`components/engine/embed.js`): `complete` / `setScore` / `passed` /
  `failed` / `setStatus` → cmi yazımları. **Ayrı modül** — `scorm.js` her pakete koşulsuz inline
  edilir, oraya eklemek embed'siz kursların baytlarını değiştirirdi. Aynı nedenle embed CSS/JS
  **koşullu** üretilir → bayt-parite fixture'ı etkilenmez.
- **Kompakt kalıcı kayıt** `state.eb` (`{s,c,k,d,m}`): cmi anahtarları saklanmaz, `embedWrites()`
  ile türetilir (SCORM 1.2 3500 bayt suspend bütçesi + geri okumada beyaz-liste doğrulaması).
- **`html_to_asset`** — ham HTML → `text/html` asset (base64 gerekmez; `add_asset(source=https://…)`
  HTML kabul etmez).
- **`wrap_artifact`** — tek adımda proje + `embed_html` ekranı. `html_content` **XOR** `source_url`
  (boş string de "verilmiş" sayılır). Uzak yol `safe_fetch_asset` ile SSRF-korumalı; yalnız
  içerik-tipi kapısı genişler (`text/html`, `application/xhtml+xml`, `text/plain`) — çekilen mime
  kullanılmaz, asset her hâlde `text/html` saklanır. Tüm doğrulama proje yaratımından ÖNCE;
  sonraki adımda hata olursa telafi rollback (rollback hatası orijinali maskelemez).
- HTML sandbox'lı iframe'de çalışır, **sanitize edilmez** — kasıtlı tam uygulama.

### Added — `adaptive_practice` ustalık döngüsü (`loop_mode="mastery"`)
ALEKS tarzı döngü: yanlışta ipucu (scaffold), aynı becerinin farklı öğesi, doğruya kadar yinele.
- `AdaptiveItem.scaffold_html`, `loop_mode` = `sample` | `mastery`, `scaffold_on_wrong`,
  `score_mode` = `ratio` | `mastery` (hep-ya-hiç), `related_retry`, `max_consecutive_wrong`.
- **Tekrarda cevap arayüzü yeniden etkinleşir** — aksi hâlde ilk yanlıştan sonra şıklar disabled
  kalır, öğe hiç `done` olmaz ve ekran BİTMEZ (`related_retry` varsayılan açık olduğu için ana yol).
- **Probing direnci:** ustalık döngüsünde yanlış cevap doğruyu sızdırmaz — öğe çözülene dek
  (doğru cevap VEYA `max_consecutive_wrong` ile pes) ne doğru-şık işareti ne `explain_html`
  gösterilir; yerine scaffold gelir. `sample` modunda davranış eskisi gibi (reveal her zaman açık).
- Kazanılmış ipucu tekrarda görünür kalır — döngünün amacı bu.
- Anti-slop: `mastery_loop_without_mastery_score`, `scaffold_enabled_without_content`.

### Added — şıka özel gerekçe (`Choice.feedback_html`)
Quiz şıklarında şık başına gerekçe metni — doğru/yanlış ayrımından bağımsız, seçilen şıka özgü
açıklama gösterilebilir.

### Added — #126: `labeled_diagram` salt-gösterim (callout) modu — split-attention exhibit çözümü
Ölçüm raporunun (`docs/research/2026-07-30-layout-split-attention-measurement.md` §5.3)
belgelediği "exhibit okuma-protokolü" deseninin (3/6 sınıf-b split) kalıcı çözümü. Yeni ekran
tipi DEĞİL (tip enflasyonu 3.7) — mevcut `labeled_diagram`'a **parametre**.
- **`labeled_diagram.mode: "quiz" | "display" = "quiz"`.** `quiz` (varsayılan) etkileşimli/skorlu
  davranış **bayt-bayt** korunur (3.3 — regresyon testiyle kilitli; flat_menu fixture'ı kasıtlı
  yenilendi, diff = yalnız additive CSS bloğu + JS guard).
- **`display` = salt-gösterim callout:** her işaretçinin `text`'i görsel ÜSTÜNDE statik, daima
  görünür callout kutusu olarak (koordinat @num dot + leader line + metin) render edilir → yorum
  görselle BİRLİKTE durur, göz gidiş-gelişi (split-attention) elenir. select/skor/feedback YOK;
  `_quiz_shell` kullanılmaz. Metin gerçek DOM metni (yalnız `title` tooltip DEĞİL) →
  klavye + dokunma + ekran-okuyucu erişilebilir; ≤640px'te dikey listeye reflow.
- **Skor semantiği:** `display` ekranı skorlanmaz — `total_points` dışı, `is_quiz=false`,
  feedback config'e yazılmaz, `_has_scored_content` tek-başına puanlı-içerik saymaz (mastery/
  threshold regresyonu önlenir). Tek doğruluk kaynağı `core.project.is_display_diagram`.
- **Kanıt (E1):** `display` diyagram kanıt-taşıyabilir hedef (annotasyon yorum taşır) ama
  skorlanmaz → skorlu bir soru `evidence_screen_ids` ile bu exhibit'e yaslanabilir (K1).
- **AA:** callout renkleri yalnız gated token'dan (kutu surface-alt/text = `text_on_surface_alt`,
  num dot primary/contrast = `contrast_on_primary`); leader line dekoratif (1.4.11 muaf) →
  **kontrast matris deltası 0** (yeni çift yok; ref'ler dokümante edildi).
- Contract: CONTRACTS §labeled_diagram.mode + E1 kanıt listesi; `docs/SCREEN_TYPES.md` §22
  (yazım örneğiyle). Tests: `tests/test_labeled_diagram_callout.py` (14 — model/render/byte-parite/
  skor/kanıt + ölçülen exhibit c_email regresyonu).

### Added — Faz 6 (senaryo hattı 6/6): grafik okunabilirliği + dar lint'ler + karanlık mod
Grounded in the layout/split-attention measurement report
(`docs/research/2026-07-30-layout-split-attention-measurement.md`) — the generic
`SPLIT_ATTENTION` lint was measured out and intentionally NOT written (locked by test).
- **Chart readability (the 2/6 renderer gap):** line `data_chart` now renders a y-axis with
  nice-step (1/2/5×10^k) numeric tick labels, a light grid, and first/last point VALUE labels
  (symmetry with bar's on-bar values; single-series data model). Numeric texts carry
  `direction="ltr"` (RTL-safe anchors). Pie legend now carries raw value + percent
  ("A (30 · 30%)"); bar value labels regression-locked. Contract: CONTRACTS §12.5;
  tests `tests/test_charts.py`.
- **Chart colors are theme tokens:** `ColorPalette.chart_series` (8 colors) replaces the
  hardcoded `_CHART_COLORS` hex (report §4.1: 3.19:1 on premium dark). SVG uses
  `var(--chart-N, <fallback>)`; `--chart-N` vars are emitted ONLY for courses containing a
  `data_chart` (byte parity for chartless courses). Series 4/7 nearest-compliant fixes:
  `#7c3aed→#8040ee`, `#65a30d→#64a10d` (every series ≥3:1 on every shipped surface).
- **Narrow layout lint `MEDIA_NO_CAPTION`** (WARN, strict-promoted per E1 precedent):
  uncaptioned image block in `content_slide.blocks` + >80 words of screen prose. 0 hits
  today (measured) — a guard rail, not a penalty. `CHART_VALUES_UNREADABLE` was NOT
  implemented as a lint (the render fix makes labels unconditional → spec-level lint would
  be dead code); its final form is a test-level render invariant
  (`test_chart_values_unreadable_invariant`).
- **Dark mode as an orthogonal axis (plan 7.3):** `theme_mode: "light"|"dark"|"auto"`
  (CourseSpec + Project; default `light` = byte-identical output, test-locked). Dark is an
  overlay (`themes/_dark-overlay.json`) composed at render time onto the RESOLVED Faz 5
  layer chain (preset identity — typography/radii/motion/brand primary — preserved;
  primary/hover/focus fitted to dark grounds by deterministic nearest-compliant white-mix,
  already-passing inks unchanged). `auto` = pure-CSS `@media (prefers-color-scheme: dark)`
  block. The AA gate grew: 34→42 pairs (8 chart series) × 18 presets × 2 modes =
  **612→1512 assertions**, all green incl. focus/hover/disabled/selected states.
- **Deferred (issue kemalyy/edumints-scorm-mcp#126):** labeled_diagram display-only callout
  mode — the permanent fix for the exhibit reading-protocol pattern (3/6 measured splits).

### Added — Faz 4 follow-up: suspend truncation ladder + republish-resume resilience
- **Truncation ladder** (`encodeSuspendFit`): on overflow, data drops bottom-up with re-measure
  after every rung — position (id-based `z` record: screen id + node id + `content_version`)
  NEVER drops › objective/score state › per-page answers › learner free text (`xp`) › history.
  The rung is written into the envelope (`t` short key); the player treats state as partial
  per rung (linear back-nav, exploration placeholders, `g`/`e` score floor via
  `mergeObjectiveSnapshot` — scores never regress, rung-4 linear visited approximation).
- **All measurement in UTF-8 BYTES** (`byteLen`/`byteSlice`): working budget
  **`SUSPEND_BUDGET_12` = 3500 bytes** (rest of the 4096 limit reserved for LMS escaping
  overhead; same ratio for 2004). Fixes the Turkish multi-byte trap (ç ğ ı ö ş ü = 2 bytes);
  `setExploration` now caps at 500 bytes, never splitting a character. Envelope fields are
  provably ASCII (test).
- **Loss is never silent and never learner-facing**: `console.warn` ALWAYS (bytes + budget +
  rung; independent of xAPI/LRS), xAPI `suspend.trouble` additionally when an LRS is
  configured; SCORM offers no cheap learner-invisible LMS error channel (documented decision).
  New `trimmed` issue kind for ladder drops. Author-facing half: compile-time worst-case
  projection (`estimate_suspend_size`, now in bytes, including the new envelope fields) warns
  **`SUSPEND_OVERFLOW`** with the projected number vs the 3500 budget — surfaced by
  `scenario_compile`'s lint report and by direct `build_from_spec` lint alike.
- **Republish-resume read ladder** (`resumeSuspend`): an orderFp mismatch no longer wipes the
  attempt. Positional fields are discarded (misattribution protection preserved), id-based
  fields survive, and the `z` position record resolves: node alive → resume silently (exact
  screen if it survived, else the node's new first screen); node gone but screen alive →
  resume at the screen's NEW node + friendly notice; both gone (or pre-ladder payload) →
  course start + notice — no silent reset. Notice is non-technical, i18n tr/en
  (`resume_updated`/`resume_restart`), `role=status` `aria-live=polite`, dismissible.
  `COURSE.content_version`: deterministic djb2 digest (20-bit int) of ordered node + screen
  ids — equality-only semantics, source-independent, no mutable counter.
- **ID stability (precondition)**: verified `compile_scenario` passes ids through untouched
  (mid-outline insert / reorder never renumbers — tests). Deleted page/node ids are retired
  (`ScenarioDocument.retired_ids`) and can never be reused; upserts reject retired ids.
- Probe: real-browser republish scenario (build → enter node 2 → suspend → modify outline +
  recompile → relaunch → resumes at the surviving screen + accessible notice; silent full
  resume stays notice-free). Acceptance #12 re-run against the 3500-byte budget.
- Fixture regenerated (deliberate engine/runtime change — the 3.11 "no new envelope fields"
  invariant is consciously revised: the only outline cost is the `z.n` node id).

### Added — scenario line Faz 5: theme consolidation + automated AA contrast gate — 5/6
- **`themes/_tokens.json` base layer**: the shared semantic token set (kept byte-synced with
  `ThemeTokens` model defaults by a bidirectional drift test). Every shipped preset (18,
  incl. `corporate/*`) is now a **thin override layer** reaching `_tokens` through its
  `extends` chain — only differing fields remain in each file. Consolidation verified
  byte-identical: resolved tokens AND rendered HTML per theme hashed against master before
  the AA fixes below. Resolved tokens are fixture-locked (`tests/fixtures/themes_resolved.json`).
- **Audience override layer (mechanism only, no packs shipped)**: layer order is now
  `_tokens → style preset → audience override (themes/audience/<pack>.json, if present) →
  course custom` (CONTRACTS §1.1). Audience files are narrow overrides: `extends` is
  rejected (`AUDIENCE_NO_EXTENDS`), `name` is ignored (audience_pack ≠ theme, 3.4), screen
  types can't be constrained (3.7 — schema rejects unknown fields), missing file is a
  contracted no-op (`themes/audience/_README.md`). `audience=None` resolution is
  byte-identical to before (3.3).
- **Automated AA contrast gate** (`tests/test_theme_contrast.py`, pure-python WCAG 2.x math,
  no deps): a 34-pair ink×surface matrix derived line-by-line from the CSS the renderer
  actually emits (each pair cites its source selector), including **state variants**:
  disabled (effective composited colors through `opacity`), placeholder, secondary/helper
  text, focus ring (1.4.11 non-text ≥3:1 against both adjacent surfaces), hover, and
  selected/active tints (`color-mix` reproduced gamma-space per CSS Color 5). Runs for every
  shipped preset **and** every preset × audience-override combination automatically; a
  negative-control test proves the gate catches a deliberately broken theme.
- **AA fixes (3.5 — floor, no exceptions)**: 15/18 themes failed the gate; fixed by
  nearest-compliant lightness adjustment (hue/saturation preserved). Base `_tokens` (and
  synced `ColorPalette` defaults): `text_muted #71717a→#6c6c75`, `success #16a34a→#168139`,
  `error #dc2626→#cb2323`, `warning #d97706→#975606`; 13 presets carry additional per-theme
  deltas (full list in PR body). CSS state fixes: focus rings are now **solid
  `var(--c-focus)`** (a 50%-alpha ring mathematically cannot reach 3:1 on light themes),
  `::placeholder` pinned to `--c-muted` (real text — not UA grey), `.title-kicker` opacity
  removed (real text at `opacity:.7` broke 4.5), disabled button opacity `.45/.4 → .55`
  (in-house ≥2:1 perceivability floor; WCAG 1.4.3 exempts inactive controls — documented).
- **No-CDN font gate**: theme files may contain no external URLs; rendered HTML per theme is
  greped for CDN/font-host markers. Theme font stacks are name-references with system
  fallbacks; actual embedding stays the `custom_fonts` woff2-asset `@font-face` path (W10).

### Added — scenario line Faz 4: position, per-objective progress, resume-to-node, locks — 4/6
- **`OutlineNode.unlock_rule`** (`"free" | "sequential"`, additive, default `"free"`):
  `sequential` locks a node until every screen in the **previous sibling's subtree** has been
  visited ("complete" = visited; score thresholds can never lock navigation — accessibility
  floor). New hard error **`UNREACHABLE_NODE`**: a sequential node whose previous sibling's
  subtree has no attached screens could never unlock (validator rejects; runtime defensively
  leaves such nodes open).
- **Position strip** (`#posStrip`, outlined courses only): "Ünite 1 · Bölüm 1.1 · 2/4" — node
  chain + within-node n/m; `aria-live="polite"` announces only on change; the n/m fragment is
  isolated `dir="ltr"` (RTL-safe); the ungrouped-screens label is server-resolved i18n (tr/en).
- **Per-node progress** in the tree menu (`.mtree-progress`, cumulative subtree n/m) and
  **results_breakdown section completion** (`.rb-comp`, "n/m completed") driven by the SAME
  `data-screens` mechanism as section scores — no parallel objective-progress machinery.
- **Lock UI**: locked nodes stay visible with `aria-disabled="true"`, the server-rendered
  reason (naming the blocking node, i18n) becomes visible and is part of the button's
  accessible name; the locked branch collapses; focusable-but-not-activatable, no keyboard
  trap.
- **Resume-to-node**: relaunch restores the exact screen, expands the node chain
  (`aria-expanded`) and re-seats `aria-current`; manual collapse choices are never overridden
  (only the active chain is expanded).
- **Hierarchical suspend (non-negotiable 3.11): NO new envelope fields** — `n` is derived from
  static config (`screens[cursor].node_id`), `s`/`st` already exist in the v2 envelope. Free
  text never enters suspend_data. Realistic 3-level × 30-page course: **780 chars < 4096**
  (vitest acceptance #12). Overflow now logs a greppable `SUSPEND_OVERFLOW` warning + xAPI
  `suspend.trouble` (no silent truncation). `estimate_suspend_size` provably unchanged by
  outlines (test).
- **Byte-parity repair**: Faz 4 helpers moved out of the unconditional scorm bundle into
  `components/engine/progress.js` (`window.SCORMP`, inlined **only** for outlined courses);
  all Faz 4 runtime lives in OUTLINE_JS — outline-less course HTML is byte-identical to the
  previous release (fixture-locked).
- Probe: 23 new real-browser checks (strip, lock semantics, focusability, resume expansion,
  suspend hygiene). Docs: CONTRACTS §2.1, ACCESSIBILITY-CONFORMANCE player section.

### Added — scenario line Faz 3: media federation (fill/match/provenance) — 3/6
- **`fill_media_slot`** (39th tool): fills a scenario page's media slot from a `data:` URI or
  https URL — DELEGATES to the same ingest internals as `add_asset` (SSRF guard + quota). Assets
  live in the **scenario asset home** (`ScenarioDocument.assets`, same `AssetRef` shape +
  `Store.put_asset` mechanics namespaced by `scenario_id`; scenario asset bytes now count into
  the storage quota). Hard gates (data-integrity class): **sniffed-MIME ↔ kind mismatch**
  (`kind_mime_mismatch` — magic bytes, declared MIME is never trusted) and **`A11Y_NO_TEXT_ALT`**
  for `role="kanit"` slots missing `alt_text` (plus `transcript_html` for audio/video), rejected
  before any byte is fetched. **sha256 content-dedup** (acceptance #9): same bytes → same
  `asset_id`, single storage. `provenance` (plan §5.4: source/tool/ref/generated_at/license_note)
  stored as given; `generated_at` server-stamped when absent.
- **`match_media_manifest`** (40th tool): matches a **metadata-only** manifest
  (`[{name,size,sha256,mime}]`) against unfilled slots — the server NEVER touches a filesystem
  path (acceptance #10: schema has no path field; negative grep test proves no directory-scan
  call in the federation module or the two tools). Signals: filename↔slot_id/spec/source_hint
  token overlap (Turkish chars ASCII-folded), MIME↔kind, size sanity, sha256 already-ingested
  ("already_ingested_dedup"). **Proposes, never assigns**: ambiguous → `proposed: null` +
  scored candidate list; deterministic ordering.
- **Client script `scripts/import_media_folder.py`**: standalone (stdlib; `requests` optional,
  NO server imports — tested), scans a local folder, builds the manifest, calls
  `match_media_manifest` over MCP HTTP, renders a proposal table, and on confirm (`--yes`)
  base64s files into `fill_media_slot` per approved match. `--dry-run` supported; without server
  info it prints the manifest + manual instructions. Fixture folder
  `tests/fixtures/media_folder/` (1px PNG + tiny mp3 + txt).
- **`assets/PROVENANCE.json` in the package** (acceptance #11): compiled courses embed one
  record per filled slot (`{page_id, slot_id, asset_id, role, kind, sha256, provenance}`,
  deterministic order, listed in the manifest). New additive `CourseSpec/Project
  .media_provenance` (default `[]`) — plain `build_from_spec` courses do NOT gain the file
  (backward-compat byte-parity class, tested).
- **Compile mapping per kind + asset injection**: `scenario_compile` injects REFERENCED scenario
  assets into `spec.assets[]` as `data:` URIs with ids preserved (slot references stay valid;
  refill leftovers never leak into packages). Slot→field mapping: image AND **data_chart →
  image fields** (DECISION: a data_chart slot carries a *rendered chart image* — the data_chart
  *screen* carries inline data, no asset field → `SLOT_NOT_ATTACHED` warn there); audio/video/
  lottie → their asset fields; **model_3d → `fallback_image_asset_id`** attached as image, else
  `SLOT_KIND_UNSUPPORTED` warn + slot skipped. A `role="kanit"` slot keeps the compiled
  content_slide in the evidence-capable set (media present — aligns with E1), tested.
- **Contract amendment (flagged)**: `MediaSlot.fallback_image_asset_id: str | None` — the ONE
  additive addition to the Faz-2-frozen MediaSlot contract (2D stand-in for kinds without a
  render path today). `scenario_gaps` warns `SLOT_KIND_UNSUPPORTED` when a model_3d slot lacks it.
- **Fix**: `scenario_compile(compile_and_build=True)` called `build_from_spec.fn` — an
  `AttributeError` under fastmcp 3.x (decorator returns the plain function); now a direct call,
  covered end-to-end by the PROVENANCE zip test.

### Added — scenario line Faz 2: scenario tools + gap report + compiler
- **Scenario document** (`core/scenario.py`, new — keeps hot files thin): `ScenarioDocument`
  (`schema_version: 1`, owner-scoped JSON blob, quota-counted) = hierarchical outline + pages.
  `Page` schema with `MediaSlot` (Faz-3 contract FROZEN now: `slot_id`, `role: kanit|aciklayici`
  — no decorative, `kind`, `spec`, `source_hint?`, `asset_id?`, `a11y`, `provenance?`) and
  **`EvidenceDecl`** — ENUM-forced discriminated union (oneOf, `extra=forbid`) with per-kind
  required sub-models: `islenmis_ornek` (steps min 2, each action+reasoning), `karsit_cift`
  (dogru/bozuk/fark), `anotasyonlu_artefakt` (artefakt_ref + anotasyonlar min 1), `ogrenci_kesfi`
  (kayit_yontemi + commit_prompt), `hatali_ornek` (hata/neden_yanlis/dogru_karsilik).
- **Objective inheritance**: nearest-ancestor wins (walk up from `page.node_id`); none →
  `ORPHAN_PAGE` (⛔). Compiled `objective_ids = [inherited] + extra_objective_refs` (dedup,
  stable order); dangling extra refs → ⛔.
- **`scenario_gaps`** (the compile GATE): `{ blockers, warnings, suggestions,
  evidence_binding_coverage_estimate }`. 9 blocker codes (ORPHAN_PAGE, DANGLING_*,
  SCORED_NO_EVIDENCE_FROM, OBJECTIVE_NO_EVIDENCE, EVIDENCE_KIND_MISSING, PREDICTION_SCORED,
  AUTO_GRADE_OPEN_TEXT); warnings (EMPTY_MEDIA_SLOTS, PHASE_NOT_IN_PACK via reused E2
  `_load_packs`, DURATION_DRIFT ±20%, NARRATION_ECHO — token containment ≥0.8/min 5 tokens);
  `SCREEN_TYPE_SUGGESTION` suggests-only (never auto-picks). All checks order-independent (3.9).
- **`scenario_compile`**: blockers → `ToolError` (refused). Else build_from_spec payload —
  outline passthrough with node objectives hoisted to course level + `pedagogy_pack →
  Objective.method_pack`; pages → screens (screen_type REQUIRED at compile); `copy.body_md →`
  sanitized HTML (deterministic md→html + nh3, no raw svg/canvas/script per 3.10);
  `evidence_from → evidence_screen_ids`; empty slots omitted (model_3d → SLOT_KIND_UNSUPPORTED
  warn); **phase NEVER emitted into the spec (3.2)**. Result carries the full `lint_course`
  report of the produced spec; optional `compile_and_build` chains into `build_from_spec`.
- **8 MCP tools** (30 → **38**): `create_scenario`, `scenario_upsert_node`,
  `scenario_upsert_page`, `scenario_reorder`, `scenario_tree` (compact summary), `scenario_gaps`,
  `scenario_compile`, `scenario_delete_node` (`strategy: refuse|reparent`) + `scenario_delete_page`
  (cleans `evidence_from` refs → gap, not dangle). Store: new `scenarios` table (projects/demos
  pattern; size counts into `total_bytes`).
- Acceptance: realistic mini scenario compiles → `lint_course` 0 errors + coverage 1.0 (#1);
  intentionally broken scenario → EXACT blocker set (#2); compile refusal (#3); phase grep-0 in
  compiled spec (#7); index-independence — evidence page after scored page compiles+lints clean
  (#8); backward compat — no schema changes to existing models (#5).

### Added — scenario line Faz 1: outline schema + hierarchical player menu
- **`OutlineNode`** (additive): hierarchical course skeleton — flat list + `parent_id`
  tree, `kind: "unit" | "section"` (no `"page"` on purpose — scenario pages are the Faz 2
  schema), machine-friendly id (`[A-Za-z0-9_.-]{1,64}`), optional per-node `Objective`
  (registers into the course objective NAMESPACE — id collisions with `course.objectives`
  or other nodes are hard errors) and optional `pedagogy_pack` declaration (carried only;
  no behavior in Faz 1).
- **`CourseSpec.outline` / `Project.outline`** (additive, default `[]`) propagated through
  `build_from_spec` like objectives; **`ScreenBase.node_id`** (additive) links a screen to
  an outline node.
- **Structural hard validation** (data integrity per non-negotiable 3.8): dangling
  `parent_id`, cycles (incl. self-parent), depth > 3 (root=1), duplicate node ids, dangling
  `screen.node_id`, objective-namespace collisions. Outline absent → zero new validation
  output. Nearest-ancestor objective inheritance and `ORPHAN_PAGE` are Faz 2 compile logic
  — deliberately NOT here (Faz 1 screens are still authored directly).
- **Hierarchical player menu skeleton**: with a non-empty outline the slide menu renders as
  a server-side APG tree (`role="tree"`/`treeitem`/`group`, native buttons, collapsible
  `aria-expanded`, `aria-level` ≤3 + screen leaves, `aria-current="page"`, roving tabindex,
  full keyboard incl. RTL-mirrored arrows, Home/End and first-letter type-ahead; RTL-safe
  logical-property CSS + `prefers-reduced-motion`). Screens without `node_id` render in a
  trailing flat group titled via new i18n key `menu_ungrouped` (tr+en). Behavior JS is
  injected via the existing review-slot pattern; CSS/JS/config appear ONLY on outlined
  courses — **with an empty outline the produced HTML is byte-identical to master**
  (fixture-locked: `tests/fixtures/flat_menu_small.preview.html`). Locking/progress/resume
  are Faz 4.
- **`Objective.outcome_type`** (additive, optional, machine-friendly): outcome-kind
  declaration; no behavior in Faz 1.
- **`CourseSpec.audience_pack` RESERVED** (additive): accepted, stored, validated as a
  machine-friendly string only — NO behavior until Faz 5. Distinct concept from
  `pedagogy_pack`/`method_pack` (non-negotiable 3.4).
- **scorm-probe**: new real-browser section proving tree collapse/expand, keyboard
  navigation and `aria-current` refresh (10 checks).

### Added — pack conformance checker (E2 / #111)
- **`Objective.method_pack`** (additive, optional): per-objective declaration of the pedagogy
  pack the objective follows (pack id, e.g. `"gagne-9"`). Objective-scoped on purpose — the
  skill-side `_SCHEMA.md` defines `conflicts_with` per OBJECTIVE, so one objective = one pack
  and conflicting packs may legally coexist on different objectives of the same course.
- **Vendored pack manifest** `runtime/pedagogy-packs.json`, generated by
  `tools/gen_packs_manifest.py` from the 12 skill pack files
  (`skills/authoring-scorm-courses/references/pedagogy/*.md` YAML frontmatter, same parsing
  approach as the skill repo's `validate_packs.py`). Deterministic projection (requires_platform,
  conflicts_with, evidence_phases — singular form normalized, scoring_allowed_from, phases);
  the server never reads the skill repo at runtime. A sync test fails when packs change
  without regenerating.
- **Four new `lint_course` WARN codes** (advisory wave: none strict-promoted, zero output
  without a `method_pack` declaration — fully backward compatible):
  - `unknown_method_pack` — declared pack id not in the manifest (other checks skipped for
    that objective);
  - `pack_conflict_on_screen` — the SAME screen is bound (`objective_ids`) to two objectives
    whose packs are mutually `conflicts_with` (one WARN per pack pair per screen);
  - `pack_platform_missing` — a `requires_platform` type is absent from the objective's usage
    (satisfied by: bound screen of that type, OR evidence target of the objective's scored
    screens, OR — for types that cannot carry `objective_ids` at all, e.g. worked_example /
    exploration / branching — course-wide presence; the bindable-type set is derived from the
    Screen union, no hand-maintained list);
  - `evidence_type_outside_pack` — a scored screen's evidence target type is not allowed in
    the pack's evidence phase(s) (`hepsi` = unconstrained; dangling/self ids stay E1's job).
- Deliberately deferred: a direct `scoring_allowed_from` order check requires screen-level
  phase tags (`Screen.phase` candidate field); the platform + evidence-type checks are its
  phase-tag-free approximations. Documented in CONTRACTS §1.3 E2.

### Added — `exploration` screen type (F2 / #113)
- New 30th screen type `exploration`: the inquiry primitive — learner input (an attempt,
  prediction or classification) is **stored** and **replayed on later screens** ("your
  prediction was…" attribution). Unlocks the input-replay upgrade for the `5e-inquiry` and
  `productive-failure` pedagogy packs; the learner's own output is K1 type-2 evidence.
- **Input kinds** (`input_kind`): `text` (free-text observation/attempt note, optional
  `placeholder`/`min_length`), `choice` (classification) and `prediction` (commit-then-see
  prediction taken *before* the experiment) — the latter two require ≥2 `choices`
  (model-validated).
- **Replay surface**: `<span data-exploration-ref="store_key"></span>` inside any rich-HTML
  field. The runtime injects the stored value as **textContent only** (never innerHTML —
  browser-probe-verified with an XSS payload); an empty value falls back to an i18n
  placeholder ("henüz cevaplamadın" / "not answered yet"). The sanitizer allowlist was
  extended *narrowly*: only `span`, only this one `data-*` attribute.
- **`store_key`**: machine-friendly replay address (`[a-z0-9_-]+`, ≤64), **unique across the
  course** — duplicates are a hard `validate_project` error.
- **Persistence**: new `xp` map ({store_key: value}) rides in the suspend v2 envelope tail
  (`components/engine/scorm.js` `setExploration`/`getExploration`; identity-keyed, not
  positional). Values are capped at **500 chars** (truncate + one console.warn);
  `estimate_suspend_size` counts 500 + key per exploration so SCORM 1.2 courses with many
  explorations trip the existing `suspend_size_risk` WARN. `encodeSuspendFit` keeps `xp`
  even when history is dropped; v1-JSON migration carries it through (vitest-covered).
- **Not scorable by design**: no `points` field, not in `QUIZ_TYPES`, never writes to score
  state (probe-verified) — the technical counterpart of A4's unscored-early-attempt
  exception (Z3: scoring the attempt turns exploration into a guessing contest).
- **Lint integration**: added to the E1 evidentiary set (`_EVIDENCE_CONTENT_TYPES`,
  unconditional — the learner's own artifact); not inherently visual.
- a11y/i18n: labelled `<textarea>`, `role="radiogroup"` labelled by the prompt, live-region
  saved indicator, RTL-safe CSS, all strings via the i18n table (tr/en).
- Fixture course `examples/exploration-5e.tr.json` (5e mini loop: prediction + choice + text,
  replay + evidence binding — lint-clean), `tests/test_exploration.py`, vitest codec coverage
  and an end-to-end browser probe section (store → replay → resume → XSS-safety).

### Added — `worked_example` screen type (F1 / #112)
- New 29th screen type `worked_example`: the authored-demonstration primitive (expert solution
  as a step list — each step is an **action + rationale + optional artifact** triple). Unlocks
  the `4cid` pedagogy pack (`requires_platform: [worked_example]`) and carries the most direct
  form of K1 type-1 evidence.
- **Fading levels** (`fading`, progressive disclosure of support): `full` (everything visible,
  fully worked), `partial` (actions visible, each step's *rationale* behind a per-step reveal
  button — learner constructs their own rationale first), `problem_only` (only the problem
  statement (`intro_html`) visible; each step body revealed on demand — skeleton).
- **Embedded UNSCORED self-explanation prompt** (`self_explanation_prompt_html`): renders a
  free-text area that is never written to any LMS field (poll pattern) — verified by test.
- **Not scorable by design**: no `points` field, not in `QUIZ_TYPES` (scoring a supported
  example measures the support, not the learner — Z2/Z3).
- **Lint integration**: added to the E1 evidentiary set (`_EVIDENCE_CONTENT_TYPES` —
  unconditionally evidence-carrying; scored questions may bind to it via `evidence_screen_ids`);
  counts as visual for the visual-budget rules only when a step carries an artifact (not in
  `_INHERENTLY_VISUAL_TYPES` — artifacts are optional); `artifact_caption` doubles as alt text
  (missing → `missing_alt_text` WARN); new WARN `step_without_rationale` for blank rationales.
- a11y/i18n: native-button reveals with `aria-expanded`/`aria-controls`, `prefers-reduced-motion`
  respected, RTL-safe logical CSS properties, all shell strings via the i18n table (tr/en).
- Fixture course `examples/worked-example-4cid.tr.json` (4C/ID mini course, all three fading
  levels, explicit evidence binding — lint-clean) + `tests/test_worked_example.py`.

### Added — evidence-binding lint checks (E1 / #110)
- `lint_course` now enforces the Layer-1 evidence rules from the authoring skill
  (`references/core/evidence-binding.md` K1–K3, `alignment.md` H3, `scoring-timing.md` Z1/Z3,
  `anti-slop.md` T1). All checks look at the *existence* of evidence only — there is deliberately
  **no order/position/phase check** (in branching/adaptive courses screen index ≠ presentation
  order; where evidence sits in the flow is the teaching method's choice).
- New additive schema field `evidence_screen_ids: list[str]` on every scored screen type
  (plural — a question may rest on several artifacts): the ids of the in-course evidence-source
  screens the answer is derived from. This explicit declaration is the *only* thing that counts
  as a binding; the heuristic candidate discovery (shared objective with a formative screen, or
  an evidentiary screen in the same `section`) only softens the default WARN message with
  suggestions and never satisfies the check — in strict mode only the explicit field passes.
- New additive schema field `source_item_count: int | None` on `CourseSpec`/`Project`
  (declaration-based): the item/heading count of the source document the course was derived from.
- New lint codes:
  - `unbound_scored_question` (WARN, strict-promoted): scored screen (Z1: `points` > 0 or writing
    to the points variable via `on_correct`) with no explicit evidence binding; message carries
    the K2 audit question and the K3 bind-or-drop procedure plus discovered candidates.
  - `evidence_screen_missing` (ERROR, blocks builds like unknown `objective_ids`): dangling or
    self-referencing evidence id. Only fires when the new field is used — backward compatible.
  - `evidence_target_not_evidentiary` (WARN, strict-promoted): a resolved evidence id points at a
    screen that cannot carry evidence (plain-text `content_slide` without blocks/media,
    title/summary/poll/results/branching, captionless video, promptless lottie, or another
    *scored* screen — formative `points: 0` screens are valid evidence per K1 type 3/5 and Z3),
    so the binding cannot be ceremonial.
  - `scored_over_objectives` (WARN, not promoted — H3 is explicitly warn-tier): scored screen
    count exceeds declared objective count + 1.
  - `source_item_parity` (WARN, declaration-based): screen count ≈ declared `source_item_count`
    (±10%, source ≥ 5) — the 1:1 copy smell from #110.
- `lint_course` output gains `evidence_binding_coverage` (0..1): explicitly-bound scored
  questions / total scored questions (1.0 when there are none). Ceremonial bindings and heuristic
  candidates do not count, so the ratio makes audit drift visible even while lint stays green.
- The `visual_poverty` ratio now counts **teaching** visuals only (#110: decorative visuals do
  not count): a bare `video` (external-asset container without caption/narration_text) and a
  promptless `lottie` no longer satisfy the visual-density requirement.
- `STRICT_PROMOTED_CODES` grows by `unbound_scored_question` and `evidence_target_not_evidentiary`;
  default (non-strict) behavior stays advisory, so existing courses keep building unchanged.
- Out of scope here (deferred to E2 / #111): the declared-pack `evidence_phase` conformance check
  (`conflicts_with`, `scoring_allowed_from`) — it presupposes the pack front-matter schema.

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
