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
    ExplorationScreen,
    GameScreen,
    Project,
    ScreenType,
    VideoScreen,
    ValidationError,
)

SUSPEND_DATA_LIMIT_12 = 4096  # SCORM 1.2 char sınırı
OUTLINE_MAX_DEPTH = 3  # senaryo hattı — outline derinlik sınırı (kök=1)


def validate_project(project: Project, *, strict: bool = False) -> list[ValidationError]:
    """strict (SP-5, opt-in): anti-slop'un küratörlü WARN kümesi de bloklar (bkz. antislop.
    STRICT_PROMOTED_CODES). Varsayılan False → davranış değişmedi."""
    errors: list[ValidationError] = []

    if not project.screens:
        errors.append(ValidationError(code="validation_error",
                                      message="Proje en az bir ekran içermeli", path="screens"))

    asset_ids = {a.id for a in project.assets}
    screen_ids = {s.id for s in project.screens if s.id}

    # S2 (2.4) — hedef referans bütünlüğü: kurs hedef id'leri tekil olmalı; puanlı ekranın
    # objective_ids'i yalnız tanımlı hedeflere işaret edebilir (bilinmeyen id = sert hata).
    objective_ids: set[str] = set()
    for j, o in enumerate(project.objectives):
        if o.id in objective_ids:
            errors.append(ValidationError(code="validation_error",
                          message=f"Yinelenen hedef id'si: {o.id}", path=f"objectives[{j}]"))
        objective_ids.add(o.id)

    # Senaryo hattı Faz 1 — outline yapısal bütünlüğü (sert hatalar). Outline boşsa bu blok
    # TEK kalem bile üretmez (geriye uyum; yalnız sarkan node_id istisnası — o da veri hatasıdır).
    errors.extend(_validate_outline(project, objective_ids))

    # F2 (#113) — exploration.store_key kurs genelinde TEKİL olmalı: geri-oynatma
    # (data-exploration-ref) referansının tek adresidir; çakışma sessiz veri karışmasıdır.
    seen_store_keys: set[str] = set()

    for i, s in enumerate(project.screens):
        path = f"screens[{i}]"

        if isinstance(s, ExplorationScreen):
            if s.store_key in seen_store_keys:
                errors.append(ValidationError(code="validation_error",
                              message=f"Yinelenen exploration store_key: '{s.store_key}' — "
                                      "kurs genelinde tekil olmalı (geri-oynatma adresi)",
                              path=f"{path}.store_key"))
            seen_store_keys.add(s.store_key)
        # asset referansları
        # task-5 / FIX 2 — html_asset_id (embed_html) BURADA olmak ZORUNDA: eksikken hatalı bir
        # id doğrulamayı geçiyordu, build_package başarılı oluyor, manifest geçerli kalıyor ama
        # assetSrc() "" dönüp iframe'e src HİÇ verilmiyordu — üstelik varsayılan on_view ile kurs
        # LMS'e yine `completed` raporluyordu (doğrulamayı geçen BOŞ kurs).
        for field in ("background_asset_id", "media_asset_id", "image_asset_id",
                      "video_asset_id", "poster_asset_id", "html_asset_id"):
            ref = getattr(s, field, None)
            if ref and ref not in asset_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"Bilinmeyen asset referansı: {ref}", path=f"{path}.{field}"))

        # P1/P3/P4 — per-item asset referansları (içerik blokları + item/card/event görselleri)
        def _aref(ref, sub):
            if ref and ref not in asset_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"Bilinmeyen asset referansı: {ref}", path=f"{path}.{sub}"))
        for b in getattr(s, "blocks", None) or []:
            _aref(getattr(b, "asset_id", None), "blocks.asset_id")
        for it in getattr(s, "items", None) or []:
            _aref(getattr(it, "image_asset_id", None), "items.image_asset_id")
        for t in getattr(s, "tabs", None) or []:
            _aref(getattr(t, "image_asset_id", None), "tabs.image_asset_id")
        for c in getattr(s, "cards", None) or []:
            _aref(getattr(c, "front_asset_id", None), "cards.front_asset_id")
            _aref(getattr(c, "back_asset_id", None), "cards.back_asset_id")
        for e in getattr(s, "events", None) or []:
            _aref(getattr(e, "image_asset_id", None), "events.image_asset_id")

        # S2 (2.4) — puanlı ekranın hedef bağları: bilinmeyen hedef id'si build'i bloklar
        for oid in getattr(s, "objective_ids", None) or []:
            if oid not in objective_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"Bilinmeyen hedef referansı: {oid} (course.objectives'te tanımlı değil)",
                              path=f"{path}.objective_ids"))

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

    # W6 — oyun anti-slop kapısı: YAPISAL bug'lar (ulaşılamaz düğüm, sahte seçim) build'i bloklar.
    # Pedagojik kokular (süs skor, bedava ipucu, dar zorluk) WARN'dur → lint_course aracı (build'i bloklamaz).
    # SP-5: strict modda terfi eden WARN'lar mesajda [strict:<kod>] öneki taşır — çağıran hangi
    # kuralın yalnız strict'te blokladığını ayırt edebilsin (aksiyon alınabilir hata yükü).
    from .antislop import lint_errors
    for li in lint_errors(project, strict=strict):
        msg = li.message if li.severity == "error" else f"[strict:{li.code}] {li.message}"
        errors.append(ValidationError(code="validation_error", message=msg, path=li.path))
    return errors


