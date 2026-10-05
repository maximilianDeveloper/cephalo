#!/usr/bin/env python3
"""
build_reference_docx.py

Builds the reference document Pandoc takes the layout of an exported DOCX
from (`pandoc --reference-doc`): page size, margins, the page number, the
title page's numbering, and the paragraph styles Pandoc sets the text in.
The values come from styleguide.md; the orchestrator reads them there and
passes them as options. What is not given stays as in Pandoc's own reference
document (see docs/reference_management.md, "The reference document").

Usage:
    python3 scripts/build_reference_docx.py 08_Formal_Review/reference.docx \\
        --font Arial --size 11 --line-spacing 1.5 --align justify \\
        --space-after 6 --heading-sizes 14,12,11 --heading-bold yes \\
        --heading-color 000000 --quote-indent 1,0 --quote-size 10 \\
        --quote-line-spacing 1 --footnote-size 10 --bib-hanging 1 \\
        --page-size A4 --margins 2.5 --page-number bottom-right \\
        --title-page counted --lang de-DE

    Sizes in pt, lengths in cm, line spacing as a multiple (1, 1.15, 1.5, 2).
    --margins takes one value for all sides, or top,right,bottom,left.
    --quote-indent takes left[,right].

Starts from Pandoc's own reference document (`pandoc
--print-default-data-file reference.docx`), or from --base FILE.
On Windows, use `py` instead of `python3`.

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
    from docx.shared import Cm, Pt, RGBColor
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


class UsageError(Exception):
    pass


def number(text, what, low=0.0, high=1000.0):
    """A number; a single value may take a decimal comma (1,5)."""
    try:
        value = float(text.strip().replace(",", "."))
    except ValueError:
        raise UsageError(f"{what}: '{text}' is not a number")
    if not low <= value <= high:
        raise UsageError(f"{what}: {text} is out of range ({low:g} to {high:g})")
    return value


def numbers(text, what, count_allowed, low=0.0, high=1000.0):
    """A list of numbers separated by commas; decimals take a point here (2.5,3)."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) not in count_allowed or not all(parts):
        raise UsageError(f"{what}: expected {' or '.join(map(str, count_allowed))} values separated by commas "
                         f"(decimals with a point), got '{text}'")
    return [number(p, what, low, high) for p in parts]


def yes_no(text, what):
    t = text.strip().lower()
    if t in ("yes", "y", "true", "1", "bold"):
        return True
    if t in ("no", "n", "false", "0", "regular"):
        return False
    raise UsageError(f"{what}: '{text}' is not yes or no")


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


def style(doc, name, kind=WD_STYLE_TYPE.PARAGRAPH, based_on=None):
    """The style of this name, created (based on based_on) if the document lacks it."""
    for s in doc.styles:
        if s.name == name and s.type == kind:
            return s
    s = doc.styles.add_style(name, kind)
    if based_on is not None:
        s.base_style = based_on
    return s


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


