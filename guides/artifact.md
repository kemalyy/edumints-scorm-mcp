# Artifact → SCORM (`embed_html`) — arbitrary self-contained HTML as a tracked course

You have an interactive HTML thing — a simulation, a calculator, a bespoke visualization — and you want
an LMS to track it. `embed_html` hosts that HTML in a **sandboxed iframe** inside a normal course screen;
the launcher does the LMS talking. The artifact can stay dumb (the launcher reports completion by itself)
or opt into a small **postMessage bridge** to report score/status.

## When to use it — and when NOT to

**Not a shortcut for authoring.** Native screen types are preferable whenever they fit: they are scored,
accessible, themed, translated, linted (`lint_course`), and they carry evidence binding. A `content_slide`
with `blocks[]`, a `simulation`, a `data_chart`, a `game` or an `adaptive_practice` screen will beat a
hand-rolled HTML page on every one of those axes. Rebuilding a quiz as an artifact is a regression.

Use `embed_html` when the interactivity is **genuinely custom** and no native type expresses it:
- a physics/finance/process **simulation** with continuous state,
- a **calculator** or configurator the learner drives,
- a **bespoke visualization** (custom canvas/WebGL, D3, an interactive map),
- an existing self-contained HTML tool you already own and don't want to re-author.

**`embed_html` is not in `QUIZ_TYPES`** — the screen is unscored by construction. A score exists only if
the artifact sends one over the bridge, and even then the course engine does not see it (see *Limits*).

## The one-call path — `wrap_artifact`

Raw HTML (or a remote URL) → a **new project** + one `embed_html` screen, in a single call.

```
wrap_artifact(
  html_content = "<!doctype html><html>…self-contained app…</html>",   # OR source_url
  title        = "Compound interest simulator",
  scorm_version= "1.2",              # "1.2" (default) | "2004"
  language     = "tr",               # default "tr" — IMMUTABLE after creation, see below
  completion   = "on_view",          # "on_view" (default) | "on_message" | "time_threshold"
  min_seconds  = 0                   # REQUIRED > 0 when completion="time_threshold"
)
  → { project_id: "prj_…", screen_id: "scr_…", asset_id: "asset_…" }

# then the normal loop:
preview(project_id)  →  { hosted_url, … }   # include_html=true → + inline_html
build_package(project_id)  →  download URL for the LMS
```

Large or remote artifact — let the server fetch it:

```
wrap_artifact(source_url="https://…/app.html", title="Triage simulator", scorm_version="2004")
```

Rules the tool enforces (all validated **before** the project is created, so a bad call leaves nothing behind):
- **Exactly one** of `html_content` / `source_url` — the check is on `None`, so `html_content=""` counts as
  "given" and is rejected as empty rather than silently falling through to `source_url`.
- `completion="time_threshold"` **requires** `min_seconds > 0`; `min_seconds` may not be negative. In the
  other two modes `min_seconds` is ignored.
