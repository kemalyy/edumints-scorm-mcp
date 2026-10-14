# Screen-type decision guide (31 types)

Pick by *intent*, not habit. Vary them.

> **Every screen also takes** `kicker` (E3 label), `lead` (E1 — the one message) and `composition`
> (pattern name or `{preset, mirror, focal, …}` / a free grid). In `auto` projects (all new ones) the
> server picks a balanced pattern when you leave it out — see `get_guide(topic="composition")`. Composition
> renders on **all 31 screen types**; ask the user's layout preference while building
> (`composition_defaults`, `composition_questions`). Questions, polls, explorations and branching
> also take an optional case (`stimulus`).

## Content / presentation
- **title_slide** — open the course; set relevance. Supports `{{var}}` + background.
- **content_slide** — one idea. `layout`: text / text_media / media_text / full_media. Don't overload.
  **W9:** use `blocks[]` to interleave `paragraph → image → paragraph` in ONE screen instead of 3
  consecutive content slides.
- **accordion** — dense reference / FAQ; let learners expand on demand (native, accessible). *(W9: per-item `image_asset_id`.)*
- **tabs** — parallel facets of one topic (e.g., "What / Why / How"). *(W9: per-tab `image_asset_id`.)*
- **flashcards** — term ↔ definition; vocabulary; self-test recall. *(W9: `front_asset_id`/`back_asset_id`.)*
- **timeline** — chronology, process steps, history. *(W9: per-event `image_asset_id`.)*

> **Inline media (W9):** any `*_html` field accepts `{{asset:<id>}}` to embed a packaged asset inline in
> flowing text, plus inline base64 `<img src="data:image/…">`. Reorder screens with `reorder_screens`.
- **video** — demonstrations, talking-head, screen capture. `require_complete` to gate. Speech-carrying
  video: attach a WebVTT file as `captions_asset_id` (WCAG 1.2.2 — the server never generates one).
- **lottie** — designer-made animation (concept reveal, celebration, illustration). Opt-in/lazy.

## Practice / assessment (scored → tracked)
- **mcq** — single or multi (`multi_select`) select; the workhorse. Write plausible distractors.
  Per-option `feedback_html` = why THAT option is right/wrong (shown after answering, only for the chosen one).
- **true_false** — quick check; avoid ambiguity.
- **fill_blank** — recall of exact terms; list all `accepted` variants.
- **drag_drop** — categorize / map items to targets.
- **matching** — pair two columns (accessible select UI).
- **sorting** — order steps/ranking (give items in CORRECT order; runtime shuffles).
- **hotspot** — "find it on the image" (anatomy, UI, diagrams). Needs an image asset. `mode`:
  `quiz` (default, scored) | `explore` (UNSCORED — clicking a region opens its `label_html` /
  `feedback_html`; evidence carrier). `require_all: true` (explore only) = "find them all" before the
  screen counts as visited. Per-region `feedback_html` = region-specific rationale. Shapes: `rect` /
  `circle` (`poly` is rejected at build). Always write `label_html` — it becomes the region's accessible name.
