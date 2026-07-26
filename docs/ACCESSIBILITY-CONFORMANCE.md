# Accessibility Conformance — WCAG 2.2 AA

**Scope version:** v1.6.0 · **Date:** 2026-07-26 · **Standard targeted:** WCAG 2.2 Level AA

## 1. Claim & scope

This document describes the accessibility posture of the **course players produced by this
tool** — the self-contained SCORM 1.2 / 2004 HTML packages rendered from
`components/templates.py` + `components/renderer.py`. It does **not** cover the MCP server API,
the admin/portal UI, or any LMS that hosts the packages.

"Conformance" here means: for each of the 28 screen types the player can render, we state —
grounded in the actual shipped code, not intent — whether the produced markup and runtime
behavior support the relevant WCAG 2.2 AA criteria. This is a **partial conformance
statement** (in WCAG terms, "partially conforms"): most screen types support keyboard and
screen-reader use, but there are known, documented gaps (Section 3). Authors also share
responsibility: alt text, captions text, and contrast-safe theme choices are author inputs;
the toolchain lints for some of them (`lint_course`) but cannot guarantee them.

Player-wide behaviors verified in code:

- **Language & direction:** `<html lang dir>` is set from the project language; RTL scripts
  get `dir="rtl"` plus mirrored CSS (`components/i18n.py`, `components/templates.py`).
- **Focus management:** on screen change the first focusable element receives focus
  (`tabindex="-1"` + `focus()`); `:focus-visible` outlines are styled on all interactive
  elements.
- **Live regions:** quiz feedback (`role="status" aria-live="polite"`), progress bar
  (`role="progressbar"` with `aria-valuenow`), timer/level/points HUDs and the caption bar
  are `aria-live="polite"`.
