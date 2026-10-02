#!/usr/bin/env python3
"""
verbatim_check.py

Counts the verbatim word runs a chapter shares with its sources: the count
behind verification step 8 of the source-verifier, rated by the thresholds
of checklists/plagiarism_protection.md:

    5-7 words    🟡 polish
    8-14 words   ⚠️ plagiarism risk, must be reformulated
    15+ words    ❌ serious

Runs of 1-4 words are not listed. A run counts across sentence boundaries
and across citations, as Pandoc citekeys ([@key, p. 5]) or in author-year
form ((Keller 2018, S. 44), (ebd.)); letter case and punctuation are
ignored. Text in quotation marks („…“, “…”, "…", ‚…‘, ‘…’, »…«, «…»),
Markdown block quotes and Word paragraphs in a quote style (also Pandoc's
"Block Text") are marked direct quotes and are not counted. Each such quote
of five or more words (its parts between […] or (…) omissions) is looked
up in the sources instead; one that is not found verbatim is listed for a
check by hand, without changing the exit code.

Sources are files or folders, searched recursively; folders named
_guidelines (guidelines are not sources) and verification (the saved
reports) inside them are skipped:
  - extract files (.md): the quotes of the research-agent's extracts (the
    "Original" field, quoted text in the "Secondary citation?" field, and
    "- p. 42: ..." lines), with their page and quote ID. A Markdown table
    with an "Original quote" column, such as the source registry in the
    workspace/state.md of a seminar paper, is read row by row.
  - PDFs (.pdf): the text layer, read with pypdf; a page here is the PDF
    viewer's page index, which may differ from the printed page number.
    A PDF without a text layer (a scan) and a ZIP archive named .pdf are
    not checked: they are covered only through the quotes in their extract.
  - plain-text files (.txt)
What cannot be read this way (a missing path, a Word or EPUB source, PDFs
while pypdf is not installed) is listed under "Not checked".

Usage:
    python scripts/verbatim_check.py <chapter> <source> [<source> ...]
    python scripts/verbatim_check.py workspace/output/chapters/ch_2_basics.md workspace/sources/
    python scripts/verbatim_check.py --help

The chapter may be Markdown (.md), plain text (.txt) or Word (.docx).

Exit codes: 0 = no run of 8 or more words, 1 = at least one run of 8 or more
words (⚠️ or ❌), 2 = bad arguments, a chapter or source that cannot be read
(the report is printed all the same), or no source text to compare against.
"""

import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple, Optional

# Encoding guard for Windows consoles (CP1252 by default).
for stream in (sys.stdout, sys.stderr):
    if stream.encoding and stream.encoding.lower() != "utf-8":
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

# Thresholds of checklists/plagiarism_protection.md, section 1.
POLISH, RISK, SERIOUS = 5, 8, 15

USAGE = "Usage: python scripts/verbatim_check.py <chapter> <source> [<source> ...]"
CHAPTER_SUFFIXES = {".md", ".markdown", ".txt", ".docx"}
SOURCE_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}
# Source formats the script cannot read; listed as not checked, not skipped silently.
UNREAD_SUFFIXES = {".doc", ".docx", ".odt", ".rtf", ".epub", ".mobi", ".djvu", ".zip"}
# Guidelines are not sources; verification/ holds the saved reports, which quote the chapter.
SKIPPED_FOLDERS = {"_guidelines", "verification"}

WORD = re.compile(r"[^\W_]+")
# A quotation within one paragraph: in double marks, German „…“ (also „…”),
# English “…”, straight "…", and guillemets in both directions; in single marks,
# German ‚…‘, English ‘…’ and single guillemets.
QUOTED = re.compile(r'„[^„“”]*[“”]|“[^“”„]*”|"[^"]*"|»[^»«]*«|«[^«»]*»'
                    r"|‚[^‚‘]*‘|‘[^‘’]*’|›[^›‹]*‹|‹[^‹›]*›")