- **simulation** — guided multi-step software "try-mode" (İzle→Uygula→Sıra Sizde'nin "Uygula"sı):
  each step = a screenshot + a click region OR a text input; wrong → hint, all correct → scored.
- **decision_scenario** — branching **decision game** in one screen: stateful (score) narrative
  try-mode. Each choice carries a consequence + score delta; ends at a terminal node; scored by
  `pass_score`. Use for compliance/soft-skills/triage "what would you do?" practice.
- **term_match_race** — timed term↔definition matching **game** (gamified `matching` with a
  countdown + speed bonus). Vocabulary, terminology drilling under time pressure.
- **escape_room** — locked puzzle chain **game**: solve to unlock the next; lives + hints. High
  engagement for review/recall; keep puzzles answerable from the taught content.
- **labeled_diagram** — place labels onto positioned pins on an image (anatomy/diagram/map).
  Visual learning; scored. Needs an image asset + pins at normalized (x,y) 0–1000.
- **game** — **composable serious game** (not a fixed type): compose mechanic primitives
  (`score`/`lives`/`timer`/`hints`) + declarative `when event if cond then action` rules + branching
  content `nodes`. Templates: `case_sim` (branching case/decision), `escape_room` (locked chain). Use
  when the mechanic should *carry* the learning (intrinsic integration), e.g. clinical triage, incident
  response. Game a11y is enforced (hint text, timer extend/disable — WCAG 2.2.1). Scored by `pass_score`.
- **adaptive_practice** — competency-adaptive question bank: after each answer it estimates ability
  (**`elo`** — closest-to-target difficulty, flow) or mastery (**`bkt`** — Bayesian Knowledge Tracing,
  mastery + early stop) and serves the next item at the right difficulty. Give ≥4 items with spread
  `difficulty` (logit; harder = higher) + an `explain_html` each. Use for drill/review that should fit
  each learner instead of a fixed quiz. **Mastery loop** (opt-in): `loop_mode: "mastery"` → on a wrong
  answer show the item's `scaffold_html` hint (`scaffold_on_wrong: true` — a hint, NOT the answer), serve a
  DIFFERENT item of the same skill (`related_retry`, default on), repeat until correct;
  `score_mode: "mastery"` = 100% only when every item is solved; `max_consecutive_wrong` (default 5)
  moves on. Defaults keep the classic `sample` behaviour.

## Evidence primitives (not scored — unconditional evidence carriers)
- **worked_example** — expert solution shown step by step; every step is an **action + rationale**
  pair (+ optional artifact image with caption). `fading` controls support: `full` (everything
  open) → `partial` (actions open, rationales behind per-step reveal — learner builds their own
  rationale first) → `problem_only` (only the problem/`intro_html` open, steps revealed one by
  one). Optional `self_explanation_prompt_html` renders an UNSCORED free-text field (never
  written to the LMS). Structurally unscorable (no `points` field — grading a supported attempt
  measures the support, not the learner). Evidence role: K1 type 1 (worked solution) — the most
  direct carrier; scored questions bind to it via `evidence_screen_ids`. Engine of the `4cid`
  and `rosenshine-di` fading progressions. Empty rationale → `step_without_rationale` WARN;
  artifact steps count toward the visual budget (`artifact_caption` = figcaption + alt-text).
- **exploration** — learner input (attempt, prediction, classification) is STORED under
  `store_key` and REPLAYED by later screens via `<span data-exploration-ref="store_key"></span>`
  ("your prediction was…" attribution is real, not imitated in feedback text). `input_kind`:
  `text` (observation note; `placeholder`, `min_length`), `choice` (classify), `prediction`
  (commit-then-see; requires ≥2 `choices` — any `correct` flags are ignored), `slider` (numeric
  commitment — "what percentage?", Likert, "how many years?": `min_value` 0, `max_value` 100, `step` 1,
  optional `unit`; nothing is stored until the learner moves the thumb). Structurally
  unscorable (no `points` — grading the attempt turns inquiry into a guessing contest).
  Evidence role: K1 type 2 (the learner's OWN produced output) — unconditional evidence carrier.
  `store_key` must be unique course-wide (`[a-z0-9_-]+`, ≤64; hard validation error on clash);
  values are truncated at 500 chars (SCORM 1.2 suspend budget). Preferred kesfet mechanic of
  `5e-inquiry`; attempt log for productive-failure patterns.

## Visual content
- **data_chart** — server-side inline SVG chart (`bar`/`line`/`pie`). Passive data presentation /
  comparison; **not scored**. Use real data to make a point, not decoration.
- **image_compare** — draggable before/after slider (two images). Change/contrast (medical,
  design, before-after). Not scored.

## Results & participation
- **results_breakdown** — **customized results**: per-objective score breakdown computed on-show
  from the learner's answers + adaptive advice for weak sections. Map each section to its quiz
  `screen_ids`. Use as a richer, personalized alternative to `summary`. Not scored.
- **poll** — ungraded reflection/opinion (single/multi/open text) → reveals a reflection message.
  Self-assessment / engagement; doesn't gate Next.

## Decision / scenario
- **branching** — choices → different *screens*; consequence-based routing. Add `set_vars` to track
  decisions. (For a self-contained multi-step decision **game with score**, prefer `decision_scenario`.)
- **summary** — close: score, completion, recap.

## Escape hatch (custom HTML)
- **embed_html** — an arbitrary **self-contained HTML artifact** (simulation, calculator, bespoke
  visualization) hosted in a sandboxed iframe; the launcher reports completion to the LMS and the
  artifact may `postMessage` score/status over a small bridge. `completion`: `on_view` (screen entry,
  default) / `time_threshold` (`min_seconds` after entry — a minimum-exposure signal, not an audit-grade
  timer) / `on_message` (only when the artifact reports `{scorm:'complete'}`). `aspect`: `fill`
  (default) / `16:9` / `4:3`. **Not scored** (outside QUIZ_TYPES) and `passing_score` never sees the
  bridge's score. Use it ONLY when no native type expresses the interactivity — an artifact is not
  themed, not translated, not linted, and its accessibility is entirely on you. Full guide (tool calls,
  bridge vocabulary, 1.2 vs 2004, limits): **`get_guide(topic="artifact")`**.

**Selection heuristics:** sequence → timeline; terms → flashcards/term recall; categorize →
drag_drop/matching; process order → sorting; software "do it" → simulation; "what would you do?" /
consequence game → decision_scenario; **mechanic-driven serious game** (score/lives/timer/hints +
branching, intrinsic integration) → game; **adapt difficulty to the learner** → adaptive_practice;
**show an expert solution with fading support** (demonstration-first, complex skill) →
worked_example; **commit a prediction / record an attempt, then refer back to it** (inquiry-first,
"your prediction was…") → exploration; cross-screen routing → branching; dense optional detail →
accordion/tabs; visual concept → lottie/video; **genuinely custom interactivity no native type covers** →
embed_html (last resort). After 1–2 content screens, insert a practice type.
Game design patterns & scoring: see the server's `docs/GAME-PATTERNS.md`, `docs/GAME-ECD.md`,
`docs/GAME-ADAPTIVE.md`. Before publishing a game/adaptive course, run `lint_course` (anti-slop gate).