def _validate_outline(project: Project, objective_ids: set[str]) -> list[ValidationError]:
    """Senaryo hattı Faz 1 — outline YAPISAL bütünlüğü (hepsi SERT hata, 3.8 veri bütünlüğü):

      - yinelenen düğüm id'si
      - sarkan parent_id
      - döngü (self-parent dahil)
      - derinlik > OUTLINE_MAX_DEPTH (kök=1)
      - sarkan screen.node_id (outline hiç yokken node_id vermek de sarkan referanstır)
      - hedef ad-alanı çakışması: düğüm objective.id'leri kurs hedef ad-alanına KAYDOLUR
        (objective_ids kümesine eklenir → ekranların objective_ids'i bunlara referans
        verebilir); course.objectives ile veya başka düğümle çakışan id sert hatadır.

    KAPSAM NOTU: en-yakın-atadan hedef mirası ve ORPHAN_PAGE, Faz 2 derleme mantığıdır —
    Faz 1'de ekranlar hâlâ doğrudan yazarlıdır, burada yalnız yapısal doğrulama yapılır.
    Outline boş + hiçbir ekranda node_id yok → bu fonksiyon boş liste döndürür (geriye uyum)."""
    errors: list[ValidationError] = []
    outline = project.outline

    node_ids: set[str] = set()
    for j, n in enumerate(outline):
        if n.id in node_ids:
            errors.append(ValidationError(code="validation_error",
                          message=f"Yinelenen outline düğüm id'si: {n.id}", path=f"outline[{j}]"))
        node_ids.add(n.id)

    by_id = {n.id: n for n in outline}
    for j, n in enumerate(outline):
        if n.parent_id is not None and n.parent_id not in node_ids:
            errors.append(ValidationError(code="validation_error",
                          message=f"Bilinmeyen outline parent_id referansı: {n.parent_id}",
                          path=f"outline[{j}].parent_id"))

    # döngü + derinlik — parent zincirini yürü (sarkan parent'ta zincir kesilir; o zaten hatalı)
    for j, n in enumerate(outline):
        depth, seen, cur = 1, {n.id}, n
        while cur.parent_id is not None:
            if cur.parent_id in seen:
                errors.append(ValidationError(code="validation_error",
                              message=f"Outline'da döngü: '{n.id}' düğümünün atalar zinciri kendine dönüyor",
                              path=f"outline[{j}].parent_id"))
                break
            if cur.parent_id not in by_id:
                break  # sarkan parent — yukarıda raporlandı
            cur = by_id[cur.parent_id]
            seen.add(cur.id)
            depth += 1
        else:
            if depth > OUTLINE_MAX_DEPTH:
                errors.append(ValidationError(code="validation_error",
                              message=f"Outline derinlik sınırı aşıldı: '{n.id}' düğümü {depth}. "
                                      f"kademede (en çok {OUTLINE_MAX_DEPTH}, kök=1)",
                              path=f"outline[{j}]"))

    # hedef ad-alanı: düğüm hedefleri kurs hedefleriyle AYNI ad-alanına kaydolur (Faz 2
    # derleme birleşimi için ön koşul: id çakışması bugünden sert hata).
    for j, n in enumerate(outline):
        if n.objective is not None:
            if n.objective.id in objective_ids:
                errors.append(ValidationError(code="validation_error",
                              message=f"Yinelenen hedef id'si: {n.objective.id} — outline "
                                      f"'{n.id}' düğümünün hedefi kurs hedef ad-alanıyla çakışıyor",
                              path=f"outline[{j}].objective"))
            objective_ids.add(n.objective.id)

    # ekran → düğüm bağı: sarkan node_id sert hata (outline hiç yokken node_id de sarkandır)
    for i, s in enumerate(project.screens):
        nid = getattr(s, "node_id", None)
        if nid and nid not in node_ids:
            errors.append(ValidationError(code="validation_error",
                          message=f"Bilinmeyen outline node_id referansı: {nid}",
                          path=f"screens[{i}].node_id"))

    # Faz 4 (§6.1) — UNREACHABLE_NODE (SERT): unlock_rule="sequential" düğümün önceki
    # kardeşinin ALT-AĞACINDA hiç bağlı ekran yoksa düğüm asla açılamaz → erişilemez içerik.
    # AD SAPMASI (bilinçli): plan'ın hata enum'undaki NO_KEYBOARD_PATH klavye-erişim
    # sınıfının adıdır; erişilemez-İÇERİK yapılandırması ayrı adla anılır (PR'da belgeli).
    # Runtime (scorm.js lockedNodes) bu durumda savunmacı olarak KİLİTLEMEZ — kapı burasıdır.
    errors.extend(_validate_unreachable_nodes(project, node_ids))
    return errors


