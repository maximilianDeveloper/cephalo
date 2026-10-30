#!/usr/bin/env python3
"""
repeated_citations.py

Lists the repeated citations of a work, for the format check of
in_text.repeated_citation in styleguide.md: every pair of a source cited
again right after its previous citation, one line each, with the chapter
file and line of the repeated citation and the form the text gives it. It
only reads, and it judges no form: whether a line follows the styleguide's
value is for the format-verifier to check, line by line.

The previous citation is the one just before, in reading order: across
paragraphs, pages and chapter files, which are read one after the other in
the order given, and with a footnote's citations at its mark. A pair is a
source that both a citation and the one just before it name, also as one of
several sources or in a secondary citation:
    (Keller 2018, S. 4) ... (ebd., S. 5)           Keller 2018, cited again
    (Keller 2018, S. 4) ... (vgl. Keller 2018)     Keller 2018, cited again
    (Keller 2018; Weber 2019) ... (Weber 2019)     Weber 2019, cited again, after
                                                   a citation of 2 sources
    (Keller 2018) ... Weber (2019) ... (Keller 2018)   no pair

What it reads as a citation:
  - author and year in parentheses: (Keller 2018, S. 44), (vgl. Keller/Weber
    2018, S.\\ 5), (Keller & Weber, 2018, p. 5), (Keller et al. 2018), (Keller
    u. a. 2018), (Keller 2018a), (Keller 2018, 2020), (Keller o. J.), several
    sources separated by ";", and a secondary citation (Weber 1922, S. 31,
    zit. nach Keller 2018, S. 5; also "zitiert nach", "cited in", "quoted in"),
    which names both;
  - author and year in the sentence: Keller (2018, S. 44), Keller und Weber
    (2018), Keller et al. (2018);
  - ebd., ebenda, ibid. or ibidem, also with a page or "vgl." ((ebd., S. 5),
    (Ibid., p. 3)), and a page alone in parentheses ((S. 45)): these name the
    source of the citation just before, the source named last where that one
    names several;
  - Pandoc citekeys: [@keller2018, S. 5], [vgl. @keller2018; @weber2019],
    @keller2018 [S. 5], [Weber 1922, S. 31, zit. nach @keller2018, S. 5];
  - in a footnote, an inline note (^[...]) and a source line below a table
    or figure ("Quelle: Keller 2018, S. 5"), also without parentheses:
    "Vgl. Keller 2018, S. 5.", "Ebd., S. 6.".
A source is its surnames and year ("Keller/Weber 2018" and "Keller und Weber
(2018)" are one source, "Keller 2018a" and "Keller 2018b" two), or its
citekey. Left out: the YAML front matter, HTML comments, code and raw
blocks, and the reference list (the section under a heading such as
"Literaturverzeichnis" or "References" whose entries all have a year, as
scripts/verbatim_check.py finds it).

The report names the files in the order read, counts the citations, names
the reference list it left out, and lists the sources read with the number
of their citations (a parenthesis that is no citation, such as "(Mai
2020)", shows there as a source). Then "Pairs:" and one line per pair:
    - ch_2_body.md:14 — Keller 2018, cited again as `(ebd., S.\\ 5)`
with the part, for a citation of several sources (`Weber 2019, S. 3` in
`(...)`), and a note where the previous citation names several sources, is
a secondary citation or stands in another file, and for a citation in a
footnote. Last, each ebd., ibid. or page alone with no citation before it.

Usage:
    python scripts/repeated_citations.py workspace/output/chapters/
    python scripts/repeated_citations.py ch_1_intro.md ch_2_body.md ch_3_conclusion.md
    python scripts/repeated_citations.py --help

The arguments are the chapter files the export was made from, in the order
of the export: Markdown (.md) or text (.txt) files, or a folder, whose .md
files are read in the order of their names, with numbers compared as
numbers (ch_2_... before ch_10_...). It needs scripts/verbatim_check.py
beside it, and only the Python standard library.

Exit codes: 0 = listed (also when there is no pair), 2 = bad arguments, a
path that does not exist, a file that cannot be read or is no Markdown or
text file, or a folder without .md files (an Error: line on stderr).
"""

import bisect
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple, Optional

