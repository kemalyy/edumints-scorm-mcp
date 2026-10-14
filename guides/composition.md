# Composition — focal point, emphasis hierarchy, balance

Every screen needs **one** place the eye lands first, a readable order after that, and a layout
chosen for the content — symmetric when the content is balanced, asymmetric when something must
lead. The server does most of this for you on **all 31 screen types**; your job is to answer the
layout questions it asks and to override a screen only where the meaning demands it.

> Applies to projects with `composition: "auto"` — the default for every **new** project
> (`create_project`, `build_from_spec`, `wrap_artifact`). Older projects are `"classic"` and ignore
> these fields (lint says `composition_ignored_classic`); upgrade one with
> `set_composition(project_id, "auto")` — going back to `"classic"` restores the old output exactly.

## 1. The workflow

1. Build with `composition: "auto"` (the default). Do **not** set `composition` on screens up front.
2. Write content with a clear hierarchy: a `title`, at most one `lead` (the one message, ≤ 20 words),
   an optional `kicker` (≤ 40 characters), then the body. Give case-based screens a `stimulus`.
3. Call `lint_course` or `preview` (light by default — show the user `hosted_url`; pass
   `include_html=true` only if you need the full page). Read `compositions` (the layout chosen per screen) and
   `composition_questions` (the decisions the server wants from the user) — see §6.
4. Ask the user those questions, apply the answers, preview again.
5. Override a screen (`set_screen_composition`) only when the chosen layout contradicts the meaning.
   `update_screen` keeps an override when you leave `composition` out (send `null` to clear it); an
   invalid pattern is rejected at write time (`composition_not_applicable` lists the patterns that fit).

## 2. What the server chooses — all 31 types

`default` is what a screen with short text and no `lead` gets; the third column says what moves it.
Consecutive `split-thirds` screens mirror (image left / right) so the course does not feel stamped.

<!-- table:types -->
| type | default | changes to | focal (where the eye lands) |
|---|---|---|---|
| `title_slide` | `centered` | `hero-focal` with a background image | title / `lead` |
| `content_slide` | content-driven: `split-thirds` (one image) | checked in this order: `statement` (`lead` + ≤ 25 words, no media) → `split-halves` (exactly two images in ≤ 3 blocks) → `z-flow` (3–4 blocks with ≥ 2 images) → `f-flow` (any other ≥ 2 images) → `split-thirds` (one image, whatever the length) → `f-flow` (≥ 4 list items or > 120 words) → `centered` | the image, else `lead` |
| `hotspot` | `visual-stack` | `split-thirds` with a `lead` or > 30 words of text (prompt; for video also the narration text) | the image |
| `labeled_diagram` | `visual-stack` | `split-thirds` (same rule) | the diagram |
| `image_compare` | `visual-stack` | `split-thirds` (same rule) | the slider |
| `data_chart` | `visual-stack` | `split-thirds` (same rule) | the chart |
| `video` | `visual-stack` | `split-thirds` (same rule) | the player |
| `lottie` | `visual-stack` | `split-thirds` (same rule) | the animation |
| `simulation` | `visual-stack` | `split-thirds` (same rule) | the screen being simulated |
| `mcq` | `question-column` | with a `stimulus`: `visual-stack` (short case), `split-thirds` (> 40 words, or image + text) | the answers; with a stimulus, the case |
| `true_false` | `question-column` | same as `mcq` | same as `mcq` |
| `fill_blank` | `question-column` | same as `mcq` | same as `mcq` |
| `drag_drop` | `question-column` | same as `mcq` | same as `mcq` |
| `matching` | `question-column` | same as `mcq` | same as `mcq` |
| `sorting` | `question-column` | same as `mcq` | same as `mcq` |
| `adaptive_practice` | `question-column` | same as `mcq` (stimulus per item) | the exercise |
| `accordion` | `question-column` | `split-thirds` with a `lead` or > 30 words of intro | the list (opens in place) |
| `tabs` | `visual-stack` | `split-thirds` (same rule) | the open panel (master–detail, §7) |
| `flashcards` | `visual-stack` | `split-thirds` (same rule) | the cards |
| `timeline` | `question-column` | `split-thirds` (same rule) | the events |
| `summary` | `centered` | — | the score |
| `results_breakdown` | `split-thirds` | — | the section bars |
| `poll` | `question-column` | `split-thirds` (same rule); with a `stimulus`: as `mcq` | the answer area; with a stimulus, the case |
| `worked_example` | `question-column` | `split-thirds` (same rule) | the steps |
| `exploration` | `question-column` | as `poll` | as `poll` |
| `game` | `visual-stack` | `split-thirds` with a `lead` or > 30 words of intro | the scene (§7) |
| `decision_scenario` | `visual-stack` | `split-thirds` (same rule) | the scene (§7) |
| `escape_room` | `question-column` | `split-thirds` (same rule) | the puzzle |
| `term_match_race` | `question-column` | `split-thirds` (same rule) | the pairs |
| `branching` | `question-column` | `split-thirds` (same rule); with a `stimulus`: as `mcq` | the choices; with a stimulus, the case |
| `embed_html` | `visual-stack` | — (the iframe always gets the width) | the embedded page |
<!-- /table:types -->

