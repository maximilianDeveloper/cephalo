#!/usr/bin/env python3
"""
abbreviations_extract.py

Derives a list of abbreviations from a document automatically.

Steps:
1. Extract all abbreviations from the document text
2. Filter out generally common abbreviations (a small built-in list)
3. Return a sorted list of project-specific abbreviations

The output can be cross-checked against the document's actual list of 
abbreviations to identify undocumented abbreviations or unused entries.

Usage:
    python scripts/abbreviations_extract.py workspace/output/document.docx
    python scripts/abbreviations_extract.py path/to/file.docx
"""

import os
import re
import sys
from pathlib import Path

# Encoding guard for Windows consoles (CP1252 by default).
# Without this, printing ⚠️ / ✅ raises UnicodeEncodeError.
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
    sys.exit(1)


# Common abbreviations to exclude from the project-specific list.
# Extend as needed for your language / context.
COMMON_ABBREVIATIONS = {
    # English
    "e.g", "i.e", "etc", "cf", "vs", "et", "al", "Inc", "Ltd", "Co", "Corp",
    "USA", "UK", "EU", "UN", "PhD", "MA", "BA", "MSc", "BSc",
    "Mr", "Mrs", "Ms", "Dr", "Prof",
    "AM", "PM", "BC", "AD", "CE", "BCE",
    # German (common)
    "z.B", "d.h", "u.a", "ggf", "bzw", "vgl", "ebd", "Hrsg", "Aufl",
    "S", "Bd", "Nr", "Abs", "Art",
    # Punctuation/format markers that look like abbreviations
    "p", "pp", "no", "vol",
}


def extract_abbreviations(text: str) -> set[str]:
    """
    Extracts likely abbreviations from text.
    
    Patterns matched:
      - All-caps sequences (2-8 chars, digits allowed alongside at least
        one letter): ABC, EU, NATO, ÖPNV, B2B, CO2, 5G, BENELUX
      - Dotted abbreviations (trailing dot optional): U.S.A., A.B.C
      - Mixed-case with internal caps (e.g., GmbH, BaFin, AfD)

    German umlauts (Ä Ö Ü, and ß for lowercase parts) are treated as letters.
    """
    # Character classes for uppercase and lowercase that include umlauts
    upper = r"A-ZÄÖÜ"
    lower = r"a-zäöüß"
    letter = upper + lower

    # All-caps (2-8 chars; digits allowed, but at least one letter required)
    # or dotted forms. The dotted alternative ends in an optional final dot
    # plus a (?!\w) lookahead instead of \b: a plain \b cannot match between
    # the final dot and following whitespace, which made the regex backtrack
    # and truncate the last segment (U.S.A. -> "US").
    allcaps_pattern = (
        rf"\b(?=[{upper}0-9]*[{upper}])[{upper}0-9]{{2,8}}\b"
        rf"|\b(?:[{upper}]\.){{1,5}}[{upper}]\.?(?!\w)"
    )
    # Mixed-case candidates (3-8 chars)
    mixed_pattern = rf"\b[{letter}]{{3,8}}\b"
    
    all_matches = set()
    
    # Collect all-caps / dotted
    for m in re.findall(allcaps_pattern, text):
        if m.strip():
            all_matches.add(m.replace(".", "").upper())
    
    # Collect mixed-case candidates
    for m in re.findall(mixed_pattern, text):
        if m.islower() or m.isupper():
            continue
        # Require at least 2 uppercase letters
        if sum(1 for c in m if c.isupper()) < 2:
            continue
        # Skip pure Capitalized proper nouns (one initial cap, rest lower)
        if re.match(rf"^[{upper}][{lower}]+$", m):
            continue
        all_matches.add(m)
    
    return all_matches