# Encoding guard for Windows consoles (CP1252 by default); a file name that is
# not valid UTF-8 is printed with escapes instead of ending in a traceback.
for stream in (sys.stdout, sys.stderr):
    try:
        if stream.encoding and stream.encoding.lower() != "utf-8":
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        else:
            stream.reconfigure(errors="backslashreplace")
    except Exception:
        pass

USAGE = "Usage: python scripts/repeated_citations.py <chapter file or folder> [...]"
FILE_SUFFIXES = {".md", ".markdown", ".txt"}
FOLDER_SUFFIXES = {".md", ".markdown"}

# A surname: a capital letter, then letters, with an inner apostrophe or hyphen
# (Müller-Schmidt, O’Brien, OECD), after name particles (van der Berg, von
# Wagner, v. Rosenstiel); the particles are not part of the source's key.
UPPER = "A-ZÀ-ÖØ-ÞĀ-ž"
SURNAME = r"[" + UPPER + r"](?:[^\W\d_]|['’-](?=[^\W\d_]))+"
PARTICLE = r"(?:van|von|vom|de|del|della|der|den|di|da|du|dos|la|le|ter|ten|v\.|d\.)"
NAME = r"(?:" + PARTICLE + r"\s+){0,3}" + SURNAME
SEP = r"(?:\s*/\s*|\s*&\s*|\s*,\s*(?:(?:&|and|und)\s+)?|\s+(?:and|und)\s+)"
ET_AL = r"(?:\s+(?:et\s+al\.?|u\.\s*a\.))"
NAMES = r"(?P<names>" + NAME + r"(?:" + SEP + NAME + r"){0,9}" + ET_AL + r"?)"
YEAR = (r"(?:(?<!\d)(?:1[5-9]|20)\d{2}(?:[a-z](?![^\W\d_]))?(?!\d|\.\d|[^\W\d_])"
        r"|\b[oO]\.\s?J\.|\b[nN]\.\s?[dD]\.|\bin\s+press\b|\bim\s+Druck\b)")
# More years of the same names: "Keller 2018, 2020", "Keller 2018a, b".
MORE_YEARS = r"(?P<more>(?:\s*,\s*(?:" + YEAR + r"|[a-z](?![^\W\d_]|\.)))*)"
NAME_YEAR = re.compile(NAMES + r"\s*,?\s+(?P<year>" + YEAR + r")" + MORE_YEARS)
NAME_YEAR_TIGHT = re.compile(NAMES + r"\s*,\s*(?P<year>" + YEAR + r")" + MORE_YEARS)
SECONDARY = re.compile(r",?\s*\b(?:zit\.\s*n(?:ach\b|\.)|zitiert\s+nach\b|(?:as\s+)?cited\s+in\b|quoted\s+in\b)\s*",
                       re.I)
# A citation in the sentence: Keller (2018, S. 44), Keller (2018: 44 f.), Keller
# und Weber (2018). After the year only a locator, more sources after ";" or a
# secondary citation, so that "Deutschland (2020: 5,9 %)" or "Umsatz (2020, in
# Mio. €)" is none.
LOCATOR = (r"(?:\s*,\s*(?:S\.|Seiten?|pp?\.|Rn\.|Abschn\.|Kap\.|Abs\.|o\.\s?S\.|§)"
           r"|\s*:\s*\d+(?:\s*[-–]\s*\d+)?(?:\s*f{1,2}\.)?(?=\s*[;)])|\s*;|(?i:" + SECONDARY.pattern + r"))")
NARRATIVE = re.compile(r"(?<![^\W\d_])" + NAMES + r"\s+\((?P<inner>(?P<year>" + YEAR + r")" + MORE_YEARS
                       + r"(?P<rest>(?:" + LOCATOR + r"[^()]*)?))\)")
