"""Read and write docweave annotations in .docx files via custom XML parts.

Annotations are stored as a single custom XML part at
``/customXml/docweave_annotations.xml`` inside the .docx archive.  The XML
structure maps heading text to JSON-encoded annotation dicts::

    <docweave-annotations>
      <section heading="Introduction" level="1">
        {"summary": "Overview section", "tags": ["intro"]}
      </section>
    </docweave-annotations>

This part is invisible to Word users and survives normal editing.
"""

from __future__ import annotations

import json
from typing import Any
from xml.etree import ElementTree as ET

# Custom XML part name inside the .docx package
_PART_NAME = "/customXml/docweave_annotations.xml"
_CONTENT_TYPE = "application/xml"
_ROOT_TAG = "docweave-annotations"


def read_annotations(document: Any) -> dict[str, dict[str, Any]]:
    """Read annotations from a Document's custom XML part.

    Returns a mapping of ``"heading_text::level"`` → annotation dict.
    """
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    annotations: dict[str, dict[str, Any]] = {}

    for rel in document.part.rels.values():
        if rel.reltype != RT.CUSTOM_XML:
            continue
        part = rel.target_part
        if not str(part.partname).startswith("/customXml/docweave"):
            continue
        try:
            root = ET.fromstring(part.blob)
        except ET.ParseError:
            continue
        if root.tag != _ROOT_TAG:
            continue
        for section_el in root.findall("section"):
            heading = section_el.get("heading", "")
            level = section_el.get("level", "1")
            key = f"{heading}::{level}"
            text = (section_el.text or "").strip()
            if text:
                try:
                    annotations[key] = json.loads(text)
                except json.JSONDecodeError:
                    pass
        break  # only one docweave part expected

    return annotations


def write_annotations(
    document: Any,
    heading_annotations: dict[str, dict[str, Any]],
) -> None:
    """Write annotations into a Document's custom XML part.

    *heading_annotations* maps ``"heading_text::level"`` → annotation dict.
    Creates or replaces the custom XML part.
    """
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.opc.packuri import PackURI
    from docx.opc.part import Part

    root = ET.Element(_ROOT_TAG)
    for key, ann in sorted(heading_annotations.items()):
        parts = key.rsplit("::", 1)
        heading = parts[0]
        level = parts[1] if len(parts) == 2 else "1"
        el = ET.SubElement(root, "section", heading=heading, level=level)
        el.text = json.dumps(ann, ensure_ascii=False)

    blob = ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")

    # Remove existing docweave annotation part if present
    rids_to_remove = []
    for rid, rel in document.part.rels.items():
        if rel.reltype != RT.CUSTOM_XML:
            continue
        if str(rel.target_part.partname).startswith("/customXml/docweave"):
            rids_to_remove.append(rid)

    for rid in rids_to_remove:
        del document.part.rels[rid]

    # Create new part and relate it
    partname = PackURI(_PART_NAME)
    custom_part = Part(partname, _CONTENT_TYPE, blob=blob, package=document.part.package)
    document.part.relate_to(custom_part, RT.CUSTOM_XML)


def annotation_key(heading_text: str, level: int) -> str:
    """Build the lookup key for a heading."""
    return f"{heading_text}::{level}"
