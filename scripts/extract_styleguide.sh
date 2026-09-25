#!/usr/bin/env bash
#
# extract_styleguide.sh
#
# Extracts text from institutional guideline documents (PDFs) and prepares
# it for the style-resolver agent to ingest.
#
# This script does NOT do the resolution itself — that is the job of the
# style-resolver agent in Claude Code. This script collects raw texts.
#
# Usage:
#   ./scripts/extract_styleguide.sh <guidelines-directory> [output-directory]
#
# Examples:
#   ./scripts/extract_styleguide.sh workspace/sources/_guidelines/
#   ./scripts/extract_styleguide.sh guidelines/
#   ./scripts/extract_styleguide.sh 00_Shared_Materials/guidelines/ _styleguide_rawtext
#
# Requirements:
#   - bash (for wrapper)
#   - python3 (or python, or the Windows `py` launcher) with the `pypdf`
#     package installed (pure-python PDF parser), with its [crypto] extra for
#     AES-encrypted PDFs. Install: pip3 install -r requirements.txt
#     (or: pip3 install "pypdf[crypto]")
#   - pdftotext (poppler) as fallback if python / pypdf is not available
#
# Why not pdftotext directly?
# pdftotext is not available by default on Windows (Git Bash). The script
# prefers a pure-python path for portability and falls back to pdftotext
# only when python / pypdf is unavailable. If no Python interpreter exists
# at all, a limited pdftotext-only shell mode runs; in that mode disguised
# ZIP archives are not unpacked and are reported as errors instead.
#
# Exit codes:
#   0 - at least one document processed, no errors
#   1 - wrong usage, missing tools, extraction errors, or nothing processed

set -euo pipefail

case "${1:-}" in
    -h|--help)
        echo "Usage: $0 <guidelines-directory> [output-directory]"
        echo ""
        echo "Extracts text from guideline PDFs (and disguised ZIPs) into plain-text"
        echo "files for the style-resolver agent. Default output: _styleguide_rawtext/."
        echo "Requirements: bash + Python 3 with pypdf (or pdftotext as fallback)."
        exit 0
        ;;
esac