EBD = re.compile(r"(?:[^\W\d_]+\.?\s+){0,3}?(?:[Ee]bd\.?|[Ee]benda|[Ii]bid\.?|[Ii]bidem)(?![^\W\d_])")
# A page alone, "(S. 45)", "(vgl. S. 45)"; "(siehe S. 12)" is a cross-reference.
PAGE_ONLY = re.compile(r"^(?:(?:vgl|cf)\.?\s+)?(?:S\.|Seiten?|pp?\.|pages?)\s*\d", re.I)
PAREN = re.compile(r"\(([^()]*)\)")
BRACKET = re.compile(r"\[([^\[\]]*)\]")
CITEKEY = re.compile(r"(?<![\w.@])-?@(\{[^{}\s]+\}|\w(?:[\w:.#$%&+?<>~/-]*\w)?)")
FOOTNOTE_MARK = re.compile(r"\[\^([^\]\s]+)\]")
FOOTNOTE_DEF = re.compile(r"\[\^([^\]\s]+)\]:")
SOURCE_LINE = re.compile(r"(?mi)^[ \t>]*[*_]*(?:quellen?|sources?)[*_]*\s*:[*_]*")
INLINE_NOTE = re.compile(r"\^\[((?:[^\[\]]|\[[^\[\]]*\])*)\]")
FENCE = re.compile(r"(?ms)^ {0,3}(?P<f>`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}(?P=f)[`~]*[ \t]*$|\Z)")
HEADING_START = re.compile(r"\s{0,3}(#{1,6})\s+")


def heading(line: str):
    """(the #s, the title) of an ATX heading, or None: the title without a
    closing {attributes} block and closing #s. A linear check: the pattern
    it replaces took seconds on a heading with a long run of spaces inside,
    which a blanked HTML comment leaves."""
    m = HEADING_START.match(line)
    if not m:
        return None
    title = line[m.end():].rstrip().rstrip("#").rstrip()
    if title.endswith("}"):
        cut = title.rfind("}", 0, len(title) - 1) + 1
        brace = title.find("{", cut)
        if brace >= 0:
            title = title[:brace].rstrip()
    return m.group(1), title


# Capitalized words before a year that name no author: "(Stand 2020)", "(März
# 2021)", "(Tabelle 3, 2020)". Words that are also surnames (Sommer, Winter,
# Mai, August) count as authors, as in bibliography_check.py's parentheses.
NOT_AUTHORS = {
    "Jahr", "Jahre", "Jahren", "Jahres", "Stand", "Januar", "Februar", "März", "April", "Juni", "Juli",
    "September", "Oktober", "November", "Dezember", "Frühjahr", "Quartal", "Semester",
    "Sommersemester", "Wintersemester", "Kapitel", "Abschnitt", "Absatz", "Abbildung", "Abb", "Tabelle",
    "Tab", "Anhang", "Seite", "Teil", "Band", "Heft", "Auflage", "Ausgabe", "Fassung", "Phase", "Ende",
    "Anfang", "Mitte", "Beginn", "Seit", "Von", "Bis", "Ab", "Im", "In", "Am",
    "January", "February", "March", "April", "June", "July", "September", "October", "November",
    "December", "Year", "Table", "Figure", "Fig", "Chapter", "Section", "Appendix", "Page", "Part",
    "Volume", "Issue", "Edition", "Version", "Since", "From", "Until", "Before", "After", "End",
}


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(2)


class Source(NamedTuple):
    key: str        # what makes two citations one source: surnames and year, or the citekey
    shown: str      # as the report names it: "Keller/Weber 2018", "@keller2018"


class Item(NamedTuple):
    source: Optional[Source]   # for ebd., ibid. or a page alone: None until resolve() names it
    part: str                  # its part of the citation, as written: "Weber 2019, S. 3"
    short: bool = False        # ebd., ibid. or a page alone


class Citation(NamedTuple):
    file: str
    line: int
    form: str       # the citation as written, on one line
    items: list
    secondary: bool
    note: str = ""  # for a citation in a footnote: "footnote [^1], marked in l. 9"


