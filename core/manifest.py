"""core/manifest.py — imsmanifest.xml üreteci (CONTRACTS.md §10).

Versiyon-agnostik API; 1.2 tam, 2004 4th Ed iskelet (sequencing v1 kapsamı).
Tek SCO (v1): index.html. Tüm paket dosyaları <file> olarak listelenir.
"""

from __future__ import annotations

from lxml import etree

from .project import QUIZ_TYPES, Project, is_display_diagram

# Namespace'ler
NS_IMSCP_12 = "http://www.imsproject.org/xsd/imscp_rootv1p1p2"
NS_ADLCP_12 = "http://www.adlnet.org/xsd/adlcp_rootv1p2"
NS_IMSCP_2004 = "http://www.imsglobal.org/xsd/imscp_v1p1"
NS_ADLCP_2004 = "http://www.adlnet.org/xsd/adlcp_v1p3"
NS_ADLSEQ_2004 = "http://www.adlnet.org/xsd/adlseq_v1p3"
NS_ADLNAV_2004 = "http://www.adlnet.org/xsd/adlnav_v1p3"
NS_IMSSS = "http://www.imsglobal.org/xsd/imsss"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
# S7 (2.3) — imsmd LOM binding'i: HER İKİ sürüm de IMS Meta-data 1.2.4 (imsmd_v1p2p4.xsd,
# namespace imsmd_v1p2) kullanır — 1.2 için "beklenen" resmi 1.2.1 binding'i (imsmd_rootv1p2p1.xsd)
# BİLEREK kullanılmadı: o şema generalType/educationalType/… içindeki grp.any'yi namespace="##any"
# ile tanımlıyor (kendi namespace'ini de kapsıyor) → description/keyword/title gibi komşu opsiyonel
# elemanlarla UPA (Unique Particle Attribution) ihlali / "content model is not determinist" —
# libxml2 bu şemayı DERLEYEMİYOR (schema_unavailable'a sessizce düşer, XSD doğrulaması hiç
# ÇALIŞMAZ). 1.2.4 binding'i (##other, UPA-temiz) gerçekten derleniyor + doğruluyor (bkz.
# runtime/schemas/driver_12.xsd yorumu). IEEE LOM (ltsc.ieee.org/xsd/LOM) de değerlendirildi ama o
# domain doğrudan/sabit indirilebilir değil (302→portal); mevcut fetch altyapımız yalnız
# imsglobal.org/w3.org'u destekliyor (core/schema_validate.py).
NS_IMSMD_12 = "http://www.imsglobal.org/xsd/imsmd_v1p2"
NS_IMSMD_2004 = "http://www.imsglobal.org/xsd/imsmd_v1p2"
NS_XML = "http://www.w3.org/XML/1998/namespace"


def build_manifest(project: Project, *, file_list: list[str]) -> str:
    """Project + paket dosya listesi → imsmanifest.xml (string)."""
    if project.scorm_version == "2004":
        return _build_2004(project, file_list)
    return _build_12(project, file_list)


def _score_ratio(passing_score: int) -> str:
    """0-100 tam sayı geçme notu → 0-1 ölçekli metin (ör. 80 → "0.8", 100 → "1.0")."""
    ratio = passing_score / 100
    s = f"{ratio:.2f}".rstrip("0").rstrip(".")
    return s if "." in s else f"{s}.0"


