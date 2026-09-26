#!/usr/bin/env python3
"""
bibliography_check.py

Bibliography minus-test, by author surname:
- Every surname cited in the text must appear among the bibliography's authors
- The lead author of every bibliography entry must be cited in the text

The diff of both lists must be empty. Years are not compared: a citation
with a wrong year, or an uncited second work by an author who is cited
elsewhere, is not reported.

Usage:
    python scripts/bibliography_check.py workspace/output/document.docx
    python scripts/bibliography_check.py path/to/file.docx
    python scripts/bibliography_check.py --help
"""

import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

# Encoding guard for Windows consoles (CP1252 by default).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError
except ImportError:
    print("Error: python-docx not installed.", file=sys.stderr)
    print("Install: pip install python-docx  (or: pip install -r requirements.txt)", file=sys.stderr)
    sys.exit(2)


# Heuristics for detecting the bibliography section.
# These markers are language-aware; extend for your language.
BIBLIOGRAPHY_HEADERS = [
    "bibliography",
    "references",
    "works cited",
    "literaturverzeichnis",
    "literatur",
    "quellenverzeichnis",
    "sources",
]


# Capitalized words that look like surnames in German academic prose but aren't.
# Used as a safety-net filter in all author-extraction patterns. A word that
# leads a bibliography entry ("OECD. (2019). ...") is exempt from it.
# 
# Keep this list conservative: adding a real surname here would silently drop
# genuine citations. Only add words where the false-positive cost clearly
# outweighs the false-negative risk.
GERMAN_NON_AUTHOR_CAPS = {
    # Time words
    "Jahr", "Jahre", "Jahren", "Jahres",
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag",
    "Frühjahr", "Sommer", "Herbst", "Winter",
    "Quartal", "Semester", "Halbjahr",
    # Document-structural references
    "Kapitel", "Abschnitt", "Absatz", "Artikel", "Paragraph", "Seite",
    "Anhang", "Abbildung", "Tabelle", "Fußnote",
    "Teil", "Band", "Heft", "Auflage", "Phase", "Fall",
    # Supranational bodies & states (rarely authored; usually referred to as subjects)
    "EU", "USA", "BRD", "DDR", "UN", "NATO", "OECD",
    # German courts / statute abbreviations — citable, but by name, not as "authors"
    "BGH", "BVerfG", "BGB", "StGB", "HGB", "GG", "ZPO", "StPO",
    # Generic academic prose words that appear capitalized at sentence start
    "Studie", "Untersuchung", "Forschung", "Arbeit",
}

# Stoplist words that are also common surnames. In parentheses before a year
# ("(Winter, 2017)") they are far more likely a citation than prose, so the
# parenthetical stage does not filter them: a missing entry is still reported.
SURNAME_LIKE_STOPWORDS = {"Sommer", "Winter", "Herbst", "Freitag", "Montag", "Mai", "August"}

# Name particles that may precede a surname: van der Berg, de la Rosa, von Wagner.
NAME_PARTICLES = {
    "van", "von", "de", "del", "della", "di", "la", "le", "du", "dos", "das",
    "ter", "ten", "der", "den",
}

# The particles as a regex prefix of a surname, also capitalized at the start
# of an entry or citation (De Vries, Van der Berg, La Porta). "Das" stays
# lowercase: capitalized, it is the German article far more often.
NAME_PREFIX = (r"(?:(?:van|von|de|del|della|di|la|le|du|dos|das|ter|ten"
               r"|Van|Von|De|Del|Della|Di|La|Le|Du|Dos|Ter|Ten)\s+(?:der\s+|den\s+|de\s+|la\s+)?)?")

# Lowercase words that may precede a surname inside a parenthetical citation:
# name particles and short fillers after a lead word ("see also", "vgl. z. B.").
PAREN_LOWERCASE_OK = NAME_PARTICLES | {"also", "auch", "z.", "z.b.", "e.g."}


def heading_level(paragraph) -> Optional[int]:
    """Heading level of a paragraph (0 = Title, 1 = Heading 1, ...), or None
    for body text. A custom style based on a built-in heading counts as that
    heading. Built-in style names are stored in English whatever the Word UI
    language, so "Überschrift 1" is read as "Heading 1" here."""
    style = paragraph.style
    for _ in range(10):  # base-style chains are short; guard against cycles
        if style is None:
            return None
        name = (style.name or "").strip().lower()
        if name == "title":
            return 0
        match = re.fullmatch(r"heading (\d)", name)
        if match:
            return int(match.group(1))
        style = style.base_style
    return None