# ---------------------------------------------------------------------------
# Reading a chapter file
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    """UTF-8 (with or without BOM), UTF-16 with BOM, otherwise Windows-1252;
    NFC, soft hyphens dropped, line breaks as \\n."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        fail(f"cannot read {path}: {exc.strerror or exc}")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def blank(text: str, start: int, end: int) -> str:
    """text[start:end] as spaces, line breaks kept (and so the line numbers)."""
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def footnotes(lines: list) -> dict:
    """{label: [line indexes]} of the footnote definitions ("[^1]: ...", the
    lines that continue its paragraph, and later paragraphs indented by
    two spaces or more, or a tab)."""
    out, label, gap = {}, None, False
    for n, line in enumerate(lines):
        m = FOOTNOTE_DEF.match(line)
        if m:
            label, gap = m.group(1), False
            out.setdefault(label, []).append(n)
        elif label is not None and not line.strip():
            gap = True
        elif label is not None and (re.match(r" {2,}\S|\t", line) or not gap) and not heading(line):
            out[label].append(n)
            gap = False
        else:
            label = None
    return out


def chapter_parts(path: Path, vc) -> tuple:
    """(main text, {label: footnote text}, reference list lines or None): the
    file's text with what is left out blanked, so that offsets give lines."""
    text = read_text(path)
    m = re.match(r"---\n.*?\n(?:---|\.\.\.)\n", text, re.S)
    if m:
        text = blank(text, 0, m.end())
    for pattern in (FENCE, vc.HTML_COMMENT):
        for m in reversed(list(pattern.finditer(text))):
            text = blank(text, m.start(), m.end())
    lines = text.split("\n")
    notes = footnotes(lines)
    in_notes = {n for ns in notes.values() for n in ns}
    # the reference list: as verbatim_check.py finds it, its footnotes aside
    headings = []
    for n, line in enumerate(lines):
        h = heading(line)
        if h and n not in in_notes:
            headings.append((n, len(h[0]), 0, h[1]))
    cut, refs = vc.bibliography_section(headings, len(lines)), None
    if cut:
        body = [n for n in range(cut[0] + 1, cut[1]) if n not in in_notes]
        paragraphs = "\n".join(lines[n] if n in body else "" for n in range(cut[0] + 1, cut[1])).split("\n\n")
        if vc.reference_list(paragraphs):
            last = max(n for n in [cut[0]] + body if lines[n].strip())
            for n in [cut[0]] + body:
                lines[n] = " " * len(lines[n])
            refs = (cut[0] + 1, last + 1)      # its first and last line
    note_texts = {}
    for label, ns in notes.items():
        kept = set(ns)
        note_texts[label] = "\n".join(
            (FOOTNOTE_DEF.sub(lambda x: " " * len(x.group(0)), lines[n], count=1) if n == ns[0] else lines[n])
            if n in kept else "" for n in range(len(lines)))
        for n in ns:
            lines[n] = " " * len(lines[n])
    return "\n".join(lines), note_texts, refs


# ---------------------------------------------------------------------------
# Citations in a text
# ---------------------------------------------------------------------------

def plain(text: str) -> str:
    """For matching only, same length: Pandoc's escaped space (S.\\ 12) and a
    non-breaking space read as a space."""
    return text.replace("\\ ", "  ").replace("\u00a0", " ").replace("\u202f", " ")


def one_line(text: str) -> str:
    """text as written, its line breaks as spaces (a non-breaking space stays)."""
    return re.sub(r"[ \t]*\n[ \t]*", " ", text).strip(" \t\n")


def surnames(names: str) -> list:
    """The surnames of a names group, without particles and a possessive:
    "van der Berg und Weber" -> ["Berg", "Weber"], "Smith's" -> ["Smith"]."""
    names = re.sub(ET_AL + r"$", "", names)
    found = re.findall(SURNAME, re.sub(r"(?<!\S)" + PARTICLE + r"(?=\s)", " ", names))
    return [re.sub(r"['’]s$", "", s) for s in found]


def name_sources(m: re.Match) -> list:
    """The sources of a name-and-year match, one for each year: "Keller 2018,
    2020" names two, as does "Keller 2018a, b"."""
    names = m.group("names")
    found = surnames(names)
    if not found or found[0] in NOT_AUTHORS:
        return []
    et_al = re.search(ET_AL + r"$", names) is not None
    key = "/".join(s.casefold() for s in found) + (" et al." if et_al else "")
    years = [one_line(m.group("year"))]
    for y in re.findall(r",\s*(" + YEAR + r"|[a-z])", m.group("more") or ""):
        y = one_line(y)
        if len(y) == 1:                      # "2018a, b": the year of the one before
            y = years[-1][:4] + y if re.match(r"\d{4}", years[-1]) else y
        years.append(y)
    shown = one_line(names)
    return [Source(key + " " + re.sub(r"\s", "", y).casefold(), f"{shown} {y}") for y in years]


