# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

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

## [Unreleased]

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
