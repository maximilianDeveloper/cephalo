#!/usr/bin/env python3
"""
build_reference_docx.py

Builds the reference document Pandoc takes the layout of an exported DOCX
from (`pandoc --reference-doc`): page size, margins, the page number, the
title page's numbering, the paragraph styles Pandoc sets the text in, the
styles Word sets the table of contents in, and a heading style for front
matter that the table of contents does not list.
The values come from styleguide.md; the orchestrator reads them there and
passes them as options. What is not given stays as in Pandoc's own reference
document (see docs/reference_management.md, "The reference document").

Usage:
    python3 scripts/build_reference_docx.py 08_Formal_Review/reference.docx \\
        --font Arial --size 11 --line-spacing 1.5 --align justify \\
        --space-after 6 --heading-sizes 14,12,11 --heading-bold yes \\
        --heading-color 000000 --quote-indent 1 --quote-size 10 \\
        --quote-line-spacing 1 --footnote-size 10 --bib-hanging 1 \\
        --page-size A4 --margins 2.5 --page-number bottom-right \\
        --title-page counted --toc-bold 1 --lang de-DE

    Sizes in pt, lengths in cm (or with a unit: 12mm, 0.5in, 6pt), line
    spacing as a multiple (1, 1.15, 1.5, 2). A single value may take a
    decimal comma (1,5). --margins takes one value for all sides, or four
    for top, right, bottom and left, separated by slashes (2,5/3/2,5/3) or
    by commas with decimal points (2.5,3,2.5,3).

Starts from Pandoc's own reference document (`pandoc
--print-default-data-file reference.docx`), or from --base FILE (a .docx or
a .dotx template). On Windows, use `py` instead of `python3`.

Exit codes:
    0 — reference document written
    2 — it could not be written (the message says why)
"""

import argparse
import io
import os
import re
import subprocess
import sys
import zipfile

# Encoding guard for Windows consoles (CP1252 by default).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from docx import Document
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor, Twips
except ImportError:
    print("Error: python-docx is not installed (pip install -r requirements.txt).")
    sys.exit(2)

PAGE_SIZES = {"a4": (Cm(21.0), Cm(29.7)), "letter": (Cm(21.59), Cm(27.94))}
ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
         "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}
PAGE_NUMBER = ("bottom-right", "bottom-center", "bottom-left", "top-right", "top-center", "top-left", "none")
# Children of w:sectPr that follow w:pgNumType, in schema order: a new
# w:pgNumType goes before the first of them.
AFTER_PGNUMTYPE = ("cols", "formProt", "vAlign", "noEndnote", "titlePg", "textDirection",
                   "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange")
CM_PER = {"cm": 1.0, "mm": 0.1, "in": 2.54, "pt": 2.54 / 72}
# Word's own layout of its table of contents styles (toc 1, toc 2, ...): space after
# and the left indent each level below 1 adds, in twips.
TOC_SPACE_AFTER = 100
TOC_INDENT_PER_LEVEL = 220
TEMPLATE_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
DOCUMENT_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


class UsageError(Exception):
    pass


def number(text, what, low=0.0, high=1000.0, unit=None):
    """A number; a single value may take a decimal comma (1,5) and, for lengths, a unit (cm, mm, in, pt)."""
    t = text.strip().lower().replace(",", ".")
    m = re.fullmatch(r"(-?[0-9]*\.?[0-9]+)\s*([a-z]*)", t)
    if not m:
        raise UsageError(f"{what}: '{text}' is not a number")
    value, suffix = float(m.group(1)), m.group(2)
    if unit == "cm" and suffix:
        if suffix not in CM_PER:
            raise UsageError(f"{what}: '{text}' has an unknown unit (cm, mm, in or pt)")
        value *= CM_PER[suffix]
    elif suffix and suffix != unit:
        raise UsageError(f"{what}: '{text}' is not a number{' in ' + unit if unit else ''}")
    if not low <= value <= high:
        raise UsageError(f"{what}: {text} is out of range ({low:g} to {high:g}{' ' + unit if unit else ''})")
    return value