def author_year(ptext: str) -> list:
    """The sources a part of a citation names by author and year, in the
    order named (several, as in "Keller 2018, S. 5, Weber 2019")."""
    out, pos = [], 0
    while True:
        m = NAME_YEAR.search(ptext, pos) or NAME_YEAR_TIGHT.search(ptext, pos)
        if not m:
            return out
        found = name_sources(m)
        out += found
        pos = m.end() if found else m.start() + 1


def parse_part(part: str) -> tuple:
    """(items, secondary) of one part of a citation, between semicolons; a
    secondary citation names the original and then the source read."""
    ptext = plain(part)
    split = SECONDARY.search(ptext)
    spans = [(0, split.start()), (split.end(), len(ptext))] if split else [(0, len(ptext))]
    items = []
    for a, b in spans:
        piece, shown = ptext[a:b], one_line(part[a:b])
        e = EBD.match(piece, len(piece) - len(piece.lstrip()))
        if e:                                # "ebd., S. 5", and what may follow it
            items.append(Item(None, shown, True))
            piece = " " * e.end() + piece[e.end():]
        cited = CITEKEY.findall(piece)
        if cited:
            items += [Item(Source("@" + k.strip("{}"), "@" + k.strip("{}")), shown) for k in cited]
        else:
            items += [Item(src, shown) for src in author_year(piece)]
    return items, split is not None


def citations_in(text: str, file: str, lines_at: list, note: bool = False) -> list:
    """(offset, Citation) of every citation in text, in the order they stand.
    In a footnote (note: the text of a footnote definition) and in an inline
    note (^[...]) a citation also stands without parentheses: "Vgl. Keller
    2018, S. 5.", "Ebd., S. 6."."""
    ptext = plain(text)
    found, taken = [], []

    def free(a: int, b: int) -> bool:
        return not any(x < b and a < y for x, y in taken)

    def add(a: int, b: int, items: list, secondary: bool) -> None:
        line = bisect.bisect_right(lines_at, a) + 1
        found.append((a, Citation(file, line, one_line(text[a:b]), items, secondary)))
        taken.append((a, b))

    # Pandoc citekeys in brackets, then citekeys in the sentence: @key [S. 5]
    for m in BRACKET.finditer(ptext):
        if not CITEKEY.search(m.group(1)) or ptext[m.start() - 1:m.start()] == "^":
            continue
        items, secondary = [], False
        for part in text[m.start(1):m.end(1)].split(";"):
            got, sec = parse_part(part)
            items += got
            secondary = secondary or sec
        if items:
            add(m.start(), m.end(), items, secondary)
    for m in CITEKEY.finditer(ptext):
        if not free(m.start(), m.end()):
            continue
        end = m.end()
        loc = re.match(r"\s*\[[^\[\]@]*\]", ptext[end:])
        if loc:
            end += loc.end()
        key = m.group(1).strip("{}")
        add(m.start(), end, [Item(Source("@" + key, "@" + key), one_line(text[m.start():end]))], False)
    # author and year in the sentence: Keller (2018, S. 5)
    for m in NARRATIVE.finditer(ptext):
        if not free(m.start(), m.end()):
            continue
        sources = name_sources(m)
        if not sources:
            continue
        head = m.start("inner") + len(m.group("year")) + len(m.group("more") or "")
        items = [Item(s, one_line(text[m.start():m.end()])) for s in sources]
        rest = text[head:m.end("inner")].split(";")
        # a secondary citation, "Weber (1922, S. 31, zit. nach Keller 2018)", or
        # more sources after a semicolon, "Keller (2018; vgl. auch Weber 2019)"
        split = SECONDARY.search(plain(rest[0]))
        secondary = split is not None
        if split:
            rest[0] = rest[0][split.end():]
        else:
            rest = rest[1:]
        for part in rest:
            got, sec = parse_part(part)
            items += got
            secondary = secondary or sec
        add(m.start(), m.end(), items, secondary)
    # parentheses: author and year, ebd. or ibid., several sources, a page alone
    for m in PAREN.finditer(ptext):
        if not free(m.start(), m.end()) or re.search(r"\n\s*\n", m.group(1)):
            continue
        content = text[m.start(1):m.end(1)]
        items, secondary = [], False
        for part in content.split(";"):
            got, sec = parse_part(part)
            items += got
            secondary = secondary or sec
        if not items and PAGE_ONLY.match(plain(content).strip()):
            items = [Item(None, one_line(content), True)]
        if items:
            add(m.start(), m.end(), items, secondary)
    # in a footnote, an inline note and a source line ("Quelle: Keller 2018, S. 5"
    # below a table or figure): what stands between these citations, a
    # paragraph at a time
    if note:
        regions = [(0, len(text))]
    else:
        regions = [(m.start(1), m.end(1)) for m in INLINE_NOTE.finditer(ptext)]
        for m in SOURCE_LINE.finditer(ptext):
            end = ptext.find("\n", m.end())
            regions.append((m.end(), end if end >= 0 else len(ptext)))
    for ra, rb in regions:
        pos, stretches = ra, []
        for x, y in sorted(taken):
            if y <= ra or x >= rb:
                continue
            stretches.append((pos, max(pos, x)))
            pos = max(pos, y)
        stretches.append((pos, rb))
        for a, b in stretches:
            for para in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", text[a:b]):
                content = para.group(0).rstrip(" \t\n.,;:")
                start = a + para.start() + len(content) - len(content.lstrip(" \t\n.,;:"))
                content = content.lstrip(" \t\n.,;:")
                items, secondary = [], False
                for part in content.split(";"):
                    got, sec = parse_part(part)
                    items += got
                    secondary = secondary or sec
                end = start + len(content)
                if text[end:end + 1] == ".":
                    end += 1             # the form keeps its period: "Ebd.", "S. 7 ff."
                if items and free(start, end):
                    add(start, end, items, secondary)
    found.sort(key=lambda x: x[0])
    return found


