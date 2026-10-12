# Third-Party Notices

## Bundled in produced packages (`runtime/`)

### scorm-again (v3.0.5)
- SCORM 1.2 / 2004 runtime API (LMS bridge). https://github.com/jcputney/scorm-again — License: MIT.
- Vendored build + integrity: `runtime/VENDOR.lock`.

### lottie-web (lottie_light)
- Lottie animation player (opt-in; loaded only when a course uses Lottie).
  https://github.com/airbnb/lottie-web — License: MIT.

GSAP (used by the optional HyperFrames video pipeline) is loaded from a CDN at render time and is not
redistributed by this repository.

## Fonts shipped in packages (`runtime/fonts/`) — `composition: "auto"` projects only

- **Inter**, **Outfit**, **JetBrains Mono** — variable fonts (latin + latin-ext subsets, woff2),
  taken from the `@fontsource-variable/*` 5.3.0 npm packages. Licensed under the
  **SIL Open Font License 1.1**; license texts in `runtime/fonts/OFL-*.txt`, provenance and
  checksums in `runtime/fonts/FONTS.lock`. Only the families a course's theme uses are embedded.

## Used for server-side validation only (`runtime/schemas/`) — NOT shipped in packages

### ADL schemas (vendored)
- `adlcp_rootv1p2.xsd`, `adlcp_v1p3.xsd`, `adlseq_v1p3.xsd`, `adlnav_v1p3.xsd` — ADL Initiative SCORM
  content-packaging extension schemas. Public domain (U.S. Government work). Vendored in
  `runtime/schemas/adl/`.

### IMS / 1EdTech and W3C schemas (fetched at runtime, NOT vendored)
- `imscp*`, `imsss*`, `ims_xml.xsd` — IMS / 1EdTech Consortium content-packaging & simple-sequencing
  schemas. `xml.xsd` — W3C. These are **not redistributed** here; they are fetched at runtime from
  `www.imsglobal.org` / `www.w3.org` and cached locally (see `runtime/schemas/README.md`). They remain
  under their respective owners' licenses.

All third-party components retain their original licenses.