def numbers(text, what, count_allowed, low=0.0, high=1000.0, unit=None):
    """Several numbers, separated by slashes (decimal commas allowed) or by commas (decimal points)."""
    parts = [p.strip() for p in (re.split(r"[/;]", text) if re.search(r"[/;]", text) else text.split(","))]
    if len(parts) not in count_allowed or not all(parts):
        raise UsageError(f"{what}: expected {' or '.join(map(str, count_allowed))} values, separated by slashes "
                         f"or by commas with decimal points, got '{text}'")
    return [number(p, what, low, high, unit) for p in parts]


def yes_no(text, what):
    t = text.strip().lower()
    if t in ("yes", "y", "true", "1", "bold"):
        return True
    if t in ("no", "n", "false", "0", "regular"):
        return False
    raise UsageError(f"{what}: '{text}' is not yes or no")


def level_list(text, what):
    """Heading levels as a comma list (1, or 1,2), or none."""
    t = text.strip().lower()
    if t == "none":
        return []
    parts = [p.strip() for p in t.split(",")]
    if not all(re.fullmatch(r"[1-9]", p) for p in parts):
        raise UsageError(f"{what}: '{text}' is not a list of levels such as 1 or 1,2, or none")
    return sorted({int(p) for p in parts})


def levels_text(levels):
    """[1] as 'level 1', [1, 2, 3] as 'levels 1-3', [1, 3, 5] as 'levels 1, 3 and 5'."""
    runs = []
    for n in levels:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    names = [f"{a}-{b}" if b > a else str(a) for a, b in runs]
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return ("level " if len(levels) == 1 else "levels ") + joined


def hex_color(text, what):
    t = text.strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", t):
        raise UsageError(f"{what}: '{text}' is not a colour like 000000")
    return t.upper()


def default_reference(pandoc):
    try:
        out = subprocess.run([pandoc, "--print-default-data-file", "reference.docx"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError:
        raise UsageError(f"Pandoc ('{pandoc}') was not found; install it (checklists/precheck.md, "
                         "section 6) or start from a file with --base")
    if out.returncode != 0 or not out.stdout.startswith(b"PK"):
        raise UsageError(f"Pandoc did not print its reference document: "
                         f"{out.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return out.stdout


def as_document(raw):
    """A Word template (.dotx) read as a document: only its content type differs."""
    try:
        zin = zipfile.ZipFile(io.BytesIO(raw))
        types = zin.read("[Content_Types].xml")
    except (zipfile.BadZipFile, KeyError):
        return raw
    if TEMPLATE_TYPE not in types:
        return raw
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.replace(TEMPLATE_TYPE, DOCUMENT_TYPE)
            zout.writestr(item, data)
    return out.getvalue()


def style(doc, name, kind=WD_STYLE_TYPE.PARAGRAPH, based_on=None):
    """The style of this name, created (based on based_on) if the document lacks it.

    Word writes its built-in names in lower case ("footnote text") and python-docx
    translates only some of them, so names and style IDs are compared without case.
    """
    key, sid = name.lower(), name.replace(" ", "").lower()
    for s in doc.styles:
        if s.type == kind and ((s.name or "").lower() == key or (s.style_id or "").lower() == sid):
            return s
    s = doc.styles.add_style(name, kind)
    if based_on is not None:
        s.base_style = based_on
    return s


def existing(doc, name, kind=WD_STYLE_TYPE.PARAGRAPH):
    key, sid = name.lower(), name.replace(" ", "").lower()
    return next((s for s in doc.styles if s.type == kind and
                 ((s.name or "").lower() == key or (s.style_id or "").lower() == sid)), None)


def set_font(st, name):
    """Font of a style, also where it came from the document theme, which would win over a plain name."""
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn("w:" + attr), None)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + attr), name)