def read_chapter(path: Path, file: str, vc) -> tuple:
    """(citations in reading order, reference list lines or None) of one file."""
    main, notes, refs = chapter_parts(path, vc)
    lines_at = [m.start() for m in re.finditer("\n", main)]
    events = citations_in(main, file, lines_at)
    mark_line = lambda pos: bisect.bisect_right(lines_at, pos) + 1
    for m in FOOTNOTE_MARK.finditer(plain(main)):
        note = notes.get(m.group(1))
        if note is None:
            continue
        at = [x.start() for x in re.finditer("\n", note)]
        where = f"footnote [^{m.group(1)}], marked in l. {mark_line(m.start())}"
        for _, c in citations_in(note, file, at, note=True):
            events.append((m.start(), c._replace(note=where)))
        notes.pop(m.group(1))         # a footnote's citations stand once, at its first mark
    events.sort(key=lambda x: x[0])   # stable: a footnote's citations keep their order
    return [c for _, c in events], refs


# ---------------------------------------------------------------------------
# Pairs
# ---------------------------------------------------------------------------

def resolve(citations: list) -> tuple:
    """(the citations with each ebd., ibid. or page alone given the source
    named last in the citation before it, the citations of those that have
    no citation with a source before them)."""
    out, alone = [], []
    for c in citations:
        prev = out[-1] if out and out[-1].items else None
        if prev is None and any(it.source is None for it in c.items):
            alone.append(c)
        items = [it if it.source is not None else it._replace(source=prev.items[-1].source)
                 for it in c.items if it.source is not None or prev is not None]
        out.append(c._replace(items=items))
    return out, alone


def keys(c: Citation) -> list:
    seen = []
    for it in c.items:
        if it.source.key not in seen:
            seen.append(it.source.key)
    return seen


def pair_lines(citations: list) -> list:
    """One line for each source of a citation that the citation just before
    names too."""
    lines = []
    for p, c in zip(citations, citations[1:]):
        before, done = keys(p), set()
        for it in c.items:
            k = it.source.key
            if k not in before or k in done:
                continue
            done.add(k)
            again = f"`{c.form}`" if len(c.items) == 1 or it.part == c.form else f"`{it.part}` in `{c.form}`"
            line = f"- {c.file}:{c.line} — {it.source.shown}, cited again as {again}"
            if c.note:
                line += f" ({c.note})"
            where = f" in {p.file}:{p.line}" if p.file != c.file else ""
            if p.secondary:
                line += f"; the previous citation{where} is a secondary citation: `{p.form}`"
            elif len(before) > 1:
                line += f"; the previous citation{where} names {len(before)} sources: `{p.form}`"
            elif where:
                line += f"; the previous citation is in {p.file}:{p.line}: `{p.form}`"
            if it.short and (p.secondary or len(before) > 1):
                line += "; read as the source named last"
            lines.append(line)
    return lines


