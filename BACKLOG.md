# Backlog

Prioritized, code-verified feature gaps for the authoring surface. Each item was checked against
the actual schema (`core/project.py`), renderer (`components/templates.py`, `components/renderer.py`),
and tools (`server.py`) — not assumed. Schema additions must be **additive / backward-compatible**:
existing `body_html` and `*_asset_id` fields stay; new fields are optional.

## Priorities

> **Status:** ✅ **P1–P6 all shipped (W9, Unreleased)** — `content_slide` `blocks[]`; `reorder_screens`
> tool; per-item images on accordion/tabs/flashcards/timeline; `data:` URI `<img>`; `{{asset:id}}`
> interpolation. See CHANGELOG `[Unreleased]` and `docs/SCREEN_TYPES.md`. Kept here for design rationale.

### P1 — `content_slide` multi-block (`blocks[]`)
- **Gap (verified):** `ContentSlide` has a single `body_html` + one optional `media_asset_id` and a
  4-value `layout` (`text` / `text_media` / `media_text` / `full_media`). There is no way to
  interleave `paragraph → image → paragraph → image` in one screen, so a 3-step illustrated concept
  forces 3 consecutive `content_slide`s (an A1 "no 3 content slides in a row" smell).
- **Proposal:** optional `blocks: list[Block]` where a block is either `{html}` or `{asset_id, caption?}`.
  When `blocks` is present, render them in order; otherwise fall back to today's `body_html`/`media_asset_id`.
- **Touches:** `core/project.py` (model), `components/templates.py` + renderer (new block layout). Hot file.

### P2 — `reorder_screens` tool
- **Gap (verified):** no reorder/move tool exists among the 23 tools. `add_screen` always appends;
  `update_screen` replaces in place by id. Authors can't reorder after the fact.
- **Proposal:** `reorder_screens(project_id, screen_ids_in_order: list[str])` → validates the set
  matches existing screen ids, reorders `project.screens`.
- **Touches:** `server.py` only (no renderer change). Lowest-risk, high workflow value.

### P3 — Per-item images: `accordion` / `tabs`
- **Gap (verified):** `AccordionItem` (`title`, `body_html`) and `TabItem` (`label`, `body_html`)
  have no per-item asset field. Each panel/tab can't carry its own illustration.
- **Proposal:** optional `image_asset_id` on each item.
- **Touches:** `core/project.py`, renderer. Hot file.

### P4 — Per-item images: `flashcards` / `timeline`
- **Gap (verified):** `Flashcard` (`front_html`, `back_html`) and `TimelineEvent`
  (`date`, `title`, `body_html?`) have no asset fields.
- **Proposal:** optional `front_asset_id` / `back_asset_id` on cards; `image_asset_id` on events.
- **Touches:** `core/project.py`, renderer. Hot file.

### P5 — Allow `data:` URIs for `<img>` in sanitized HTML
- **Gap (verified):** nh3 already allows `<img>`/`<figure>`/`<figcaption>` with `http`/`https`, but
  `url_schemes` does **not** include `data`, so inline base64 images/icons in `body_html` are stripped.
- **Proposal:** add `data` to the img `url_schemes` (scoped, size-capped) → enables small inline SVG/PNG icons.
- **Touches:** `components/renderer.py` (sanitizer config). Small.

### P6 — `{{asset:id}}` interpolation in `body_html`
- **Gap (verified):** inline `<img src="https://…">` survives sanitization but is **not embedded** into
  the package (only `*_asset_id` fields are fetched + packaged), so inline external images aren't
  self-contained. There is no token to reference a *packaged* asset inside flowing HTML.
- **Proposal:** interpolate `{{asset:<id>}}` in `*_html` to the packaged asset's relative path at render time.
- **Touches:** renderer. Medium.

## Deferred from v1.6.0 final review (Minor — triaged, not blockers)

All four were raised by independent review during v1.6.0 and consciously deferred with rationale;
none affects correctness of served content.