- `source_url` must be **https**, is SSRF-guarded (internal IPs blocked, every redirect hop re-checked,
  size-capped by the server's `MAX_ASSET_MB`, default 25), and only `text/html` / `application/xhtml+xml` /
  `text/plain` are accepted (raw file hosts often serve `.html` as `text/plain`). The asset is stored as
  `text/html` regardless of what the server sent.
- `language` is set **at project creation and no tool can change it afterwards** — it drives the player
  shell, the runtime i18n and the LOM `general/language`. For an English course pass `language="en"` here.
- `wrap_artifact` always produces `aspect="fill"`. To pick a fixed ratio use the compose path (or
  `update_screen` afterwards).

## The compose-it-yourself path — `html_to_asset` + `add_screen`

Use this when the artifact is **one screen among many** (intro → artifact → reflection → quiz), or when
you need `aspect`, `narration_asset_id`, `visible_if`, `section`, `node_id`, …

```
create_project(title="Isı transferi", scorm_version="2004", language="tr") → { project_id }

html_to_asset(project_id, html_content="<!doctype html>…", filename="app.html")
  → { id: "asset_…", mime: "text/html", size_bytes: …, rel_path: "assets/app.html" }

add_screen(project_id, {
  "type": "embed_html",
  "id": "sim1",
  "title": "Deney: çubuğu ısıt",     # optional — omit and the screen renders with no <h2>
  "html_asset_id": "asset_…",         # REQUIRED, non-empty
  "completion": "time_threshold",     # "on_view" (default) | "on_message" | "time_threshold"
  "min_seconds": 120,                 # ≥ 0; only consumed by time_threshold
  "aspect": "16:9"                    # "fill" (default) | "16:9" | "4:3"
}) → { screen_id: "sim1" }
```

- `html_to_asset` takes the **raw HTML string** — no base64 (the `svg_to_asset` pattern). Give it a
  `.html`/`.htm` filename or the tool appends `.html`. The bytes count against your storage quota.
- `add_asset(project_id, source="https://…/app.html", …)` **will not work**: the https branch is limited to
  the media mime allowlist → `asset_error: İzin verilmeyen mime: text/html`. Use `html_to_asset` for local
  strings and `wrap_artifact(source_url=…)` for remote files.
- `build_from_spec` accepts `embed_html` screens like any other type, but its `assets[]` https fetch has the
  same media allowlist — so the HTML still has to come in through `html_to_asset` first.

## `completion` — what each mode actually does

| mode | opens when | notes |
|---|---|---|
| `on_view` (default) | the learner **enters the screen** (not on first page load) | no gate, no extra bookkeeping — the engine derives completion from `state.visited` |
| `time_threshold` | `min_seconds` after screen entry | wall-clock timer, see the two-sided caveat below |
| `on_message` | only when the artifact sends `{scorm:'complete'}` (or `{scorm:'setStatus', value:'completed'}`) | the artifact **must** send it, or the course never reports completed |

`time_threshold` and `on_message` install a **completion gate**: while a gate is pending, the course does
not report `completed` to the LMS. The gate only ever **holds back** — it can never turn an incomplete
course into a completed one, and it never touches score or `cmi.success_status`.

Sharp edges you must design around:

- **The `time_threshold` counter is a "minimum exposure" signal, not an audit-grade time measurement.**
  It is an unpaused wall-clock timer started when the screen is entered. It **overcounts**: it keeps
  running while the learner is on another screen or the tab is backgrounded — so it measures "time since
  first entering the screen", not "time spent on the screen". (The engine's `cmi.*session_time` *does*
  pause on `visibilitychange`, so the two clocks will not agree.) It also **undercounts**: the ledger entry
  is written only when the timer fires, so a session reloaded at 4:59 of a 5:00 threshold restarts from zero.
- **2004 + `on_message`: sending only `{scorm:'passed'}` does NOT complete the course.** In SCORM 2004
  `passed` goes to `cmi.success_status` and never touches completion. A 2004 artifact must **also** send
  `{scorm:'complete'}`. In 1.2 `passed` is written to `lesson_status` but still does not open the gate —
  the rule is the same in both versions: only an explicit "completed" opens it.
- **In SCORM 1.2, a `passed` reported while a gate is still pending is deferred, not lost.** 1.2 has a
  single success channel (`lesson_status`) and `passed` implies completion there, so it is withheld until
  the gate opens — the value is kept in the bridge's persisted record, survives suspend/resume, and is
  written on the first evaluation after the gate opens. In 2004 `passed` lives on `cmi.success_status`
  and is never withheld.
- **`visible_if` on a gated screen is a bypass.** A screen that is currently hidden is not counted as a
  pending gate (otherwise an unreachable screen would lock the course forever). So the course can report
  `completed` while the gated screen is hidden; if it later becomes visible the gate re-engages and the
  course goes back to `incomplete` — which an LMS that latches the first `completed` will never show. If
  the gate matters, don't put `visible_if` on it.
- **Gates do not affect the outline lock or the progress bar.** With `unlock_rule: "sequential"`, a
  `time_threshold` screen unlocks the next node as soon as it is *seen*; the threshold is not waited for.
  The gate holds only the course's cmi completion report.

## The postMessage bridge

From inside the artifact:

```js
window.parent.postMessage({ scorm: "<command>", value: <optional> }, "*");
```

| message | effect (SCORM 1.2) | effect (SCORM 2004) |
|---|---|---|
| `{scorm:"complete"}` | `cmi.core.lesson_status = "completed"` | `cmi.completion_status = "completed"` |
| `{scorm:"setScore", value:<number>}` | `cmi.core.score.raw` | `cmi.score.raw` **and** `cmi.score.scaled` (4 dp) |
| `{scorm:"passed"}` / `{scorm:"failed"}` | `cmi.core.lesson_status` | `cmi.success_status` (completion untouched) |
| `{scorm:"setStatus", value:"…"}` | any of `completed·incomplete·passed·failed·browsed·not attempted` → `lesson_status` | `completed·incomplete·not attempted` → `cmi.completion_status`; `passed·failed` → `cmi.success_status`; **`browsed` is rejected** (not in the 2004 vocabulary) |

