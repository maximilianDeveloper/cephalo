# Scripts

cephalo ships five utility scripts in `scripts/`. They are optional — the agents can guide a project without them — but each one automates a check or transformation that would otherwise take manual effort.

| Script | Purpose | When to run |
|--------|---------|-------------|
| `extract_styleguide.sh` | Convert institutional guideline PDFs to plain text for the style-resolver | Once per project during setup |
| `abbreviations_extract.py` | Derive the list of abbreviations from a finished DOCX | Phase B, final stages |
| `bibliography_check.py` | Minus-test by author surname: every cited author is in the bibliography, every entry's lead author is cited | Phase B, final stages |
| `docx_postprocess.sh` | Enable automatic hyphenation in a DOCX (python-docx doesn't set this) | Phase B, before final export |
| `cross_session_audit.py` | Cross-worktree audit: surfaces notes and changes from other worktrees/sessions that never reached the master branch | Multi-worktree projects, at session start or weekly |

---

## Installation

All scripts require Python 3.9 or newer. `abbreviations_extract.py` and `bibliography_check.py` have dependencies listed in `requirements.txt`. `cross_session_audit.py` uses only the Python standard library.

### On Linux / macOS

```bash
# From the project root:
pip3 install -r requirements.txt

# Make the shell scripts executable (one-time):
chmod +x scripts/*.sh
```

If `pdftotext` is available (optional fallback for `extract_styleguide.sh`):

- **Linux (Debian/Ubuntu):** `sudo apt install poppler-utils`
- **macOS:** `brew install poppler`

### On Windows

```powershell
# From the project root:
py -m pip install -r requirements.txt
```

**Shell scripts on Windows:** the two `.sh` scripts run under Git Bash (included with Git for Windows). If Git Bash is not installed, download Git for Windows and select the "Use Git Bash" option during installation. PowerShell alone cannot run `.sh` files directly.

**Note on `zip` on Windows:** Git Bash ships with `unzip` but NOT with `zip`. This is no longer a problem: `docx_postprocess.sh` only needs `unzip` plus Python 3 (`python3`, `python` or `py` on PATH) — re-zipping is done with Python's `zipfile` module, so `zip` itself is never invoked.

---

## Usage

### `extract_styleguide.sh`

Extracts text from institutional guideline PDFs so the style-resolver agent can read them.

```bash
# Flat structure:
./scripts/extract_styleguide.sh workspace/sources/_guidelines/

# Long-form:
./scripts/extract_styleguide.sh guidelines/

# Multi-project:
./scripts/extract_styleguide.sh 00_Shared_Materials/guidelines/

# Custom output directory:
./scripts/extract_styleguide.sh guidelines/ my_output/
```

What it does:

1. Scans the directory recursively for `.pdf` files (case-insensitive, so `.PDF` is matched the same way on every platform)
2. For each file, detects whether it is a real PDF or a ZIP archive disguised as `.pdf` (some institutional portals do this)
3. Real PDFs: extracts text via `pypdf` (preferred) or `pdftotext` (fallback)
4. Disguised ZIPs: safely extracts contained `.txt` files and text from contained PDFs (path-traversal attacks are blocked, and archives that would unpack to more than 512 MiB or 10,000 entries are refused)
5. Writes one `.txt` file per input into the output directory; if flattening two different input paths would produce the same output filename, a numeric suffix is added instead of silently overwriting one of them

After running, invoke the style-resolver agent in Claude Code:

```
Please invoke the style-resolver agent. Read the extracted texts in 
_styleguide_rawtext/ and produce styleguide.md.
```

### `abbreviations_extract.py`

Derives the list of abbreviations from a completed DOCX.

```bash
python3 scripts/abbreviations_extract.py workspace/output/document.docx

# Or from long-form submission:
python3 scripts/abbreviations_extract.py 08_Formal_Review/submissions/v_final_2026-09-01.docx

python3 scripts/abbreviations_extract.py --help
```

What it does:

1. Reads the text of body paragraphs, tables (including nested), header/footer paragraphs, and footnotes/endnotes (footnotes and endnotes are read via their raw XML, since python-docx does not expose them as a typed part)
2. Extracts candidate abbreviations:
   - All-caps sequences, 2-8 characters, digits allowed alongside at least one letter (`ABC`, `EU`, `NATO`, `ÖPNV`, `B2B`, `CO2`, `5G`, `BENELUX`)
   - Dotted forms (`U.S.A.`, `A.B.C`) — normalized to their letters (`USA`, `ABC`)
   - Mixed-case forms, 3-8 letters, with at least two capitals in any position (`GmbH`, `BaFin`, `AfD`, `mRNA`; CamelCase names like `LinkedIn` are reported too) — note that 2-character mixed-case forms like `pH` are not matched
3. Filters out common abbreviations (`e.g.`, `i.e.`, `USA`, etc.)
4. Prints the remaining project-specific list

Use the output to cross-check the document's existing list of abbreviations. Add missing entries, remove unused ones. The common-abbreviations filter removes dots on both sides before comparing, so dotted forms like `U.S.A.` are correctly recognized as `USA` and filtered. The comparison is case-sensitive, so acronyms such as `MS`, `NO` or `CO` are not hidden by the entries `Ms`, `no` or `Co`; only dotted entries also match their all-caps form, so a sentence-initial `Z.B.` or `E.G.` is filtered too (and so is the acronym `EG`).

Not extracted: acronyms longer than 8 characters, and lowercase-led mixed-case forms under 3 characters (`pH`). Not read outside footnotes/endnotes: text boxes, content controls (used by some citation managers and cover-page templates), unaccepted tracked insertions (accept all changes before running the script), simple fields, and tables inside headers/footers. If you use such abbreviations or elements, check for them manually — their absence from the tool's output is not proof they're unused.

### `bibliography_check.py`

Performs a bibliography minus-test by author surname: every surname cited in the text should appear among the authors in the bibliography, and the lead author of every bibliography entry should be cited in the text. Years are not compared (see the limitations below).

```bash
python3 scripts/bibliography_check.py workspace/output/document.docx
python3 scripts/bibliography_check.py --help
```

What it does:

1. Splits the document into body and bibliography (detects the section by header)
2. Extracts author surnames from in-text citations — supports parenthetical and narrative forms (also with a locator, `Müller (2020, S. 15)`), `et al.`/`u. a.`, joint authors (also `Müller/Schmidt`), hyphenated surnames, surnames starting with Ä/Ö/Ü, typographic apostrophes (`O’Brien`), year-suffix citations (`Schulz (2022a)`, `(Wagner, 2022a)`), name prefixes including `van der`/`van den`/`von`/`de la`/`ter`/`ten`, and the citation-lead words `vgl.`/`cf.`/`see`/`siehe`/`nach`/`zit. nach`
3. Extracts author surnames from bibliography entries, using the same surname-prefix and umlaut handling as the in-text extraction
4. Reports asymmetries in both directions

Exit code 0 = no asymmetries, 1 = asymmetries found, 2 = bibliography section not detected or another error occurred (e.g. bad arguments, file not found, a file that cannot be read as a DOCX).

The check uses heuristics and may produce false positives — and, in a few known edge cases, false negatives (a silent "no asymmetries" when there actually is one):

- **Surnames, not works**: the check compares author surnames only. Years are not compared, so a citation with a wrong year, or an uncited second work by an author who is cited elsewhere, is not reported.
- **Only body paragraphs are read**: citations in footnotes or endnotes, in tables, in content controls (Word's built-in citation tool, Citavi fields) and in unaccepted tracked insertions are not seen, so their sources are reported as "in bibliography but not cited". A bibliography placed in a table or a content control is not read either; the check then stops with "no bibliography section found". Accept tracked changes before running the check.
- **Everything after the bibliography heading is bibliography**: the first paragraph that matches a bibliography heading starts the bibliography, and every paragraph after it is treated as an entry, including an appendix or the declaration of authorship. Remove those parts first, or run the check on a copy that ends with the bibliography.
- **Multi-word institutional/corporate authors** (`Statistisches Bundesamt`, `World Health Organization`, ...) are not parsed from bibliography entries — the entry-head pattern expects a single-token name before the period, so a source cited as `(Statistisches Bundesamt, 2020)` is reported as "cited but not in bibliography" even when the entry is present. Conversely, an uncited multi-word institutional entry is never reported as "in bibliography but not cited" (a silent false negative). Single-word institutional authors (`WHO`, `UNESCO`) are handled correctly in both directions. Words on the script's stoplist of capitalized prose words (`GERMAN_NON_AUTHOR_CAPS`, e.g. `OECD`, `EU`, `UN`, `NATO`, `BGH`) count as citations only when a bibliography entry starts with that word, so a citation of such a body that is missing from the bibliography is not reported.
- **Unusual bibliography headings**: numbered (`7 Literaturverzeichnis`, `7.1 Literatur`) and punctuated (`References:`) headings are tolerated — the detection strips typed numbering and trailing punctuation before matching against `BIBLIOGRAPHY_HEADERS` (case-insensitive). Only a genuinely different heading word fails detection; if that happens, add your exact heading text to `BIBLIOGRAPHY_HEADERS` in the script.

Use the output as a starting point for manual verification, not as a final verdict.

### `docx_postprocess.sh`

Enables automatic hyphenation in a DOCX. python-docx does not expose this flag, so the script patches the XML directly.

```bash
./scripts/docx_postprocess.sh workspace/output/document.docx
```

What it does:

1. Unzips the DOCX into a temporary directory
2. Inserts `<w:autoHyphenation/>` into `word/settings.xml` if not already present, or rewrites it in place if it is present but explicitly disabled (`w:val="0"`/`"false"`/`"off"`)
3. Re-zips, keeping `[Content_Types].xml` as the first entry and stored (uncompressed) — not an OOXML requirement, but it maximizes compatibility with strict/streaming consumers
4. Replaces the original file only after the new archive was built successfully

Run once before the final export. Re-running is safe (the script detects if the flag is already set and enabled).

### `cross_session_audit.py`

Audits a multi-worktree repository for information that exists in a worktree or past session but never made it into the main worktree (the first entry of `git worktree list`, whatever branch it has checked out). Useful for projects that use `.claude/worktrees` (or any `git worktree`) to run agent sessions in parallel.

```bash
python3 scripts/cross_session_audit.py
python3 scripts/cross_session_audit.py --repo-root /path/to/repo
python3 scripts/cross_session_audit.py --report-file audit_report.md
```

What it does: after a summary, the report shows a **worktree overview** (all worktrees, their current branch/HEAD, and the number of uncommitted changes and of `_*.md`-style closing/briefing/TODO notes in each), followed by three layers, numbered as in the report:

1. **Layer 1 — `_*.md` files in a worktree but not in the main worktree** — for the `_*.md`-pattern notes, checks whether each one that exists in a linked worktree also exists in the main worktree; flags the ones that don't as potentially lost.
2. **Layer 2 — dangling refs in the main worktree** — scans the main worktree's own Markdown files for backticked references to other Markdown (`.md`) files (paths prefixed with a two-digit `NN_.../`, `scripts/...`, or `workspace/...`) and reports any that point to a file that doesn't exist. References to other file types (e.g. `scripts/tool.py`) are not checked.
3. **Layer 3 — uncommitted changes per worktree** — lists the `git status --porcelain` lines (including untracked files) of each worktree that has uncommitted changes.

Output goes to stdout by default; `--report-file PATH` additionally writes a Markdown report to that path.

Exit codes: `0` = no findings, `1` = findings reported (intended for CI/hooks), `2` = the audit could not run: `--repo-root` (default: the current directory) is not an existing directory inside a git working tree, `git` is not on PATH, a worktree could not be inspected (`git status` fails there, e.g. with "dubious ownership" or a corrupt index, or its directory cannot be read), or the `--report-file` could not be written (the report has already been printed to stdout in that case). The cause is printed as one `Error: ...` line on stderr.

Like the other checks, this is a heuristic aid, not a guarantee — it only catches the specific patterns described above (uncommitted changes, `_*.md` notes, and backticked cross-references in a recognized path format).

---

## Troubleshooting

**`python3: command not found`** — the Python utility scripts (`abbreviations_extract.py`, `bibliography_check.py`, `cross_session_audit.py`) are invoked directly with `python3` or `py`; on Windows, use `py` instead if `python3` isn't on PATH. On macOS before Monterey, you may need to install Python 3 via Homebrew. The shell scripts (`docx_postprocess.sh`, `extract_styleguide.sh`) handle this themselves: they probe for a *working* interpreter under `python3`, `python` and the Windows `py` launcher (this also catches the case where `python3` resolves to the dead Microsoft Store app-execution-alias stub on Windows) and print a clear error only if none works.

**`Error: python-docx not installed.`** (from `abbreviations_extract.py` and `bibliography_check.py`; the underlying import error is `ModuleNotFoundError: No module named 'docx'`) — install it: `pip install python-docx` (or `pip install -r requirements.txt`). If you installed `docx` instead, that is a different package: run `pip uninstall docx && pip install python-docx`.

**`Error: neither pypdf nor pdftotext available for PDF extraction.`** (from `extract_styleguide.sh`; the underlying import error is `ModuleNotFoundError: No module named 'pypdf'`) — install it: `pip install pypdf`. Alternatively, install `pdftotext` (poppler) as fallback.

**`UnicodeEncodeError: 'charmap'`** on Windows — your Python is older than 3.9. Upgrade Python.

**`bibliography_check.py` finds no bibliography section** — the script detects the section by common headers (Bibliography, References, Literaturverzeichnis, etc.), matched case-insensitively after stripping manually typed numbering and trailing punctuation (so `7 Literaturverzeichnis` and `References:` are recognized out of the box). If your document uses a genuinely different heading word, add its exact text to `BIBLIOGRAPHY_HEADERS` near the top of the script.

**`docx_postprocess.sh` breaks the document** — this should not happen; the script preserves OOXML structure. If it does, please report the case. The script's safety model: it works entirely in a temporary directory and only replaces your original file in the very last step, after the new archive has been rebuilt successfully. If the script fails at any earlier point, your original file is untouched at its original path — but the temporary directory itself is deleted on exit either way, so it is not a recovery location. If a *successful* run produces a broken file, restore from your own backup or version control (keep one before running any batch post-processing on a final export).

**Git Bash on Windows says `bash: pdftotext: command not found`** — that is fine if you have a working Python 3 with `pypdf` installed; `pdftotext` is only an optional fallback. If Python itself is unavailable but `pdftotext` is on PATH, `extract_styleguide.sh` runs in a pdftotext-only mode instead (text extraction still works; the disguised-ZIP handling described above under "What it does" does not, since that path requires Python). The script only fails if neither Python nor `pdftotext` is available.

---

## Contributing

All scripts are intentionally small and heuristic. If you add features, keep them:

- Cross-platform (Linux, macOS, Windows via Git Bash)
- Dependency-minimal (Python standard library + the two packages in `requirements.txt`)
- Safe against malicious inputs (see `extract_styleguide.sh` for ZipSlip handling)