def _build_lom(meta: etree._Element, project: Project, ns_imsmd: str) -> None:
    """S7 (2.3) — <metadata> içine opsiyonel imsmd:lom bloğu ekler (schema/schemaversion'dan SONRA;
    imscp metadataType: schema?, schemaversion?, grp.any — ##other/strict, yani başka namespace'ten
    tek bir <lom> elemanı burada geçerli).

    title + language HER ZAMAN basılır (Project'te zorunlu/varsayılı — "alan yoksa eleman yok"
    kuralı bunlar için triviyal olarak sağlanır, LOM'suz manifest yerine minimal-ama-gerçek LOM
    tercih edildi: SCORM Cloud/LMS katalog görünümü için title/language boşuna kaybedilmesin).
    description/keyword/typicalLearningTime SADECE project.metadata'da doluysa basılır.
    intended_audience LOM'a HİÇ eşlenmedi (bkz. CourseMetadata docstring — kapalı sözlük gerektiren
    imsmd:intendedenduserrole'e serbest metni zorlamak yanlış semantik olurdu)."""
    lom = etree.SubElement(meta, f"{{{ns_imsmd}}}lom")
    general = etree.SubElement(lom, f"{{{ns_imsmd}}}general")

    title_el = etree.SubElement(general, f"{{{ns_imsmd}}}title")
    title_ls = etree.SubElement(title_el, f"{{{ns_imsmd}}}langstring")
    title_ls.set(f"{{{NS_XML}}}lang", project.language)
    title_ls.text = project.title

    etree.SubElement(general, f"{{{ns_imsmd}}}language").text = project.language

    md = project.metadata
    if md and md.description:
        desc_el = etree.SubElement(general, f"{{{ns_imsmd}}}description")
        desc_ls = etree.SubElement(desc_el, f"{{{ns_imsmd}}}langstring")
        desc_ls.set(f"{{{NS_XML}}}lang", project.language)
        desc_ls.text = md.description

    for kw in (md.keywords if md else []):
        if not kw:
            continue
        kw_el = etree.SubElement(general, f"{{{ns_imsmd}}}keyword")
        kw_ls = etree.SubElement(kw_el, f"{{{ns_imsmd}}}langstring")
        kw_ls.set(f"{{{NS_XML}}}lang", project.language)
        kw_ls.text = kw

    if md and md.typical_learning_time:
        educational = etree.SubElement(lom, f"{{{ns_imsmd}}}educational")
        tlt = etree.SubElement(educational, f"{{{ns_imsmd}}}typicallearningtime")
        etree.SubElement(tlt, f"{{{ns_imsmd}}}datetime").text = md.typical_learning_time


def _has_scored_content(project: Project) -> bool:
    """review Important-1 — masteryscore/completionThreshold yalnız kursta ≥1 puanlı ekran
    (QUIZ_TYPES, aynı tanım core/antislop.py estimate_suspend_size/_lint_unbound_objectives'te
    kullanılıyor) varsa basılmalı. Aksi halde: varsayılan passing_score=80 ile içerik-only kurs
    yeniden derlenince masteryscore=80 basılır ama runtime hiç puanlı ekran yazmadığından
    score.raw=0 kalır — eski 1.2 LMS'lerde mastery override "completed"i "failed"a çevirir
    (geriye-dönük regresyon). objective_ids alanı YALNIZ QUIZ_TYPES ekran sınıflarında var
    (core/project.py) — puanlı ekran yoksa zaten bağlı hedef de olamaz, bu yüzden sequencing
    bloğunu burada atlamak 2.4 non-primary imsss:objective girdilerini de kaybettirmez."""
    # #126 — display-modlu labeled_diagram QUIZ_TYPES üyesi olsa da runtime'a puan yazmaz →
    # tek-başına "puanlı içerik" saydırmamalı (aksi halde mastery/threshold regresyonu geri gelir).
    return any(s.type in QUIZ_TYPES and not is_display_diagram(s) for s in project.screens)


def _bound_objective_ids(project: Project) -> list[str]:
    """S2 (2.4) — ≥1 puanlı ekrana bağlı kurs hedef id'leri, KURS HEDEF SIRASINDA (deterministik;
    runtime aggregateObjectives ile aynı politika: bağsız hedef manifest'e de yazılmaz)."""
    bound = {oid for s in project.screens for oid in (getattr(s, "objective_ids", None) or [])}
    return [o.id for o in project.objectives if o.id in bound]


def _common_files(file_list: list[str]) -> list[str]:
    # index.html her zaman başta; tekilleştir, sırayı koru
    seen: list[str] = []
    for f in ["index.html", *file_list]:
        if f not in seen:
            seen.append(f)
    return seen