def read_docx_paragraphs(path: Path) -> list[tuple[str, Optional[int]]]:
    """Read all paragraphs of a .docx file as (text, heading level) pairs."""
    try:
        doc = Document(str(path))
        # NFC: decomposed umlauts (e.g. pasted from a PDF) would never match
        # their precomposed form or the [ÄÖÜ]/\w name classes. ’ -> ': Word's
        # AutoCorrect writes O’Brien in the text, a pasted entry keeps O'Brien.
        return [(unicodedata.normalize("NFC", p.text).replace("’", "'"), heading_level(p))
                for p in doc.paragraphs]
    except PackageNotFoundError:
        print(f"Error: {path} is not a valid .docx file (corrupt or renamed?)", file=sys.stderr)
    except Exception as exc:
        # Damaged or non-Word packages fail in many ways (KeyError, ValueError,
        # BadZipFile, zlib.error, XMLSyntaxError, OSError, ...). Report them as
        # an operational error (exit 2): an uncaught traceback would exit 1,
        # which means "asymmetries found".
        detail = " ".join(str(exc).split())
        print(f"Error: {path} could not be read as a .docx file ({type(exc).__name__}: {detail})", file=sys.stderr)
    sys.exit(2)


def _header_key(text: str) -> str:
    """Normalize a paragraph for comparison with BIBLIOGRAPHY_HEADERS."""
    text = text.strip().lower()
    # Tolerate manually typed heading numbers ("7 Literaturverzeichnis",
    # "7. Literaturverzeichnis") and trailing punctuation ("References:").
    # Word's automatic heading numbering is not part of the paragraph
    # text, so only literal-text numbering needs stripping here.
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", text)
    return text.rstrip(".:").strip()


def split_text_and_bibliography(
    paragraphs: list[tuple[str, Optional[int]]],
) -> tuple[str, list[str]]:
    """
    Split the document into body text and bibliography paragraphs.
    
    Heuristic: the bibliography starts at a heading whose text matches a
    common bibliography header (case-insensitive). Manually typed heading
    numbers ("7 Literaturverzeichnis", "7.1 Literatur") and trailing
    punctuation ("References:") are tolerated. If several paragraphs match,
    the highest-level heading wins, the first one on a tie: a body
    sub-heading "3.2 Sources" does not start the bibliography before the
    "References" chapter, and "Literaturverzeichnis" wins over its own
    sub-section "Literatur".
    
    It ends at the next top-level heading (Heading 1, or Title for a
    bibliography styled as Title) that is not itself a bibliography header,
    e.g. an appendix or a declaration of authorship. What follows counts as
    body text again: citations in an appendix are citations, and a signature
    line such as "Ort, Datum" is not a bibliography entry. Sub-headings
    ("Internetquellen") and a separate "Quellenverzeichnis" chapter stay in
    the bibliography. Without heading styles, it runs to the end.
    
    Returns: (body_text, bibliography_paragraphs)
    """
    texts = [text for text, _level in paragraphs]
    # Normalized like the paragraphs, so an entry added as the heading is
    # spelled ("Quellenangaben", "A. Literaturverzeichnis") matches too.
    headers = {_header_key(h) for h in BIBLIOGRAPHY_HEADERS}
    bib_start_idx = None
    best_level = None
    for i, p in enumerate(texts):
        if _header_key(p) in headers:
            # A header that is not styled as a heading counts as level 1.
            level = paragraphs[i][1] if paragraphs[i][1] is not None else 1
            if best_level is None or level < best_level:
                bib_start_idx, best_level = i, level
    
    if bib_start_idx is None:
        # No clear bibliography heading found
        return "\n".join(texts), []
    
    end_level = min(best_level, 1)
    bib_end_idx = len(paragraphs)
    for j in range(bib_start_idx + 1, len(paragraphs)):
        level = paragraphs[j][1]
        if (level is not None and level <= end_level
                and _header_key(texts[j]) not in headers):
            bib_end_idx = j
            break

    body = "\n".join(texts[:bib_start_idx] + texts[bib_end_idx:])
    # Sub-headings belong to the section but are not entries: a heading such
    # as "Gesetze, Verordnungen" would otherwise be read as an author.
    bibliography = [p for p, level in paragraphs[bib_start_idx + 1:bib_end_idx]
                    if p.strip() and level is None]
    return body, bibliography