def set_color(st, hexval):
    """Colour of a style, also where it came from the document theme, which would win over a plain value."""
    rpr = st.element.get_or_add_rPr()
    color = rpr.find(qn("w:color"))
    if color is None:
        st.font.color.rgb = RGBColor.from_string(hexval)
        return
    for attr in ("themeColor", "themeShade", "themeTint"):
        color.attrib.pop(qn("w:" + attr), None)
    color.set(qn("w:val"), hexval)


def set_lang(st, lang):
    rpr = st.element.get_or_add_rPr()
    el = rpr.find(qn("w:lang"))
    if el is None:
        el = OxmlElement("w:lang")
        rpr.append(el)
    el.set(qn("w:val"), lang)


def page_field(paragraph):
    """A PAGE field in the paragraph, as Word writes a simple field."""
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " PAGE ")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "1"
    run.append(text)
    fld.append(run)
    paragraph._p.append(fld)


def is_page(instr):
    """Whether a field instruction is a PAGE field."""
    return "PAGE" in (instr or "").upper().split()


def strip_page_field(p):
    """Take the PAGE fields out of paragraph p, with the text and fields between the same tabs or line breaks
    ("Page 3 of 9"); a running head, a logo or a link beside them stays, and so does a text box in p, whose
    paragraphs are taken on their own. The number of PAGE fields taken out."""
    items, stop, field, depth = [], 0, None, 0  # items: [tab stop, elements, whether a PAGE field]
    for el in p.iter(qn("w:fldSimple"), qn("w:r")):
        if next(el.iterancestors(qn("w:p")), None) is not p \
                or any(a.tag == qn("w:fldSimple") for a in el.iterancestors()):
            continue
        if el.tag == qn("w:fldSimple"):
            items.append([stop, [el], is_page(el.get(qn("w:instr")))])
            continue
        chars = [c.get(qn("w:fldCharType")) for c in el.iter(qn("w:fldChar"))]
        if depth == 0 and "begin" in chars:
            field = [stop, [], False]
            items.append(field)
        depth += chars.count("begin")
        if depth:  # a field from its begin to its end, as Word writes one: runs of its own
            field[1].append(el)
            field[2] = field[2] or any(is_page(t.text) for t in el.iter(qn("w:instrText")))
            depth = max(depth - chars.count("end"), 0)
            continue
        for c in el:
            if c.tag in (qn("w:tab"), qn("w:ptab"), qn("w:br"), qn("w:cr")):
                stop += 1
            elif c.tag == qn("w:t"):
                items.append([stop, [c], False])
    stops = {s for s, _, page in items if page}
    for s, elements, _ in items:
        for e in elements if s in stops else ():
            if e.getparent() is not None:
                e.getparent().remove(e)
    return sum(1 for _, _, page in items if page)


def remove_page_numbers(part_element):
    """Remove page numbers a starting document already has: Word's gallery blocks, and PAGE fields with the text
    between the same tabs."""
    removed = 0
    for sdt in list(part_element.iter(qn("w:sdt"))):
        gallery = sdt.find(".//" + qn("w:docPartGallery"))
        if gallery is not None and "page number" in (gallery.get(qn("w:val")) or "").lower():
            sdt.getparent().remove(sdt)
            removed += 1
    for p in list(part_element.iter(qn("w:p"))):
        parent = p.getparent()
        if parent is None or not strip_page_field(p):
            continue
        removed += 1
        if "".join(t.text or "" for t in p.iter(qn("w:t"))).strip() \
                or any(p.find(".//" + qn(tag)) is not None
                       for tag in ("w:drawing", "w:pict", "w:object", "w:fldSimple", "w:instrText")):
            continue  # a running head (also a field such as STYLEREF), a logo or a link stays in its paragraph
        parent.remove(p)
        # A table cell or text box needs at least one paragraph or table, or Word reports the file damaged.
        if parent.tag in (qn("w:tc"), qn("w:txbxContent")) and parent.find(qn("w:p")) is None \
                and parent.find(qn("w:tbl")) is None:
            parent.append(OxmlElement("w:p"))
    # A header or footer needs at least one paragraph or table.
    if part_element.find(qn("w:p")) is None and part_element.find(qn("w:tbl")) is None:
        part_element.append(OxmlElement("w:p"))
    return removed