- `setScore.value` must be a **real, finite `number`** — `null`, `""`, `[]`, `true` and `Infinity` are all
  rejected (no implicit coercion). Accepted values are clamped to **0–100**.
- Anything unknown or malformed is **silently dropped** (no error surfaces to the artifact).
- The launcher validates the message by **`event.source` identity** (its own iframe windows), not by origin
  — a sandboxed artifact has no usable origin. Always post to `"*"`.
- The reported values are persisted in `suspend_data`, so they survive suspend/resume. Keep them small.

Paste-ready artifact side:

```js
// --- SCORM bridge (safe no-op outside a course) -------------------------
function scormSend(scorm, value) {
  try { window.parent.postMessage(value === undefined ? { scorm } : { scorm, value }, "*"); }
  catch (e) { /* standalone: nothing is listening */ }
}

// the learner finished the simulation with 85/100:
scormSend("setScore", 85);        // number only, clamped 0–100
scormSend("passed");              // 1.2 → lesson_status; 2004 → success_status
scormSend("complete");            // REQUIRED for completion="on_message" (and for 2004 completion)
```

Ordering note for 2004 + `on_message`: `passed` alone leaves the course incomplete — send `complete` too,
as above.

## Limits that will bite

- **The artifact HTML is NOT sanitized. That is deliberate.** The `body_html` sanitizer (which strips
  `<svg>`/`<canvas>`/`<script>`) does not apply here: the HTML is never inlined into the launcher DOM, it is
  stored as its own `text/html` asset and referenced by the iframe's `src`. This is the sanctioned escape
  hatch for a full application — and it means **you** are responsible for what is inside it. There is no
  LLM and no rewriting on the server.
- **The bridge is a convenience API, not a security boundary.** The iframe carries
  `sandbox="allow-scripts allow-same-origin allow-forms allow-popups"`, so in a **built package** the
  artifact can walk the `findAPI` chain and call `window.API` / `window.API_1484_11` directly. It runs with
  the same privileges as the course — your content, your LMS. Expected, not a hole.
- **…but that only holds in `package` mode.** In `preview` and `publish_demo` the assets are embedded as
  `data:` URIs, and a `data:` iframe has an **opaque origin** — reading `window.parent.API` throws and
  `findAPI` finds nothing. An artifact that writes to the SCORM API directly will do **nothing in preview**
  and work once packaged; "it doesn't report in preview" is often this, not a bug. The postMessage bridge
  works in **both** modes. Portable answer: always use the bridge.
- **`passing_score` never sees the artifact's score.** The engine computes pass/fail from `state.results`
  (answers on quiz screens); the bridge's `setScore` is written to cmi but never enters `state.results`.
  So a course with `completion_rule: "passed_quiz"` (or `"viewed_all_and_passed"`) whose only score comes
  from an artifact **never completes** — you get a permanent `score.raw=95` + `lesson_status=incomplete`.
  Either leave `completion_rule: "viewed_all"`, or have the artifact also send
  `{scorm:'passed'}` / `{scorm:'complete'}`.
- **Analytics pipelines see a score flicker.** On every navigation the engine first writes the course score
  (`0` in a scoreless embed course) and commits it, then the bridge's pinned value is re-written and
  committed. Last-write-wins LMSs end up correct; a pipeline that records *every* commit will see
  `0 → 85` on each screen change.
- **`aspect`** — `fill` (the default, and what `wrap_artifact` always produces) makes the iframe take the
  full remaining stage height; `16:9` and `4:3` letterbox it at that ratio inside the remaining area. `fill`
  is the safe default for a responsive artifact; pick a fixed ratio only when the artifact itself is drawn
  at a fixed canvas ratio. In `layout_mode:"flow"`, on narrow/short screens, and when the stage falls back
  to reflow, `fill` gets a `60vh` floor so it cannot collapse.
- **Preview payload size.** `preview` returns everything in one file (base ~546 KB) with assets base64'd
  (≈ size × 1.33). For a wrapped artifact, share/open `hosted_url` instead of pulling `inline_html` into
  context.
- Keep the artifact **self-contained**: no CDN scripts, no external fonts/images. The package is offline on
  the LMS and the preview is a single file.
- Accessibility and theming are on you inside the iframe — nothing from the course theme, the a11y overlay
  or `lint_course` reaches in. Give the artifact a keyboard path and readable contrast, and keep the
  learning in the course around it (the skill's `references/core/evidence-binding.md` still applies to any scored
  question that leans on what the artifact showed).
