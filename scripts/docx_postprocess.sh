#!/usr/bin/env bash
#
# docx_postprocess.sh
#
# Post-processing for .docx files generated programmatically.
# Adds settings that python-docx and similar libraries cannot set directly:
#
#   - Automatic hyphenation
#   - (Future: other settings as needed)
#
# Usage:
#   ./docx_postprocess.sh path/to/document.docx
#
# Background:
# Word documents are ZIP archives containing XML files. The settings.xml
# file controls document-level options. Programmatic libraries often omit
# the auto-hyphenation flag, leading to ugly word breaks at line ends.
# This script unzips the document, patches the XML, and re-zips.
#
# Requirements:
#   - bash, unzip (re-zipping uses Python's zipfile module — `zip` is NOT needed)
#   - Python 3 (`python3` or `python` on PATH; used for portable XML patching
#     and re-zipping)

set -euo pipefail

case "${1:-}" in
    -h|--help)
        echo "Usage: $0 path/to/document.docx"
        echo ""
        echo "Enables automatic hyphenation in a .docx (patches word/settings.xml"
        echo "and re-zips in place; re-running on a patched file is a no-op)."
        echo "Requirements: bash, unzip, Python 3."
        exit 0
        ;;
esac

if [ $# -lt 1 ]; then
    echo "Usage: $0 path/to/document.docx" >&2
    exit 1
fi

DOC="$1"

if [ ! -f "$DOC" ]; then
    echo "Error: file not found: $DOC" >&2
    exit 1
fi

if [[ "$DOC" != *.docx ]]; then
    echo "Error: expected a .docx file" >&2
    exit 1
fi

# Dependency checks
if ! command -v unzip >/dev/null 2>&1; then
    echo "Error: unzip not installed." >&2
    echo "  Install:" >&2
    echo "    Linux:       apt install unzip" >&2
    echo "    macOS:       brew install unzip" >&2
    echo "    Windows:     ships with Git Bash; otherwise 'scoop install unzip'" >&2
    exit 1
fi

# Find a working Python 3. `command -v python3` alone is not enough on Windows:
# python3 may resolve to the dead Microsoft Store app-execution-alias stub, and
# the python.org installer creates `python`/`py` but no `python3`. So probe that
# the interpreter actually runs, and fall back to `python`.
PY=""
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 \
        && "$cand" -c 'import sys; raise SystemExit(sys.version_info[0] < 3)' >/dev/null 2>&1; then
        PY="$cand"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "Error: no working Python 3 interpreter found (tried: python3, python)." >&2
    echo "  Install: 'apt install python3' (Linux), 'brew install python' (macOS)," >&2
    echo "  or the python.org installer on Windows (it provides 'python', not 'python3')." >&2
    exit 1
fi

# Absolute path before changing directory
DOC_ABS=$(cd "$(dirname "$DOC")" && pwd)/$(basename "$DOC")

# Work in a temporary directory. Deliberately NOT named TMPDIR: that is the
# standard POSIX temp-dir override, and reassigning it would silently leak
# into child processes (e.g. Python's tempfile module).
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

cd "$WORK_DIR"
unzip -q "$DOC_ABS"

# Refuse documents containing symbolic links: unzip restores symlink entries,
# and following them would embed arbitrary local files in the re-zipped
# document or write the settings patch outside the work directory. Checked
# with Python (fails closed) rather than `find`, which may be missing.
"$PY" - << 'PYEOF'
import os
import sys

for dirpath, dirnames, filenames in os.walk('.'):
    for name in dirnames + filenames:
        if os.path.islink(os.path.join(dirpath, name)):
            sys.exit('Error: document contains symbolic links; refusing to process it')
PYEOF

SETTINGS="word/settings.xml"

if [ ! -f "$SETTINGS" ]; then
    echo "Error: $SETTINGS not found inside the document" >&2
    exit 1
fi

# Check whether auto-hyphenation is already ENABLED. Only the bare element or
# w:val in {1,true,on} counts as enabled — w:val="0"/"false"/"off" means
# explicitly disabled (OOXML ST_OnOff) and is rewritten below, not skipped.
if grep -qE "<w:autoHyphenation([[:space:]]+w:val=[\"'](1|true|on)[\"'])?[[:space:]]*/>" "$SETTINGS" 2>/dev/null; then
    echo "Note: auto-hyphenation already enabled — no change."
    SKIP_PATCH=1
else
    SKIP_PATCH=0
fi

# Patch settings.xml using Python (portable across Linux/macOS/Windows)
if [ "$SKIP_PATCH" = "0" ]; then
    "$PY" - "$SETTINGS" << 'PYEOF'
import re
import sys

path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Enabled = bare element or w:val in {1,true,on}. Per OOXML ST_OnOff,
# w:val="0"/"false"/"off" means explicitly DISABLED and must be rewritten.
ENABLED_RE = re.compile(r'<w:autoHyphenation(?:\s+w:val=["\'](?:1|true|on)["\'])?\s*/>')
PRESENT_RE = re.compile(r'<w:autoHyphenation(?:\s[^>]*)?/>')

if ENABLED_RE.search(content):
    sys.exit(0)

if PRESENT_RE.search(content):
    # Element exists but disables hyphenation — rewrite it in place
    # (same position, so no element-ordering concerns).
    content = PRESENT_RE.sub('<w:autoHyphenation/>', content, count=1)
# Preferred: insert directly after defaultTabStop, its schema predecessor
# (python-docx, Word and LibreOffice all write defaultTabStop)
elif re.search(r'<w:defaultTabStop\b[^>]*/>', content):
    content = re.sub(
        r'(<w:defaultTabStop\b[^>]*/>)',
        r'\1<w:autoHyphenation/>',
        content,
        count=1,
    )
else:
    # Fallback: insert as first child of <w:settings ...>
    content = re.sub(
        r'(<w:settings[^>]*>)',
        r'\1<w:autoHyphenation/>',
        content,
        count=1,
    )

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
PYEOF
    echo "Auto-hyphenation enabled."
fi

# Re-zip. [Content_Types].xml is kept as the first entry and stored (not
# compressed) — not a spec requirement (OPC mandates neither entry order nor
# compression method), but it maximizes compatibility with strict/streaming
# consumers. Use Python's zipfile for this — `zip -r` does not guarantee
# entry order.
NEW_DOC="${DOC_ABS}.new"
"$PY" - "$NEW_DOC" "$WORK_DIR" << 'PYEOF'
import os
import sys
import zipfile

out_path = sys.argv[1]
src_dir = sys.argv[2]

def collect_files(root):
    """Walk root and return list of (abs_path, rel_path) pairs."""
    entries = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(abs_path, root).replace(os.sep, '/')
            entries.append((abs_path, rel_path))
    return entries

all_entries = collect_files(src_dir)

# Keep [Content_Types].xml FIRST and STORED (no compression) for maximum
# compatibility with strict/streaming consumers (not a spec requirement).
content_types = [e for e in all_entries if e[1] == '[Content_Types].xml']
others = [e for e in all_entries if e[1] != '[Content_Types].xml']

if not content_types:
    print('Error: [Content_Types].xml missing — not a valid docx.', file=sys.stderr)
    sys.exit(1)

# Stable ordering of the rest
others.sort(key=lambda e: e[1])

# strict_timestamps=False: Word dates every entry 1980-01-01 00:00, which the
# restored mtime can turn into 1979-12-31 in some time zones (e.g. Asia/Singapore).
with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED, strict_timestamps=False) as zf:
    # First: Content_Types, stored
    abs_path, rel_path = content_types[0]
    zf.write(abs_path, rel_path, compress_type=zipfile.ZIP_STORED)
    # Rest: deflated
    for abs_path, rel_path in others:
        zf.write(abs_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)
PYEOF

mv "$NEW_DOC" "$DOC_ABS"

echo "Post-processing complete: $DOC"
