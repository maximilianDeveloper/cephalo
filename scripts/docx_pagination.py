#!/usr/bin/env python3
"""
docx_pagination.py

Numbers the front matter of an exported DOCX unlike the main text: Roman
numerals, counted but not shown, or not counted at all, and a main text that
continues the count or starts at 1 (pagination.front_matter and
pagination.main_text in styleguide.md). A reference document cannot do this:
it gives the whole export one section, so the table of contents page shows
its number like a text page. This script splits the export into two
sections at the end of the front matter, after each export.

The end of the front matter is marked in the title page file by a hidden
bookmark on the page break that ends it (docs/reference_management.md,
"The title page"):

    <w:p><w:bookmarkStart w:id="990001" w:name="_cephalo_front_matter_end"/><w:bookmarkEnd w:id="990001"/><w:r><w:br w:type="page"/></w:r></w:p>

That page break becomes the section break. The title page keeps the
reference document's numbering (pagination.title_page, set with
scripts/build_reference_docx.py --title-page): whether it is counted is read
from the document.

Usage:
    python3 scripts/docx_pagination.py workspace/output/document.docx \\
        --front-matter roman --main-text restart

    --front-matter  roman        Roman numerals, I, II, ... (lower: roman-lower)
                    hidden       counted but not shown
                    none         not counted, no number shown
                    arabic       Arabic, like the main text
    --main-text     continue     the main text continues the count
                    restart      the main text starts at 1

With --front-matter arabic and --main-text continue nothing changes: the
export already numbers it that way. A document split before is left as it
is. On Windows, use `py` instead of `python3`. Update the fields in Word
afterwards (Ctrl+A, then F9), so that the table of contents shows the new
numbers.

Exit codes:
    0 — document written, or nothing to change
    2 — not written (the message says why)
"""

import argparse
import copy
import os
import sys

# Encoding guard for Windows consoles (CP1252 by default).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from docx import Document
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.parts.hdrftr import FooterPart, HeaderPart
except ImportError:
    print("Error: python-docx is not installed (pip install -r requirements.txt).")
    sys.exit(2)

MARKER = "_cephalo_front_matter_end"
FRONT = ("roman", "roman-lower", "hidden", "none", "arabic")
MAIN = ("continue", "restart")
# Children of w:sectPr that follow w:pgNumType, in schema order: a new
# w:pgNumType goes before the first of them.
AFTER_PGNUMTYPE = ("cols", "formProt", "vAlign", "noEndnote", "titlePg", "textDirection",
                   "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange")
# Children of w:pPr that follow w:sectPr.
AFTER_SECTPR = ("pPrChange",)
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


class UsageError(Exception):
    pass


def remove_page_numbers(part_element):
    """Remove page numbers: Word's gallery blocks and paragraphs with a PAGE field."""
    removed = 0
    for sdt in list(part_element.iter(qn("w:sdt"))):
        gallery = sdt.find(".//" + qn("w:docPartGallery"))
        if gallery is not None and "page number" in (gallery.get(qn("w:val")) or "").lower():
            sdt.getparent().remove(sdt)
            removed += 1
    for p in list(part_element.iter(qn("w:p"))):
        has_field = any("PAGE" in (f.get(qn("w:instr")) or "").upper().split() for f in p.iter(qn("w:fldSimple")))
        has_field = has_field or any("PAGE" in (t.text or "").upper().split() for t in p.iter(qn("w:instrText")))
        if has_field and p.getparent() is not None:
            p.getparent().remove(p)
            removed += 1
    return removed


def is_empty(part_element):
    """No text, drawing, picture or table left in a header or footer."""
    if part_element.find(".//" + qn("w:tbl")) is not None:
        return False
    for tag in ("w:drawing", "w:pict", "w:object"):
        if part_element.find(".//" + qn(tag)) is not None:
            return False
    return not "".join(t.text or "" for t in part_element.iter(qn("w:t"))).strip()


def without_page_numbers(doc, ref):
    """The relationship id of a copy of the referenced header or footer without page numbers.

    The same id if it shows none; None if nothing is left of it."""
    rid = ref.get(R_ID)
    part = doc.part.related_parts[rid]
    element = copy.deepcopy(part.element)
    if not remove_page_numbers(element):
        return rid
    if is_empty(element):
        return None
    if element.find(qn("w:p")) is None and element.find(qn("w:tbl")) is None:
        element.append(OxmlElement("w:p"))
    footer = ref.tag == qn("w:footerReference")
    new = (FooterPart if footer else HeaderPart).new(doc.part.package)
    new._element = element
    for rel in part.rels.values():  # the copy keeps the pictures and links of the original, under the same ids
        new.rels.add_relationship(rel.reltype, rel.target_ref if rel.is_external else rel.target_part,
                                  rel.rId, rel.is_external)
    return doc.part.relate_to(new, RT.FOOTER if footer else RT.HEADER)


def page_number_type(sect):
    """The section's w:pgNumType, created in schema order if it has none."""
    el = sect.find(qn("w:pgNumType"))
    if el is None:
        el = OxmlElement("w:pgNumType")
        follower = next((c for c in sect if c.tag in {qn("w:" + n) for n in AFTER_PGNUMTYPE}), None)
        if follower is not None:
            follower.addprevious(el)
        else:
            sect.append(el)
    return el


def drop_if_bare(el):
    if el is not None and not el.attrib and len(el) == 0:
        el.getparent().remove(el)