def _build_12(project: Project, file_list: list[str]) -> str:
    nsmap = {None: NS_IMSCP_12, "adlcp": NS_ADLCP_12, "imsmd": NS_IMSMD_12, "xsi": NS_XSI}
    manifest = etree.Element(
        "manifest",
        nsmap=nsmap,
        attrib={
            "identifier": f"MANIFEST-{project.id}",
            "version": "1.2",
            f"{{{NS_XSI}}}schemaLocation": (
                f"{NS_IMSCP_12} imscp_rootv1p1p2.xsd "
                f"{NS_IMSMD_12} imsmd_v1p2p4.xsd "
                f"{NS_ADLCP_12} adlcp_rootv1p2.xsd"
            ),
        },
    )
    meta = etree.SubElement(manifest, "metadata")
    etree.SubElement(meta, "schema").text = "ADL SCORM"
    etree.SubElement(meta, "schemaversion").text = "1.2"
    # S7 (2.3) — imsmd LOM: title/language her zaman, description/keyword/typicalLearningTime
    # yalnız project.metadata doluysa (bkz. _build_lom docstring).
    _build_lom(meta, project, NS_IMSMD_12)

    orgs = etree.SubElement(manifest, "organizations", default="ORG-1")
    org = etree.SubElement(orgs, "organization", identifier="ORG-1")
    etree.SubElement(org, "title").text = project.title
    item = etree.SubElement(org, "item", identifier="ITEM-1", identifierref="RES-1")
    etree.SubElement(item, "title").text = project.title
    # S6 (2.1) — geçme notu varsa adlcp:masteryscore (0-100 tam sayı ölçeği); title'dan hemen sonra,
    # item'ın tek diğer çocuğu (metadata yok) — imscp itemType: title?, item*, metadata?, ##other.
    # review Important-1 — EK OLARAK kursta ≥1 puanlı ekran (QUIZ_TYPES) olması gerekir: aksi halde
    # varsayılan passing_score=80 ile içerik-only kurslarda masteryscore basılır ama runtime hiç
    # score.raw yazmaz → eski 1.2 LMS mastery override'ı "completed"i "failed"a çevirir (bkz.
    # _has_scored_content docstring).
    passing_score = project.tracking.passing_score
    if passing_score and _has_scored_content(project):
        etree.SubElement(item, f"{{{NS_ADLCP_12}}}masteryscore").text = str(int(passing_score))

    resources = etree.SubElement(manifest, "resources")
    res = etree.SubElement(
        resources, "resource",
        attrib={
            "identifier": "RES-1",
            "type": "webcontent",
            f"{{{NS_ADLCP_12}}}scormtype": "sco",
            "href": "index.html",
        },
    )
    for f in _common_files(file_list):
        etree.SubElement(res, "file", href=f)

    return _serialize(manifest)


