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

- **Auto-TTS from `narration_text`.** `narration_text` is caption (CC) text only; speech is generated
  via the explicit `synthesize_speech` tool. No server-side LLM/auto-synthesis runs during build —
  this is the project's "no server-side LLM, deterministic build" principle, not a gap.
- **`<iframe>` / live Canva embeds in `*_html`.** Stripped by nh3 on purpose (security + self-contained
  packaging). Use a packaged image/PDF export instead of a live embed.