def header_footer_parts(section):
    """The header and footer definitions the section already has (default and first page)."""
    parts = []
    for hf in (section.header, section.footer, section.first_page_header, section.first_page_footer):
        if not hf.is_linked_to_previous:
            parts.append(hf)
    return parts


def set_page_number_start(section, start):
    sect = section._sectPr
    el = sect.find(qn("w:pgNumType"))
    if el is None:
        el = OxmlElement("w:pgNumType")
        follower = next((c for c in sect if c.tag in {qn("w:" + n) for n in AFTER_PGNUMTYPE}), None)
        if follower is not None:
            follower.addprevious(el)
        else:
            sect.append(el)
    el.set(qn("w:start"), str(start))


def complete_page_margins(section):
    """w:pgMar needs all seven values; python-docx writes only the ones set, Pandoc's own has none."""
    pgmar = section._sectPr.find(qn("w:pgMar"))
    if pgmar is None:
        return
    for name, default in (("top", 1440), ("right", 1440), ("bottom", 1440), ("left", 1440),
                          ("header", 709), ("footer", 709), ("gutter", 0)):
        if pgmar.get(qn("w:" + name)) is None:
            pgmar.set(qn("w:" + name), str(default))


def build(args):
    raw = open(args.base, "rb").read() if args.base else default_reference(args.pandoc)
    try:
        doc = Document(io.BytesIO(as_document(raw)))
    except Exception as e:
        raise UsageError(f"cannot read the starting document ({args.base or 'Pandoc reference.docx'}): {e}")
    done = []

    normal = style(doc, "Normal")
    body = style(doc, "Body Text", based_on=normal)
    first = style(doc, "First Paragraph", based_on=body)
    quote = style(doc, "Block Text", based_on=body)
    bib = style(doc, "Bibliography", based_on=normal)
    note = style(doc, "Footnote Text", based_on=normal)
    compact = existing(doc, "Compact")  # list items and table cells; based on Body Text in Pandoc's own

    # Body text: Normal carries font, size and line spacing to every style based on it.
    if args.font:
        set_font(normal, args.font)
        done.append(f"font {args.font}")
    if args.size is not None:
        normal.font.size = Pt(args.size)
        done.append(f"size {args.size:g} pt")
    if args.line_spacing is not None:
        normal.paragraph_format.line_spacing = args.line_spacing
        done.append(f"line spacing {args.line_spacing:g}")
    if args.align:
        for st in (body, first):
            st.paragraph_format.alignment = ALIGN[args.align]
        done.append(f"body text {args.align}")
    if args.space_before is not None or args.space_after is not None:
        # One of the two given: the other is 0, not Pandoc's 9 pt.
        before = args.space_before or 0.0
        after = args.space_after or 0.0
        for st in (body, first):
            st.paragraph_format.space_before = Pt(before)
            st.paragraph_format.space_after = Pt(after)
        done.append(f"paragraph spacing {before:g} pt before, {after:g} pt after")
    if args.first_line_indent is not None:
        body.paragraph_format.first_line_indent = Cm(args.first_line_indent)
        # Pandoc sets the paragraph after a heading, block quote or list in First Paragraph;
        # block quotes, list items and table cells are based on Body Text and get no indent.
        for st in (first, quote, compact):
            if st is not None:
                st.paragraph_format.first_line_indent = Cm(0)
        done.append(f"first-line indent {args.first_line_indent:g} cm "
                    "(none after a heading, block quote or list, none in quotes, lists and tables)")
    if args.lang:
        set_lang(normal, args.lang)
        done.append(f"language {args.lang}")

    # Headings: every level the document has, with the character styles Word links to them.
    heading_font = args.heading_font or args.font
    heading_options = (heading_font or args.heading_sizes or args.heading_bold is not None or args.heading_color
                       or args.heading_space_before is not None or args.heading_space_after is not None)
    if heading_options:
        for level in range(1, 10):
            sized = bool(args.heading_sizes) and level <= len(args.heading_sizes)
            h = existing(doc, f"Heading {level}")
            if h is None:
                if not sized:
                    continue
                h = style(doc, f"Heading {level}", based_on=normal)
            hc = existing(doc, f"Heading {level} Char", WD_STYLE_TYPE.CHARACTER)
            for st in (h, hc):
                if st is None:
                    continue
                if heading_font:
                    set_font(st, heading_font)
                if sized:
                    st.font.size = Pt(args.heading_sizes[level - 1])
                if args.heading_bold is not None:
                    st.font.bold = args.heading_bold
                st.font.italic = False  # Pandoc's own sets level 4 and below in italics
                if args.heading_color:
                    set_color(st, args.heading_color)
            if args.heading_space_before is not None:
                h.paragraph_format.space_before = Pt(args.heading_space_before)
            if args.heading_space_after is not None:
                h.paragraph_format.space_after = Pt(args.heading_space_after)
        done.append("headings upright")
    if args.heading_sizes:
        done.append("headings " + "/".join(f"{s:g}" for s in args.heading_sizes) + " pt from level 1 on")
    if args.heading_bold is not None:
        done.append("headings " + ("bold" if args.heading_bold else "regular"))
    if args.heading_color:
        done.append(f"heading colour {args.heading_color}")
    if args.heading_font:
        done.append(f"heading font {args.heading_font}")
    for name in ("Title", "Subtitle", "Author", "Date"):
        st = existing(doc, name)
        if st is None:
            continue
        if heading_font:
            set_font(st, heading_font)
        if args.heading_color:
            set_color(st, args.heading_color)
    # A heading in front matter that shows no page number (docs/reference_management.md, "The title page"): it looks
    # like Heading 1 but has no outline level, so the table of contents does not list it, and no chapter number from
    # a template's numbered Heading 1. A starting document's own style of that name stays as it is.
    if existing(doc, "Front Matter Heading") is None:
        fmh = style(doc, "Front Matter Heading", based_on=existing(doc, "Heading 1") or normal)
        fmh.next_paragraph_style = body
        ppr = fmh.element.get_or_add_pPr()
        num, num_id, level = OxmlElement("w:numPr"), OxmlElement("w:numId"), OxmlElement("w:outlineLvl")
        num_id.set(qn("w:val"), "0")
        num.append(num_id)
        level.set(qn("w:val"), "9")  # body text
        ppr.append(num)  # w:numPr before w:outlineLvl, the order Word expects
        ppr.append(level)

    # Table of contents: the styles Word sets its entries in when it fills the field in, named as
    # Word names them. A new one gets Word's own layout; one the starting document has keeps its
    # layout. Only the weight comes from the styleguide.
    if args.toc_bold is not None:
        depth = max([3] + args.toc_bold)
        for level in range(1, depth + 1):
            toc = existing(doc, f"toc {level}")
            if toc is None:
                toc = doc.styles.add_style(f"toc {level}", WD_STYLE_TYPE.PARAGRAPH, builtin=True)
                toc.style_id = f"TOC{level}"
                toc.base_style = normal
                toc.next_paragraph_style = normal
                toc.priority = 39
                toc.unhide_when_used = True
                toc.paragraph_format.space_after = Twips(TOC_SPACE_AFTER)
                if level > 1:
                    toc.paragraph_format.left_indent = Twips(TOC_INDENT_PER_LEVEL * (level - 1))
            toc.font.bold = level in args.toc_bold
        regular = [n for n in range(1, depth + 1) if n not in args.toc_bold]
        parts = [levels_text(args.toc_bold) + " bold"] if args.toc_bold else []
        parts += [levels_text(regular) + " regular"] if regular else []
        done.append("table of contents: " + ", ".join(parts))

    # Block quotes.
    if args.quote_indent is not None:
        # Pandoc's own indents block quotes on both sides; a styleguide usually names only the left.
        right = args.quote_indent_right if args.quote_indent_right is not None else 0.0
        quote.paragraph_format.left_indent = Cm(args.quote_indent)
        quote.paragraph_format.right_indent = Cm(right)
        quote.paragraph_format.first_line_indent = Cm(0)
        done.append(f"block quotes indented {args.quote_indent:g} cm left, {right:g} cm right")
    elif args.quote_indent_right is not None:
        quote.paragraph_format.right_indent = Cm(args.quote_indent_right)
        done.append(f"block quotes indented {args.quote_indent_right:g} cm right")
    if args.quote_size is not None:
        quote.font.size = Pt(args.quote_size)
        done.append(f"block quotes {args.quote_size:g} pt")
    if args.quote_line_spacing is not None:
        quote.paragraph_format.line_spacing = args.quote_line_spacing
        done.append(f"block quotes line spacing {args.quote_line_spacing:g}")

    # Footnotes.
    if args.footnote_font:
        set_font(note, args.footnote_font)
        done.append(f"footnotes in {args.footnote_font}")
    if args.footnote_size is not None:
        note.font.size = Pt(args.footnote_size)
        done.append(f"footnotes {args.footnote_size:g} pt")
    if args.footnote_line_spacing is not None:
        note.paragraph_format.line_spacing = args.footnote_line_spacing
        done.append(f"footnotes line spacing {args.footnote_line_spacing:g}")

    # Reference list.
    if args.bib_hanging is not None:
        bib.paragraph_format.left_indent = Cm(args.bib_hanging)
        bib.paragraph_format.first_line_indent = Cm(-args.bib_hanging)
        done.append(f"reference list hanging indent {args.bib_hanging:g} cm")
    if args.bib_line_spacing is not None:
        bib.paragraph_format.line_spacing = args.bib_line_spacing
        done.append(f"reference list line spacing {args.bib_line_spacing:g}")
    if args.bib_space_after is not None:
        bib.paragraph_format.space_after = Pt(args.bib_space_after)
        done.append(f"reference list {args.bib_space_after:g} pt after an entry")
    if args.bib_align:
        bib.paragraph_format.alignment = ALIGN[args.bib_align]
        done.append(f"reference list {args.bib_align}")

    # Links.
    if args.link_color:
        set_color(style(doc, "Hyperlink", WD_STYLE_TYPE.CHARACTER), args.link_color)
        done.append(f"link colour {args.link_color}")

    # Page: the body's last section, which Pandoc takes over (created if the document has none).
    if args.page_size or args.margins or args.page_number or (args.title_page and args.title_page != "none"):
        doc.element.body.get_or_add_sectPr()
        section = doc.sections[-1]
        if args.page_size:
            section.page_width, section.page_height = PAGE_SIZES[args.page_size.lower()]
            done.append(f"page {args.page_size}")
        if args.margins:
            m = args.margins * 4 if len(args.margins) == 1 else args.margins
            section.top_margin, section.right_margin, section.bottom_margin, section.left_margin = (Cm(v) for v in m)
            done.append("margins " + "/".join(f"{v:g}" for v in m) + " cm (top/right/bottom/left)")
        if args.page_number:
            removed = sum(remove_page_numbers(hf._element) for hf in header_footer_parts(section))
            if removed:
                done.append(f"{removed} page number(s) of the starting document removed")
        if args.page_number and args.page_number != "none":
            where, align = args.page_number.split("-")
            part = section.footer if where == "bottom" else section.header
            part.is_linked_to_previous = False
            hf_style = style(doc, "Footer" if where == "bottom" else "Header", based_on=normal)
            hf_style.paragraph_format.line_spacing = 1.0
            hf_style.paragraph_format.space_before = Pt(0)
            hf_style.paragraph_format.space_after = Pt(0)
            p = part.add_paragraph()
            p.style = hf_style
            p.alignment = ALIGN[align]
            page_field(p)
            # The empty paragraph a new header or footer starts with would add a line.
            for old in list(part._element.findall(qn("w:p"))):
                if old is not p._p and not "".join(old.itertext()).strip() \
                        and all(old.find(".//" + qn(tag)) is None for tag in ("w:drawing", "w:pict", "w:object")):
                    part._element.remove(old)
            done.append(f"page number {args.page_number}")
        if args.title_page and args.title_page != "none":
            section.different_first_page_header_footer = True
            for hf in (section.first_page_header, section.first_page_footer):
                if not hf.is_linked_to_previous:
                    remove_page_numbers(hf._element)
            if args.title_page == "not-counted":
                set_page_number_start(section, 0)
            done.append("title page " + ("counted, no number shown" if args.title_page == "counted"
                                         else "not counted, no number shown"))
        complete_page_margins(section)

    doc.save(args.output)
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build Pandoc's reference document (--reference-doc) from styleguide values.",
        epilog="Sizes in pt, lengths in cm (or with a unit: mm, in, pt), line spacing as a multiple; a single "
               "value may take a decimal comma. Values not given stay as in the starting document. "
               "Exit codes: 0 written, 2 not written.")
    ap.add_argument("output", help="the reference document to write, e.g. 08_Formal_Review/reference.docx")
    ap.add_argument("--base", help="start from this DOCX or DOTX instead of Pandoc's own reference document")
    ap.add_argument("--pandoc", default="pandoc", help="the Pandoc command (default: pandoc)")
    ap.add_argument("--font", help="font of the text (body.font)")
    ap.add_argument("--size", help="font size of the text in pt (body.size)")
    ap.add_argument("--line-spacing", help="line spacing of the text, e.g. 1.5 (body.line_spacing)")
    ap.add_argument("--align", choices=("left", "justify"), help="alignment of the text (body.alignment)")
    ap.add_argument("--space-before", help="space before a paragraph in pt (0 if only --space-after is given)")
    ap.add_argument("--space-after", help="space after a paragraph in pt (body.paragraph_spacing; 0 if only "
                                          "--space-before is given)")
    ap.add_argument("--first-line-indent", help="first-line indent in cm (none after a heading, block quote or "
                                                "list, none in quotes, lists and tables)")
    ap.add_argument("--lang", help="language of the text, e.g. de-DE (spell check and hyphenation)")
    ap.add_argument("--heading-font", help="font of headings and title page (default: --font)")
    ap.add_argument("--heading-sizes", help="heading sizes in pt from level 1 on, e.g. 14,12,11; any heading "
                                            "option also sets all heading levels upright")
    ap.add_argument("--heading-bold", help="headings bold: yes or no (all levels)")
    ap.add_argument("--heading-color", help="heading colour as hex, e.g. 000000 (all levels; Pandoc's own is blue)")
    ap.add_argument("--heading-space-before", help="space before a heading in pt")
    ap.add_argument("--heading-space-after", help="space after a heading in pt")
    ap.add_argument("--toc-bold", help="table of contents levels in bold, e.g. 1 or 1,2, or none "
                                       "(headings.toc_emphasis); writes Word's styles toc 1 to toc 3")
    ap.add_argument("--quote-indent", help="block quote indent on the left in cm (style.block_quote_format)")
    ap.add_argument("--quote-indent-right", help="block quote indent on the right in cm (default 0 once "
                                                 "--quote-indent is given)")
    ap.add_argument("--quote-size", help="block quote font size in pt")
    ap.add_argument("--quote-line-spacing", help="block quote line spacing, e.g. 1")
    ap.add_argument("--footnote-font", help="footnote font (footnotes.font; default: --font)")
    ap.add_argument("--footnote-size", help="footnote font size in pt (footnotes.size)")
    ap.add_argument("--footnote-line-spacing", help="footnote line spacing (footnotes.line_spacing)")
    ap.add_argument("--bib-hanging", help="reference list hanging indent in cm (bibliography.hanging_indent)")
    ap.add_argument("--bib-line-spacing", help="reference list line spacing (bibliography.line_spacing)")
    ap.add_argument("--bib-space-after", help="space after a reference list entry in pt")
    ap.add_argument("--bib-align", choices=("left", "justify"), help="reference list alignment (bibliography.alignment)")
    ap.add_argument("--link-color", help="colour of links and URLs as hex, e.g. 000000 (Pandoc's own is blue)")
    ap.add_argument("--page-size", choices=("A4", "a4", "letter", "Letter"), help="page size (document.page_size)")
    ap.add_argument("--margins", help="margins in cm: one value, or top/right/bottom/left (document.margins)")
    ap.add_argument("--page-number", choices=PAGE_NUMBER,
                    help="page number position (pagination.position); page numbers of a --base are removed")
    ap.add_argument("--title-page", choices=("counted", "not-counted", "none"),
                    help="first page without a number: counted, or not counted (pagination.title_page)")
    args = ap.parse_args(argv)

    try:
        if args.base and not os.path.isfile(args.base):
            raise UsageError(f"--base: {args.base} not found")
        parent = os.path.dirname(os.path.abspath(args.output))
        if not os.path.isdir(parent):
            raise UsageError(f"the folder of {args.output} does not exist")
        if not args.output.lower().endswith(".docx"):
            raise UsageError(f"{args.output}: the reference document must end in .docx")
        for name in ("size", "space_before", "space_after", "heading_space_before", "heading_space_after",
                     "quote_size", "footnote_size", "bib_space_after"):
            v = getattr(args, name)
            if v is not None:
                setattr(args, name, number(v, "--" + name.replace("_", "-"), 0, 200, "pt"))
        for name in ("line_spacing", "quote_line_spacing", "footnote_line_spacing", "bib_line_spacing"):
            v = getattr(args, name)
            if v is not None:
                setattr(args, name, number(v, "--" + name.replace("_", "-"), 0.5, 5))
        for name in ("first_line_indent", "bib_hanging", "quote_indent", "quote_indent_right"):
            v = getattr(args, name)
            if v is not None:
                setattr(args, name, number(v, "--" + name.replace("_", "-"), 0, 10, "cm"))
        if args.heading_sizes:
            args.heading_sizes = numbers(args.heading_sizes, "--heading-sizes", range(1, 10), 1, 200, "pt")
        if args.margins:
            args.margins = numbers(args.margins, "--margins", (1, 4), 0, 10, "cm")
        if args.heading_bold is not None:
            args.heading_bold = yes_no(args.heading_bold, "--heading-bold")
        if args.heading_color:
            args.heading_color = hex_color(args.heading_color, "--heading-color")
        if args.toc_bold is not None:
            args.toc_bold = level_list(args.toc_bold, "--toc-bold")
        if args.link_color:
            args.link_color = hex_color(args.link_color, "--link-color")
        done = build(args)
    except UsageError as e:
        print(f"Error: {e}")
        return 2
    except Exception as e:  # an unusual starting document: one line and exit 2, not a traceback
        print(f"Error: {type(e).__name__}: {e}")
        return 2
    print(f"Reference document written: {args.output}")
    for line in done or ["nothing changed: no values given"]:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