def marker_paragraph(body):
    starts = [b for b in body.iter(qn("w:bookmarkStart")) if b.get(qn("w:name")) == MARKER]
    if len(starts) > 1:
        raise UsageError(f"the bookmark {MARKER} occurs {len(starts)} times; the front matter ends once")
    if not starts:
        return None
    p = starts[0]
    while p is not None and p.tag != qn("w:p"):
        p = p.getparent()
    if p is None:
        raise UsageError(f"the bookmark {MARKER} is not inside a paragraph")
    return p


def split(path, front, main):
    doc = Document(path)
    body = doc.element.body
    body_sect = body.find(qn("w:sectPr"))
    if body_sect is None:
        raise UsageError("the document has no section properties; export it with a reference document "
                         "(pandoc --reference-doc)")
    if front == "arabic" and main == "continue":
        return None, ["front matter numbered like the main text: one section, nothing to change"]
    p = marker_paragraph(body)
    if p is None:
        raise UsageError(f"no end of the front matter marked: the page break that ends it needs the bookmark "
                         f"{MARKER} (docs/reference_management.md, \"The title page\")")
    ppr = p.find(qn("w:pPr"))
    if ppr is not None and ppr.find(qn("w:sectPr")) is not None:
        return None, ["the front matter is a section of its own already: nothing changed"]

    pg = body_sect.find(qn("w:pgNumType"))
    title_counted = pg is None or pg.get(qn("w:start")) != "0"

    # Section 1, the front matter: the page setup and the title page of the export.
    sect1 = copy.deepcopy(body_sect)
    for el in sect1.findall(qn("w:type")) + sect1.findall(qn("w:sectPrChange")):
        sect1.remove(el)
    done = []
    if front in ("hidden", "none"):
        # Without its page numbers; the title page keeps its own (first-page) header and footer.
        for ref in sect1.findall(qn("w:headerReference")) + sect1.findall(qn("w:footerReference")):
            if ref.get(qn("w:type")) == "first":
                continue
            rid = without_page_numbers(doc, ref)
            if rid is None:
                sect1.remove(ref)
            else:
                ref.set(R_ID, rid)
        done.append("front matter " + ("counted but not shown" if front == "hidden" else "not counted, no number shown"))
    elif front in ("roman", "roman-lower"):
        page_number_type(sect1).set(qn("w:fmt"), "upperRoman" if front == "roman" else "lowerRoman")
        done.append("front matter in Roman numerals (" + ("I, II, III" if front == "roman" else "i, ii, iii") + ")")
    else:
        done.append("front matter in Arabic numerals")

    # Section 2, the main text: the export's own section properties, without the title page.
    for el in body_sect.findall(qn("w:titlePg")) + body_sect.findall(qn("w:type")):
        body_sect.remove(el)
    pg2 = page_number_type(body_sect)
    for attr in ("w:start", "w:fmt"):
        if pg2.get(qn(attr)) is not None:
            del pg2.attrib[qn(attr)]
    if main == "restart":
        pg2.set(qn("w:start"), "1")
        done.append("main text from 1")
    elif front == "none":
        # Not counted: the main text follows the title page's number.
        pg2.set(qn("w:start"), "2" if title_counted else "1")
        done.append(f"main text from {2 if title_counted else 1}, after the title page")
    else:
        done.append("main text continuing the count")
    drop_if_bare(pg2)
    drop_if_bare(sect1.find(qn("w:pgNumType")))

    # The page break that ends the front matter becomes the section break.
    for br in list(p.iter(qn("w:br"))):
        if br.get(qn("w:type")) == "page":
            run = br.getparent()
            run.remove(br)
            if run.tag == qn("w:r") and all(c.tag == qn("w:rPr") for c in run):
                run.getparent().remove(run)
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p.insert(0, ppr)
    follower = next((c for c in ppr if c.tag in {qn("w:" + n) for n in AFTER_SECTPR}), None)
    if follower is not None:
        follower.addprevious(sect1)
    else:
        ppr.append(sect1)
    return doc, done


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Number the front matter of an exported DOCX unlike the main text (pagination.front_matter, "
                    "pagination.main_text): two sections, split at the bookmark " + MARKER + ".",
        epilog="Exit codes: 0 written or nothing to change, 2 not written. Update the fields in Word "
               "afterwards (Ctrl+A, then F9).")
    ap.add_argument("document", help="the exported DOCX, changed in place")
    ap.add_argument("--front-matter", required=True, choices=FRONT,
                    help="roman (I, II), roman-lower (i, ii), hidden (counted but not shown), "
                         "none (not counted, no number shown) or arabic (like the main text)")
    ap.add_argument("--main-text", required=True, choices=MAIN,
                    help="continue (the main text continues the count) or restart (it starts at 1)")
    args = ap.parse_args(argv)
    try:
        if not os.path.isfile(args.document):
            raise UsageError(f"{args.document} not found")
        if not args.document.lower().endswith(".docx"):
            raise UsageError(f"{args.document}: expected a .docx file")
        doc, done = split(args.document, args.front_matter, args.main_text)
        if doc is not None:
            doc.save(args.document)
    except UsageError as e:
        print(f"Error: {e}")
        return 2
    except Exception as e:  # a damaged or unusual document: one line and exit 2, not a traceback
        print(f"Error: {type(e).__name__}: {e}")
        return 2
    if doc is None:
        print(f"{args.document}: {done[0]}")
    else:
        print(f"Front matter set as a section of its own: {args.document}")
        for line in done:
            print(f"  - {line}")
        print("  Update the fields in Word (Ctrl+A, then F9) for the table of contents' page numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