- **Navigation:** Prev/Next/Play/Menu buttons are real `<button>`s with `aria-label`s; the
  slide menu is a labelled `<nav>` with Enter-key activation and `aria-current` on the
  active item.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` disables flashcard flip
  transition, timeline block reveal animation, escape-room shake, game-choice hover
  transform, and simulation pulse. (Exception: Lottie — see Section 3.)
- **Screen-level countdown (`timer_sec`)**: any screen may carry an author-set countdown.
  This player-level timer has **no extend/disable control** (unlike `game` screens) — see
  Section 3.

## 2. Conformance matrix — 28 screen types

Column meanings:
- **Keyboard** — 2.1.1 Keyboard, 2.4.7 Focus Visible: fully operable without a mouse.
- **Screen reader / ARIA** — 1.1.1, 1.3.1, 4.1.2/4.1.3: semantics, names, live announcements.
- **Contrast / theme** — 1.4.3/1.4.11: depends on the selected theme (see note below the table).
- **Motion** — 2.3.3: honors `prefers-reduced-motion`.
- **Time limits** — 2.2.1 Timing Adjustable.

Status values: **Supports** / **Partial** / **Does not support** / **N/A**.

| # | Screen type | Keyboard | Screen reader / ARIA | Motion | Time limits | Notes |
|---|---|---|---|---|---|---|
| 1 | `title_slide` | Supports | Supports | Supports | N/A¹ | Static content; heading structure; logo alt linted (`theme.logo_alt`). |
| 2 | `content_slide` | Supports | Partial | Supports | N/A¹ | Block images use `caption` as alt; missing alt is a lint WARN, not a build failure. |
| 3 | `mcq` | Supports | Supports | Supports | N/A¹ | Options are `<button>`s; feedback in `role="status"` live region. |
| 4 | `true_false` | Supports | Supports | Supports | N/A¹ | Same button pattern as `mcq`. |
| 5 | `fill_blank` | Supports | Supports | Supports | N/A¹ | Inputs wrapped in `<label>`; Enter submits (keydown handler). |
| 6 | `drag_drop` | **Does not support** | Partial | Supports | N/A¹ | HTML5 drag + touch fallback only; **no keyboard alternative** (fails 2.1.1, 2.5.7). Use `matching` instead where keyboard access is required. |
| 7 | `hotspot` | Supports | Partial | Supports | N/A¹ | Regions are `<button>`s (focusable/activatable); accessible name only via `title` attribute; image alt is author-supplied (linted). |
| 8 | `branching` | Supports | Supports | Supports | N/A¹ | Choices are `<button>`s. |
| 9 | `video` | Supports | Partial | Supports | N/A¹ | Native `controls` (pause/seek); autoplay is muted. **No synchronized captions** (no `<track>`/WebVTT) — see Section 3. Static `caption` + optional `narration_text` description only. |
| 10 | `summary` | Supports | Supports | Supports | N/A¹ | Static content + score/completion text. |
| 11 | `accordion` | Supports | Supports | Supports | N/A¹ | Native `<details>/<summary>` disclosure. |
| 12 | `tabs` | Supports | Supports | Supports | N/A¹ | `role="tablist"/"tab"/"tabpanel"`, `aria-selected`, Left/Right arrow-key navigation. |
| 13 | `flashcards` | Supports | Supports | Supports | N/A¹ | Cards are `<button>`s with `aria-label`; flip transition disabled under reduced motion. |
| 14 | `matching` | Supports | Supports | Supports | N/A¹ | `<select>`-based with `aria-label` — the keyboard-safe alternative to `drag_drop`. |
| 15 | `sorting` | Supports | Supports | Supports | N/A¹ | Per-item ▲/▼ buttons with `aria-label`s; pointer drag is an enhancement, not the only path. |
| 16 | `timeline` | Supports | Supports | Supports | N/A¹ | Reveal animation forced visible (`opacity:1`) under reduced motion. |
| 17 | `lottie` | N/A | Partial | **Does not support** | N/A¹ | `role="img"` + `aria-label` (title); but the animation plays/loops regardless of `prefers-reduced-motion` and has no pause control (2.2.2 risk for looping animations). |
| 18 | `simulation` | Supports | Partial | Supports | N/A¹ | Step regions are `<button>`s; text steps auto-focus input, Enter submits; pulse cue disabled under reduced motion; step images need author alt (linted). |
| 19 | `decision_scenario` | Supports | Supports | Supports | N/A¹ | Choice `<button>`s; focus moved to first option on node entry. |
| 20 | `term_match_race` | Supports | Supports | Supports | **Does not support** | `<select>`-based (keyboard-safe) but the countdown **auto-grades at 0 with no extend/disable control** — fails 2.2.1. See Section 3. |
| 21 | `escape_room` | Supports | Supports | Supports | N/A² | Text inputs + Enter; hints are text (screen-reader readable); lives shown as icons + counted; shake animation disabled under reduced motion. |
| 22 | `labeled_diagram` | Supports | Partial | Supports | N/A¹ | Pins are `<button>`s; answers via labelled `<select>`s; diagram image alt is author-supplied. |
| 23 | `data_chart` | N/A | Partial | Supports | N/A¹ | Inline SVG has `role="img"` but **no `aria-label`/`<title>`** — value/label `<text>` nodes inside may not be announced. `caption` (figcaption) is the only reliable text alternative. |
| 24 | `results_breakdown` | Supports | Supports | Supports | N/A¹ | Textual score breakdown; progress bars are decorative alongside text values. |
| 25 | `poll` | Supports | Supports | Supports | N/A¹ | Option `<button>`s + submit button. |
| 26 | `image_compare` | Supports | Partial | Supports | N/A¹ | Slider is a native `<input type="range">` with `aria-label` (keyboard-operable); before/after image alts are author-supplied. |
| 27 | `game` | Supports | Supports | Supports | **Supports** | Choices are `<button>`s; HUD is `role="status" aria-live`; hints are text; timer has visible **+30 s extend** and **disable (∞)** buttons, and `core/validator.py` rejects builds where the timer allows neither (`allow_extend`/`allow_disable`). |
| 28 | `adaptive_practice` | Supports | Supports | Supports | N/A¹ | Option `<button>`s; mastery HUD is a live region. |

¹ **N/A only while no `timer_sec` is set.** Any screen type can carry an author-set
countdown (`timer_sec`), which is announced via the `aria-live` timer HUD but **cannot be
extended or disabled by the learner** — a screen with `timer_sec` set drops to
*Does not support* for 2.2.1. Only the `game` screen type ships learner-facing timing controls.

² `escape_room` is lives-based, not time-based (no countdown).

**Contrast / theme note (applies to all rows):** contrast is a property of the selected
theme, not the screen type. Bundled themes use token pairs designed for AA (including an
explicit `high-contrast` theme), and axe's `color-contrast` rule runs in CI — but only
against the game example fixtures (see Section 4), and custom author themes are not
contrast-checked at build time. Treat contrast as **Partial (theme-dependent)** across the
board.

## 3. Known limitations (honest)

1. **No synchronized captions or transcripts for video** (WCAG 1.2.2 fail for videos with
   audio). `_r_video` emits a `<video controls>` without any `<track>` element; there is no
   WebVTT pipeline. Mitigations available today: the static `caption` (figcaption) and the
   optional `narration_text` block rendered next to the video — neither is time-synced.
   Autoplayed video is muted, but a learner who unmutes a video that contains speech has no
   caption support.
2. **TTS/audio narration has captions only when the author provides `narration_text`.**
   When present, the player shows it via the CC bar (toggle button, `aria-live`) — as a
   full-screen text block, not word-level synced captions. When the author supplies only a
   narration audio asset without `narration_text`, there is **no transcript at all**.
3. **`drag_drop` is pointer-only.** Mouse drag (HTML5 DnD) and a touch fallback exist; there
   is no keyboard or select-based alternative in this screen type (fails 2.1.1 and 2.5.7
   Dragging Movements). The documented workaround is authoring the same task as `matching`
   (select-based) — `docs/GAME-A11Y.md` requires this pattern for game mechanics, but the
   standalone `drag_drop` screen itself does not enforce or provide it.
4. **`term_match_race` countdown is not adjustable** (2.2.1). It auto-grades when time
   expires with no extend/disable affordance. Contrast with composed `game` screens, where
   the validator *rejects* timers that can be neither extended nor disabled and the HUD
   exposes both controls.
5. **Screen-level `timer_sec` countdowns are not adjustable** (2.2.1). The generic per-screen
   timer (available on all screen types) counts down and fires `on_timeout`/`timeout_goto`
   with no learner control.
6. **Lottie animations ignore `prefers-reduced-motion` and cannot be paused** (2.2.2 /
   2.3.3). All other animated surfaces in the player degrade under reduced motion; Lottie
   playback (including looping) does not.
7. **`data_chart` SVG lacks a programmatic name.** `role="img"` without `aria-label` means
   screen readers may announce nothing useful; the optional figcaption is the only text
   alternative.
8. **Hotspot regions are named only via `title`.** Focusable and activatable, but the
   accessible name relies on the `title` attribute (inconsistently exposed by AT) and the
   author supplying `label_html`.
9. **Alt text is linted, not enforced.** `lint_course` (`core/antislop.py`) walks every
   image-bearing field across screen types and the theme logo and emits `missing_alt_text`
   WARNs — advisory, so a course can still build and ship without alt text.
10. **The CI axe audit is non-blocking and covers only game example fixtures** — see
    Section 4. A regression in, say, `accordion` markup would not be caught by it unless an
    example exercises it.

## 4. Test methodology

- **Automated axe-core audit (CI):** the `a11y-audit` job in `.github/workflows/ci.yml`
  renders every spec in `examples/games/*.json` to real player HTML via the actual
  `build_from_spec` → `preview` pipeline (`tests/a11y/generate_fixtures.py`), then runs
  **axe-core via Playwright/Chromium** on each fixture (`tests/a11y/audit.mjs`). axe covers
  the machine-checkable subset of WCAG (names/roles, contrast, landmark/label rules, etc.).
  The job is deliberately **non-blocking** (`continue-on-error: true`, script always exits
  0 — decision of 2026-07-22): violations are reported, not build-failing. Coverage is
  limited to what the game examples render.
- **Build-time validation:** `core/validator.py` rejects composed-game timers with both
  `allow_extend` and `allow_disable` off (2.2.1 gate for `game` screens).
- **Lint (advisory):** `lint_course` flags missing alt text on every image-bearing field
  (all screen types + theme logo) as `missing_alt_text` WARNs.
- **Game mechanics contract:** `docs/GAME-A11Y.md` defines per-primitive a11y contracts
  (timer/score/lives/hints/item bank/branch graph) that the game gate checks.
- **Recommended manual testing (not automated):** keyboard-only walkthrough of each course
  (Tab/Enter/Arrows, no pointer), a screen-reader pass (NVDA + Firefox, VoiceOver + Safari),
  a reduced-motion OS setting pass, and 200 % zoom / 320 px reflow checks. Automated axe
  runs catch roughly a third of WCAG issues at best; manual passes are required before
  claiming conformance for a specific published course.

## 5. RTL & language note

- The player sets `<html lang="…" dir="…">` from the project language (3.1.1 Language of
  Page). Direction is derived from the language (`components/i18n.py` `_RTL_LANGS`):
  RTL scripts (Arabic, Hebrew, Farsi, Urdu, …) get `dir="rtl"`, and the stylesheet flips
  directional UI (nav chevrons, replay icon, `--dir-x`) plus uses logical properties.
- UI strings (buttons, HUD labels, `aria-label`s) come from a string table with the lookup
  chain **full locale → base language → `en`**: e.g. `pt-BR` → `pt` → `en`. The fallback is
  deliberately English (not Turkish) so a course in any language degrades to English UI
  labels, never to a third language.
- Author content (screen text, alt text, captions) is whatever language the author wrote —
  the toolchain does not translate or validate content language.

---

*Maintenance: update the matrix when adding a screen type (`core/project.py ScreenType`) or
changing interaction bindings in `components/templates.py` / `components/renderer.py`. Every
"Supports" cell above was verified against the code at v1.6.0; keep it that way.*