if [ $# -lt 1 ]; then
    echo "Usage: $0 <guidelines-directory> [output-directory]" >&2
    echo "Example: $0 guidelines/" >&2
    exit 1
fi

GUIDELINES_DIR="$1"
OUT_DIR="${2:-_styleguide_rawtext}"

if [ ! -d "$GUIDELINES_DIR" ]; then
    echo "Error: directory not found: $GUIDELINES_DIR" >&2
    exit 1
fi

# Tool discovery. Prefer python3, but accept `python` and the Windows `py`
# launcher too when they are a Python 3. `command -v python3` alone is not
# enough on Windows: python3 may resolve to the dead Microsoft Store
# app-execution-alias stub, and the python.org installer creates no `python3`
# and by default puts only the `py` launcher on PATH. So probe that the
# interpreter actually runs, and fall back to `python`, then `py`.
PYTHON_BIN=""
for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1 \
        && "$cand" -c 'import sys; raise SystemExit(sys.version_info[0] < 3)' >/dev/null 2>&1; then
        PYTHON_BIN="$cand"
        break
    fi
done

HAVE_PDFTOTEXT=0
if command -v pdftotext >/dev/null 2>&1; then
    HAVE_PDFTOTEXT=1
fi

if [ -z "$PYTHON_BIN" ] && [ "$HAVE_PDFTOTEXT" = "0" ]; then
    echo "Error: no working Python 3 interpreter (tried: python3, python, py) and no pdftotext found." >&2
    echo "Install one of:" >&2
    echo "  - python3 + 'pip3 install \"pypdf[crypto]\"' (recommended, cross-platform)" >&2
    echo "  - pdftotext (poppler-utils on Linux, poppler on macOS)" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

echo "Extracting text from guideline documents in: $GUIDELINES_DIR"
echo "Output directory: $OUT_DIR"
echo ""

if [ -z "$PYTHON_BIN" ]; then
    # pdftotext-only fallback: no Python interpreter available. Mirrors the
    # Python path (recursive case-insensitive *.pdf search, flattened output
    # names, collision uniquifying, empty-extraction warnings, exit codes),
    # but cannot unpack disguised ZIP archives - those are reported as errors.
    echo "Note: no Python interpreter found - using the pdftotext-only fallback." >&2
    echo "      (Disguised ZIP archives are not unpacked in this mode.)" >&2
    echo ""
    count=0
    errors=0
    used_names="|"
    written="|"
    base="${GUIDELINES_DIR%/}"
    while IFS= read -r -d '' pdf; do
        # Flatten the relative path; strip only the FINAL .pdf extension
        # (any case), so 'notes.pdf.pdf' does not collapse onto 'notes.pdf'.
        rel="${pdf#"$base"}"
        rel="${rel#/}"
        flat="${rel//\//__}"
        flat="${flat%.[Pp][Dd][Ff]}"
        # Uniquify: flattened names can still collide (e.g. 'A/x.pdf' vs
        # 'A__x.pdf'); add a numeric suffix instead of silently overwriting.
        name="$flat"
        n=2
        while [ "${used_names#*"|$name|"}" != "$used_names" ]; do
            name="${flat}_$n"
            n=$((n + 1))
        done
        used_names="${used_names}${name}|"
        out_file="$OUT_DIR/$name.txt"

        magic="$(head -c 4 "$pdf" 2>/dev/null | tr -d '\0' || true)"
        if [ "$magic" != "%PDF" ]; then
            # Distinguish a disguised ZIP (starts with "PK") from a merely
            # corrupt file, so users are not sent to install Python for a
            # download that is simply broken.
            case "$magic" in
                PK*) echo "  ?   $(basename "$pdf") - ZIP archive disguised as PDF (unpacking needs python3)" >&2 ;;
                *)   echo "  ?   $(basename "$pdf") - not a PDF (corrupt or wrong file type?)" >&2 ;;
            esac
            errors=$((errors + 1))
            continue
        fi
        # -enc UTF-8: the xpdf build of pdftotext defaults to Latin-1.
        if pdftotext -layout -enc UTF-8 "$pdf" "$out_file" 2>/dev/null \
           && grep -q '[^[:space:]]' "$out_file"; then
            lines=$(($(wc -l < "$out_file")))
            echo "  OK  $(basename "$pdf")  ->  $name.txt ($lines lines)"
            written="${written}${name}.txt|"
            count=$((count + 1))
        else
            rm -f "$out_file"
            echo "  ERR $(basename "$pdf") - PDF extraction failed or produced no text" >&2
            errors=$((errors + 1))
        fi
    done < <(find "$base" -type f -iname '*.pdf' -print0 | sort -z)

    echo ""
    echo "Done."
    echo "  Processed: $count document(s)"
    if [ "$errors" -gt 0 ]; then
        echo "  Errors:    $errors document(s)"
    fi
    # Text files from an earlier run (a guideline since replaced, renamed or
    # removed) would still be read by the style-resolver: name them.
    stale=""
    for f in "$OUT_DIR"/*.txt; do
        [ -e "$f" ] || continue
        case "$written" in
            *"|${f##*/}|"*) ;;
            *) stale="$stale ${f##*/}" ;;
        esac
    done
    if [ -n "$stale" ]; then
        echo "Note: not written by this run (left over from an earlier run?):$stale" >&2
        echo "      Delete them from $OUT_DIR before invoking the style-resolver, or it reads them too." >&2
    fi
    if [ "$count" -eq 0 ]; then
        echo ""
        echo "Warning: no documents were successfully processed from $GUIDELINES_DIR" >&2
        exit 1
    fi
    echo ""
    echo "Next step: invoke the style-resolver agent in Claude Code."
    echo "It will read the extracted texts in $OUT_DIR and produce styleguide.md."
    if [ "$errors" -gt 0 ]; then
        exit 1
    fi
    exit 0
fi

# Delegate to Python for all heavy lifting — handles file-type detection,
# recursive search, safe ZIP extraction (ZipSlip-hardened), and pypdf.
"$PYTHON_BIN" - "$GUIDELINES_DIR" "$OUT_DIR" "$HAVE_PDFTOTEXT" << 'PYEOF'
import os
import sys
import subprocess
import tempfile
import zipfile
import zlib
from pathlib import Path