def _build_2004(project: Project, file_list: list[str]) -> str:
    nsmap = {
        None: NS_IMSCP_2004,
        "adlcp": NS_ADLCP_2004,
        "adlseq": NS_ADLSEQ_2004,
        "adlnav": NS_ADLNAV_2004,
        "imsss": NS_IMSSS,
        "imsmd": NS_IMSMD_2004,
        "xsi": NS_XSI,
    }
    manifest = etree.Element(
        "manifest",
        nsmap=nsmap,
        attrib={
            "identifier": f"MANIFEST-{project.id}",
            "version": "1.0",
            f"{{{NS_XSI}}}schemaLocation": (
                f"{NS_IMSCP_2004} imscp_v1p1.xsd "
                f"{NS_ADLCP_2004} adlcp_v1p3.xsd "
                f"{NS_ADLSEQ_2004} adlseq_v1p3.xsd "
                f"{NS_ADLNAV_2004} adlnav_v1p3.xsd "
                f"{NS_IMSSS} imsss_v1p0.xsd "
                f"{NS_IMSMD_2004} imsmd_v1p2p4.xsd"
            ),
        },
    )
    meta = etree.SubElement(manifest, "metadata")
    etree.SubElement(meta, "schema").text = "ADL SCORM"
    etree.SubElement(meta, "schemaversion").text = "2004 4th Edition"
    # S7 (2.3) — imsmd LOM (bkz. _build_12'deki not; aynı kural).
    _build_lom(meta, project, NS_IMSMD_2004)

    orgs = etree.SubElement(manifest, "organizations", default="ORG-1")
    org = etree.SubElement(orgs, "organization", identifier="ORG-1")
    etree.SubElement(org, "title").text = project.title
    item = etree.SubElement(org, "item", identifier="ITEM-1", identifierref="RES-1")
    etree.SubElement(item, "title").text = project.title
    # NOT: Tek-SCO (leaf) item'a imsss:controlMode flow/choice KOYULMAZ — SCORM Cloud parser'ı
    # bunu "Flow on a leaf node [6022]" diye uyarır (flow/choice yalnız cluster düğümlerde anlamlı).
    # Tek-SCO pakette sequencing'e gerek yok; imsss namespace bildirimi (nsmap) ileride çoklu-SCO
    # için duruyor.
    # S6 (2.1) — geçme notu varsa: adlcp:completionThreshold (0-1) + imsss:sequencing/objectives/
    # primaryObjective/minNormalizedMeasure (0-1). controlMode EKLENMEZ (yukarıdaki [6022] gerekçesi
    # geçerli) — sequencingType'ta tüm alt elemanlar opsiyonel, objectives tek başına geçerli.
    # review Important-1 — EK OLARAK ≥1 puanlı ekran (QUIZ_TYPES) şartı: bkz. _has_scored_content
    # docstring / 1.2 dalındaki aynı yorum. Puanlı ekran yoksa objective_ids da olamaz (yalnız
    # QUIZ_TYPES ekran sınıflarında tanımlı alan) → bloğu atlamak hedef kaybına yol açmaz.
    passing_score = project.tracking.passing_score
    if passing_score and _has_scored_content(project):
        ratio = _score_ratio(passing_score)
        etree.SubElement(item, f"{{{NS_ADLCP_2004}}}completionThreshold").text = ratio
        seq = etree.SubElement(item, f"{{{NS_IMSSS}}}sequencing")
        objectives = etree.SubElement(seq, f"{{{NS_IMSSS}}}objectives")
        primary = etree.SubElement(objectives, f"{{{NS_IMSSS}}}primaryObjective")
        etree.SubElement(primary, f"{{{NS_IMSSS}}}minNormalizedMeasure").text = ratio
        # S2 (2.4) — kurs hedefleri, primaryObjective'den SONRA non-primary imsss:objective olarak
        # (imsss objectivesType: primaryObjective, objective*). KARAR: yalnız ≥1 puanlı ekrana
        # bağlı hedefler basılır (runtime cmi.objectives politikasıyla birebir — LMS 2004'te bu
        # kayıtları pre-populate ederse runtime id'ye göre indeks çözer, .id'yi yeniden yazmaz).
        # objectiveID = Objective.id (xs:anyURI-güvenli alfabe modelde doğrulanır). Kural/rollup
        # eklenmez → leaf item'da atıl (inert) kalırlar, [6022] tarzı yan etki yok; controlMode
        # yine EKLENMEZ. passing_score 0 iken sequencing bloğu hiç basılmadığından (2.1 sözleşmesi,
        # primaryObjective zorunlu-ilk-çocuk) hedefler o durumda RUNTIME-ONLY kalır.
        for oid in _bound_objective_ids(project):
            etree.SubElement(objectives, f"{{{NS_IMSSS}}}objective", objectiveID=oid)

    resources = etree.SubElement(manifest, "resources")
    res = etree.SubElement(
        resources, "resource",
        attrib={
            "identifier": "RES-1",
            "type": "webcontent",
            f"{{{NS_ADLCP_2004}}}scormType": "sco",
            "href": "index.html",
        },
    )
    for f in _common_files(file_list):
        etree.SubElement(res, "file", href=f)

    return _serialize(manifest)


def _serialize(root) -> str:
    return etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True
    ).decode("utf-8")