def _validate_unreachable_nodes(project: Project, node_ids: set[str]) -> list[ValidationError]:
    outline = project.outline
    if not outline:
        return []
    # düğüm başına ALT-AĞAÇ ekran sayısı (scorm.js nodeProgress ile aynı sayım: ekranın
    # düğüm zincirindeki her ataya işlenmesi). Döngü/sarkan zincirler yukarıda raporlandı;
    # burada savunmacı olarak zincir kesilir.
    by_id = {n.id: n for n in outline}
    subtree_screens: dict[str, int] = {n.id: 0 for n in outline}
    for s in project.screens:
        nid = getattr(s, "node_id", None)
        seen: set[str] = set()
        while nid and nid in by_id and nid not in seen:
            subtree_screens[nid] += 1
            seen.add(nid)
            nid = by_id[nid].parent_id
    errors: list[ValidationError] = []
    for j, n in enumerate(outline):
        if n.unlock_rule != "sequential":
            continue
        prev = None
        for k in range(j - 1, -1, -1):
            if outline[k].parent_id == n.parent_id:
                prev = outline[k]
                break
        if prev is None:
            continue  # ilk kardeşte sequential = baştan açık (meşru)
        if subtree_screens.get(prev.id, 0) == 0:
            errors.append(ValidationError(
                code="validation_error",
                message=(f"UNREACHABLE_NODE: '{n.id}' düğümü sequential kilitli ama önceki "
                         f"kardeşi '{prev.id}' alt-ağacında tamamlanabilir ekran yok — düğüm "
                         "asla açılamaz (kilidi kaldır ya da önceki kardeşe ekran bağla)"),
                path=f"outline[{j}].unlock_rule"))
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