- **Weak-ETag `If-None-Match` comparison** — `server.py` `_if_none_match_hits` does exact-string
  matching only. Behind a proxy that weakens ETags (e.g. nginx+gzip emits `W/"…"`), revalidation
  returns 200 instead of 304 — never wrong content, just a missed cache win. Fix: RFC 9110 weak
  comparison (strip `W/` prefix on both sides), ~3 lines + test.
- **ETag hash memo** — `/demo` GET reads + sha256-hashes the full HTML on every request including
  the 304 path. Correct and restart-safe; cost bounded by `max-age=300`. Fix: memoize by
  `(path, mtime)` if demos grow to multi-MB or traffic rises.
- **`estimate_suspend_size` is approximate** — the antislop WARN estimator mirrors the encoder's
  cost model with authoring-time defaults; runtime var growth can exceed it. Docstring already
  softened (v1.6.0); a headroom factor could be added if field reports show under-warning.
- **Test file cosmetics** — `tests/test_scorm_runtime.py` S2 insertion consumed a section header /
  blank lines around `test_s2_no_objectives_no_config_key`. Ruff-green; readability only.

## Already supported — do NOT re-add as gaps

These were claimed as gaps but verified to already work:

- **Inline `<img>` in `body_html`** — allowed by the nh3 allowlist (`<img>`, `src`, `alt`, `width`,
  `height`; `http`/`https`). Caveat: `data:` URIs are stripped (see P5) and external inline images are
  not embedded into the package (see P6).
- **Per-step/per-node images** — `simulation` (`SimStep.image_asset_id`) and `decision_scenario`
  (`ScenarioNode.image_asset_id`) already attach an image per step/node. A multi-step illustrated flow
  is achievable today via these two screen types.
- **Multi-asset screens** — `video` (`video_asset_id` + `poster_asset_id`), `image_compare`
  (`before_asset_id` + `after_asset_id`).

## Verified non-issues (closed)

- **"Canva TTL/signed URLs break assets after build."** False. `add_asset` / `build_from_spec` fetch
  the asset server-side at build time and embed the bytes into the zip (`packager.build_sync` writes
  stored bytes; no runtime network). Post-build URL expiry is irrelevant. The only real exposure is
  fetch-time: a signed URL that expires *before* the fetch runs. Mitigation: fetch promptly / use a
  public or long-TTL export URL.
- **"SSRF guard blocks Canva/CDN URLs."** False. The guard (`auth/ssrf.py`) is IP-range based — it
  blocks private/loopback/link-local/CGNAT/ULA/metadata IPs only. Public `*.canva.com` / S3 export
  URLs pass; the MIME allowlist covers PNG/PDF/image/video/audio.
- **"Two different asset ID systems."** False. Single namespace: `AssetInput.id` flows straight into
  `AssetRef.id`, which screens reference via `*_asset_id`. Nuance: in the imperative `add_asset` flow
  the server generates the id (author can't pre-pick it); in the `build_from_spec` flow the author may
  supply it.

## Out of scope (by design)

- **Server-side Canva `design_id` → asset.** Not feasible: Canva is a **client-side MCP connector** in
  Claude, not a server API — the scorm server cannot reach the user's Canva connector. The correct (and
  shipped) design is the **client-side pipeline**: Claude orchestrates both connectors — Canva MCP
  (`generate-design` → `export-design` → signed URL) then scorm `add_asset` (which downloads + embeds the
  bytes, so the source URL's TTL is irrelevant post-build). Documented in the skill's `references/media.md`.
- **`<iframe>` / live Canva embeds in `*_html`.** Stripped by nh3 on purpose (security + self-contained
  packaging). Use a packaged image/PDF export instead of a live embed.

## Shipped since (Unreleased)

- **Opt-in auto-TTS** — `build_from_spec` `auto_tts` (default `false`) generates Piper narration for
  screens with `narration_text`; deterministic, no server-side LLM; silently skipped without Piper.
  (Previously listed here as out-of-scope; now available as explicit opt-in.)
- **`content_slide` `blocks[].width`** — sized/centered inline image blocks.
