# SCORM Conformance

This document records how packages produced by this server are validated for SCORM conformance.

## Two layers of validation

1. **Authoritative / gating proof — SCORM Cloud (and an LMS).**
   The *binding* evidence that a package conforms is a successful round-trip on
   [SCORM Cloud](https://cloud.scorm.com) and at least one production LMS (e.g. Moodle): the package
   **imports**, **launches**, and **tracks** completion/score correctly. XSD validity alone does **not**
   prove SCORM conformance — runtime behavior does.

2. **Supporting / internal check — XSD schema validation.**
   `validate_package` (the MCP tool) validates the generated `imsmanifest.xml` against the official
   ADL/IMS XSD schemas (see below). This catches manifest-level structural/namespace errors early in
   CI and during authoring. It is a **supporting** signal, not the gate.

## XSD validation details

- **ADL schemas** (`adlcp`, `adlseq`, `adlnav`) are **vendored** in `runtime/schemas/adl/` (public domain).
- **IMS / W3C schemas** (`imscp`, `imsss*`, `ims_xml`, `xml.xsd`) are **fetched at runtime** from
  `www.imsglobal.org` / `www.w3.org` and cached on disk (not redistributed — licensing). Integrity is
  pinned via `runtime/schemas/ims_sources.json` (URL + sha256).
- Validation runs **fully offline** (`no_network`): all schema imports resolve from local files.
  For **air-gapped** deployments, set `SCORM_SCHEMA_DIR=<dir>` containing `12/` and `2004/`
  sub-directories with all schema files; no network access is then attempted.
- If schemas are unavailable (offline, no override), validation **degrades gracefully** to structural
  checks and emits a non-blocking `schema_unavailable` **warning** (it never fails the build).

Automated tests (`tests/test_conformance.py`) assert the generated 1.2 and 2004 manifests are
XSD-valid.

## SCORM Cloud / LMS test procedure (gating)

1. Build a package: call `build_from_spec` with `examples/small.json` (SCORM 1.2) and again with a
   2004 variant (`"scorm_version": "2004"`), then `build_package` → download the `.zip`.
2. SCORM Cloud → **Add Content → Import a SCORM package** → upload the `.zip`.
3. **Launch**; complete the course, answer the quiz.
4. Verify the **registration** shows correct **completion status** and **score**.
5. Repeat on a target LMS (Moodle: *Add an activity → SCORM package*).

## Sürekli otomasyon (W9 P1, 2026-07-23)

Yukarıdaki tek-seferlik doğrulama artık **her `master` push'unda otomatik tekrarlanıyor**:
`.github/workflows/scorm-cloud-conformance.yml` (private repo) → `tools/scorm_cloud_ci_check.py` →
`tools/scorm_cloud.py`. 4 kombinasyon (small/rich × 1.2/2004) her seferinde gerçek SCORM Cloud'a
import edilir, 0-parser-uyarı + launchable doğrulanır, temizlenir. **Bu artık bir gate** (pip-audit
gibi non-blocking değil) — herhangi bir kombinasyon başarısız olursa CI kırmızı olur.

**Hâlâ manuel kalan (bilinçli sınır):** completion/score doğrulaması — SCORM Cloud API ile interaktif
öğrenci oturumu (quiz cevaplama) simüle etmek bu otomasyonun kapsamında değil; elle launch edip
tamamlayarak doğrulanmaya devam eder (bkz. aşağıdaki "SCORM Cloud / LMS test procedure").

## Results — SCORM Cloud (automated, 2026-06-05)

Automated via SCORM Cloud REST API v2 (`/courses/importJobs/upload` → poll job → create
registration → launch link → verify launchable → poll registration). The SCORM Cloud parser is the
de-facto reference; **zero import errors** is the first gating leg, a verified **launchable** link is
the second. Test courses were cleaned up after the run.

| Package | SCORM version | Import | Parser errors | Parser warnings | Registration | Launchable | Completion / Score |
|---|---|---|---|---|---|---|---|
| small.json | 1.2 | COMPLETE | 0 | 0 | created | yes (HTTP 303) | manual* |
| small.json | 2004 4th Ed | COMPLETE | 0 | 0 | created | yes (HTTP 303) | manual* |
| rich.json | 1.2 | COMPLETE | 0 | 0 | created | yes (HTTP 303) | manual* |
| rich.json | 2004 4th Ed | COMPLETE | 0 | 0 | created | yes (HTTP 303) | manual* |

\* **Completion / score** require an interactive learner session (the example courses contain a quiz);
this cannot be produced by an unattended API call. Import + a verified launchable link are automated;
the runtime↔LMS tracking bridge (`cmi.*` score/completion) is exercised by `tests/test_golden.py` and a
manual launch. To verify tracking by hand: build a package, import to SCORM Cloud, **launch**, complete
the quiz, and confirm the registration shows the expected completion/score.

### Finding driven by this run
The SCORM Cloud parser initially flagged the 2004 packages with one warning —
*"Sequencing Control Mode 'Flow' detected on a leaf node, only applicable to cluster nodes [6022]"* —
because the single-SCO manifest placed `imsss:controlMode flow/choice` on the leaf `<item>`. Fixed in
`core/manifest.py` (no sequencing control mode on a single-SCO leaf); re-import now reports **0 warnings**.

## Diğer LMS'ler — manuel checklist (5-LMS matrisinin geri kalanı)

SCORM Cloud dışındaki bu 4 LMS, gerçek kurulum/hesap erişimi gerektirdiği için otomatikleştirilmedi
(W9 P1 kararı, 2026-07-22) — elle doldurulacak bir checklist olarak burada duruyor.

| LMS | Import | Launch | Completion | Score | Tarih | Not |
|---|---|---|---|---|---|---|
| Moodle | ☐ | ☐ | ☐ | ☐ | | |
| Canvas | ☐ | ☐ | ☐ | ☐ | | |
| Blackboard | ☐ | ☐ | ☐ | ☐ | | |
| TalentLMS | ☐ | ☐ | ☐ | ☐ | | |
| Docebo | ☐ | ☐ | ☐ | ☐ | | |

Test paketi: `examples/small.en.json` (1.2) veya `build_from_spec` ile üretilen herhangi bir paket.
Her LMS'in kendi "SCORM paketi yükle" akışını kullan (bkz. `docs/LMS-INTEGRATION.md`).