def extract_in_text_authors(body: str, keep: frozenset[str] = frozenset()) -> set[str]:
    """
    Extract author surnames from in-text citations.
    
    Recognizes common patterns:
      (Smith, 2020)                              -> Smith
      (Smith & Jones, 2020)                      -> Smith, Jones
      (Smith et al., 2020)                       -> Smith
      Smith (2020)                               -> Smith
      (cf. Smith, 2020, p. 15)                   -> Smith
      (siehe Weber, 2020, S. 3)                  -> Weber
      Schulz (2022a)                             -> Schulz
      (Smith & Jones, 2020; Brown et al., 2021)  -> Smith, Jones, Brown
    
    Two-stage parsing:
      1. Find parenthesized blocks that look like citations
      2. Split each block on semicolons, then parse each fragment
    
    The recognition is heuristic and may produce false positives. The output
    is intended for cross-checking, not as ground truth.
    
    keep: surnames exempt from GERMAN_NON_AUTHOR_CAPS (the lead authors of
    the bibliography entries), so that "(OECD, 2019)" still counts when
    the bibliography lists "OECD. (2019)".
    """
    authors = set()
    stop = GERMAN_NON_AUTHOR_CAPS - keep
    # Name particles: van der Berg, de la Rosa, von Wagner, ter Horst, De Vries
    prefix = NAME_PREFIX
    
    # Stage 1: find parenthesized blocks containing a year (YYYY)
    paren_blocks = re.findall(r"\(([^()]*\d{4}[^()]*)\)", body)
    
    # Stage 2: per block, split on semicolons and parse each fragment
    for block in paren_blocks:
        for fragment in block.split(";"):
            fragment = fragment.strip()
            # A citation fragment typically has "Author(s), YYYY[, p. X]"
            # (English/APA style — comma before year)
            # or "Author(s) YYYY[, S. X]" (German author-year style — no comma)
            match = re.match(r"^((?:cf\.\s+|see\s+|vgl\.\s+|siehe\s+|nach\s+|zit\.\s+nach\s+)?[^,]+(?:\s+(?:et\s+al\.?|u\.\s*a\.))?(?:\s*(?:,\s*)?(?:&|and|und)\s+[\w'’-]+|,\s*[\w'’-]+)*),\s*\d{4}", fragment)
            if not match:
                # Try German style: "Author YYYY" without comma
                # (lead word in any case: "(Vgl. Smith 2020)"; a filler only
                # after a lead word: "(vgl. auch Müller 2020)", "(see also
                # Smith 2020)", not "(auch Deutschland 2020)")
                match = re.match(
                    r"^((?i:(?:vgl\.|cf\.|see|siehe|nach|zit\.\s+nach)\s+(?:(?:auch|also|z\.\s*b\.|e\.g\.)\s+)?)?"
                    + prefix + r"[A-ZÄÖÜ][\wäöüß'’-]+"
                    + r"(?:(?:\s+(?:&|und|and)\s+|\s*/\s*)" + prefix + r"[A-ZÄÖÜ][\wäöüß'’-]+)?"
                    + r"(?:\s+(?:et\s+al\.?|u\.\s*a\.))?)"
                    + r"\s+\d{4}",
                    fragment,
                )
            if not match:
                continue
            name_part = match.group(1)
            # Strip leading prefixes
            name_part = re.sub(r"^(cf\.\s+|see\s+|vgl\.\s+|siehe\s+|nach\s+|zit\.\s+nach\s+)", "", name_part, flags=re.IGNORECASE)
            # Remove "et al." / German "u. a."
            name_part = re.sub(r"\s+(?:et\s+al\.?|u\.\s*a\.)", "", name_part, flags=re.IGNORECASE)
            # Split on & or , or / or "and"/"und"
            for part in re.split(r"\s*[&,/]\s*|\s+(?:and|und)\s+", name_part):
                # The surname is the last capitalized token ("van den Berg" ->
                # Berg); numbers ("Tabelle 3") and lowercase words never
                # qualify, single letters ("N = 1200") are rejected
                tokens = part.split()
                idx = next((i for i in range(len(tokens) - 1, -1, -1) if tokens[i][:1].isupper()), None)
                if idx is None:
                    continue
                # Lowercase words before the surname must be name particles or
                # fillers ("see also Smith", "vgl. z. B. Smith"); otherwise the
                # fragment is prose ("eigene Darstellung", "etwa Deutschland").
                if any(t[:1].islower() and t.lower() not in PAREN_LOWERCASE_OK for t in tokens[:idx]):
                    continue
                surname = tokens[idx]
                # Safety net: skip known non-author capitalized words
                # (e.g., "(März 2021)", "(Tabelle 3, 2020)"). All-caps
                # acronyms and surname-like stopwords are kept here: in
                # parentheses before a year, "(OECD, 2019)" or
                # "(Winter, 2017)" is a citation, and a missing entry for it
                # must still be reported. After a particle, a stopword is
                # prose: "(von Mai 2020 bis Juni 2021)".
                after_particle = any(t.lower() in NAME_PARTICLES for t in tokens[:idx])
                if len(surname) > 1 and (surname not in stop or surname.isupper()
                                         or (surname in SURNAME_LIKE_STOPWORDS and not after_particle)):
                    authors.add(surname)
    
    # Pattern 2: narrative citations (Author (YYYY))
    # Supports:
    #   - hyphenated surnames: Müller-Schmidt
    #   - letters of any script and apostrophes: García, O'Brien, O’Brien
    #   - name prefixes: van der Berg, de la Rosa, von Wagner
    #   - joint authors: Smith and Jones, Müller-Schmidt & Weiss
    #   - et al. narrative: Brown et al. (2021), German Müller u. a. (2021)
    #   - same-author-same-year suffixes: Schulz (2022a)
    #   - locator or further years inside the parentheses: Müller (2020, S. 15),
    #     Müller (2020: 15), Smith (2019, 2020)
    #   - German author-year style: Schmidt 2020 (no parentheses, handled below)
    name_token = r"[A-ZÄÖÜ](?:[^\W\d_]|['’-])+"
    # Joint form OR et-al form
    joint = r"\s+(?:&|and|und)\s+" + prefix + name_token
    et_al = r"\s+(?:et\s+al\.?|u\.\s*a\.)"
    # Narrative with parentheses: Author (YYYY[, locator])
    narrative_paren = (
        r"(" + prefix + name_token
        + r"(?:" + joint + r"|" + et_al + r")?)\s+\(\d{4}[a-z]?"
        # locator: page ("2020, S. 15", "2020: 15-17") or further years
        # ("2019, 2020"); not any text, or "Deutschland (2020: 5,9 %)" and
        # "Umsatz (2020, in Mio. €)" would count as citations
        + r"(?:,\s*(?:S\.|p\.|pp\.)\s*\d[^()]*|:\s*\d+(?:\s*[-–]\s*\d+)?|[,;]\s*\d{4}[a-z]?[^()]*)?\)"
    )
    for match in re.findall(narrative_paren, body):
        cleaned = re.sub(et_al, "", match, flags=re.IGNORECASE)
        for part in re.split(r"\s+(?:&|and|und)\s+", cleaned):
            name = part.strip()
            if not name:
                continue
            tokens = name.split()
            surname = next((t for t in reversed(tokens) if t[:1].isupper()), tokens[-1])
            # Possessive: "Smith's (2020) study", "Jones' (2020) model" -> Smith, Jones
            surname = re.sub(r"['’]s?$", "", surname)
            # Safety net: skip known non-author capitalized words
            # (e.g., "Die EU (2020)", "Das Kapitel (2020)")
            if surname in stop:
                continue
            authors.add(surname)
    
    # German author-year narrative without parentheses: "Schmidt 2020 führt aus..."
    # 
    # False-positive trap: "Im Jahr 2020...", "Die EU 2020...", "Januar 2020..."
    # 
    # Two defenses layered here:
    # 
    #   1. Only accept the match if a page reference follows within a short window:
    #      "Schmidt 2020, S. 15"  YES
    #      "Schmidt 2020 (S. 15)" YES
    #      "Jahr 2020 wurde..."    NO
    #      This is strict but safe. Real German-style bare citations almost always
    #      carry a page number; prose like "Im Jahr 2020" never does.
    # 
    #   2. Filter the narrow class of German words that look like capitalized names
    #      but aren't (months, common prose nouns, supranational bodies). See
    #      GERMAN_NON_AUTHOR_CAPS at module top.
    
    # Strict pattern: name-token + year + (comma + page-ref OR parenthetical page-ref)
    # page-ref: S./p./pp. + digit
    german_narrative_strict = (
        r"(?:^|[\s,\.;\(])"
        r"(" + prefix + name_token
        + r"(?:" + joint + r"|" + et_al + r")?)"
        r"\s+\d{4}[a-z]?"
        r"(?:\s*,\s*(?:S\.|p\.|pp\.)\s*\d"       # "Schmidt 2020, S. 15"
        r"|\s*\((?:S\.|p\.|pp\.)\s*\d)"          # "Schmidt 2020 (S. 15)"
    )
    for match in re.findall(german_narrative_strict, body):
        cleaned = re.sub(et_al, "", match, flags=re.IGNORECASE)
        for part in re.split(r"\s+(?:&|and|und)\s+", cleaned):
            name = part.strip()
            if not name:
                continue
            tokens = name.split()
            surname = next((t for t in reversed(tokens) if t[:1].isupper()), tokens[-1])
            # Safety net: skip known non-author capitalized words
            if surname in stop:
                continue
            authors.add(surname)
    
    return authors


