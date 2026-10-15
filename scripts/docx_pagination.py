#!/usr/bin/env python3
"""
docx_pagination.py

Numbers the front matter of an exported DOCX unlike the main text: Roman
numerals, counted but not shown, or not counted at all, and a main text that
continues the count or starts at 1 (pagination.front_matter and
pagination.main_text in styleguide.md); and, if pagination.back_matter asks
for it, the back matter too (the reference list, an appendix and what
follows them). A reference document cannot do this: it gives the whole
export one section, so the table of contents page shows its number like a
text page. This script splits the export into sections at the end of the
front matter and at the start of the back matter, after each export.

The end of the front matter is marked in the title page file by a hidden
bookmark on the page break that ends it (docs/reference_management.md,
"The title page"):

    <w:p><w:bookmarkStart w:id="990001" w:name="_cephalo_front_matter_end"/><w:bookmarkEnd w:id="990001"/><w:r><w:br w:type="page"/></w:r></w:p>

The start of the back matter is marked the same way, on the page break
before the reference list (same document, "The reference list"):

    <w:p><w:bookmarkStart w:id="990002" w:name="_cephalo_back_matter_start"/><w:bookmarkEnd w:id="990002"/><w:r><w:br w:type="page"/></w:r></w:p>

Each of these page breaks becomes a section break; a bookmark in a paragraph
of its own, or text after the break, stops the script. The title page keeps
the reference document's numbering (pagination.title_page, set with
scripts/build_reference_docx.py --title-page): whether it is counted is read
from the document.

Usage:
    python3 scripts/docx_pagination.py workspace/output/document.docx \\
        --front-matter roman --main-text restart --back-matter roman-continue

    --front-matter  roman        Roman numerals, I, II, ... (lower: roman-lower)
                    hidden       counted but not shown
                    none         not counted, no number shown
                    arabic       Arabic, like the main text
    --main-text     continue     the main text continues the count
                    restart      the main text starts at 1
    --back-matter   main         like the main text (the default)
                    roman-continue
                                 Roman numerals, continuing the front matter's
                                 count (small ones after roman-lower)
                    roman        Roman numerals from I (lower: roman-lower)
                    restart      Arabic from 1
                    none         no number shown
    --back-matter-start N        with roman-continue: the number of the back
                                 matter's first page (4 for IV)

With roman-continue, the script counts the front matter's pages by its page
breaks: the title page and one page for each page break up to the end of the
front matter. A table of contents or list that fills more than one page,
once Word updates the fields, is not counted that way: give the number with
--back-matter-start.

With --front-matter arabic, --main-text continue and --back-matter main
nothing changes: the export already numbers it that way. A document split
before is left as it is. On Windows, use `py` instead of `python3`. Update
the fields in Word afterwards (Ctrl+A, then F9), so that the table of
contents shows the new numbers.

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
BACK_MARKER = "_cephalo_back_matter_start"
FRONT = ("roman", "roman-lower", "hidden", "none", "arabic")
MAIN = ("continue", "restart")
BACK = ("main", "roman-continue", "roman", "roman-lower", "restart", "none")
# Number formats that give way to Arabic numerals in the main text, and in back matter from 1.
NOT_ARABIC = ("upperRoman", "lowerRoman", "upperLetter", "lowerLetter")
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
        parent = p.getparent()
        if has_field and parent is not None:
            parent.remove(p)
            removed += 1
            # A table cell or text box needs at least one paragraph or table, or Word reports the file damaged.
            if parent.tag in (qn("w:tc"), qn("w:txbxContent")) and parent.find(qn("w:p")) is None \
                    and parent.find(qn("w:tbl")) is None:
                parent.append(OxmlElement("w:p"))
    return removed


def is_empty(part_element):
    """No text, drawing, picture or table left in a header or footer."""
    if part_element.find(".//" + qn("w:tbl")) is not None:
        return False
    for tag in ("w:drawing", "w:pict", "w:object"):
        if part_element.find(".//" + qn(tag)) is not None:
            return False
    return not "".join(t.text or "" for t in part_element.iter(qn("w:t"))).strip()


def without_page_numbers(doc, ref, keep_empty=False):
    """The relationship id of a copy of the referenced header or footer without page numbers.

    The same id if it shows none; None if nothing is left of it, unless keep_empty: then that of the
    empty copy (a later section without a reference of its own would show the previous one's)."""
    rid = ref.get(R_ID)
    part = doc.part.related_parts[rid]
    element = copy.deepcopy(part.element)
    if not remove_page_numbers(element):
        return rid
    if is_empty(element) and not keep_empty:
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


def marker_paragraph(body, name, once):
    """The paragraph that holds the bookmark name; None if there is none."""
    starts = [b for b in body.iter(qn("w:bookmarkStart")) if b.get(qn("w:name")) == name]
    if len(starts) > 1:
        raise UsageError(f"the bookmark {name} occurs {len(starts)} times; {once}")
    if not starts:
        return None
    p = starts[0]
    while p is not None and p.tag != qn("w:p"):
        p = p.getparent()
    if p is None:
        raise UsageError(f"the bookmark {name} is not inside a paragraph")
    return p


def is_split(p):
    """Whether the paragraph ends a section already (a document split before)."""
    ppr = p.find(qn("w:pPr"))
    return ppr is not None and ppr.find(qn("w:sectPr")) is not None


def to_section_break(p, sect):
    """The page break in paragraph p becomes a section break, which ends a section with the properties sect."""
    for br in list(p.iter(qn("w:br"))):
        if br.get(qn("w:type")) == "page":
            run = br.getparent()
            run.remove(br)
            if run.tag == qn("w:r") and all(c.tag == qn("w:rPr") for c in run):
                run.getparent().remove(run)
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p.insert(0, ppr)
    follower = next((c for c in ppr if c.tag in {qn("w:" + n) for n in AFTER_SECTPR}), None)
    if follower is not None:
        follower.addprevious(sect)
    else:
        ppr.append(sect)


def roman(n):
    out = ""
    for value, letters in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                           (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += letters
            n -= value
    return out


def front_matter_last_page(body, p, first):
    """The number of the front matter's last page: the title page's (first), plus one for each page break
    before the one in paragraph p, which ends the front matter."""
    breaks = [br for br in body.iter(qn("w:br")) if br.get(qn("w:type")) == "page"]
    own = [br for br in p.iter(qn("w:br")) if br.get(qn("w:type")) == "page"]
    return first + breaks.index(own[-1])


def outline_level(p, styles):
    """The outline level of a paragraph, its own or its style's (Word's headings have one); None for body text."""
    el, seen = p, set()
    while el is not None:
        lvl = el.find(qn("w:pPr") + "/" + qn("w:outlineLvl"))
        if lvl is not None:
            val = lvl.get(qn("w:val")) or ""
            return int(val) if val.isdigit() and int(val) < 9 else None
        name = el.find(qn("w:name"))
        name = (name.get(qn("w:val")) or "").lower() if name is not None else ""
        if name.startswith("heading ") and name[8:].isdigit():
            return int(name[8:]) - 1
        ref = el.find(qn("w:pPr") + "/" + qn("w:pStyle")) if el is p else el.find(qn("w:basedOn"))
        sid = ref.get(qn("w:val")) if ref is not None else None
        if sid is None or sid in seen:
            return None
        seen.add(sid)
        el = styles.get(sid)
    return None


def listed_headings(doc, end):
    """The text of each paragraph before the end of the front matter that a table of contents lists."""
    styles = {s.get(qn("w:styleId")): s for s in doc.styles.element.findall(qn("w:style"))}
    found = []
    for el in doc.element.body.iter(qn("w:p")):
        if el is end:
            break
        text = "".join(t.text or "" for t in el.iter(qn("w:t"))).strip()
        if text and outline_level(el, styles) is not None:
            found.append(text)
    return found


def ends_with_page_break(p):
    """Whether the paragraph holds a page break with no text or picture after it."""
    breaks = [br for br in p.iter(qn("w:br")) if br.get(qn("w:type")) == "page"]
    if not breaks:
        return False
    after = False
    for el in p.iter():
        if el is breaks[-1]:
            after = True
        elif after and (el.tag in (qn("w:drawing"), qn("w:pict"), qn("w:object"))
                        or (el.tag == qn("w:t") and (el.text or "").strip())):
            return False
    return True


def split_front_matter(doc, p, front, main, title_counted, done):
    """The front matter as a section of its own, up to the page break in paragraph p."""
    body_sect = doc.element.body.find(qn("w:sectPr"))

    # Section 1, the front matter: the page setup and the title page of the export.
    sect1 = copy.deepcopy(body_sect)
    for el in sect1.findall(qn("w:type")) + sect1.findall(qn("w:sectPrChange")):
        sect1.remove(el)
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
    # The main text is Arabic: a template's Roman or letter numbering goes, its "- 1 -" stays.
    if pg2.get(qn("w:start")) is not None:
        del pg2.attrib[qn("w:start")]
    if pg2.get(qn("w:fmt")) in NOT_ARABIC:
        del pg2.attrib[qn("w:fmt")]
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
    if front == "none" or (front == "hidden" and main == "restart"):
        # The table of contents gives a heading here the count of the front matter, which the main text repeats.
        headings = listed_headings(doc, p)
        if headings:
            done.append("warning: the table of contents lists " + ", ".join(f"\"{h}\"" for h in headings)
                        + " with a number the front matter counts but does not show, and which the main text shows "
                          "again: write such a heading in a style of its own (docs/reference_management.md, "
                          "\"The title page\")")

    # The page break that ends the front matter becomes the section break.
    to_section_break(p, sect1)


def split_back(doc, q, back, front, start, computed):
    """The back matter as a section of its own (pagination.back_matter), from the page break in paragraph q."""
    body_sect = doc.element.body.find(qn("w:sectPr"))
    # The section before it, the main text (or everything before it, where the front matter is not split),
    # ends at q with the numbering it has now.
    before = copy.deepcopy(body_sect)
    for el in before.findall(qn("w:type")) + before.findall(qn("w:sectPrChange")):
        before.remove(el)
    # The back matter: the export's section properties, without the title page, on a new page.
    for el in body_sect.findall(qn("w:titlePg")) + body_sect.findall(qn("w:type")):
        body_sect.remove(el)
    pg = page_number_type(body_sect)
    if pg.get(qn("w:start")) is not None:
        del pg.attrib[qn("w:start")]
    if back == "none":
        # A section without a header or footer of its own would show the previous one's: each gets a copy
        # without the page number, empty if nothing else was in it.
        for ref in body_sect.findall(qn("w:headerReference")) + body_sect.findall(qn("w:footerReference")):
            if ref.get(qn("w:type")) != "first":
                ref.set(R_ID, without_page_numbers(doc, ref, keep_empty=True))
        text = "back matter without a page number"
    elif back == "restart":
        # Arabic numerals, in the format the main text has, such as "- 1 -".
        if pg.get(qn("w:fmt")) in NOT_ARABIC:
            del pg.attrib[qn("w:fmt")]
        pg.set(qn("w:start"), "1")
        text = "back matter from 1"
    else:
        lower = back == "roman-lower" or (back == "roman-continue" and front == "roman-lower")
        pg.set(qn("w:fmt"), "lowerRoman" if lower else "upperRoman")
        if back != "roman-continue":
            start = 1
        # Word and LibreOffice would continue the main text's count, not the front matter's: the start is set.
        pg.set(qn("w:start"), str(start))
        number = roman(start).lower() if lower else roman(start)
        text = f"back matter in Roman numerals from {number}"
        if back == "roman-continue":
            text += (", continuing the front matter's count as its page breaks give it (a table of contents or "
                     "list that fills more than one page once Word updates the fields: give --back-matter-start)"
                     if computed else f" (--back-matter-start {start})")
    drop_if_bare(pg)
    to_section_break(q, before)
    return text


def split(path, front, main, back="main", back_start=None):
    doc = Document(path)
    body = doc.element.body
    body_sect = body.find(qn("w:sectPr"))
    if body_sect is None:
        raise UsageError("the document has no section properties; export it with a reference document "
                         "(pandoc --reference-doc)")
    split_front = not (front == "arabic" and main == "continue")
    if not split_front and back == "main":
        return None, ["front matter numbered like the main text: one section, nothing to change"]
    p = marker_paragraph(body, MARKER, "the front matter ends once")
    q = marker_paragraph(body, BACK_MARKER, "the back matter starts once") if back != "main" else None
    if p is None and split_front:
        raise UsageError(f"no end of the front matter marked: the page break that ends it needs the bookmark "
                         f"{MARKER} (docs/reference_management.md, \"The title page\")")
    if p is not None and is_split(p):
        return None, ["the front matter is a section of its own already: nothing changed"]
    if q is not None and is_split(q):
        return None, ["the back matter is a section of its own already: nothing changed"]
    if back != "main" and q is None:
        raise UsageError(f"no start of the back matter marked: the page break before the reference list needs the "
                         f"bookmark {BACK_MARKER} (docs/reference_management.md, \"The reference list\")")
    count_front = back == "roman-continue" and back_start is None
    if count_front and front == "none":
        raise UsageError("--back-matter roman-continue continues the front matter's count, which --front-matter none "
                         "does not count: give the back matter's first number with --back-matter-start")
    if count_front and p is None:
        raise UsageError(f"no end of the front matter marked, from which --back-matter roman-continue counts: put the "
                         f"bookmark {MARKER} on the page break that ends it (docs/reference_management.md, \"The title "
                         f"page\"), or give --back-matter-start")
    # After those checks: in a document split before, the page break is gone.
    if p is not None and (split_front or count_front) and not ends_with_page_break(p):
        raise UsageError(f"the bookmark {MARKER} is not on the page break that ends the front matter: write them "
                         f"as one paragraph with nothing after the break (docs/reference_management.md, "
                         f"\"The title page\")")
    if q is not None and not ends_with_page_break(q):
        raise UsageError(f"the bookmark {BACK_MARKER} is not on the page break before the back matter: write them "
                         f"as one paragraph with nothing after the break (docs/reference_management.md, "
                         f"\"The reference list\")")
    if p is not None and q is not None:
        paragraphs = list(body.iter(qn("w:p")))
        if paragraphs.index(q) <= paragraphs.index(p):
            raise UsageError(f"the bookmark {BACK_MARKER} stands before the end of the front matter ({MARKER}): it "
                             f"goes on the page break before the reference list (docs/reference_management.md, "
                             f"\"The reference list\")")

    pg = body_sect.find(qn("w:pgNumType"))
    title_counted = pg is None or pg.get(qn("w:start")) != "0"
    if count_front:
        first = pg.get(qn("w:start")) if pg is not None else None
        back_start = front_matter_last_page(body, p, int(first) if first and first.isdigit() else 1) + 1
    done = []
    if split_front:
        split_front_matter(doc, p, front, main, title_counted, done)
    if back != "main":
        done.append(split_back(doc, q, back, front, back_start, count_front))
    return doc, done


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Number the front matter of an exported DOCX unlike the main text (pagination.front_matter, "
                    "pagination.main_text), and the back matter (pagination.back_matter): sections of their own, "
                    "split at the bookmarks " + MARKER + " and " + BACK_MARKER + ".",
        epilog="Exit codes: 0 written or nothing to change, 2 not written. Update the fields in Word "
               "afterwards (Ctrl+A, then F9).")
    ap.add_argument("document", help="the exported DOCX, changed in place")
    ap.add_argument("--front-matter", required=True, choices=FRONT,
                    help="roman (I, II), roman-lower (i, ii), hidden (counted but not shown), "
                         "none (not counted, no number shown) or arabic (like the main text)")
    ap.add_argument("--main-text", required=True, choices=MAIN,
                    help="continue (the main text continues the count) or restart (it starts at 1)")
    ap.add_argument("--back-matter", default="main", choices=BACK,
                    help="main (like the main text, the default), roman-continue (Roman numerals, continuing the "
                         "front matter's count), roman or roman-lower (Roman numerals from I or i), restart (Arabic "
                         "from 1) or none (no number shown)")
    ap.add_argument("--back-matter-start", type=int, metavar="N",
                    help="with roman-continue: the number of the back matter's first page (4 for IV), where the "
                         "front matter's page breaks do not give it, as for a table of contents or list that fills "
                         "more than one page")
    args = ap.parse_args(argv)
    try:
        if not os.path.isfile(args.document):
            raise UsageError(f"{args.document} not found")
        if not args.document.lower().endswith(".docx"):
            raise UsageError(f"{args.document}: expected a .docx file")
        if args.back_matter_start is not None and args.back_matter != "roman-continue":
            raise UsageError("--back-matter-start goes with --back-matter roman-continue only")
        if args.back_matter_start is not None and args.back_matter_start < 1:
            raise UsageError("--back-matter-start needs a number from 1 on")
        doc, done = split(args.document, args.front_matter, args.main_text, args.back_matter,
                          args.back_matter_start)
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
        front = not (args.front_matter == "arabic" and args.main_text == "continue")
        what = ("Front matter and back matter set as sections of their own" if front and args.back_matter != "main"
                else "Front matter set as a section of its own" if front else "Back matter set as a section of its own")
        print(f"{what}: {args.document}")
        for line in done:
            print(f"  - {line}")
        print("  Update the fields in Word (Ctrl+A, then F9) for the table of contents' page numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