# Omissions and insertions inside a quotation split it into parts that are
# looked up separately: […], [...], (…), (...), …, ..., and [any insertion].
OMISSION = re.compile(r"\[[^\]]*\]|\((?:…|\.{3})\)|…|\.{3}")
PANDOC_CITATION = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")
# A citation in parentheses, author-year style: "(Keller 2018, S. 44)", "(vgl. Keller
# & Weber 2018; Smith 2020, p. 5)", "(2018)", "(ebd., S. 45)". Like a citekey it is
# skipped, in the chapter and in the sources, so that a run continues across it.
CITATION = re.compile(
    r"\((?:(?:vgl|cf|see|siehe)\.?\s+)?"
    r"(?:[A-ZÄÖÜ][^()]{0,150}?(?:\b\d{4}[a-z]?\b|\bo\.\s?J\.|\bn\.\s?d\.)[^()]{0,80}"
    r"|\d{4}[a-z]?(?:\s*[,:;][^()]{0,80})?"
    r"|(?:[Ee]bd|[Ee]benda|[Ii]bid(?:em)?)\.?(?:[,\s][^()]{0,80})?)\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
FOOTNOTE_MARK = re.compile(r"\[\^[^\]]*\]")


def normalize(text: str) -> str:
    """NFKC (ligatures such as ﬁ become fi), soft hyphens dropped."""
    return unicodedata.normalize("NFKC", text).replace("­", "")


def tokens(text: str) -> list:
    return [m.group(0).casefold() for m in WORD.finditer(text)]


def one_line(exc: Exception) -> str:
    return " ".join(str(exc).split())


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Chapter
# ---------------------------------------------------------------------------

class Chapter(NamedTuple):
    words: list            # casefolded words, None where a run must break
    places: list           # for each entry of words: (line or paragraph number) or None
    spans: list            # for each entry of words: (start, end) in text, or None
    text: str              # the normalized text the spans refer to
    unit: str              # "line" or "paragraph"
    quotes: list           # (place, quotation text) of the marked direct quotes


def blank(text: str, start: int, end: int) -> str:
    """Replace text[start:end] by spaces, keeping line breaks (and line numbers)."""
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def read_markdown(path: Path) -> list:
    """Paragraph-sized pieces of a Markdown or text chapter: (text, first line, is_quote)."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1252", errors="replace")
    text = normalize(raw).replace("\r\n", "\n").replace("\r", "\n")
    # YAML front matter at the top
    m = re.match(r"---\n.*?\n(?:---|\.\.\.)\n", text, re.S)
    if m:
        text = blank(text, 0, m.end())
    for pattern in (HTML_COMMENT, PANDOC_CITATION, FOOTNOTE_MARK):
        for m in reversed(list(pattern.finditer(text))):
            text = blank(text, m.start(), m.end())
    pieces = []
    lines = text.split("\n")
    buf, first, quote = [], 0, False
    for n, line in enumerate(lines, 1):
        is_quote = bool(re.match(r"\s{0,3}>", line))
        if not line.strip() or (buf and is_quote != quote):
            if buf:
                pieces.append(("\n".join(buf), first, quote))
            buf = []
            if not line.strip():
                continue
        if not buf:
            first, quote = n, is_quote
        buf.append(re.sub(r"^\s{0,3}>\s?", "", line) if is_quote else line)
    if buf:
        pieces.append(("\n".join(buf), first, quote))
    return pieces


def read_docx(path: Path) -> list:
    """Paragraphs of a Word chapter: (text, paragraph number, is_quote)."""
    try:
        from docx import Document
    except ImportError:
        fail("python-docx not installed. Install: pip install -r requirements.txt")
    try:
        doc = Document(str(path))
    except Exception as exc:
        fail(f"cannot read {path} as .docx ({type(exc).__name__}: {one_line(exc)})")
    pieces = []
    for n, p in enumerate(doc.paragraphs, 1):
        style = (p.style.name if p.style is not None else "") or ""
        # Pandoc writes Markdown block quotes in the style "Block Text"
        is_quote = bool(re.search(r"(?i)quote|zitat|block ?text", style))
        if p.text.strip():
            pieces.append((normalize(p.text), n, is_quote))
    return pieces


def read_chapter(path: Path) -> Chapter:
    docx = path.suffix.lower() == ".docx"
    pieces = read_docx(path) if docx else read_markdown(path)
    words, places, spans, quotes = [], [], [], []
    text_parts, offset = [], 0

    def brk():
        if words and words[-1] is not None:
            words.append(None)
            places.append(None)
            spans.append(None)

    for piece, first, is_quote in pieces:
        base = offset
        text_parts.append(piece + "\n\n")
        offset += len(piece) + 2
        if is_quote:
            quotes.append((first, piece))
            brk()
            continue
        quoted = [(m.start(), m.end()) for m in QUOTED.finditer(piece)]
        for s, e in quoted:
            quotes.append((first + piece.count("\n", 0, s), piece[s + 1:e - 1]))
        # an author-year citation is skipped without breaking the run
        cited = [(m.start(), m.end()) for m in CITATION.finditer(piece)]
        pos = 0
        for s, e in quoted + [(len(piece), len(piece))]:
            for m in WORD.finditer(piece, pos, s):
                if any(a <= m.start() < b for a, b in cited):
                    continue
                words.append(m.group(0).casefold())
                places.append(first + (0 if docx else piece.count("\n", 0, m.start())))
                spans.append((base + m.start(), base + m.end()))
            brk()
            pos = e
    return Chapter(words, places, spans, "".join(text_parts), "paragraph" if docx else "line", quotes)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class NotChecked(Exception):
    """A source that is skipped with a note instead of an error."""


class Sequence(NamedTuple):
    words: list     # casefolded words of one quote, one text file or one whole PDF
    pages: list     # for each word: its page (str) or None
    label: str      # how a match is named: "Brandt_2019.md Q3", "Brandt_2019.pdf"
    kind: str       # "extract", "pdf" or "text"
    note: str = ""  # shown with the page, e.g. "secondary citation"
    first: bool = True  # False for the later parts of a quote split at an omission


WORDS = {}  # one str object per distinct word: a book-length source stays small


def source_tokens(text: str) -> list:
    return [WORDS.setdefault(w, w) for w in tokens(CITATION.sub(" ", text))]


def page_of(heading: str) -> Optional[str]:
    m = re.search(r"(?i)(?:\bpage|\bseite|\bpp?\.|\bs\.)\s*((?:\d+|[ivxlc]+\b)(?:\s*(?:[-–]|to|bis)\s*(?:\d+|[ivxlc]+\b))?(?:\s*ff?\.)?)", heading)
    return re.sub(r"\s+", " ", m.group(1)) if m else None


FIELD = re.compile(r"\s*(?:[-*+]\s*)?\*\*([^*:]+?):?\*\*:?\s*(.*)")
# The bullet layout of the research-agent's rule examples: - p. 42: "quote"
PAGE_BULLET = re.compile(r"\s*[-*+]\s*((?:pp?\.|S\.|page|Seite)\s*[^:]{1,30}?)\s*:\s*(?=[\"„“»«])(.*)", re.I)


def read_extract(path: Path) -> list:
    """
    The quotes of an extract, each with its page and quote ID: the
    "Original" field, quoted text in the "Secondary citation?" field, and
    "- p. 42: \"...\"" bullets. A Markdown table with an "Original quote"
    column (the source registry of workspace/state.md in seminar projects)
    is read row by row.
    """
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1252", errors="replace")
    lines = normalize(raw).replace("\r\n", "\n").split("\n")
    seqs = []
    page, qid = None, None

    def add(text: str, where: Optional[str], label: str, note: str = "") -> None:
        # the parts of a quote between […] omissions are not one run in the source
        first = True
        for part in OMISSION.split(text):
            words = source_tokens(part)
            if words:
                seqs.append(Sequence(words, [where] * len(words), label, "extract", note, first))
                first = False

    def continuation(i: int, first: str) -> tuple:
        parts = [first]
        while i < len(lines) and lines[i].strip() and not re.match(r"\s*(?:[-*+]\s+|#|\|)", lines[i]):
            parts.append(lines[i].strip())
            i += 1
        return " ".join(parts), i

    i = 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r"\s{0,3}#{1,6}\s+(.*)", line)
        if h:
            heading = h.group(1).strip()
            q = re.match(r"(Q\d+)\b", heading)
            if q:
                qid = q.group(1)
                page = page_of(heading[q.end():]) or page
            else:
                # any other heading starts a new page, or a part without one
                qid = None
                page = page_of(heading)
            i += 1
            continue
        if line.lstrip().startswith("|"):
            i = read_table(lines, i, path, add)
            continue
        label = path.name + (f" {qid}" if qid else "")
        f = FIELD.match(line)
        if f:
            name, rest = f.group(1).strip().lower(), f.group(2)
            if name in ("original", "original quote"):
                text, i = continuation(i + 1, rest)
                add(text, page, label)
                continue
            elif name.startswith("secondary citation"):
                text, i = continuation(i + 1, rest)
                for m in QUOTED.finditer(text):
                    add(m.group(0)[1:-1], page, label, "secondary citation")
                continue
        b = PAGE_BULLET.match(line)
        if b:
            text, i = continuation(i + 1, b.group(2))
            add(text, page_of(b.group(1)) or page, label)
            continue
        i += 1
    return seqs


def read_table(lines: list, i: int, path: Path, add) -> int:
    """A Markdown table; rows of one with an "Original quote" column are quotes."""
    rows = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
        i += 1
    if len(rows) < 2:
        return i
    head = [c.lower() for c in rows[0]]
    quote = next((n for n, c in enumerate(head) if "original" in c or c in ("quote", "zitat")), None)
    if quote is None:
        return i
    page = next((n for n, c in enumerate(head) if c in ("page", "seite", "p.", "s.")), None)
    source = next((n for n, c in enumerate(head) if c in ("source", "quelle")), None)
    for row in rows[1:]:
        if len(row) <= quote or re.fullmatch(r"[\s:-]*", "".join(row)):
            continue  # the separator row |---|---|
        where = row[page] if page is not None and page < len(row) and row[page] else None
        name = row[source] if source is not None and source < len(row) and row[source] else ""
        add(row[quote], where, f"{path.name}: {name}" if name else path.name)
    return i


def read_pdf(path: Path) -> list:
    try:
        import logging
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
    except ImportError:
        raise NotChecked("pypdf not installed: pip install -r requirements.txt")
    with open(path, "rb") as fh:
        if fh.read(4) == b"PK\x03\x04":
            raise NotChecked("a ZIP archive named .pdf: extract it with scripts/extract_styleguide.sh "
                             "into a folder outside the sources")
    reader = PdfReader(str(path))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("encrypted with a password")
    words, pages = [], []
    hyphen = False  # the previous page ended in a hyphenated word
    for n, pg in enumerate(reader.pages, 1):
        text = normalize(pg.extract_text() or "")
        # A word hyphenated at the end of a line ("Verdun-\nstung") is joined;
        # before a capital letter the hyphen belongs to a compound ("Stadt-\nGrün").
        text = re.sub(r"(\w)-[ \t]*\n[ \t]*([^\W\d_])",
                      lambda m: m.group(1) + m.group(2) if m.group(2).islower() else m.group(0),
                      text)
        text = CITATION.sub(" ", text)
        page_words = source_tokens(text)
        first = WORD.search(text)
        # ... and so is one hyphenated across a page break
        if hyphen and first and first.group(0)[0].islower() and words:
            joined = words[-1] + page_words.pop(0)
            words[-1] = WORDS.setdefault(joined, joined)
        hyphen = bool(re.search(r"\w-\s*$", text))
        words += page_words
        pages += [str(n)] * len(page_words)
    return [Sequence(words, pages, path.name, "pdf")] if words else []


def read_text(path: Path) -> list:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1252", errors="replace")
    words = source_tokens(normalize(raw))
    return [Sequence(words, [None] * len(words), path.name, "text")] if words else []


def source_files(arg: str, unchecked: list) -> list:
    """The source files of one argument; what cannot be read goes to unchecked."""
    p = Path(arg)
    if p.is_dir():
        found = []
        for root, dirs, files in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in SKIPPED_FOLDERS and not d.startswith("."))
            for f in sorted(files):
                suffix = Path(f).suffix.lower()
                if suffix in SOURCE_SUFFIXES:
                    found.append(Path(root) / f)
                elif suffix in UNREAD_SUFFIXES:
                    unchecked.append(f"{Path(root) / f} ({suffix} is not read: give a PDF or text version)")
        return found
    try:
        with open(p, "rb"):
            pass
    except OSError as exc:
        reason = "not found" if isinstance(exc, FileNotFoundError) else exc.strerror or str(exc)
        unchecked.append(f"{p} ({reason})")
        return []
    if p.suffix.lower() not in SOURCE_SUFFIXES:
        unchecked.append(f"{p} ({p.suffix or 'a file without extension'} is not read: "
                         "use .md extracts, .pdf or .txt)")
        return []
    return [p]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def find_runs(chapter: Chapter, seqs: list) -> list:
    """Maximal runs of at least POLISH words: [(start, length, [(seq, pos)])]."""
    ch = chapter.words
    # The chapter's word windows are indexed, not the sources': a few thousand
    # entries instead of one per source word, however long the sources are.
    index = {}
    for i in range(len(ch) - POLISH + 1):
        window = ch[i:i + POLISH]
        if None not in window:
            index.setdefault(tuple(window), []).append(i)
    runs = {}
    for s, seq in enumerate(seqs):
        w = seq.words
        for p in range(len(w) - POLISH + 1):
            for i in index.get(tuple(w[p:p + POLISH]), ()):
                if i > 0 and p > 0 and ch[i - 1] is not None and ch[i - 1] == w[p - 1]:
                    continue  # part of a run that starts earlier
                n = POLISH
                while i + n < len(ch) and p + n < len(w) and ch[i + n] is not None and ch[i + n] == w[p + n]:
                    n += 1
                runs.setdefault((i, n), []).append((s, p))
    kept = []
    for (i, n), hits in sorted(runs.items(), key=lambda r: -r[0][1]):
        if not any(j <= i and i + n <= j + m for j, m, _ in kept):
            kept.append((i, n, hits))
    return sorted(kept)


def found_quotes(parts: list, seqs: list) -> set:
    """The indexes of the parts (word lists of POLISH or more words) found verbatim in a source."""
    starts = {}
    for k, words in enumerate(parts):
        starts.setdefault(tuple(words[:POLISH]), []).append(k)
    found = set()
    for seq in seqs:
        w = seq.words
        for p in range(len(w) - POLISH + 1):
            for k in starts.get(tuple(w[p:p + POLISH]), ()):
                if k not in found and w[p:p + len(parts[k])] == parts[k]:
                    found.add(k)
    return found


def describe(seqs: list, hits: list, n: int) -> str:
    names = []
    for s, p in hits:
        seq = seqs[s]
        pages = [pg for pg in seq.pages[p:p + n] if pg]
        if seq.kind == "pdf" and pages:
            where = [f"PDF page {pages[0]}" if pages[0] == pages[-1] else f"PDF pages {pages[0]}-{pages[-1]}"]
        else:
            where = [f"p. {pages[0]}"] if pages else []
        where += [seq.note] if seq.note else []
        name = f"{seq.label} ({', '.join(where)})" if where else seq.label
        if name not in names:
            names.append(name)
    shown = "; ".join(names[:3])
    return shown + (f"; and {len(names) - 3} more" if len(names) > 3 else "")


def shorten(text: str) -> str:
    """One line; a long text keeps its first and last words around " … "."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r" ([.,;:!?])", r"\1", text)  # a blanked citekey leaves "word ."
    if len(text) <= 160:
        return text
    return text[:120].rsplit(" ", 1)[0] + " … " + text[-40:].split(" ", 1)[-1]


def rating(n: int) -> str:
    return "❌" if n >= SERIOUS else "⚠️ " if n >= RISK else "🟡"


def main() -> None:
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print((__doc__ or USAGE).strip())
        sys.exit(0)
    if len(args) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(2)

    chapter_path = Path(args[0])
    try:
        with open(chapter_path, "rb"):
            pass
    except OSError as exc:
        reason = "is a directory" if os.path.isdir(chapter_path) else exc.strerror or exc
        fail(f"cannot open {chapter_path}: {reason}")
    if chapter_path.suffix.lower() not in CHAPTER_SUFFIXES:
        fail(f"expected a .md, .txt or .docx chapter, got "
             f"{chapter_path.suffix or 'a file without extension'}: {chapter_path}")

    chapter = read_chapter(chapter_path)

    files, unchecked = [], []
    for arg in args[1:]:
        files += [f for f in source_files(arg, unchecked) if f.resolve() != chapter_path.resolve()]

    seqs, unreadable = [], []
    counts = {"extract": 0, "pdf": 0, "text": 0}
    for f in files:
        suffix = f.suffix.lower()
        try:
            if suffix == ".pdf":
                found = read_pdf(f)
                if not found:
                    unchecked.append(f"{f} (no text layer, a scan?)")
            elif suffix == ".txt":
                found = read_text(f)
            else:
                found = read_extract(f)
                if not found:
                    unchecked.append(f"{f} (no quotes found: not an extract?)")
        except SystemExit:
            raise
        except NotChecked as note:
            unchecked.append(f"{f} ({note})")
            continue
        except Exception as exc:
            unreadable.append(f"{f} ({type(exc).__name__}: {one_line(exc)})")
            continue
        if found:
            counts[found[0].kind] += 1
        seqs += found

    if not seqs:
        # A clean result would claim a check that did not happen.
        fail("nothing to compare against: no extract quotes, PDF text or text files in "
             + ", ".join(args[1:])
             + "".join(f"; {u}" for u in unchecked + unreadable))
    runs = find_runs(chapter, seqs)

    print(f"Verbatim check for: {chapter_path.name}")
    print(f"  Sources: {counts['extract']} extract(s) with "
          f"{sum(1 for s in seqs if s.kind == 'extract' and s.first)} quotes, "
          f"{counts['pdf']} PDF(s), {counts['text']} text file(s)")
    print()

    for i, n, hits in runs:
        start, end = chapter.spans[i][0], chapter.spans[i + n - 1][1]
        excerpt = shorten(chapter.text[start:end])
        print(f"{rating(n)} {n} words, {chapter.unit} {chapter.places[i]}: \"{excerpt}\"")
        print(f"    in {describe(seqs, hits, n)}")
    if runs:
        print()

    checks = []  # (place, quote, words of one part between omissions)
    for place, quote in chapter.quotes:
        for part in OMISSION.split(quote):
            words = tokens(CITATION.sub(" ", part))
            if len(words) >= POLISH:
                checks.append((place, quote, words))
    found = found_quotes([words for _, _, words in checks], seqs)
    missing = []
    for k, (place, quote, _) in enumerate(checks):
        if k not in found and (place, quote) not in missing:
            missing.append((place, quote))
    if missing:
        print("Direct quotes not found verbatim in the sources (check by hand; "
              "the source may be missing here):")
        for place, quote in missing:
            print(f"    {chapter.unit} {place}: \"{shorten(quote)}\"")
        print()

    if unchecked:
        print("Not checked:")
        for u in unchecked:
            print(f"    {u}")
        print()
    if unreadable:
        print("Could not be read:")
        for u in unreadable:
            print(f"    {u}")
        print()

    serious = sum(1 for _, n, _ in runs if n >= SERIOUS)
    risk = sum(1 for _, n, _ in runs if RISK <= n < SERIOUS)
    polish = sum(1 for _, n, _ in runs if n < RISK)
    if runs:
        print(f"Summary: ❌ {serious}, ⚠️ {risk}, 🟡 {polish}. Runs of 1-4 words are not listed;")
    else:
        print("✅ No verbatim run of 5 or more words outside quotation marks"
              + (" in the sources that were read." if unchecked or unreadable else "."))
    print("text in quotation marks and block quotes is not counted (see checklists/plagiarism_protection.md).")

    if unreadable:
        sys.exit(2)
    sys.exit(1 if serious or risk else 0)


if __name__ == "__main__":
    main()