The table is checked against the code by a test, so it is exact. Two rules sit on top of it:

- **Course rhythm** — first screen, last screen and each unit opener are `high` intensity,
  explanation screens `calm`, practice `normal`; never three `high` in a row; never the same pattern
  four times in a row (except a run of plain questions in `question-column` — consistency is the
  point there — and anything the user chose explicitly).
- **Reading order** (what phones and screen readers get): the kicker + title always come first; then a
  case (stimulus) before the question it belongs to; check / submit buttons and feedback always come
  after the answers. On image-first layouts the title sits on top of the text column.
- **Why a screen got its layout:** each `compositions[]` entry carries `source` (`auto`, `rhythm`,
  `course:visual=…`, `course:question=…`, `screen`), a short `reason` (e.g. `stimulus_words=46>40`) and
  `dom_order`. Read `source` before overriding — `rhythm` means variety, `course:*` means the user chose it.

## 3. Focal point, the rule of thirds, eye flow

- The focal element sits on one of the four **thirds intersections** — not dead centre — unless the
  moment is formal or symmetric (a title, a section opener, a single decision).
- Focal = the thing the question will be about: the image region, the number, the one sentence.
- **One focal per screen.** Two things competing (a big `lead` *and* a big image in `statement`)
  → `multiple_focal_points`.
- **Z-flow** — little text, strong visuals, a sequence or cause → effect; put the result last
  (bottom-right). **F-flow** — scannable text, checklists, procedures; the decisive item first.
  **Center** — one message, formal, calm.

## 4. Symmetric or asymmetric?

| Choose | When |
|---|---|
| **symmetric** (`centered`, `split-halves`) | comparison of equals, before/after, formal moments, balance is the point |
| **asymmetric** (`split-thirds`, `statement`, `hero-focal`, `z-flow`, `f-flow`, `visual-stack`) | something must lead: evidence + short explanation, a striking number, a scene, a sequence |

In asymmetric layouts **whitespace is the counterweight** — do not fill the empty two-thirds of a
`statement` screen.

## 5. Emphasis levels (type + colour together)

| Level | Role | Where it comes from |
|---|---|---|
| **E1** | focus — the one message | `lead`, the focal image frame, a big number |
| **E2** | structure | title, question stem |
| **E3** | emphasis | `kicker`, `<mark>` in any `*_html` |
| **E4** | body | paragraphs, options |
| **E5** | background | captions, sources, progress |

Rules: one E1 per screen · `lead` ≤ 20 words (`lead_too_long`) · ≤ 3 `<mark>` per screen
(`mark_overuse`) · emphasised text (`<mark>` + `<strong>`) ≤ 20 % of the block
(`emphasis_inflation`). Colours come from the theme (`mint` by default; `ink`, `slate` also ship);
hierarchy is carried by neutrals with a **single accent family** — never several bright colours.

## 6. Ask while you build

The layout should follow what the learner and the client want, not a fixed rule.

1. **At the start**, ask once (only what applies to the course):
   - visual screens: *"Should the text sit in a band above the visual, in a column beside it, or
     should I decide per screen?"* → `"composition_defaults": {"visual": "stack" | "split" | "auto"}`;
   - case-based screens (questions, polls, explorations, branching with a `stimulus`): *"Should the
     case sit above the question or beside it?"* → `"composition_defaults": {"question": …}`.
   Or call `set_composition(project_id, "auto", visual=…, question=…)`. The two answers are independent.
