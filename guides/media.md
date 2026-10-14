# Media — cross-MCP ingestion & ffmpeg

The unique strength: you (Claude) **orchestrate other MCP servers and local files**, then feed media to
scorm-mcp, which assembles + processes it into the package.

## Ingesting media (`add_asset`)
`add_asset(project_id, source, filename)` — `source` is either:
- a **data-URI** (`data:<mime>;base64,…`) — for bytes you produce or read from a local file, or
- an **https URL** — fetched server-side, **SSRF-guarded** (internal IPs blocked, redirects re-checked,
  size-capped, mime allowlisted: images, mp4/webm/ogg video, mp3/m4a/aac/ogg/wav/webm audio, pdf, json, WebVTT
  captions `text/vtt` — use as a video's `captions_asset_id`).

Typical orchestration (**primary path** for all media — audio/image/video):
- **Narration:** call a TTS MCP → get audio (URL or bytes) → `add_asset` → use as `narration_asset_id`
  (per-screen audio player) or feed into a video (below).
- **Images:** call an image-gen MCP or use provided URLs → `add_asset` → `media_asset_id` / `image_asset_id`.
- **Video:** call a video MCP (or `render_motion_video`, see `video-generation.md`) → `add_asset` / `video_asset_id`.
- **Local files:** read a file in the working dir → base64 data-URI → `add_asset`.

> Bringing media from **your own MCPs** is the main way — it gives you top quality and any language/voice.

## Built-in Turkish TTS (Piper) — optional alternative
- `synthesize_speech(project_id, text, voice=None, filename="narration.mp3")` → **Türkçe** mp3 narration
  asset (Piper, free, **offline, no GPU**). Use as `narration_asset_id`. Good for quick Turkish narration
  without an external TTS MCP. For top studio quality or other languages, prefer your own TTS MCP (above).
- LAZY: if Piper isn't installed the tool errors clearly; nothing else is affected.

## Local media helper (offload slow server render / local TTS)
Server video render has no GPU (slow). Run heavy media **locally** instead:
`python tools/local_media.py tts --text "…" --out a.mp3 --upload --project <id> --key sk_…`
or `... render --spec spec.json --out v.mp4 --quality high --upload …` — generates audio/video on your
machine (fast) and uploads via `add_asset`. Needs local piper-tts + Node/HyperFrames.

## Processing with ffmpeg (server-side, lazy)
- `make_video_from_image_audio(project_id, image_asset_id, audio_asset_id, filename)` → an **mp4** (still
  image + narration → narrated video, H.264/AAC). Use it for `video` screens. Great for turning a designed
  slide + TTS voice into a polished video segment.
- `normalize_audio_asset(project_id, audio_asset_id, filename)` → tarayıcı-safe mp3 (44.1k/128k) — run on
  wav/ogg/m4a from other MCPs so it plays everywhere.

ffmpeg is opt-in: it only runs when you call these tools; courses without media processing are unaffected.

## Guidance
- Keep media purposeful (it should teach, not decorate). Compress large media; the asset size counts
  against quota. Provide alt text / captions for accessibility.

## Canva cross-MCP pipeline (image → SCORM asset)

> **This is client-side orchestration.** Canva is a **client-side MCP connector in Claude** — the scorm
> server cannot call it. So *you* (the client) call both connectors: Canva MCP to make/export the image,
> then scorm MCP `add_asset` to pull it into the package. There is no server-side `canva_design_id`.

The correct order to bring a Canva image into a SCORM course:

```
1. Canva:generate-design (design_type, query — for Turkish content WRITE A TURKISH PROMPT)
     → returns job_id + candidate_id(s)
2. Canva:create-design-from-candidate (job_id + chosen candidate_id)
     → returns design_id (e.g. "DAHNeYb8aDE")
3. Canva:export-design (design_id, format: { type:"png", width:1280 })
     → returns a signed download URL
4. scorm:add_asset (project_id, signed_url, filename)   ← CALL IMMEDIATELY
     → returns asset id (e.g. "asset_01KVW8GM…")
5. Use that id in build_from_spec / add_screen:
     media_asset_id · image_asset_id · front_asset_id · back_asset_id · blocks[].asset_id …
```

**Critical rules**
- Canva export URLs are **TTL'd AWS S3 signed URLs (~1–12 h)**. Call `add_asset` **immediately** after
  export. Do **not** put the signed URL directly in `build_from_spec` `assets[].source` — it will be
  expired by the time the course is (re)built or previewed. `add_asset` downloads + embeds the bytes,
  so the package stays self-contained regardless of the source URL's TTL.
- Use the **`id`** returned by granular `add_asset`. (`build_from_spec` `assets[].id` is an author-chosen
  local alias for bulk pre-load; the granular tool's returned id is the real asset id.)
- **Turkish content → Turkish Canva prompt.** The template language follows the prompt language.
- The image must be **instructional** (anti-slop C1/C4): a diagram, flow chart, or step-by-step
  infographic that shows the concept — not a decorative poster or stock photo.
- `add_asset` may not appear in tool-search but is directly callable — call it directly.

## SVG diagrams (Claude-generated)

Claude can produce instructional SVG diagrams. The **only** way into a SCORM course is the asset
pipeline — **never inline `<svg>` in `body_html`**: the sanitizer strips `<svg>`/`<canvas>`/`<script>`,
so the visual silently disappears.

**Preferred — `svg_to_asset`** (no base64, validates, optional rasterize):
```
svg_to_asset(project_id, svg_content="<svg …>…</svg>", filename="token-vektor.svg")
  → { id: "asset_…", mime: "image/svg+xml" }
# then: content_slide(media_asset_id=id, layout="text_media") · or blocks[].asset_id · or image_asset_id
# Max LMS compatibility (rare): svg_to_asset(..., rasterize=true) → PNG (needs cairosvg server-side).
```

**Alternative — `add_asset` with a data-URI** (equivalent; `image/svg+xml` is already allowed):
```
add_asset(project_id, "data:image/svg+xml;base64,<b64>", "diagram.svg") → { id }
```

The server packages it as `assets/…/diagram.svg`; the screen renders `<img src="…diagram.svg">`
(responsive `max-width:100%`). SVG renders via `<img>` in all modern LMS browsers, so `rasterize` is
seldom needed. The diagram must be **instructional** (anti-slop C1/C5) — a concept diagram/flow, not decoration.

**Per-diagram workflow (mandatory, no exception):** `svg_to_asset()` → `id` → set `media_asset_id`
(or block `asset_id` / `image_asset_id`) → bind the screen → **`preview` and confirm the image renders**.
*(Mechanism: in preview the asset is embedded as base64 in the page's `__ASSETS__` map and the runtime
sets `img.src`; in the built package it is a real `assets/…/diagram.svg` file referenced by `<img>`.)*

**Animation (not a static diagram)?** `render_motion_video` needs Chromium on the server; if it's absent
the tool returns `render_unavailable`. Fallbacks: a static `svg_to_asset` image, `make_video_from_image_audio`
(PNG + TTS → MP4), or a Lottie asset. Never try to animate via inline `<canvas>`/`<script>` — it's stripped.
