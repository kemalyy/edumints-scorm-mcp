# AGENTS.md — edumints-scorm-mcp

> For autonomous coding agents (Google Jules, Claude Code, etc.) and human contributors. **Read this file fully before starting a task.** If a rule conflicts with a task description, stop and ask. The specific scope of each task is defined in its linked GitHub issue.

---

## 1. What this project is

A self-hostable **FastMCP server** that turns a structured spec from an AI client into a **self-contained, SCORM-compliant e-learning package** (HTML5 + the vendored scorm-again runtime).

**Invariant architecture principle:** Author = the MCP client · Assembler = this server. **The server never calls an LLM.** It only validates, scaffolds, renders components, bridges the runtime, and packages. Any change that violates this is rejected.

Output: a self-contained `index.html` + `imsmanifest.xml` + assets + embedded SCORM runtime, zipped — runs in any LMS (Moodle, SCORM Cloud).

---

## 2. Architecture map

```
server.py            # FastMCP tools (@mcp.tool) — PUBLIC CONTRACT, do not break
core/
  project.py         # Pydantic models + spec schemas + ID generators  ⚠ HOT
  store.py           # SQLite (aiosqlite/WAL) persistence
  packager.py        # SCORM zip packaging (deterministic)
  manifest.py        # imsmanifest.xml generation (1.2 + 2004)
  validator.py       # project + package validation (+ XSD)
  schema_validate.py # XSD conformance — ADL vendored, IMS fetch+cache
  media.py/tts.py/video*.py   # media/audio/video (lazy/opt-in)
  integrations/      # external source adapters (greenfield): provenance, openverse, ...
components/
  renderer.py        # spec → HTML  ⚠ HOT
  templates.py       # SHELL / BASE_CSS / ENGINE_JS / FALLBACK  ⚠ HOT
  engine/            # extracted pure-logic JS modules
runtime/             # ⛔ VENDORED: scorm-again.min.js, lottie — do not hand-edit
auth/                # ⛔ SENSITIVE: SSRF guard, OAuth, API-key, sanitization
themes/  tools/  tests/  docs/
```

Screen types (31): title_slide, content_slide, mcq, true_false, fill_blank, drag_drop, hotspot, branching, video, summary, accordion, tabs, flashcards, matching, sorting, timeline, lottie, simulation, decision_scenario, term_match_race, escape_room, labeled_diagram, data_chart, results_breakdown, poll, image_compare, game, adaptive_practice, worked_example, exploration, embed_html.

---

