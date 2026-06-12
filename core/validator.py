"""core/validator.py — Proje + paket doğrulama (CONTRACTS.md §3, §10, §12.4).

validate_project: spec/yapı tutarlılığı (referans bütünlüğü, suspend_data limiti).
validate_zip: build çıktısının paket yapısı (index.html, geçerli imsmanifest.xml, scorm-again gömülü).
"""

from __future__ import annotations

import json
import zipfile

from lxml import etree

from .project import (
    AdaptivePracticeScreen,
    BranchingScreen,
    GameScreen,
    Project,
    ScreenType,
    VideoScreen,
    ValidationError,
)

SUSPEND_DATA_LIMIT_12 = 4096  # SCORM 1.2 char sınırı


def validate_project(project: Project) -> list[ValidationError]:
    errors: list[ValidationError] = []

    if not project.screens:
        errors.append(ValidationError(code="validation_error",
                                      message="Proje en az bir ekran içermeli", path="screens"))

    asset_ids = {a.id for a in project.assets}
    screen_ids = {s.id for s in project.screens if s.id}

    for i, s in enumerate(project.screens):
        path = f"screens[{i}]"
        # asset referansları
        for field in ("background_asset_id", "media_asset_id", "image_asset_id",
                      "video_asset_id", "poster_asset_id"):
            ref = getattr(s, field, None)
            if ref and ref not in asset_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"Bilinmeyen asset referansı: {ref}", path=f"{path}.{field}"))
        # video: asset ya da url
        if isinstance(s, VideoScreen) and not s.video_asset_id and not s.video_url:
            errors.append(ValidationError(code="validation_error",
                          message="Video ekranı video_asset_id veya video_url gerektirir", path=path))
        # branching hedefleri
        if isinstance(s, BranchingScreen):
            for c in s.choices:
                if c.goto_screen_id not in screen_ids:
                    errors.append(ValidationError(code="validation_error",
                                  message=f"Dallanma hedefi bulunamadı: {c.goto_screen_id}",
                                  path=f"{path}.choices"))
            if s.default_goto and s.default_goto not in screen_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"default_goto bulunamadı: {s.default_goto}", path=path))

        # W3b — oyun iç-tutarlılığı: düğüm-grafiği referansları + a11y süre kapısı (WCAG 2.2.1)
        if isinstance(s, GameScreen):
            node_ids = {n.id for n in s.nodes}
            if s.start_node_id and s.start_node_id not in node_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"Oyun başlangıç düğümü bulunamadı: {s.start_node_id}",
                              path=f"{path}.start_node_id"))
            for n in s.nodes:
                for c in n.choices:
                    if c.to is not None and c.to not in node_ids:
                        errors.append(ValidationError(code="validation_error",
                                      message=f"Oyun seçim hedefi (to) bulunamadı: {c.to}",
                                      path=f"{path}.nodes[{n.id}].choices[{c.id}]"))
                # düğüm-içi asset ref'i jenerik döngüde kontrol edilmez (s.* alanları) → ayrı
                if n.image_asset_id and n.image_asset_id not in asset_ids:
                    errors.append(ValidationError(code="validation_error",
                                  message=f"Bilinmeyen asset referansı: {n.image_asset_id}",
                                  path=f"{path}.nodes[{n.id}].image_asset_id"))
            t = s.mechanics.timer
            if t is not None and not t.allow_extend and not t.allow_disable:
                errors.append(ValidationError(code="validation_error",
                              message="Süreli oyun erişilebilir olmalı (WCAG 2.2.1): timer.allow_extend "
                                      "veya allow_disable en az biri açık olmalı",
                              path=f"{path}.mechanics.timer"))

        # W4b — adaptif pratik: her öğe puanlanabilir olmalı (≥1 doğru seçenek)
        if isinstance(s, AdaptivePracticeScreen):
            for it in s.items:
                if not any(o.correct for o in it.options):
                    errors.append(ValidationError(code="validation_error",
                                  message=f"Adaptif öğe en az bir doğru seçenek gerektirir: {it.id}",
                                  path=f"{path}.items[{it.id}]"))
            if s.max_items and s.max_items > len(s.items):
                errors.append(ValidationError(code="validation_error",
                              message=f"max_items ({s.max_items}) öğe sayısından ({len(s.items)}) büyük olamaz",
                              path=f"{path}.max_items"))

    # suspend_data tahmini (branching durumu) — 1.2 limiti
    if project.scorm_version == "1.2":
        est = _suspend_estimate(project)
        if est > SUSPEND_DATA_LIMIT_12:
            errors.append(ValidationError(code="validation_error",
                          message=f"Tahmini suspend_data ({est}) SCORM 1.2 limitini ({SUSPEND_DATA_LIMIT_12}) aşıyor",
                          path="tracking"))
    return errors


def _suspend_estimate(project: Project) -> int:
    # visited + results + history kabaca
    sample = {"visited": {s.id or str(i): True for i, s in enumerate(project.screens)},
              "results": {s.id or str(i): {"points": 10, "max": 10} for i, s in enumerate(project.screens)
                          if s.type in {ScreenType.mcq, ScreenType.true_false, ScreenType.fill_blank,
                                        ScreenType.drag_drop, ScreenType.hotspot}},
              "history": [s.id or str(i) for i, s in enumerate(project.screens)]}
    return len(json.dumps(sample))


def validate_zip(zip_path: str, scorm_version: str) -> list[ValidationError]:
    errors: list[ValidationError] = []
    try:
        zf = zipfile.ZipFile(zip_path)
    except Exception as e:  # noqa: BLE001
        return [ValidationError(code="build_error", message=f"Zip açılamadı: {e}")]

    with zf:
        names = set(zf.namelist())
        if "index.html" not in names:
            errors.append(ValidationError(code="validation_error", message="index.html eksik"))
        if "imsmanifest.xml" not in names:
            errors.append(ValidationError(code="validation_error", message="imsmanifest.xml eksik"))
        else:
            manifest_bytes = zf.read("imsmanifest.xml")
            try:
                root = etree.fromstring(manifest_bytes)
                tag = etree.QName(root).localname
                if tag != "manifest":
                    errors.append(ValidationError(code="validation_error",
                                  message="Kök öğe <manifest> değil", path="imsmanifest.xml"))
                xml_text = manifest_bytes.decode("utf-8", "ignore")
                if "schemaversion" not in xml_text:
                    errors.append(ValidationError(code="validation_error",
                                  message="schemaversion bulunamadı", path="imsmanifest.xml"))
                if "index.html" not in xml_text:
                    errors.append(ValidationError(code="validation_error",
                                  message="Manifest index.html'i listelemiyor", path="imsmanifest.xml"))
                # Faz 1 — resmi XSD conformance (additive; offline/no_network; şema yoksa uyarı).
                from .schema_validate import validate_manifest_xsd
                errors.extend(validate_manifest_xsd(manifest_bytes, scorm_version))
            except Exception as e:  # noqa: BLE001
                errors.append(ValidationError(code="validation_error",
                              message=f"imsmanifest.xml ayrıştırılamadı: {e}", path="imsmanifest.xml"))
        # scorm-again gömülü mü? (paket modunda runtime/ olarak)
        has_runtime = any(n.endswith("scorm-again.min.js") for n in names)
        index_inlines = False
        if "index.html" in names:
            idx = zf.read("index.html").decode("utf-8", "ignore")
            index_inlines = "Scorm12API" in idx or "API_1484_11" in idx
        if not (has_runtime or index_inlines):
            errors.append(ValidationError(code="validation_error",
                          message="scorm-again runtime gömülü değil"))
    return errors
