#!/usr/bin/env python3
"""
verbatim_check.py

Counts the verbatim word runs a chapter shares with its sources: the count
behind verification step 8 of the source-verifier, rated by the thresholds
of checklists/plagiarism_protection.md:

    5-7 words    🟡 polish
    8-14 words   ⚠️ plagiarism risk, must be reformulated
    15+ words    ❌ serious

Runs of 1-4 words are not listed. A run counts across sentence boundaries;
letter case and punctuation are ignored. Text in quotation marks („…“, “…”,
"…", »…«, «…»), Markdown block quotes and Word paragraphs in a quote style
are marked direct quotes and are not counted. Each such quote of five or
more words (its parts between […] or (…) omissions) is looked up in the
sources instead; one that is not found verbatim is listed for a check by
hand, without changing the exit code.

Sources are files or folders, searched recursively; a folder named
_guidelines inside them is skipped, since guidelines are not sources:
  - extract files (.md): the "Original" quotes of the research-agent's
    extracts, with their page and quote ID
  - PDFs (.pdf): the text layer, read with pypdf; a page here is the PDF
    viewer's page index, which may differ from the printed page number.
    A PDF without a text layer (a scan) is not checked: it is covered only
    through the quotes in its extract.
  - plain-text files (.txt)

Usage:
    python scripts/verbatim_check.py <chapter> <source> [<source> ...]
    python scripts/verbatim_check.py workspace/output/chapters/ch_2_basics.md workspace/sources/
    python scripts/verbatim_check.py --help

The chapter may be Markdown (.md), plain text (.txt) or Word (.docx).

Exit codes: 0 = no run of 8 or more words, 1 = at least one run of 8 or more
words (⚠️ or ❌), 2 = bad arguments, or a chapter or source that cannot be read.
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
SKIPPED_FOLDERS = {"_guidelines"}

WORD = re.compile(r"[^\W_]+")
# A quotation in double marks, within one paragraph: German „…“ (also „…”),
# English “…”, straight "…", and guillemets in both directions.
QUOTED = re.compile(r'„[^„“”]*[“”]|“[^“”„]*”|"[^"]*"|»[^»«]*«|«[^«»]*»')
# Omissions and insertions inside a quotation split it into parts that are
# looked up separately: […], [...], (…), (...), …, ..., and [any insertion].
OMISSION = re.compile(r"\[[^\]]*\]|\((?:…|\.{3})\)|…|\.{3}")
PANDOC_CITATION = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
FOOTNOTE_MARK = re.compile(r"\[\^[^\]]*\]")


def normalize(text: str) -> str:
    """NFKC (ligatures such as ﬁ become fi), soft hyphens dropped."""
    return unicodedata.normalize("NFKC", text).replace("­", "")


def tokens(text: str) -> list:
    return [m.group(0).casefold() for m in WORD.finditer(text)]


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
        fail(f"cannot read {path} as .docx ({type(exc).__name__}: {exc})")
    pieces = []
    for n, p in enumerate(doc.paragraphs, 1):
        style = (p.style.name if p.style is not None else "") or ""
        is_quote = bool(re.search(r"(?i)quote|zitat", style))
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
        pos = 0
        for s, e in quoted + [(len(piece), len(piece))]:
            for m in WORD.finditer(piece, pos, s):
                words.append(m.group(0).casefold())
                places.append(first + (0 if docx else piece.count("\n", 0, m.start())))
                spans.append((base + m.start(), base + m.end()))
            brk()
            pos = e
    return Chapter(words, places, spans, "".join(text_parts), "paragraph" if docx else "line", quotes)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

class Sequence(NamedTuple):
    words: list     # casefolded words of one quote, one text file or one whole PDF
    pages: list     # for each word: its page (str) or None
    label: str      # how a match is named: "Brandt_2019.md Q3", "Brandt_2019.pdf"
    kind: str       # "extract", "pdf" or "text"


def page_of(heading: str) -> Optional[str]:
    m = re.search(r"(?i)(?:\bpage|\bseite|\bpp?\.|\bs\.)\s*(\d+(?:\s*(?:[-–]|to|bis)\s*\d+)?(?:\s*ff?\.)?)", heading)
    return re.sub(r"\s+", " ", m.group(1)) if m else None


def read_extract(path: Path) -> list:
    """The "Original" quotes of an extract, each with its page and quote ID."""
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1252", errors="replace")
    lines = normalize(raw).replace("\r\n", "\n").split("\n")
    seqs = []
    page, qid = None, None
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
                qid = None
                page = page_of(heading) or page
            i += 1
            continue
        f = re.match(r"\s*(?:[-*+]\s*)?\*\*ID:?\*\*:?\s*(Q\d+)", line)
        if f:
            qid = f.group(1)
        o = re.match(r"\s*(?:[-*+]\s*)?\*\*Original(?: quote)?:?\*\*:?\s*(.*)", line, re.I)
        if o:
            parts = [o.group(1)]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"\s*(?:[-*+]\s+\*\*|#)", lines[i]):
                parts.append(lines[i].strip())
                i += 1
            words = tokens(" ".join(parts))
            if words:
                label = path.name + (f" {qid}" if qid else "")
                seqs.append(Sequence(words, [page] * len(words), label, "extract"))
            continue
        i += 1
    return seqs


def read_pdf(path: Path) -> list:
    try:
        import logging
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
    except ImportError:
        fail("pypdf not installed. Install: pip install -r requirements.txt")
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
        page_words = tokens(text)
        first = WORD.search(text)
        # ... and so is one hyphenated across a page break
        if hyphen and first and first.group(0)[0].islower() and words:
            words[-1] += page_words.pop(0)
        hyphen = bool(re.search(r"\w-\s*$", text))
        words += page_words
        pages += [str(n)] * len(page_words)
    return [Sequence(words, pages, path.name, "pdf")] if words else []


def read_text(path: Path) -> list:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="cp1252", errors="replace")
    words = tokens(normalize(raw))
    return [Sequence(words, [None] * len(words), path.name, "text")] if words else []


def source_files(arg: str) -> list:
    p = Path(arg)
    if p.is_dir():
        found = []
        for root, dirs, files in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in SKIPPED_FOLDERS and not d.startswith("."))
            found += [Path(root) / f for f in sorted(files)
                      if Path(f).suffix.lower() in SOURCE_SUFFIXES]
        return found
    try:
        with open(p, "rb"):
            pass
    except OSError as exc:
        fail(f"cannot open source {p}: {exc.strerror or exc}")
    if p.suffix.lower() not in SOURCE_SUFFIXES:
        fail(f"unsupported source type {p.suffix or '(none)'}: {p} (use .md extracts, .pdf or .txt)")
    return [p]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def index_sources(seqs: list) -> dict:
    index = {}
    for s, seq in enumerate(seqs):
        w = seq.words
        for p in range(len(w) - POLISH + 1):
            index.setdefault(tuple(w[p:p + POLISH]), []).append((s, p))
    return index


def find_runs(chapter: Chapter, seqs: list, index: dict) -> list:
    """Maximal runs of at least POLISH words: [(start, length, [(seq, pos)])]."""
    ch = chapter.words
    runs = {}
    for i in range(len(ch) - POLISH + 1):
        window = ch[i:i + POLISH]
        if None in window:
            continue
        for s, p in index.get(tuple(window), ()):
            w = seqs[s].words
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


def contains(seqs: list, index: dict, words: list) -> bool:
    if len(words) < POLISH:
        return True
    for s, p in index.get(tuple(words[:POLISH]), ()):
        if seqs[s].words[p:p + len(words)] == words:
            return True
    return False


def describe(seqs: list, hits: list, n: int) -> str:
    names = []
    for s, p in hits:
        seq = seqs[s]
        pages = [pg for pg in seq.pages[p:p + n] if pg]
        if seq.kind == "pdf" and pages:
            where = f"PDF page {pages[0]}" if pages[0] == pages[-1] else f"PDF pages {pages[0]}-{pages[-1]}"
            name = f"{seq.label} ({where})"
        elif pages:
            name = f"{seq.label} (p. {pages[0]})"
        else:
            name = seq.label
        if name not in names:
            names.append(name)
    shown = "; ".join(names[:3])
    return shown + (f"; and {len(names) - 3} more" if len(names) > 3 else "")


def shorten(text: str) -> str:
    """One line; a long text keeps its first and last words around " … "."""
    text = re.sub(r"\s+", " ", text).strip()
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

    files = []
    for arg in args[1:]:
        files += [f for f in source_files(arg) if f.resolve() != chapter_path.resolve()]
    if not files:
        fail("no sources found (.md extracts, .pdf or .txt) in: " + ", ".join(args[1:]))

    seqs, unreadable, unchecked = [], [], []
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
                    unchecked.append(f"{f} (no **Original:** quotes; not an extract?)")
        except SystemExit:
            raise
        except Exception as exc:
            unreadable.append(f"{f} ({type(exc).__name__}: {exc})")
            continue
        if found:
            counts[found[0].kind] += 1
        seqs += found

    chapter = read_chapter(chapter_path)
    index = index_sources(seqs)
    runs = find_runs(chapter, seqs, index)

    print(f"Verbatim check for: {chapter_path.name}")
    print(f"  Sources: {counts['extract']} extract(s) with "
          f"{sum(1 for s in seqs if s.kind == 'extract')} quotes, "
          f"{counts['pdf']} PDF(s), {counts['text']} text file(s)")
    print()

    for i, n, hits in runs:
        start, end = chapter.spans[i][0], chapter.spans[i + n - 1][1]
        excerpt = shorten(chapter.text[start:end])
        print(f"{rating(n)} {n} words, {chapter.unit} {chapter.places[i]}: \"{excerpt}\"")
        print(f"    in {describe(seqs, hits, n)}")
    if runs:
        print()

    missing = []
    for place, quote in chapter.quotes:
        for part in OMISSION.split(quote):
            words = tokens(part)
            if len(words) >= POLISH and not contains(seqs, index, words):
                missing.append((place, quote))
                break
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
        print("Could not be read:", file=sys.stderr)
        for u in unreadable:
            print(f"    {u}", file=sys.stderr)
        print(file=sys.stderr)

    serious = sum(1 for _, n, _ in runs if n >= SERIOUS)
    risk = sum(1 for _, n, _ in runs if RISK <= n < SERIOUS)
    polish = sum(1 for _, n, _ in runs if n < RISK)
    if runs:
        print(f"Summary: ❌ {serious}, ⚠️ {risk}, 🟡 {polish}. Runs of 1-4 words are not listed;")
    else:
        print("✅ No verbatim run of 5 or more words outside quotation marks.")
    print("text in quotation marks and block quotes is not counted (see checklists/plagiarism_protection.md).")

    if unreadable:
        sys.exit(2)
    sys.exit(1 if serious or risk else 0)


if __name__ == "__main__":
    main()