def extract_bibliography_authors(bibliography: list[str]) -> tuple[set[str], set[str]]:
    """
    Extract author surnames from bibliography entries.
    
    Returns: (first_authors, all_authors)
    
    first_authors contains only the lead author of each entry — these are the
    keys used for matching against in-text citations (since et-al. citations
    only mention the first author).
    
    all_authors additionally includes co-authors, useful for disambiguation
    but not for symmetry checks.
    
    Heuristic: the surname is the first word of an entry — before the comma
    for personal authors, before the period preceding the year for
    institutional authors.
      Smith, J. (2020). ...                -> first: Smith
      Smith, J., & Jones, R. (2020). ...   -> first: Smith; all: Smith, Jones
      Dawson, R., Ellis, S., & Fowler, T. (2020). ...
                                           -> first: Dawson; all: Dawson, Ellis, Fowler
      WHO. (2019). ...                     -> first: WHO
    """
    first_authors = set()
    all_authors = set()
    # Pattern accepts surname forms:
    #   - simple: Smith
    #   - non-ASCII initial: Öztürk (same class as the in-text patterns)
    #   - hyphenated: Müller-Schmidt
    #   - apostrophe, straight or typographic (Word AutoCorrect): O'Brien, O’Brien
    #   - with prefix: van der Berg, van den Berg, de la Rosa, von Wagner,
    #     also capitalized: De Vries, Van der Berg
    surname_core = r"[A-ZÄÖÜ][\w'’-]+"
    surname_token = NAME_PREFIX + surname_core
    
    for entry in bibliography:
        if not entry.strip():
            continue
        # Lead author — full token captured, but store the final capitalized word.
        # Personal entries: "Smith, J. (2020). ..." — comma after the surname.
        match = re.match(r"^(" + surname_token + r"),", entry.strip())
        if not match:
            # Institutional entries: "WHO. (2019). ..." — period before the year.
            match = re.match(r"^(" + surname_token + r")\.\s*\(\d{4}", entry.strip())
        if match:
            full = match.group(1)
            # Keep the last capitalized token as the canonical surname
            tokens = full.split()
            surname = next((t for t in reversed(tokens) if t[:1].isupper()), tokens[-1])
            first_authors.add(surname)
            all_authors.add(surname)
        
        # Co-authors after & or "and" / "und"
        coauthor_pattern = r"(?:&|and|und)\s+(" + surname_token + r"),"
        for match in re.findall(coauthor_pattern, entry):
            tokens = match.split()
            surname = next((t for t in reversed(tokens) if t[:1].isupper()), tokens[-1])
            all_authors.add(surname)

        # Middle authors of 3+-author entries ("Dawson, R., Ellis, S., &
        # Fowler, T. (2020)"): every "Surname, I." pair in the head of the
        # entry (before the year) is an author. The lead and the &-author
        # are re-matched here too — the set dedupes. all_authors is only
        # subtracted from the cited-author set, so growing it can only
        # remove false positives, never add any.
        head = re.split(r"\(\d{4}", entry, maxsplit=1)[0]
        middle_pattern = r"(" + surname_token + r"),\s*(?:[A-ZÄÖÜ]\.[\s-]*)+"
        for m in re.finditer(middle_pattern, head):
            tokens = m.group(1).split()
            surname = next((t for t in reversed(tokens) if t[:1].isupper()), tokens[-1])
            all_authors.add(surname)
        # Co-authors after / or ; with full given names ("Müller, Hans/Schmidt,
        # Karl (2019)", "Smith, John; Jones, Robert (2019)"), in the head only,
        # so a slash in the title ("Theory/Practice,") adds nothing.
        for m in re.finditer(r"[/;]\s*(" + surname_token + r"),", head):
            tokens = m.group(1).split()
            surname = next((t for t in reversed(tokens) if t[:1].isupper()), tokens[-1])
            all_authors.add(surname)
    
    return first_authors, all_authors


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/bibliography_check.py <file.docx>", file=sys.stderr)
        sys.exit(2)

    if sys.argv[1] in ("-h", "--help"):
        # __doc__ is None under python -OO
        print((__doc__ or "Usage: python scripts/bibliography_check.py <file.docx>").strip())
        sys.exit(0)

    doc_path = Path(sys.argv[1])
    if not doc_path.exists():
        print(f"Error: file not found: {doc_path}", file=sys.stderr)
        sys.exit(2)

    if doc_path.suffix.lower() != ".docx":
        print(f"Error: expected a .docx file, got {doc_path.suffix}", file=sys.stderr)
        sys.exit(2)
    
    paragraphs = read_docx_paragraphs(doc_path)
    body, bibliography = split_text_and_bibliography(paragraphs)
    
    if not bibliography:
        print("Warning: no bibliography section found.")
        print(f"Searched for headers: {', '.join(BIBLIOGRAPHY_HEADERS)}")
        print("Add the appropriate header for your language to BIBLIOGRAPHY_HEADERS in this script.")
        sys.exit(2)
    
    bib_first_authors, bib_all_authors = extract_bibliography_authors(bibliography)
    if not bib_first_authors:
        # Comparing two empty sets would report a passed check, e.g. for a
        # numeric bibliography ("[1] J. Smith, ...").
        print(f"Warning: none of the {len(bibliography)} bibliography entries could be read.")
        print('The check needs author-year entries such as "Smith, J. (2020)" or "WHO. (2019)";')
        print("numeric styles such as IEEE are not supported.")
        sys.exit(2)
    cited_authors = extract_in_text_authors(body, keep=frozenset(bib_first_authors))
    
    # Asymmetry check:
    # - cited_only: cited in text but no matching lead author in bibliography
    #   (allow match against co-authors too, since citations sometimes use
    #    co-author surnames in narrative form)
    # - listed_only: lead author of a bibliography entry not cited anywhere
    cited_only = cited_authors - bib_all_authors
    listed_only = bib_first_authors - cited_authors
    
    print(f"Bibliography minus-test for: {doc_path.name}")
    print(f"  Authors cited in text:            {len(cited_authors)}")
    print(f"  Lead authors in bibliography:     {len(bib_first_authors)}")
    print(f"  All authors in bibliography:      {len(bib_all_authors)}")
    print()
    
    if cited_only:
        print(f"⚠️  Cited but NOT in bibliography ({len(cited_only)}):")
        for a in sorted(cited_only):
            print(f"    {a}")
        print()
    
    if listed_only:
        print(f"⚠️  In bibliography but NOT cited ({len(listed_only)}):")
        for a in sorted(listed_only):
            print(f"    {a}")
        print()
    
    if not cited_only and not listed_only:
        print("✅ Bibliography minus-test passed: no asymmetries detected.")
    else:
        print("Note: this check uses surname-matching heuristics and may produce")
        print("false positives (e.g., for ambiguous in-text citations). Use the")
        print("output as a starting point for manual verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