## 3. Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install ".[dev]"        # pytest, pytest-asyncio, ruff, mcp[cli]
pip install ".[tts]"        # only for TTS tasks (piper-tts; heavy)
sudo apt-get install -y ffmpeg   # media/video tests
npm ci                      # JS tests (vitest + jsdom)
```

Python `>=3.11`. You don't need to run the server; agent tasks are test-driven.

---

## 4. Tests & validation — ALL green before opening a PR

```bash
pytest -q        # all Python tests
npm test         # JS engine unit tests (vitest)
ruff check .     # lint (line-length 100, py311)
```

Open a PR only when you've **added a test for new/changed behavior and the whole suite is green.** "Existing tests pass" is not enough — prove you didn't break out-of-scope behavior with a new test.

---

## 5. Conventions

- **Turkish comments/docstrings** consistent with the existing style.
- **Additive & backward-compatible.** Preserve existing signatures, return schemas, behavior. New features are opt-in.
- **Small, focused modules.** Prefer a new file (greenfield) for a new capability.
- ruff line-length 100. Pydantic v2 models live only in `core/project.py`.
- No emoji in comments; rendered HTML uses inline SVG icons.
- All `*_html` user input is sanitized with `nh3` — never bypass this layer.

---

## 6. ⛔ DO-NOT-BREAK list

Touch these only with maintainer approval; if a PR touches one, **flag and justify it explicitly:**

1. **`server.py` `@mcp.tool` signatures / return schema** — the public MCP contract.
2. **`auth/`** (SSRF guard, OAuth, API-key, sanitization) — security boundary; always human/interactive.
3. **`runtime/*.min.js`** — vendored.
4. **Generated package format** (index.html/imsmanifest structure, runtime embedding) — golden tests guard this.
5. **`ENGINE_JS` behavior** (scoring, branching, suspend_data serialization) — only behavior-preserving, with tests.
6. **Meaning of existing `*.json` example/golden fixtures.**

---

## 7. Working rules (async, multi-agent)

- **One task = one issue = one narrow scope = one PR.** Don't widen scope.
- Branch: `agent/<lane>/<short-topic>`.
- PR description: what · why · files touched · tests added · `pytest -q`/`npm test` summary · "did not touch the DO-NOT-BREAK list" confirmation · (if media added) **provenance record** (§9).
- **Stay inside your lane / file area** (defined in the issue). If other areas need work, note it in the PR and propose a separate issue — don't do it yourself.
- Don't redo work already done — the issue describes the current frontier; advance it, don't re-polish existing capabilities.
- **Do not create or edit `CAPABILITIES.md` or this `AGENTS.md`** — they are maintained outside the fleet. State what you completed in the PR description instead.
- If CI isn't green, leave the PR as **draft**.

### Lane ownership (conflict avoidance)

| Lane | File area | Example |
|------|-----------|---------|
| tests-js | `tests/js/**` | engine unit/edge tests |
| examples | `examples/**` | example/game course specs (multilingual) |
| tooling | `pyproject.toml [tool.*]`, `.pre-commit-config.yaml`, `.github/workflows/**` | lint, pre-commit, deps |
| themes | `themes/**`, `tests/test_themes.py` | theme/corporate presets |
| docs | `docs/**`, `*.md` (except README) | developer/integration docs |
| tests-load | `tests/load/**` | load/perf/regression |
| i18n | `messages/**`, `examples/i18n/**` | localization |
| asset-curator | `core/integrations/**`, `tests/test_integrations.py` | CC0/generative source adapters + provenance |
| security-audit | `tests/security/**`, `docs/SECURITY-FINDINGS.md` | tests/report only — no code weakening |
| corporate-template | `themes/corporate/**`, `examples/corporate/**` | corporate template packs |
| docs-i18n | `README.*.md`, `docs/**` | sync docs across all languages |

> **`templates.py` / `renderer.py` / `core/project.py` / `ENGINE_JS` are "hot files".** Work touching them (new screen type, model change) is **not parallelizable** — done one at a time, interactively, by maintainers. Async fleet tasks never touch them.

---

## 8. Suitable / not suitable for the async fleet

**Suitable (async, narrow, patterned, greenfield):** test coverage, example/game specs, docs, dependency reports, theme/corporate presets, i18n, isolated source adapters (new `core/integrations/*` file + test), security test scans.

**Not suitable (human + interactive):** XSD conformance closure, suspend_data format design, a11y interaction design, new screen type / game engine architecture, `auth/` changes, MCP contract/tool changes, hot-file refactors.

---

## 9. Asset provenance (copyright safety — REQUIRED)

Every binary media asset (image/audio/video) that enters a package needs a provenance record. Allowed `source`: **only** `ai-generated`, `cc0`, `public-domain`, `own`, `local`. Anything else (copyrighted, "found online", unclear license) is **rejected** by CI.

```json
{ "asset": "img/x.svg", "source": "cc0", "license": "CC0-1.0",
  "url": "https://...", "author": "", "retrieved_at": "2026-06-07", "license_url": "https://..." }
```

---

## 10. Security

- Never commit secrets/keys. `.env` never enters the repo.
- Don't weaken `auth/` or the SSRF/sanitization code. All external fetches go through the SSRF guard.
- A PR touching `auth/` is **never auto-merged.**
- When in doubt, **stop and ask** — don't silently assume.

---

> PRs are gated by CI (tests + lint + XSD + a11y) and additional guardrails (provenance, file-area conflict). Maintainers review and integrate.