# Encoding guard for Windows consoles (CP1252 by default) — same pattern as
# the framework's standalone Python scripts.
for stream in (sys.stdout, sys.stderr):
    if stream.encoding and stream.encoding.lower() != "utf-8":
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

guidelines_dir = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
have_pdftotext = sys.argv[3] == "1"

try:
    from pypdf import PdfReader
    have_pypdf = True
except ImportError:
    have_pypdf = False

if not have_pypdf and not have_pdftotext:
    print("Error: neither pypdf nor pdftotext available for PDF extraction.", file=sys.stderr)
    print('  Install: pip3 install "pypdf[crypto]"', file=sys.stderr)
    sys.exit(1)


def sniff_file_type(path):
    """Return 'pdf', 'zip', or 'unknown' by reading the magic bytes."""
    try:
        with open(path, 'rb') as f:
            header = f.read(8)
    except OSError:
        return 'unknown'
    if header.startswith(b'%PDF'):
        return 'pdf'
    if header.startswith(b'PK\x03\x04'):
        return 'zip'
    return 'unknown'


def extract_pdf_text(pdf_path, out_path):
    """Extract text from a real PDF, preferring pypdf."""
    if have_pypdf:
        try:
            reader = PdfReader(str(pdf_path))
            texts = []
            failed = 0
            for page in reader.pages:
                try:
                    texts.append(page.extract_text() or '')
                except Exception as e:
                    texts.append('')
                    failed += 1
                    last_err = e
            # Every page failed (e.g. an AES-encrypted PDF where pypdf was
            # installed without its [crypto] extra): report the real cause, not
            # "empty text".
            if texts and failed == len(texts):
                raise last_err
            out_path.write_text('\n\n'.join(texts), encoding='utf-8')
            return True
        except Exception as e:
            print(f"    pypdf failed ({e})" + (", trying pdftotext..." if have_pdftotext else ""), file=sys.stderr)
    if have_pdftotext:
        try:
            # -enc UTF-8: the xpdf build of pdftotext (common on Windows)
            # defaults to Latin-1, which the UTF-8 reads below would reject.
            subprocess.run(
                ['pdftotext', '-layout', '-enc', 'UTF-8', str(pdf_path), str(out_path)],
                check=True, capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
    return False


def read_text_member(path):
    """Decode a .txt archive member: UTF-8 (with or without BOM), else
    Windows-1252, the usual encoding of text files saved on Windows."""
    data = path.read_bytes()
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('cp1252', errors='replace')


def safe_extract_zip(zip_path, target_dir):
    """Safely extract ZIP contents, blocking path-traversal (ZipSlip) and zip bombs."""
    target_abs = target_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        # Cap entry count and unpacked size. The declared sizes can be
        # trusted: zipfile never extracts more bytes than an entry declares.
        infos = zf.infolist()
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 512 * 1024 * 1024:
            raise ValueError("archive too large when unpacked (limit: 512 MiB, 10000 entries)")
        for member in zf.namelist():
            # Reject absolute paths and any '..' components
            if member.startswith('/') or member.startswith('\\'):
                raise ValueError(f"Zip contains absolute path: {member}")
            normalized = Path(member).as_posix()
            if '..' in normalized.split('/'):
                raise ValueError(f"Zip contains path traversal: {member}")
            destination = (target_dir / member).resolve()
            # Final check: destination must stay inside target
            try:
                destination.relative_to(target_abs)
            except ValueError:
                raise ValueError(f"Zip entry escapes target: {member}")
        zf.extractall(target_dir)


# Main loop: recursive PDF search. Case-insensitive by explicit filter, so
# 'LEITFADEN.PDF' is found on Linux/macOS too, where rglob('*.pdf') would
# be case-sensitive.
count = 0
errors = 0
pdf_files = sorted(
    p for p in guidelines_dir.rglob('*')
    if p.is_file() and p.suffix.lower() == '.pdf'
)

if not pdf_files:
    print(f"Warning: no PDF files found in {guidelines_dir}", file=sys.stderr)

used_names = set()
written = set()

for pdf in pdf_files:
    # Flatten the relative path into one output name, stripping only the
    # FINAL .pdf extension (any case). '__' CAN legally appear in filenames
    # and flattened names can still collide (e.g. 'A/x.pdf' vs 'A__x.pdf'),
    # so collisions get a numeric suffix instead of silently overwriting.
    rel_path = pdf.relative_to(guidelines_dir).as_posix()
    flat_name = rel_path.replace('/', '__')[:-len(pdf.suffix)]
    unique_name = flat_name
    n = 2
    while unique_name in used_names:
        unique_name = f"{flat_name}_{n}"
        n += 1
    used_names.add(unique_name)
    out_file = out_dir / f"{unique_name}.txt"

    file_type = sniff_file_type(pdf)

    if file_type == 'pdf':
        if extract_pdf_text(pdf, out_file):
            text = out_file.read_text(encoding='utf-8', errors='replace')
            if not text.strip():
                out_file.unlink()
                print(f"  WARN {rel_path} - extracted text is empty (scanned/image-only PDF?)", file=sys.stderr)
                errors += 1
            else:
                lines = len(text.splitlines())
                print(f"  OK  {pdf.name}  ->  {out_file.name} ({lines} lines)")
                written.add(out_file.name)
                count += 1
        else:
            print(f"  ERR {rel_path} - PDF extraction failed", file=sys.stderr)
            errors += 1

    elif file_type == 'zip':
        print(f"  !   {pdf.name} is a ZIP archive (disguised), extracting safely...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            try:
                safe_extract_zip(pdf, tmp_path)
            except ValueError as e:
                print(f"    Blocked (security): {e}", file=sys.stderr)
                errors += 1
                continue
            except (zipfile.BadZipFile, zlib.error, RuntimeError,
                    NotImplementedError, EOFError, OSError) as e:
                # Corrupt, encrypted or unsupported archive: report it and
                # continue with the next file instead of aborting the run.
                print(f"  ERR {rel_path} - could not unpack archive ({type(e).__name__}: {e})", file=sys.stderr)
                errors += 1
                continue
            # Collect .txt members and extract text from contained PDFs
            members = sorted(p for p in tmp_path.rglob('*') if p.is_file())
            parts = []
            for member in members:
                suffix = member.suffix.lower()
                if suffix == '.txt':
                    parts.append(read_text_member(member))
                elif suffix == '.pdf':
                    member_out = tmp_path / (member.name + '.extracted')
                    if extract_pdf_text(member, member_out):
                        parts.append(member_out.read_text(encoding='utf-8', errors='replace'))
                    else:
                        print(f"    ERR {member.name} (in archive) - PDF extraction failed", file=sys.stderr)
            combined = '\n\n'.join(parts)
            if combined.strip():
                out_file.write_text(combined, encoding='utf-8')
                lines = len(combined.splitlines())
                print(f"      -> {out_file.name} ({lines} lines)")
                written.add(out_file.name)
                count += 1
            else:
                found = ', '.join(m.name for m in members[:10]) if members else 'none'
                print(f"    No usable text in archive (members: {found})", file=sys.stderr)
                errors += 1

    else:
        print(f"  ?   {rel_path} - unrecognized file type", file=sys.stderr)
        errors += 1

print()
print("Done.")
print(f"  Processed: {count} document(s)")
if errors > 0:
    print(f"  Errors:    {errors} document(s)")
# Text files from an earlier run (a guideline since replaced, renamed or
# removed) would still be read by the style-resolver: name them.
stale = sorted(p.name for p in out_dir.glob('*.txt') if p.name not in written)
if stale:
    print("Note: not written by this run (left over from an earlier run?): "
          + ", ".join(stale[:10]) + (" ..." if len(stale) > 10 else ""), file=sys.stderr)
    print(f"      Delete them from {out_dir} before invoking the style-resolver, or it reads them too.",
          file=sys.stderr)
if count == 0:
    print()
    print(f"Warning: no documents were successfully processed from {guidelines_dir}", file=sys.stderr)
    sys.exit(1)
print()
print("Next step: invoke the style-resolver agent in Claude Code.")
print(f"It will read the extracted texts in {out_dir} and produce styleguide.md.")
if errors > 0:
    sys.exit(1)
PYEOF
