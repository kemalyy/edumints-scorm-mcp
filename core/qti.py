"""core/qti.py — W8 QTI 2.1 dışa aktarım: quiz ekranlarını IMS QTI 2.1 assessmentItem'lara çevirir.

Endüstriyel interop: scorm-mcp quiz içeriği QTI-uyumlu sistemlere (LMS / madde bankası / değerlendirme
platformu) taşınabilir. Deterministik XML üretimi (lxml — imsmanifest gibi). SUNUCUDA LLM YOK. Additive.

Desteklenen: mcq (choiceInteraction), true_false (choiceInteraction), fill_blank (textEntryInteraction).
Diğer tipler (oyun/adaptif/sürükle/hotspot…) QTI standart etkileşimlerine birebir oturmaz → atlanır.
NOT: fill_blank için her boşluğun YALNIZ ilk kabul edilen cevabı dışa aktarılır (eşanlamlı eşleme için
QTI mapResponse ileride eklenebilir).
"""
from __future__ import annotations

import html as _html
import re

from lxml import etree

from .project import Project, ScreenType

QTI_NS = "http://www.imsglobal.org/xsd/imsqti_v2p1"
_MATCH_CORRECT = "http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct"
_TAG = re.compile(r"<[^>]+>")

# QTI dışa aktarılabilen quiz tipleri
QTI_EXPORTABLE = (ScreenType.mcq, ScreenType.true_false, ScreenType.fill_blank)


def _text(s: str | None) -> str:
    return _html.unescape(_TAG.sub("", s or "")).strip()


def _q(tag: str) -> str:
    return f"{{{QTI_NS}}}{tag}"


def _new_item(identifier: str, title: str) -> etree._Element:
    return etree.Element(_q("assessmentItem"), nsmap={None: QTI_NS},
                         identifier=identifier, title=title or identifier,
                         adaptive="false", timeDependent="false")


def _choice_item(s, choices: list[tuple[str, str]], correct: list[str], multi: bool) -> etree._Element:
    """choiceInteraction tabanlı madde (mcq + true_false ortak)."""
    item = _new_item(f"item-{s.id}", _text(s.prompt_html)[:120] or s.id)
    rd = etree.SubElement(item, _q("responseDeclaration"), identifier="RESPONSE",
                          cardinality="multiple" if multi else "single", baseType="identifier")
    cr = etree.SubElement(rd, _q("correctResponse"))
    for cid in correct:
        etree.SubElement(cr, _q("value")).text = cid
    etree.SubElement(item, _q("outcomeDeclaration"), identifier="SCORE",
                     cardinality="single", baseType="float")
    body = etree.SubElement(item, _q("itemBody"))
    ci = etree.SubElement(body, _q("choiceInteraction"), responseIdentifier="RESPONSE",
                          maxChoices="0" if multi else "1", shuffle="false")
    etree.SubElement(ci, _q("prompt")).text = _text(s.prompt_html)
    for cid, label in choices:
        sc = etree.SubElement(ci, _q("simpleChoice"), identifier=cid)
        sc.text = label
    etree.SubElement(item, _q("responseProcessing"), template=_MATCH_CORRECT)
    return item


def _mcq_item(s) -> etree._Element:
    choices = [(o.id, _text(o.text_html)) for o in s.options]
    correct = [o.id for o in s.options if o.correct]
    return _choice_item(s, choices, correct, multi=s.multi_select)


def _true_false_item(s) -> etree._Element:
    choices = [("true", "Doğru"), ("false", "Yanlış")]
    correct = ["true" if s.correct else "false"]
    return _choice_item(s, choices, correct, multi=False)


def _fill_blank_item(s) -> etree._Element:
    """Her boşluk için bir textEntryInteraction; ilk kabul edilen cevap correctResponse."""
    item = _new_item(f"item-{s.id}", _text(s.prompt_html)[:120] or s.id)
    for i, b in enumerate(s.blanks):
        rid = f"RESPONSE_{i + 1}"
        rd = etree.SubElement(item, _q("responseDeclaration"), identifier=rid,
                              cardinality="single", baseType="string")
        cr = etree.SubElement(rd, _q("correctResponse"))
        etree.SubElement(cr, _q("value")).text = (b.accepted[0] if b.accepted else "")
    etree.SubElement(item, _q("outcomeDeclaration"), identifier="SCORE",
                     cardinality="single", baseType="float")
    body = etree.SubElement(item, _q("itemBody"))
    p = etree.SubElement(body, _q("p"))
    p.text = _text(s.prompt_html)
    for i in range(len(s.blanks)):
        etree.SubElement(body, _q("textEntryInteraction"), responseIdentifier=f"RESPONSE_{i + 1}",
                         expectedLength="20")
    etree.SubElement(item, _q("responseProcessing"), template=_MATCH_CORRECT)
    return item


_BUILDERS = {
    ScreenType.mcq: _mcq_item,
    ScreenType.true_false: _true_false_item,
    ScreenType.fill_blank: _fill_blank_item,
}


def export_qti_items(project: Project) -> list[tuple[str, str]]:
    """Projedeki QTI-uyumlu quiz ekranlarını QTI 2.1 assessmentItem XML'lerine çevir.
    Döner: [(dosya_adı, xml_string)]. Dışa aktarılamayan tipler sessizce atlanır."""
    out: list[tuple[str, str]] = []
    for idx, s in enumerate(project.screens):
        builder = _BUILDERS.get(s.type)
        if builder is None:
            continue
        sid = s.id or f"idx{idx}"
        item = builder(s)
        xml = etree.tostring(item, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        out.append((f"qti/{sid}.xml", xml.decode("utf-8")))
    return out
