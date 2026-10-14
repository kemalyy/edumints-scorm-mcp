"""v1.8.1 (#178) — SVG temizliği: paketlenen SVG doğrudan açıldığında etkin içerik çalıştırmasın.

`<img>` içinde SVG script'i zaten çalışmaz; ama paketteki .svg dosyası tarayıcıda tek başına açılabilir.
Bu yüzden `svg_to_asset` ve `build_from_spec` `assets[].svg` aynı temizlikten geçer: DTD/entity
reddedilir (XXE / entity genişletme); ayrıntı `clean` belgesinde (allowlist, v1.8.1 final inceleme)."""
from __future__ import annotations

import re

from lxml import etree

_SVG = "http://www.w3.org/2000/svg"
_XLINK = "{http://www.w3.org/1999/xlink}href"
_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
_DROP = {"script", "foreignobject", "style"}
_ANIM = {"set", "animate", "animatemotion", "animatetransform", "discard"}
_URL = re.compile(r"url\(\s*['\"]?\s*(?!#)", re.I)


class SvgError(ValueError):
    pass


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _ns(tag) -> str:
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


def _remove(el) -> None:
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def clean(svg: str) -> str:
    """Allowlist: yalnız SVG ad alanındaki öğeler kalır (XHTML iframe/object/meta vb. düşer);
    `<script>`/`<foreignObject>`/`<style>` düşer; `href`'i hedefleyen animasyon (`set`/`animate…`)
    düşer; `on*`, `xml:base`, yerel olmayan `href` ve dış `url(…)` içeren `style` kaldırılır."""
    if "<!doctype" in svg.lower() or "<!entity" in svg.lower():
        raise SvgError("SVG'de DTD/ENTITY bildirimine izin verilmez")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
                             huge_tree=False, remove_comments=True, remove_pis=True)
    try:
        root = etree.fromstring(svg.strip().encode("utf-8"), parser)
    except etree.XMLSyntaxError as e:
        raise SvgError(f"Geçersiz SVG/XML: {e}") from e
    if _local(root.tag) != "svg" or _ns(root.tag) != _SVG:
        raise SvgError("Kök öğe SVG ad alanında <svg> olmalı (xmlns=\"http://www.w3.org/2000/svg\")")
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        tag = _local(el.tag)
        if _ns(el.tag) != _SVG or tag in _DROP:
            _remove(el)
            continue
        if tag in _ANIM and _local(el.get("attributeName", "")).endswith("href"):
            _remove(el)
            continue
        for attr in list(el.attrib):
            name, v = _local(attr), (el.attrib[attr] or "").strip().lower()
            if name.startswith("on") or attr == _XML_BASE or name == "base":
                del el.attrib[attr]
            elif attr in ("href", _XLINK):
                if not (v.startswith("#") or v.startswith("data:image/")):
                    del el.attrib[attr]
            elif name == "style" and (_URL.search(v) or "@import" in v or "expression(" in v):
                del el.attrib[attr]
            elif _URL.search(v):  # fill="url(https://…)" vb. dış kaynak
                del el.attrib[attr]
    etree.cleanup_namespaces(root)
    return etree.tostring(root, encoding="unicode")