# ---------------------------------------------------------------------------

def natural(name: str) -> list:
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.casefold()) for t in re.split(r"(\d+)", name) if t]


def chapter_files(args: list) -> list:
    files, seen = [], set()
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            try:
                found = sorted((x for x in p.iterdir() if x.is_file() and not x.name.startswith((".", "~$"))
                                and x.suffix.lower() in FOLDER_SUFFIXES), key=lambda x: natural(x.name))
            except OSError as exc:
                fail(f"cannot read the folder {p}: {exc.strerror or exc}")
            if not found:
                fail(f"no .md chapter files in the folder {p}")
            files += found
        elif p.is_file():
            if p.suffix.lower() == ".docx":
                fail(f"{p} is a Word file: give the Markdown chapter files the export was made from")
            if p.suffix.lower() not in FILE_SUFFIXES:
                fail(f"expected a .md or .txt chapter file or a folder, got "
                     f"{p.suffix or 'a file without extension'}: {p}")
            files.append(p)
        else:
            fail(f"not found: {p}")
    # a file named twice (a folder and a file in it, "./x.md" and "x.md") is read once
    unique = []
    for f in files:
        key = os.path.normcase(str(f.resolve()))
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def report(args: list) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import verbatim_check as vc
    except Exception as exc:
        fail(f"scripts/verbatim_check.py could not be loaded beside this script ({type(exc).__name__}: {exc})")
    files = chapter_files(args)
    names = [f.name for f in files]
    shown = {f: (f.name if names.count(f.name) == 1 else f.as_posix()) for f in files}
    raw, refs = [], []
    for f in files:
        cits, ref = read_chapter(f, shown[f], vc)
        raw += cits
        if ref:
            refs.append(f"{shown[f]}, l. {ref[0]}–{ref[1]}")
    citations, alone = resolve(raw)
    pairs = pair_lines(citations)

    several = sum(1 for c in citations if len(keys(c)) > 1 and not c.secondary)
    secondary = sum(1 for c in citations if c.secondary)
    short = sum(1 for c in raw for it in c.items if it.short)
    cited = sum(1 for c in raw for it in c.items if not it.short and it.source.key.startswith("@"))
    counts = {}
    for c in citations:
        for k in keys(c):
            shown_as = next(it.source.shown for it in c.items if it.source.key == k)
            counts.setdefault(k, [shown_as, 0])[1] += 1

    print(f"Repeated citations (in_text.repeated_citation), read in this order: {', '.join(shown[f] for f in files)}")
    print(f"Citations read: {len(raw)}; with several sources: {several}; secondary: {secondary}; "
          f"ebd., ibid. or a page alone: {short}; citekeys: {cited}")
    print("Reference list left out: " + ("; ".join(refs) if refs else "none found in these files"))
    if counts:
        line, out = "Sources (citations):", []
        for shown_as, n in counts.values():
            entry = f"{shown_as} ({n})"
            if len(line) + len(entry) > 110 and line.strip():
                out.append(line + ";")
                line = " "
            line += (" " if line.endswith(":") or line == " " else "; ") + entry
        print("\n".join(out + [line]))
    if cited:
        print("Citekeys: the export shows the form the CSL style gives a repeated citation; check that form in the DOCX.")
    print()
    print(f"Pairs: {len(pairs)}")
    for line in pairs:
        print(line)
    if alone:
        print()
        print(f"ebd., ibid. or a page alone with no citation before it: {len(alone)}")
        for c in alone:
            print(f"- {c.file}:{c.line} — `{c.form}`" + (f" ({c.note})" if c.note else ""))
    return 0


def main() -> None:
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print((__doc__ or USAGE).strip())
        sys.exit(0)
    if not args or any(a.startswith("-") for a in args):
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    try:
        code = report(args)
    except SystemExit:
        raise
    except Exception as exc:  # an unexpected error: exit 2, never a list that looks complete
        fail(f"{type(exc).__name__}: {' '.join(str(exc).split())}")
    sys.exit(code)


if __name__ == "__main__":
    main()