def build(args):
    raw = open(args.base, "rb").read() if args.base else default_reference(args.pandoc)
    try:
        doc = Document(io.BytesIO(raw))
    except Exception as e:
        raise UsageError(f"cannot read the starting document ({args.base or 'Pandoc reference.docx'}): {e}")
    done = []

    normal = style(doc, "Normal")
    body = style(doc, "Body Text", based_on=normal)
    first = style(doc, "First Paragraph", based_on=body)
    quote = style(doc, "Block Text", based_on=body)
    bib = style(doc, "Bibliography", based_on=normal)
    note = style(doc, "Footnote Text", based_on=normal)

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
    for st in (body, first):
        if args.align:
            st.paragraph_format.alignment = ALIGN[args.align]
        if args.space_before is not None:
            st.paragraph_format.space_before = Pt(args.space_before)
        if args.space_after is not None:
            st.paragraph_format.space_after = Pt(args.space_after)
    if args.align:
        done.append(f"body text {args.align}")
    if args.space_before is not None or args.space_after is not None:
        before = "-" if args.space_before is None else f"{args.space_before:g}"
        after = "-" if args.space_after is None else f"{args.space_after:g}"
        done.append(f"paragraph spacing {before}/{after} pt before/after")
    if args.first_line_indent is not None:
        body.paragraph_format.first_line_indent = Cm(args.first_line_indent)
        first.paragraph_format.first_line_indent = Cm(0)
        done.append(f"first-line indent {args.first_line_indent:g} cm (not after a heading)")
    if args.lang:
        set_lang(normal, args.lang)
        done.append(f"language {args.lang}")

    # Headings, with the character styles Word links to them.
    heading_font = args.heading_font or args.font
    levels = max(3, len(args.heading_sizes or []))
    for level in range(1, levels + 1):
        h = style(doc, f"Heading {level}", based_on=normal)
        hc = style(doc, f"Heading {level} Char", WD_STYLE_TYPE.CHARACTER)
        for st in (h, hc):
            if heading_font:
                set_font(st, heading_font)
            if args.heading_sizes and level <= len(args.heading_sizes):
                st.font.size = Pt(args.heading_sizes[level - 1])
            if args.heading_bold is not None:
                st.font.bold = args.heading_bold
            if args.heading_color:
                set_color(st, args.heading_color)
        if args.heading_space_before is not None:
            h.paragraph_format.space_before = Pt(args.heading_space_before)
        if args.heading_space_after is not None:
            h.paragraph_format.space_after = Pt(args.heading_space_after)
    if args.heading_sizes:
        done.append("headings " + "/".join(f"{s:g}" for s in args.heading_sizes) + " pt")
    if args.heading_bold is not None:
        done.append("headings " + ("bold" if args.heading_bold else "regular"))
    if args.heading_color:
        done.append(f"heading colour {args.heading_color}")
    if heading_font and args.heading_font:
        done.append(f"heading font {heading_font}")
    for name in ("Title", "Subtitle", "Author", "Date"):
        st = style(doc, name, based_on=normal)
        if heading_font:
            set_font(st, heading_font)
        if args.heading_color:
            set_color(st, args.heading_color)

    # Block quotes.
    if args.quote_indent:
        left = args.quote_indent[0]
        right = args.quote_indent[1] if len(args.quote_indent) > 1 else 0.0
        quote.paragraph_format.left_indent = Cm(left)
        quote.paragraph_format.right_indent = Cm(right)
        quote.paragraph_format.first_line_indent = Cm(0)
        done.append(f"block quotes indented {left:g} cm left, {right:g} cm right")
    if args.quote_size is not None:
        quote.font.size = Pt(args.quote_size)
        done.append(f"block quotes {args.quote_size:g} pt")
    if args.quote_line_spacing is not None:
        quote.paragraph_format.line_spacing = args.quote_line_spacing
        done.append(f"block quotes line spacing {args.quote_line_spacing:g}")

    # Footnotes.
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

    # Page.
    section = doc.sections[0]
    if args.page_size:
        section.page_width, section.page_height = PAGE_SIZES[args.page_size.lower()]
        done.append(f"page {args.page_size}")
    if args.margins:
        m = args.margins * 4 if len(args.margins) == 1 else args.margins
        section.top_margin, section.right_margin, section.bottom_margin, section.left_margin = (Cm(v) for v in m)
        done.append("margins " + "/".join(f"{v:g}" for v in m) + " cm (top/right/bottom/left)")
    if args.page_number and args.page_number != "none":
        where, align = args.page_number.split("-")
        part = section.footer if where == "bottom" else section.header
        part.is_linked_to_previous = False
        style(doc, "Footer" if where == "bottom" else "Header", based_on=normal)
        p = part.paragraphs[0] if part.paragraphs else part.add_paragraph()
        for child in list(p._p):
            if child.tag != qn("w:pPr"):
                p._p.remove(child)
        p.style = doc.styles["Footer" if where == "bottom" else "Header"]
        p.alignment = ALIGN[align]
        page_field(p)
        done.append(f"page number {args.page_number}")
    if args.title_page and args.title_page != "none":
        section.different_first_page_header_footer = True
        if args.title_page == "not-counted":
            set_page_number_start(section, 0)
        done.append("title page " + ("counted, no number shown" if args.title_page == "counted"
                                     else "not counted, no number shown"))

    doc.save(args.output)
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build Pandoc's reference document (--reference-doc) from styleguide values.",
        epilog="Sizes in pt, lengths in cm, line spacing as a multiple. Values not given stay as in "
               "the starting document. Exit codes: 0 written, 2 not written.")
    ap.add_argument("output", help="the reference document to write, e.g. 08_Formal_Review/reference.docx")
    ap.add_argument("--base", help="start from this DOCX instead of Pandoc's own reference document")
    ap.add_argument("--pandoc", default="pandoc", help="the Pandoc command (default: pandoc)")
    ap.add_argument("--font", help="font of the text (body.font)")
    ap.add_argument("--size", help="font size of the text in pt (body.size)")
    ap.add_argument("--line-spacing", help="line spacing of the text, e.g. 1.5 (body.line_spacing)")
    ap.add_argument("--align", choices=("left", "justify"), help="alignment of the text (body.alignment)")
    ap.add_argument("--space-before", help="space before a paragraph in pt")
    ap.add_argument("--space-after", help="space after a paragraph in pt (body.paragraph_spacing)")
    ap.add_argument("--first-line-indent", help="first-line indent in cm (none after a heading)")
    ap.add_argument("--lang", help="language of the text, e.g. de-DE (spell check and hyphenation)")
    ap.add_argument("--heading-font", help="font of headings and title page (default: --font)")
    ap.add_argument("--heading-sizes", help="heading sizes in pt from level 1 on, e.g. 14,12,11")
    ap.add_argument("--heading-bold", help="headings bold: yes or no")
    ap.add_argument("--heading-color", help="heading colour as hex, e.g. 000000 (Pandoc's own is blue)")
    ap.add_argument("--heading-space-before", help="space before a heading in pt")
    ap.add_argument("--heading-space-after", help="space after a heading in pt")
    ap.add_argument("--quote-indent", help="block quote indent in cm: left[,right] (style.block_quote_format)")
    ap.add_argument("--quote-size", help="block quote font size in pt")
    ap.add_argument("--quote-line-spacing", help="block quote line spacing, e.g. 1")
    ap.add_argument("--footnote-size", help="footnote font size in pt (footnotes.size)")
    ap.add_argument("--footnote-line-spacing", help="footnote line spacing (footnotes.line_spacing)")
    ap.add_argument("--bib-hanging", help="reference list hanging indent in cm (bibliography.hanging_indent)")
    ap.add_argument("--bib-line-spacing", help="reference list line spacing (bibliography.line_spacing)")
    ap.add_argument("--bib-space-after", help="space after a reference list entry in pt")
    ap.add_argument("--bib-align", choices=("left", "justify"), help="reference list alignment (bibliography.alignment)")
    ap.add_argument("--link-color", help="colour of links and URLs as hex, e.g. 000000 (Pandoc's own is blue)")
    ap.add_argument("--page-size", choices=("A4", "a4", "letter", "Letter"), help="page size (document.page_size)")
    ap.add_argument("--margins", help="margins in cm: one value, or top,right,bottom,left (document.margins)")
    ap.add_argument("--page-number", choices=PAGE_NUMBER, help="page number position (pagination.position)")
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
                setattr(args, name, number(v, "--" + name.replace("_", "-"), 0, 200))
        for name in ("line_spacing", "quote_line_spacing", "footnote_line_spacing", "bib_line_spacing"):
            v = getattr(args, name)
            if v is not None:
                setattr(args, name, number(v, "--" + name.replace("_", "-"), 0.5, 5))
        for name in ("first_line_indent", "bib_hanging"):
            v = getattr(args, name)
            if v is not None:
                setattr(args, name, number(v, "--" + name.replace("_", "-"), 0, 10))
        if args.heading_sizes:
            args.heading_sizes = numbers(args.heading_sizes, "--heading-sizes", range(1, 10), 1, 200)
        if args.quote_indent:
            args.quote_indent = numbers(args.quote_indent, "--quote-indent", (1, 2), 0, 10)
        if args.margins:
            args.margins = numbers(args.margins, "--margins", (1, 4), 0, 10)
        if args.heading_bold is not None:
            args.heading_bold = yes_no(args.heading_bold, "--heading-bold")
        if args.heading_color:
            args.heading_color = hex_color(args.heading_color, "--heading-color")
        if args.link_color:
            args.link_color = hex_color(args.link_color, "--link-color")
        done = build(args)
    except UsageError as e:
        print(f"Error: {e}")
        return 2
    except OSError as e:
        print(f"Error: {e}")
        return 2
    print(f"Reference document written: {args.output}")
    for line in done or ["nothing changed: no values given"]:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