2. **After `lint_course` / `preview`**, read `composition_questions`. Each item has a `question` (in
   the course's language), `options`, a `default` and an `apply` that says exactly which tool to call
   (`set_composition` for a course question, `set_screen_composition` for a screen — it changes only
   that screen's layout). Ask, apply, preview again. **If the user does not answer or says "you
   decide", apply the `default`** — otherwise the question comes back on every preview. At most three
   screen questions per preview; a course-level answer is honoured on every matching screen.

```json
{"id": "screen:h3", "scope": "screen", "screen_id": "h3",
 "question": "'Find the fake sender' — text above or beside the visual?",
 "options": [{"value": "visual-stack", "label": "Above"}, {"value": "split-thirds", "label": "Beside"}],
 "default": "visual-stack",
 "apply": {"tool": "set_screen_composition", "args": {"screen_id": "h3", "composition": "$value"}}}
```

## 7. Special layouts

- **Case (stimulus) screens** — the case is the focal point and is read first; on wide screens it sits
  above the question (`visual-stack`) or beside it (`split-thirds`). Write the case so the learner must
  *apply* the concept — never copy the answer into it (`stimulus_answer_leak`); give images an `alt`
  (`stimulus_without_alt`). See `assessment.md` → application questions.
- **Tabs** — master–detail on wide screens (tab list left, open panel right; ↑/↓ and ←/→ both work),
  horizontal on narrow ones. **Accordions** open in place.
- **Games and decision scenarios** — give a node an image and, on wide screens, it becomes a scene:
  image left, narrative and choices right, the HUD on top. On phones: narrative → image → choices.
- **Long content** (long text columns, long accordions, timelines, worked examples) is never cut: the
  layout starts at the top and the stage scrolls; a side title stays visible.
- **Embedded HTML** — a title band on top, the iframe fills the rest of the stage.
- **Long answer lists** — `mcq` with > 6 options and `matching` with > 5 pairs flow into two columns;
  other question types (sorting included) stay one column.

## 8. Overriding a screen

```jsonc
// 1 · just a pattern
{ "type": "content_slide", "title": "Check the sender", "kicker": "Step 1",
  "lead": "The domain is one letter off.", "media_asset_id": "mail",
  "body_html": "<p>Read the address <mark>letter by letter</mark>.</p>",
  "composition": "split-thirds" }

// 2 · pattern + fine-tuning: image left, focal on the lower-left intersection
{ "composition": { "preset": "split-thirds", "mirror": true, "focal": "r3c1" } }

// 3 · fully free: 1:2 columns, text top-left, media bottom-right, Z flow, generous whitespace
{ "composition": { "grid": "1:2",
                   "areas": { "support": "c1r1-c1r2", "focal": "c2r2-c2r3" },
                   "focal": "focal", "flow": "z", "whitespace": "high" } }
```

Grid cells are `c{column}r{row}` (1-based, rows 1–3); an area is `cXrY-cXrY` (both ends
inclusive). Slots: `support` (title + text), `focal`, `aux` (second image), `steps` (z-flow
sequence). `list_compositions()` lists the catalogue (9 patterns) and which screen types each fits.
Invalid patterns/areas fail the build (`composition_unknown`, `focal_area_empty`).

## 9. Before / after

**Before** (classic): a password-strength screen — title, three paragraphs, an image underneath; on a
laptop the image is below the fold and the one rule that matters is paragraph three.

```json
{ "type": "content_slide", "title": "What Makes a Password STRONG?",
  "body_html": "<p>…</p><p>…</p><p>The rules: long, unique, secret.</p>", "media_asset_id": "meter" }
```

**After** (auto): the rule becomes the `lead` (E1), the image sits beside the text (`split-thirds`),
and the rest is short supporting body.

```json
{ "type": "content_slide", "kicker": "Rule 1", "title": "What Makes a Password STRONG?",
  "lead": "Long beats complex.", "media_asset_id": "meter", "media_alt": "Strength meter",
  "body_html": "<p>A passphrase of three or four random words is longer, harder to crack and easier to remember.</p>" }
```