def read_docx_text(path: Path) -> str:
    """
    Read text from a .docx file, including all locations where abbreviations
    might appear: paragraphs, tables, headers, footers, and footnotes.

    Footnotes and endnotes are reached via the low-level XML: python-docx
    does not expose them on the Document object and loads their parts as
    generic opc parts (no typed .element), so the raw XML blob is parsed.
    """
    try:
        doc = Document(str(path))
    except PackageNotFoundError:
        print(f"Error: {path} is not a valid .docx file (corrupt or renamed?)", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # A ZIP that is not a readable Word package: BadZipFile, zlib.error,
        # KeyError (missing part), ValueError (not a Word file),
        # XMLSyntaxError, OSError, ...
        print(f"Error: cannot read {path} as .docx ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        sys.exit(1)
    chunks: list[str] = []
    
    # Paragraphs in the main body
    for p in doc.paragraphs:
        if p.text:
            chunks.append(p.text)
    
    # Tables (including nested)
    def collect_table_text(tbl):
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if p.text:
                        chunks.append(p.text)
                for nested in cell.tables:
                    collect_table_text(nested)
    for table in doc.tables:
        collect_table_text(table)
    
    # Headers and footers across all sections
    for section in doc.sections:
        for container in (section.header, section.footer,
                          section.first_page_header, section.first_page_footer,
                          section.even_page_header, section.even_page_footer):
            try:
                for p in container.paragraphs:
                    if p.text:
                        chunks.append(p.text)
            except Exception:
                # Not all sections have every header/footer variant
                continue
    
    # Footnotes and endnotes (XML-level access). python-docx loads these as
    # generic opc parts without a typed .element, so parse the raw XML blob.
    try:
        from docx.oxml import parse_xml
        from docx.oxml.ns import qn
    except ImportError as exc:
        print(f"Warning: footnotes/endnotes skipped ({exc})", file=sys.stderr)
    else:
        for part in doc.part.package.iter_parts():
            partname = part.partname.lower()
            if "footnotes" in partname or "endnotes" in partname:
                try:
                    root = parse_xml(part.blob)
                except Exception as exc:
                    print(f"Warning: could not read {part.partname}: {exc}",
                          file=sys.stderr)
                    continue
                # Join the runs of each note paragraph, as python-docx does for
                # body paragraphs: Word often splits one word across runs, so
                # one chunk per w:t would cut UNESCO into UNES + CO. Tabs,
                # breaks and non-breaking hyphens become a space separator.
                for para in root.iter(qn("w:p")):
                    text = "".join(
                        (el.text or "") if el.tag == qn("w:t") else " "
                        for el in para.iter(qn("w:t"), qn("w:tab"), qn("w:ptab"),
                                            qn("w:br"), qn("w:cr"),
                                            qn("w:noBreakHyphen"))
                    )
                    if text.strip():
                        chunks.append(text)

    return "\n".join(chunks)


def main():
    usage = "Usage: python scripts/abbreviations_extract.py <file.docx>"
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(usage)
        sys.exit(0)
    if len(sys.argv) != 2:
        print(usage, file=sys.stderr)
        sys.exit(1)

    doc_path = Path(sys.argv[1])
    # Probe with open() rather than Path.exists(): exists() is True for a
    # directory and raises PermissionError when a parent is not searchable.
    try:
        with open(doc_path, "rb"):
            pass
    except OSError as exc:
        # Windows reports a directory as "Permission denied"
        reason = "is a directory" if os.path.isdir(doc_path) else exc.strerror or exc
        print(f"Error: cannot open {doc_path}: {reason}", file=sys.stderr)
        sys.exit(1)
    
    if doc_path.suffix.lower() != ".docx":
        print(f"Error: expected a .docx file, got "
              f"{doc_path.suffix or 'a file without extension'}: {doc_path}",
              file=sys.stderr)
        sys.exit(1)
    
    text = read_docx_text(doc_path)
    found = extract_abbreviations(text)
    
    # Filter out common abbreviations. Both sides must be normalized identically:
    # the extract_abbreviations() function strips dots and uppercases for all-caps
    # candidates; we apply the same normalization here to the COMMON_ABBREVIATIONS
    # set. Mixed-case candidates (GmbH) are kept as-is and matched case-sensitively.
    common_normalized = {c.replace(".", "").upper() for c in COMMON_ABBREVIATIONS}
    project_specific = sorted(
        a for a in found
        if a.replace(".", "").upper() not in common_normalized
    )
    
    print(f"Project-specific abbreviations found in {doc_path.name}:")
    print(f"  Total candidates: {len(found)}")
    print(f"  After filtering common: {len(project_specific)}")
    print()
    
    for abbr in project_specific:
        print(f"  {abbr}")
    
    print()
    print("Cross-check this list against your document's list of abbreviations.")
    print("Add any missing entries; remove any unused entries.")


if __name__ == "__main__":
    main()
