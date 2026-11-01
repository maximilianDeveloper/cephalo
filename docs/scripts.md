# Scripts

cephalo ships ten utility scripts in `scripts/`, and the cephalo guard, a Claude Code hook that setup installs (see [cephalo guard](#cephalo-guard)). The utility scripts are optional — the agents can guide a project without them — but each one automates a check or transformation that would otherwise take manual effort.

| Script | Purpose | When to run |
|--------|---------|-------------|
| `extract_styleguide.sh` | Convert institutional guideline PDFs to plain text for the style-resolver | Once per project during setup |
| `verbatim_check.py` | Count the verbatim word runs a chapter shares with its sources, rated by the plagiarism thresholds, and with `--chapters` those it shares with the other chapters; with `--words`, the chapter's word count for the page budget | Phase A, before each chapter verification (bachelor and master workflows: step A.4) |
| `state_check.py` | List the state file's Current state, Chapter status and open items in full, with the chapters' word counts, and report its lines over 500 characters | Flat projects, at the end of every chat |
| `abbreviations_extract.py` | Derive the list of abbreviations from a finished DOCX | Phase B, final stages |
| `bibliography_check.py` | Minus-test by author surname: every cited author is in the bibliography, every entry's lead author is cited | Phase B, final stages |
| `repeated_citations.py` | List every repeated citation (a source cited again right after its previous citation) with its chapter file and line, for the check of `in_text.repeated_citation` | Each full format check (Phase B; seminar: F.1; presentation: step 3), by the format-verifier |
| `build_reference_docx.py` | Build Pandoc's reference document (layout of the exported DOCX) from the styleguide's values | Phase B, before the first export and after a layout finding |
| `docx_postprocess.sh` | Enable automatic hyphenation in a DOCX (Pandoc and python-docx don't set this) | Phase B, right after every export (orchestrator), only if `document.hyphenation` is automatic |
| `docx_pagination.py` | Number the front matter of an exported DOCX unlike the main text: Roman numerals, counted but not shown, or not counted, and a main text from 1 or continuing the count; and the back matter (the reference list, an appendix) unlike the main text | Phase B, right after every export (orchestrator), only if `pagination.front_matter`, `pagination.main_text` or `pagination.back_matter` asks for it |
| `cross_session_audit.py` | Cross-worktree audit: surfaces notes and changes from other worktrees/sessions that never reached the main worktree | Multi-worktree projects, at session start or weekly |

---

## Installation

All scripts require Python 3.9 or newer. `abbreviations_extract.py`, `bibliography_check.py`, `build_reference_docx.py`, `docx_pagination.py`, `verbatim_check.py` and `extract_styleguide.sh` have dependencies listed in `requirements.txt`, and so does `state_check.py` for the word count of a Word chapter (`python-docx`, and `pypdf` with its `[crypto]` extra, which installs `cryptography` for AES-encrypted PDFs). `cross_session_audit.py` uses only the Python standard library, and so does `repeated_citations.py`, which needs `verbatim_check.py` beside it.

### On Linux / macOS

```bash
# From the project root:
pip3 install -r requirements.txt

# Make the shell scripts executable (one-time):
chmod +x scripts/*.sh
```

If pip stops with `error: externally-managed-environment` (Debian 12, Ubuntu 23.04 and later, Homebrew Python), install into a virtual environment in the project root instead:

```bash
python3 -m venv .venv        # Debian/Ubuntu: if this fails, first run: sudo apt install python3-venv
. .venv/bin/activate
pip install -r requirements.txt
```

Activate it (`. .venv/bin/activate`) in every terminal where you run the scripts, and before you start Claude Code there: the agents call `python3` from that shell. `.venv/` is git-ignored, and setup does not copy it into a `--target` project.

If `pdftotext` is available (optional fallback for `extract_styleguide.sh`):

- **Linux (Debian/Ubuntu):** `sudo apt install poppler-utils`
- **macOS:** `brew install poppler`

### On Windows

```powershell
# From the project root:
py -m pip install -r requirements.txt
```

**Commands on Windows:** the examples in this file and in the agent definitions write `python3`; on Windows, run them with `py` in its place, in Git Bash as in PowerShell. Save a command's output to a file in Git Bash: in Windows PowerShell 5.1, `>` writes the file in UTF-16.

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

# Multi-project (from the multi-project root, where scripts/ is):
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
6. Lists `.txt` files in the output directory that this run did not write (left over from an earlier run, e.g. for a guideline since replaced or removed). They are not deleted, but the style-resolver would read them too, so remove them first

After running, invoke the style-resolver agent in Claude Code:

```
Please invoke the style-resolver agent. Read the extracted texts in 
_styleguide_rawtext/ and produce styleguide.md.
```

Multi-project: Claude Code is opened on a sub-project, one level below the folder the script wrote to, so name `../_styleguide_rawtext/` in the prompt.

### `verbatim_check.py`

Counts the verbatim word runs a chapter shares with its sources: the count behind verification step 8 of the source-verifier, rated by the thresholds of `checklists/plagiarism_protection.md` (5–7 words 🟡, 8–14 ⚠️, 15 or more ❌); with `--chapters`, also those it shares with the other chapters, the count behind the self-plagiarism check between chapters (`checklists/consistency.md`, A.2). Neither the writer-agent nor the source-verifier can count reliably by eye, and neither has a shell, so the orchestrator runs the script before each chapter verification and hands its output, saved with `> <file> 2>&1`, to the source-verifier. In the seminar and presentation workflows, which have no orchestrator, you have Claude run it or run it yourself; in Windows PowerShell, do not save its output with `>`, which writes UTF-16 (or, with some settings, UTF-8 with a byte order mark).

```bash
# Flat structure: the chapter against the extracts and source files
python3 scripts/verbatim_check.py workspace/output/chapters/ch_2_basics.md workspace/sources/

# ... and against the other chapter files in its folder (self-plagiarism, checklists/consistency.md A.2)
python3 scripts/verbatim_check.py workspace/output/chapters/ch_2_basics.md workspace/sources/ --chapters workspace/output/chapters/

# Seminar paper: the quotes are in the source registry of the state file
python3 scripts/verbatim_check.py workspace/output/chapters/ch_2_basics.md workspace/sources/ workspace/state.md --chapters workspace/output/chapters/

# Long-form, the other chapters by name (in a multi-project sub-project: ../scripts/verbatim_check.py):
python3 scripts/verbatim_check.py 03_Theory_chapters/chapter_3_theory.md 02_Literature/extracts/ 02_Literature/sources/ --chapters 03_Theory_chapters/chapter_2_basics.md

# A Word document, against the extracts folder and a single PDF:
python3 scripts/verbatim_check.py workspace/output/document.docx workspace/sources/extracts/ workspace/sources/smith_2020.pdf

# The chapter's word count alone, for the page budget (no sources needed):
python3 scripts/verbatim_check.py --words workspace/output/chapters/ch_2_basics.md
```

What it does:

1. Reads the chapter (`.md`, `.txt` or `.docx`) and leaves out what is a marked direct quote: a quotation of five or more words in quotation marks („…“, “…”, "…", ‚…‘, ‘…’, '…', »…«, «…»; an apostrophe as in "city’s" does not end one, and an apostrophe before a digit or after a letter, as in "'90s" or "U.S.'s", opens none), Markdown block quotes (`>`, also lines continuing one without `>`) and Word paragraphs in a quote style, including Pandoc's "Block Text" and LibreOffice's "Quotations". The words of a shorter quotation, such as a technical term in quotation marks, keep a run going, so that the term does not cut a copied sentence into pieces, but are not counted in its length: the report gives them as `(and 3 in quotation marks)`. In Markdown it also skips the YAML front matter, footnote marks and HTML comments. The chapter's bibliography is not counted, since its titles would match the sources: the section from a heading such as "Literaturverzeichnis", "Literatur", "References" or "Bibliography" to the next heading of the same level, if every entry in it has a year, as in a reference list. A body section of that name ("2.1 Literatur") with prose, an appendix after the bibliography and footnotes still count; the report names the lines or paragraphs left out
2. Reads the sources, files or folders searched recursively (folders named `_guidelines` and `verification` inside them are skipped: guidelines are not sources, and the saved reports quote the chapter): the quotes of the research-agent's extracts (`.md`: the `**Original:**` field, quoted text in the `**Secondary citation?**` field, and `- p. 42: "…"` lines), with their page (also from a page bullet such as `- p. 87 ❓`, ❓ included) and quote ID, a quote with a `[…]` omission as separate parts; a Markdown table with an "Original quote" column, such as the source registry in `workspace/state.md` of a seminar paper; the text layer of PDFs, without running headers and footers (also those alternating between left and right pages, and in a short excerpt a head that carries the page number) and page numbers; plain-text files (UTF-8, UTF-16 with byte order mark, or Windows-1252). What it cannot read is listed under "Not checked": a path that does not exist, Word, EPUB, HTML or image files among the sources (other files, such as a `.bib` or the assets folder of a saved web page, and hidden files are passed over), a scan, the pages without text of a PDF of which half or more of the pages are scans, a ZIP archive named `.pdf`, and all PDFs while `pypdf` is not installed. An `.md` file in a folder that has no extract fields (a `handover.md`, a `README.md`) is passed over
3. Finds every run of five or more consecutive words the chapter shares with a source, ignoring letter case and punctuation, also across sentence boundaries and across citations (Pandoc citekeys such as `[@key, S. 5]`, and author-year citations in parentheses such as `(Keller 2018, S. 44)` or `(ebd.)`, are skipped in the chapter and in the sources; a citation that holds only a page, such as `(S. 44)`, is not skipped and cuts a run), and reports the longest run at each place with its rating, the line (Markdown) or paragraph (Word), and where it occurs: `Smith_2020.md Q4 (p. 45)` for an extract quote, `smith_2020.pdf (PDF page 3)` for a PDF. A source that has only part of the run is named too, with the number of words it shares (`Smith_2020.md Q4 (p. 45, 9 of these words)`), so that the quote ID is not lost when the PDF has a longer run. A run's length is counted in words as written: a hyphenated compound (`long-term`) or a word with an apostrophe (`city’s`) counts as one, though its parts are matched one by one, and a dash between words (`surroundings—as`, also a typed `---`) separates them; step 1 counts the five words of a quotation the same way
4. Looks up each marked direct quote of five or more words (the parts between `[…]` or `(…)` omissions) in the sources and lists one that is not found verbatim for a check by hand, since a changed word in a quotation is an error too
5. With `--chapters` and the paths after it, after the sources, compares the chapter with the other chapters as well, for the self-plagiarism check between chapters (`checklists/consistency.md`, A.2): chapter files, or the `.md` and `.docx` files directly in a folder (not those in subfolders, no hidden file), the chapter itself left out. Each is read as the chapter is (step 1), so that the bibliography and raw blocks take no part, and a run is found and counted as in step 3, across citations and punctuation; quotations and block quotes are compared only with text outside quotation marks on the other side (below). The section "Runs shared with other chapters" at the end of the report lists each run of five or more words the chapter shares with another chapter, with that chapter's file and line or paragraph (`in ch_2_basics.md (line 18)`), unless it lies wholly within a run from the sources listed above, which step 8 of the source-verifier rates already; a longer one says how many of its words that run has. It also lists each direct quote of the chapter that the sources do not have but another chapter has outside quotation marks (`quotation of 9 words, line 12: …`): a quotation of that chapter, such as the research question quoted again; and the other way round, a run of the chapter's own text that another chapter has in quotation marks (`in quotation marks there`). With `--chapters` but no other chapter to compare, the section says `no other chapter compared`. The section rates nothing: whether a run is an overlap or an intended repetition (a definition repeated, a name, a title, a technical term of the sources) is the source-verifier's call. The header names the other chapters compared (`Other chapters: 2 (…)`); without `--chapters` the report is as before

Exit code 0 = no run of 8 or more words from the sources, 1 = at least one run of 8 or more words from the sources (⚠️ or ❌), 2 = bad arguments, a chapter that cannot be read or holds no text (one error line), a source or another chapter (`--chapters`) that cannot be read (corrupt, or encrypted with a password; the report is printed all the same, with the file under "Could not be read"), or no source text at all to compare against. Exit code 1 is a finished report, not a failure. Direct quotes not found, 🟡 runs and runs shared with other chapters do not change the exit code; another chapter's path that does not exist is listed under "Not checked".

The report's header also gives the chapter's word count, `Words: N`, for the page budget, and `--words <chapter>` prints only that line, without sources (exit code 0, or 2 for a chapter it cannot read). It counts the words as written in the text the check reads, each stretch between whitespace or dashes that holds a letter or digit (so a hyphenated compound is one word): headings, block quotes and quotations count, and in Markdown footnotes, but not the YAML front matter, HTML comments, raw blocks for the export (`` ```{=openxml} ``, such as the bookmark above the reference list; text in a Word raw block's `<w:t>` elements, which the export writes into the document, is still compared with the sources, a paragraph at a time, as a quote in Pandoc's block-quote style (`BlockText`; a quote style a `--base` template adds, such as `Zitat`, counts as plain text) and as an entry of the bibliography if it stands in it), footnote marks or the bibliography. If the line says "no bibliography recognized", a reference list in the file is counted: one under a heading the script does not know, or with an entry without a year (step 1). Pandoc citekeys (`[@key, S. 5]`, the whole bracket) are not counted either, since Pandoc writes the citation only at the export: a chapter with citekeys counts a few words fewer per citation than its export, while author-year citations written into the text count. A Word chapter counts its body paragraphs only (see "Word chapters" below).

The word index is built from the chapter; the source words are held in memory once. A check against a million source words takes about 50 MB when they are spread over several files, up to about 110 MB in a single text file, and a few seconds, plus the time `pypdf` needs to read the PDFs.

Limitations:

- **Only what is given is checked**: a source that is not among the arguments, or an extract quote that is missing, cannot be matched. What is listed under "Not checked" (the script unpacks nothing) is covered only through the quotes in its extract.
- **Citations it does not recognize** (a footnote-style citation written into the running text, or a parenthesis without a year) break a run like any word the source does not have, so a run around one is reported in two parts; a parenthesis with a year that is not a citation, such as `(Stand 2020)`, is skipped as if it were one.
- **Verbatim only**: a paraphrase that swaps every few words for a synonym, or a translation, is not found. That is still the source-verifier's call (step 8, and step 7 on overinterpretation), and so is a paraphrase of another chapter, or a quotation that two chapters both set in quotation marks.
- **PDF pages are the viewer's page index**: the printed page number may differ; extract quotes carry the printed one.
- **Text extraction**: a word hyphenated at a line or page break in a PDF (also with a soft hyphen, and across a running header or footer) is joined when the chapter has the joined word (`Verdun-` + `stung`); otherwise the hyphen is kept as that of a compound (`long-` + `term`, `Stadt-` + `und`). PDFs with unusual encodings can yield garbled text, which then matches nothing.
- **Word chapters**: only the body paragraphs are read, with their tracked changes accepted (inserted text counts, deleted text does not, a deleted paragraph mark joins the paragraph to the next one, and a page break keeps the words on either side apart; ruby text above a word is left out, and a symbol from a symbol font counts as a space); text in tables, footnotes, text boxes and content controls (a block of paragraphs inside a content control, as some templates use for placeholders) is not checked. The report numbers the paragraphs as the file holds them with its tracked changes shown (in Word: All Markup): deleted and empty paragraphs count, paragraphs in tables do not, and joined paragraphs have the number of the one where the text starts. Export the chapter from Markdown, or check the Markdown file instead.
- **A direct quote not found** may also mean that its source is missing from the arguments, or that the quotation keeps an omission without marking it; check those by hand.

### `state_check.py`

Lists, in full, what the closing check of a chat compares in the state file of a flat project, `workspace/state.md`: a Grep result leaves out every line over about 500 characters, and a Read in parts leaves out what lies between them. It only reads. The orchestrator, or in the seminar and presentation workflows Claude in the main chat, runs it at the end of every chat (`orchestrator.md`, "Chat closure ritual", item 1) and in the closing step.

```bash
# The state file and the folder of the chapter files
python3 scripts/state_check.py workspace/state.md workspace/output/chapters/

# Or single chapter files (.md, .txt or .docx)
python3 scripts/state_check.py workspace/state.md workspace/output/chapters/ch_2_basics.md
```

The report starts with a summary line: the open and ticked items, the chapter files counted, and the lines over 500 characters with their numbers. Then it gives, each with its line number:
- every line of "Current state";
- every line of "Chapter status", its table and anything else in it;
- every open item (`- [ ] …`, in any section) with its section, and the number of ticked ones;
- the word count of each chapter file named, as `verbatim_check.py --words` counts it (a folder: its `.md` and `.docx` files, not those in subfolders and no hidden file). A chapter it cannot count (a Word file without `python-docx`, or one that is broken) and an argument that is no chapter or does not exist are listed with the reason, and the report goes on;
- the lines of "Current state" and "Chapter status" over 500 characters, which "State file format" in `orchestrator.md` keeps short.

A section runs from its heading, at any level and with more words after its name (`### Chapter status (2026-10-28)`), to the next heading. The source registry, the decision log and the pre-check result are not listed: their rows may be long. Whether an open item is resolved, and whether the sections agree, is for whoever reads the report to judge; the script compares no wording.

Exit code 0 = no line of "Current state" or "Chapter status" over 500 characters, 1 = at least one (shorten it and run the script again), 2 = bad arguments, a state file that cannot be read, or one without a "Current state" or "Chapter status" heading (an `Error:` line on stderr). A chapter that cannot be counted does not change the exit code. The long-form status file `00_Status.md` has another structure and is not read.

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
   - All-caps sequences, 2-8 characters, digits allowed alongside at least one letter (`ABC`, `EU`, `NATO`, `ÖPNV`, `B2B`, `CO2` — also written with a subscript digit, `CO₂` —, `5G`, `BENELUX`)
   - Dotted forms (`U.S.A.`, `A.B.C`) — normalized to their letters (`USA`, `ABC`)
   - Mixed-case forms, 3-8 letters, with at least two capitals in any position (`GmbH`, `BaFin`, `AfD`, `mRNA`; CamelCase names like `LinkedIn` are reported too) — note that 2-character mixed-case forms like `pH` are not matched
3. Filters out common abbreviations (`e.g.`, `i.e.`, `USA`, etc.)
4. Prints the remaining project-specific list

Use the output to cross-check the document's existing list of abbreviations. Add missing entries, remove unused ones. The script reads the whole document, including the list of abbreviations and the bibliography: run it on a copy of the DOCX without the list of abbreviations, or every listed entry is found in the list itself and counts as used; abbreviations that occur only in the bibliography (journal or publisher names) are listed too. The common-abbreviations filter removes dots on both sides before comparing, so dotted forms like `U.S.A.` are correctly recognized as `USA` and filtered. The comparison is case-sensitive, so acronyms such as `MS`, `NO` or `CO` are not hidden by the entries `Ms`, `no` or `Co`; only dotted entries also match their all-caps form, so a sentence-initial `Z.B.` or `E.G.` is filtered too (and so are the acronyms `EG`, `IE`, `ZB`, `DH` and `UA`).

Not extracted: acronyms longer than 8 characters, mixed-case forms with digits (`IPv6`, `HbA1c`, `CO2e`), and lowercase-led mixed-case forms under 3 characters (`pH`). Not read outside footnotes/endnotes: text boxes, content controls (used by some citation managers and cover-page templates), unaccepted tracked insertions (accept all changes before running the script), simple fields, and tables inside headers/footers. If you use such abbreviations or elements, check for them manually — their absence from the tool's output is not proof they're unused.

### `bibliography_check.py`

Performs a bibliography minus-test by author surname: every surname cited in the text should appear among the authors in the bibliography, and the lead author of every bibliography entry should be cited in the text. Years are not compared (see the limitations below).

```bash
python3 scripts/bibliography_check.py workspace/output/document.docx
python3 scripts/bibliography_check.py --help
```

What it does:

1. Splits the document into body and bibliography (detects the section by header)
2. Extracts author surnames from in-text citations — supports parenthetical and narrative forms (also with a page locator, `Müller (2020, S. 15)`, `Müller (2020: 15)`, `Müller (2020: 15 f.)`), `et al.`/`u. a.`, joint authors, also three or more (`Dawson, Ellis und Fowler (2018)`, `(Müller/Schmidt/Weber 2019)`: a listed name counts as cited when an entry starts with it; a list in prose reads the same way, so `(März, April und Mai 2020)` counts an entry `Mai, M. (2018)` as cited, and a missing entry for such a citation may go unreported), hyphenated surnames, surnames starting with Ä/Ö/Ü, typographic apostrophes (`O’Brien`), a German genitive (`Webers (1922) Begriff` counts as `Weber` when only that name is listed and every mention of `Webers` has this form), year-suffix citations (`Schulz (2022a)`, `(Wagner, 2022a)`), lowercase name prefixes including `van der`/`van den`/`von`/`de la`/`ter`/`ten` (also the German abbreviation `v.`/`v. d.` right before the surname: `(v. Rosenstiel 2007)` counts for an entry `von Rosenstiel, L.`, while `(Roe v. Wade, 1973)` is not read as a citation), and the citation-lead words `vgl.`/`cf.`/`see`/`siehe`/`nach`/`zit. nach` (`zit. nach` also after the original of a secondary citation: `(Weber 1922, zit. nach Keller 2018)`, see step 4), also followed by `auch`/`also`/`z. B.`/`e.g.` (`(vgl. auch Müller 2020)`; such a name counts only if the bibliography lists it and at most a page locator follows the year, since the same pattern opens prose such as `(see also Horizon 2020)`)
3. Extracts author surnames from bibliography entries, using the same surname-prefix and umlaut handling as the in-text extraction. An entry may also start with a capitalized particle (`De Vries, R. (2018)`, `Van der Berg, J.`; not `Das`, the German article): it counts as cited when its full name appears anywhere in the text, since a parenthetical citation with a capitalized particle and no comma is not parsed (in parentheses such a word opens prose too often: `(Von Anfang 2020 bis ...)`, `(La Liga 2018/19)`), so a missing entry for `(De Vries 2020)` is not reported; `(De Vries, 2020)` and `De Vries (2020)` are read as `Vries`. co-authors are read after `&`/`and`/`und`, as `Surname, I.` pairs, and after `/` or `;` also with full given names (`Müller, Hans/Schmidt, Karl (2019)`) when they continue the list of names that starts the entry (editors after `in`, places and title words are not read). An entry `Ders. (2021)` or `Dies. (2020)` stands for the author of the entry above and adds no name
4. Reports asymmetries in both directions. The original of a secondary citation (`(Weber 1922, S. 31, zitiert nach Keller 2018)`; also after `zit. nach`, `zit. n.`, `as cited in`, `cited in`, `quoted in`) needs no entry, since many guidelines list only the source actually read: if it has none, it is listed separately and does not count as a finding. A name that is also cited the usual way elsewhere needs its entry as usual

Exit code 0 = no asymmetries, 1 = asymmetries found, 2 = bibliography section not detected, no bibliography entry could be read (the check supports author-year styles only, not numeric styles such as IEEE), or another error occurred (e.g. bad arguments, file not found, a file that cannot be read as a DOCX).

The check uses heuristics and may produce false positives — and, in a few known edge cases, false negatives (a silent "no asymmetries" when there actually is one):

- **Surnames, not works**: the check compares author surnames only. Years are not compared, so a citation with a wrong year, or an uncited second work by an author who is cited elsewhere, is not reported. Name particles are not part of the compared surname either: `De Witte` and `Witte` count as the same name, so a citation of one can hide a missing entry of the other.
- **Only body paragraphs are read**: citations in footnotes or endnotes, in tables, in text boxes (such as a figure's source line), in simple fields, in content controls (Word's built-in citation tool, Citavi fields) and in unaccepted tracked insertions are not seen, so their sources are reported as "in bibliography but not cited". A bibliography placed in a table or a content control is not read either; the check then stops with "no bibliography section found". Accept tracked changes before running the check.
- **Where the bibliography ends depends on heading styles**: if several paragraphs match a bibliography heading, the highest-level heading starts the bibliography (the first on a tie; a paragraph typed as a heading counts as Heading 1 but yields to a styled Heading 1, so a body paragraph that reads just `Literatur` does not start it; for the same reason, a typed `Literaturverzeichnis` followed by a styled `Quellenverzeichnis` chapter is read from the `Quellenverzeichnis` on, so style both headings the same way). It ends at the next top-level heading (Word style Heading 1, or a style based on it) that is not itself a bibliography heading, such as an appendix or the declaration of authorship; what follows is read as body text again. A bibliography heading in the style Title ends only at the next Title: an appendix or declaration styled Heading 1 after it is then read as part of the bibliography (a signature line such as `Ort, Datum` is reported as an uncited author), so style the bibliography heading Heading 1. Sub-headings inside the bibliography (not read as entries) and a separate `Quellenverzeichnis` chapter stay part of it. If the document uses no heading styles (headings typed as bold body text), every paragraph after the bibliography heading is treated as an entry: then remove an appendix or declaration first, or run the check on a copy that ends with the bibliography.
- **Citations without a year** (`o. J.`, `n.d.`, `in press`, `im Druck`) are not recognized in the text: every in-text pattern expects a four-digit year. Their bibliography entries are therefore reported as "in bibliography but not cited"; check those names by hand.
- **Multi-word institutional/corporate authors** (`Statistisches Bundesamt`, `World Health Organization`, ...) are not parsed from bibliography entries — the entry-head pattern expects a single-token name before the period, so a source cited as `(Statistisches Bundesamt, 2020)` is reported as "cited but not in bibliography" even when the entry is present. Conversely, an uncited multi-word institutional entry is never reported as "in bibliography but not cited" (a silent false negative). Single-word institutional authors (`WHO`, `UNESCO`) are handled in both directions when the entry has a period after the name (`WHO. (2019). ...`); with the form `WHO (2019): ...` a citation is reported as "cited but not in bibliography", and an uncited entry is not reported. Words on the script's stoplist of capitalized prose words (`GERMAN_NON_AUTHOR_CAPS`, e.g. `OECD`, `EU`, `UN`, `NATO`, `BGH`) count in narrative form (`Die OECD (2019)`) only when a bibliography entry starts with that word, so a narrative citation of such a body that is missing from the bibliography is not reported; in parentheses (`(OECD, 2019)`) an all-caps acronym always counts.
- **Surnames starting with other letters**: a surname must start with A–Z or Ä/Ö/Ü to be read from a bibliography entry or a narrative citation (letters of any script are fine after that), so `Łukasiewicz`, `Øberg` or `Çelik` can be reported as "cited but not in bibliography" or not be checked at all.
- **Unusual bibliography headings**: numbered (`7 Literaturverzeichnis`, `7.1 Literatur`) and punctuated (`References:`) headings are tolerated — the detection strips typed decimal numbering and trailing punctuation before matching against `BIBLIOGRAPHY_HEADERS` (case-insensitive). A genuinely different heading word, or a typed letter or Roman number (`A. Literaturverzeichnis`, `IV. Literaturverzeichnis`), fails detection; if that happens, add your exact heading text to `BIBLIOGRAPHY_HEADERS` in the script.

Use the output as a starting point for manual verification, not as a final verdict.

### `repeated_citations.py`

Lists the repeated citations of a work for the format check of `in_text.repeated_citation`: each pair of a source cited again right after its previous citation, as one line with the chapter file and line of the repeated citation and the form the text gives it. The format-verifier runs it in every full format check and copies its lines into its report, where it checks each against the styleguide's value (`format-verifier.md`, "In-text citations"); the script judges no form. It reads the chapter files the export was made from, not the DOCX: a finding is fixed there.

```bash
# The chapter files the export was made from, in its order (a seminar paper: its numbered chapter folder)
python3 scripts/repeated_citations.py workspace/output/chapters/ch_1_intro.md workspace/output/chapters/ch_2_body.md workspace/output/chapters/ch_3_conclusion.md

# Long-form: the files the export lists, in its order (in a multi-project sub-project: ../scripts/repeated_citations.py)
python3 scripts/repeated_citations.py 07_Introduction/introduction.md 03_Theory_chapters/chapter_2_basics.md 06_Discussion_Conclusion/conclusion.md 08_Formal_Review/bibliography.md
```

What it does:

1. Reads the files one after the other, in the order given; a folder gives its `.md` files (not those in subfolders, and no hidden file) in the order of their names, with numbers compared as numbers (`ch_2_…` before `ch_10_…`). A long-form phase folder also holds `handover.md` and `README.md`: name the chapter files there. It leaves out the YAML front matter, HTML comments, code and raw blocks, and the reference list, found as `verbatim_check.py` finds it: the section under a heading such as "Literaturverzeichnis" or "References" in which every entry has a year (in a seminar paper the last section of the conclusion; long-form, `bibliography.md`, which may be given or left out)
2. Reads every citation, in reading order, a footnote's at its mark: author and year in parentheses (`(Keller 2018, S. 44)`, `(vgl. Keller/Weber 2018, S.\ 5)`, `(Keller & Weber, 2018, p. 5)`, `(Keller et al. 2018)`, `(Keller u. a. 2018)`, `(Keller 2018a)`, `(Keller 2018, 2020)`, `(Keller o. J.)`), several sources separated by `;`, and a secondary citation (`(Weber 1922, S. 31, zit. nach Keller 2018, S. 5)`, also after `zitiert nach`, `cited in` or `quoted in`), which names both; author and year in the sentence (`Keller (2018, S. 44)`, `Keller und Weber (2018)`); `ebd.`, `ebenda`, `ibid.` or `ibidem`, and a page alone in parentheses (`(S. 45)`), which name the source of the citation just before, the source named last where that one names several; Pandoc citekeys (`[@keller2018, S. 5]`, `@keller2018 [S. 5]`, a secondary citation's original as plain text in the prefix); and in a footnote, an inline note or a source line below a table or figure (`Quelle: Keller 2018, S. 5`) a citation without parentheses too (`Vgl. Keller 2018, S. 5.`, `Ebd., S. 6.`). A source is its surnames and year (`Keller/Weber 2018` and `Keller und Weber (2018)` are one source, `Keller 2018a` and `Keller 2018b` two), or its citekey
3. Lists each pair: a source that a citation names and the citation just before it names too, also as one of several sources or in a secondary citation, and across paragraphs and chapter files, since the rule counts a repeated citation "on the same page or another"; whether a new chapter starts the count anew is for the styleguide's value to say (`in_text.repeated_citation`), and the format-verifier rates the pair against it. The line gives the chapter file and line of the repeated citation, the source and the citation as written (``- ch_2_body.md:14 — Keller 2018, cited again as `(ebd., S.\ 5)` ``), for a citation of several sources with its part (`` `Weber 2019, S. 3` in `(…)` ``), and says when the previous citation names several sources, is a secondary citation or stands in another file, and when the citation stands in a footnote. Two pairs in one paragraph are two lines with the same line number

Above the pairs, the report names the files in the order read (compare it with the export's), counts the citations, names the reference list it left out and lists the sources with the number of their citations; below them, each `ebd.`, `ibid.` or page alone with no citation before it.

Exit code 0 = listed, also when there is no pair; 2 = bad arguments, a path that does not exist, a file that cannot be read or is no `.md` or `.txt` file (for a Word file, give the Markdown chapter files it was exported from), or a folder without `.md` files (an `Error:` line on stderr). No exit code means a finding: the script judges no form.

Limitations:

- **Whether a pair follows the rule** is not judged: the format-verifier checks each line against `in_text.repeated_citation`, also where the previous citation names several sources or stands in another chapter, which `styleguide.md` may leave open (then it is a ❓).
- **With citekeys**, a chapter file shows the citekey, and the export the form the CSL style gives a repeated citation: the format check reads that form in the DOCX.
- **Citations it does not read**: a citation without parentheses in the running text (only footnotes and source lines are read that way), one without a year (`(Keller, S. 5)`), `a. a. O.` and `op. cit.`; a citation it does not see between two others leaves a pair across it that is none. A source written in two ways is two sources (`Keller et al. 2018` and `Keller/Weber/Schulz 2018`, or a German genitive, `Kellers (2018)`), and an author of several words is read by the last one (`Statistisches Bundesamt 2020` as `Bundesamt 2020`).
- **Parentheses that are no citation**: a capitalized word before a year (`(Mai 2020)`, `(Zensus 2011)`) is read as a citation, except a few words such as `Stand`, `Jahr`, `Kapitel`, `Tabelle` and the months that are not also surnames; such a source shows in the list of sources. A page alone in parentheses, such as a cross-reference `(S. 12)`, is read as a citation of the source before it (one after `siehe` or `see` is not).
- **Name particles** are not part of the source: `van der Berg 2015` and `Berg 2015` count as one, as in `bibliography_check.py`.

### `build_reference_docx.py`

Builds the reference document from which Pandoc takes the layout of an exported DOCX (`pandoc --reference-doc`, see `docs/reference_management.md`, "The reference document"): fonts, sizes, line spacing, paragraph spacing and alignment, headings, block quotes, footnotes, the reference list's hanging indent, link colour, the weight of the table of contents levels, page size, margins, the page number and the title page's numbering. The orchestrator reads the values in `styleguide.md` and passes them as options; what is not given stays as in Pandoc's own reference document.

```bash
python3 scripts/build_reference_docx.py 08_Formal_Review/reference.docx \
    --font Arial --size 11 --line-spacing 1.5 --align justify --space-after 6 \
    --heading-sizes 14,12,11 --heading-bold yes --heading-color 000000 \
    --quote-indent 1 --quote-size 10 --quote-line-spacing 1 \
    --footnote-size 10 --footnote-line-spacing 1 --bib-hanging 1 --bib-line-spacing 1 \
    --page-size A4 --margins 2.5 --page-number bottom-right --title-page counted --toc-bold 1 --lang de-DE
python3 scripts/build_reference_docx.py --help
```

Sizes are in pt, lengths in cm, also with a unit (`12mm`, `0.5in`), line spacing a multiple (`1`, `1.5`); a single value also takes a decimal comma (`1,5`). `--margins` takes one value for all sides, or four for top, right, bottom and left, separated by slashes (`2,5/3/2,5/3`) or by commas with decimal points (`2.5,3,2.5,3`). Some options do more than their name says, so that a styleguide value comes out as meant:

- `--space-after` alone also sets the space before a paragraph to 0, instead of Pandoc's 9 pt (and `--space-before` alone the space after).
- `--first-line-indent` leaves out the paragraph after a heading, a block quote or a list (Pandoc sets it in `First Paragraph`), and block quotes, list items and table cells. List items and table cells follow the text's alignment.
- The heading options apply to every heading level the document has: `--heading-sizes 14,12,11` sets the sizes of levels 1 to 3, while font, weight and colour reach level 4 and below too. Any heading option also sets the headings upright (Pandoc's own sets level 4 and below in italics).
- `--quote-indent` sets the left indent and, unless `--quote-indent-right` gives one, no right indent (Pandoc's own indents block quotes on both sides).
- `--title-page counted` leaves the first page without a number, `not-counted` also starts the numbering at 0, so that the first text page shows 1 (`pagination.title_page`).
- `--heading-color` (from `headings.color`) and `--link-color` replace Pandoc's blue; `--footnote-font` sets a footnote font other than the text's.
- `--toc-bold 1` (from `headings.toc_emphasis`; a comma list such as `1,2`, or `none`) writes the styles Word sets the table of contents in when it fills the field in, `TOC 1` to `TOC 3` (deeper if a listed level is deeper), with Word's own indents and spacing: the listed levels bold, the others regular. A `--base` that has these styles keeps their layout; only their weight changes. Without the option, Word uses its own.

What it does:

1. Starts from Pandoc's own reference document (`pandoc --print-default-data-file reference.docx`), or from a DOCX or DOTX given with `--base`, such as an institution's template; styles Pandoc uses and the starting document lacks are added, and a style Word names in lower case (`footnote text`) is found as well
2. Sets the given values in the styles Pandoc uses (`Normal`, `Body Text`, `First Paragraph`, `Compact`, `Block Text`, `Heading 1` and following with their character styles, `Bibliography`, `Footnote Text`, `Title` and the other title styles, `Hyperlink`), with font and colour also where the document theme set them, and with `--toc-bold` Word's table of contents styles; it also writes the style `Front Matter Heading`, which looks like `Heading 1` but has no outline level and no number, for a heading in front matter that the table of contents does not list (`docs/reference_management.md`, "The title page"), unless the starting document has a style of that name
3. Sets page size and margins (with the header, footer and gutter distances Word needs), replaces any page number the starting document has, with the text between the same tabs (such as "Page 3 of 9"), by a `PAGE` field in the footer (or header), while a running head, a logo or a link beside the old number stays (in its own line, above the new number), and for the title page sets "different first page" and, if not counted, the start of the numbering, in the order Word expects
4. Writes the file and lists what it set

Run it before the first export of Phase B, and again after a layout finding of the format check, with the corrected value: fix the layout there, not in the chapter files. Start each run from Pandoc's own document (no `--base` with an earlier result), so that a value left out falls back to Pandoc's.

Exit code 0 = reference document written, 2 = not written (bad option, Pandoc not found and no `--base`, a folder or file that does not exist, a starting document it cannot read; one line says which).

Not covered: heading numbers (they come from the heading text, from Pandoc's `--number-sections`, or from numbering that a `--base` template links to its heading styles, which Pandoc keeps; the script does not set any); and front matter numbered unlike the main text (Roman, counted but not shown or none), a main text that starts at 1, or back matter numbered unlike the main text, which need a section of their own: `docx_pagination.py` sets it after the export.

### `docx_postprocess.sh`

Enables automatic hyphenation in a DOCX. python-docx does not expose this flag, so the script patches the XML directly.

```bash
./scripts/docx_postprocess.sh workspace/output/document.docx
```

What it does:

1. Unzips the DOCX into a temporary directory
2. Inserts `<w:autoHyphenation/>` into `word/settings.xml` if not already present, or rewrites it in place if it is present but explicitly disabled (`w:val="0"`/`"false"`/`"off"`)
   (if the settings element cannot be located, e.g. because the generator used a namespace prefix other than `w:`, the script stops with an error and leaves the file unchanged — enable hyphenation in Word instead)
3. Re-zips, keeping `[Content_Types].xml` as the first entry and stored (uncompressed) — not an OOXML requirement, but it maximizes compatibility with strict/streaming consumers
4. Replaces the original file only after the new archive was built successfully (for a symbolic link, the document it points to; the link stays)

Run it on every export right after Pandoc writes it, before the format check: a new export does not carry the flag. The format-verifier only checks that the flag is there. Re-running is safe (the script detects if the flag is already set and enabled).

### `docx_pagination.py`

Numbers the front matter of an exported DOCX unlike the main text, as `pagination.front_matter` and `pagination.main_text` in `styleguide.md` say, and the back matter, as `pagination.back_matter` says. A reference document gives the whole export one section, so the table of contents page shows its number like a text page; the script splits the export into two sections at the end of the front matter: the title page, the table of contents and the lists after it in the first, the main text in the second. Back matter numbered unlike the main text gets a third section: the reference list, an appendix after it and what follows them.

```bash
python3 scripts/docx_pagination.py workspace/output/document.docx --front-matter roman --main-text restart
python3 scripts/docx_pagination.py workspace/output/document.docx --front-matter roman --main-text restart --back-matter roman-continue
python3 scripts/docx_pagination.py --help
```

| `pagination.front_matter` | `--front-matter` |
|---|---|
| Roman numerals (I, II, …; small: i, ii, …) | `roman` (`roman-lower`) |
| counted but not shown | `hidden` |
| none (not counted, no number shown) | `none` |
| Arabic, like the main text | `arabic` |

`--main-text continue` lets the main text continue the count (`pagination.main_text`: continuing the count, or continuous), `--main-text restart` starts it at 1. After front matter that is not counted (`none`), "continuing" means the number after the title page's: 2 after a counted title page, otherwise 1. Whether the title page is counted (`pagination.title_page`) is read from the export, which takes it from the reference document (`build_reference_docx.py --title-page`); the title page keeps the first-page header and footer the reference document gives it, without a number. The main text keeps the reference document's number format, such as "- 1 -" from a `--base` template; Roman numerals or letters there give way to Arabic numerals.

| `pagination.back_matter` | `--back-matter` |
|---|---|
| like the main text | `main` (the default) |
| Roman numerals, continuing the front matter's count | `roman-continue` |
| a count of its own from 1: Arabic, or Roman (I, II, …; small: i, ii, …) | `restart`, or `roman` (`roman-lower`) |
| no number shown | `none` |

`--back-matter roman-continue` gives the back matter the Roman numerals of the front matter (small ones after `roman-lower`), from the number after its last page: IV after a front matter that ends on III. Word and LibreOffice would continue the main text's count instead, so the script sets that number, and counts the front matter's pages by its page breaks: the title page, and one page for each page break up to the one that ends the front matter. A table of contents or list that fills more than one page once Word updates the fields is not counted that way: then give the back matter's first number with `--back-matter-start` (5 for V) on a new export, since a DOCX split before is left as it is; in a DOCX the script has split already, such as the final one, set the number in Word instead (`docs/reference_management.md`, "The title page", step 5). The script says which number it set. After front matter that is not counted (`none`), there is no count to continue: `roman-continue` needs `--back-matter-start` there. `restart` keeps the main text's number format, such as "- 1 -"; `none` takes the page number out of the back matter's header or footer, as for the front matter.

A value of `styleguide.md` that does not name one of these cases is open, not a choice for whoever runs the script. That holds for a `pagination.main_text` that says neither that the main text continues the count nor that it starts at 1: "Arabic from introduction onward" in a styleguide made before 1.3.0, or an answer recorded in other words. It also holds for a `pagination.front_matter` of "none" recorded before 1.3.0, when that value did not say whether the front matter is counted, for Roman numerals without a case, and for a styleguide without `pagination.back_matter`, which a styleguide made before 1.3.0 does not have. Do not run the script with a value you chose. Ask the user, record the answer (`.claude/agents/style-resolver.md`, "Recording answers to open questions"), and then run the script; the format check judges the numbers by the recorded answer.

The end of the front matter is the page break that carries the hidden bookmark `_cephalo_front_matter_end`, which the title page file sets (`docs/reference_management.md`, "The title page"); that page break becomes the section break. Without the bookmark, the script stops with exit code 2 and changes nothing. The start of the back matter is the page break that carries the bookmark `_cephalo_back_matter_start`, before the reference list (`docs/reference_management.md`, "The reference list"); without it, a `--back-matter` other than `main` stops the script the same way. Back matter numbered unlike the main text is split also where the front matter is not (`--front-matter arabic --main-text continue`); the front matter's bookmark is then needed only for `roman-continue` without `--back-matter-start`. A page number the front matter does not show is taken out of its header or footer, with the text and fields between the same tabs or line breaks, such as "Page 3 of 9"; other content there, such as a running head, a logo or a link, stays, also in the line of the page number. The footnotes keep one count through the sections: the script takes out the restart in each section that Pandoc's reference document sets, which an export of one section never shows. With `--front-matter arabic --main-text continue` and `--back-matter main` nothing changes, since the export already numbers the pages that way, and a document split before is left as it is: run the script on every new export, before the format check. Then update the fields in Word (Ctrl+A, then F9), so that the table of contents shows the numbers of each section. With `--front-matter none`, or `hidden` before `--main-text restart`, a heading in the front matter would be listed there with a number the main text shows again: the script names it in a warning (`docs/reference_management.md`, "The title page", says how to write it).

Exit code 0 = written, or nothing to change; 2 = not written (no bookmark, the bookmark twice or not on the page break that ends the front matter, the back matter's bookmark missing, twice, not on its page break or before the end of the front matter, `roman-continue` with no front matter count to continue, `--back-matter-start` without `roman-continue`, not a DOCX, a damaged document; one line says which).

### `cross_session_audit.py`

Audits a multi-worktree repository for information that exists in a worktree or past session but never made it into the main worktree (the first entry of `git worktree list`, whatever branch it has checked out). Useful for projects that use `.claude/worktrees` (or any `git worktree`) to run agent sessions in parallel.

```bash
python3 scripts/cross_session_audit.py
python3 scripts/cross_session_audit.py --repo-root /path/to/repo
python3 scripts/cross_session_audit.py --report-file audit_report.md
```

What it does: after a summary, the report shows a **worktree overview** (all worktrees, their current branch/HEAD, and the number of uncommitted changes and of `_*.md`-style closing/briefing/TODO notes in each), followed by three layers, numbered as in the report:

1. **Layer 1 — `_*.md` files in a worktree but not in the main worktree** — for the `_*.md`-pattern notes, checks whether each one that exists in a linked worktree also exists in the main worktree; flags the ones that don't as potentially lost.
2. **Layer 2 — dangling refs in the main worktree** — scans the main worktree's own Markdown files (not its earlier reports) for backticked references to other Markdown (`.md`) files (paths prefixed with a two-digit `NN_.../`, `scripts/...`, or `workspace/...`) and reports any that point to a file that doesn't exist. References to other file types (e.g. `scripts/tool.py`) are not checked.
3. **Layer 3 — uncommitted changes per worktree** — lists the `git status --porcelain` lines (including untracked files) of each worktree that has uncommitted changes.

Output goes to stdout by default; `--report-file PATH` additionally writes a Markdown report to that path.

Exit codes: `0` = no findings, `1` = findings reported (intended for CI/hooks), `2` = the audit could not run: `--repo-root` (default: the current directory) is not an existing directory inside a git working tree, `git` is not on PATH, a worktree could not be inspected (`git status` fails there, e.g. with "dubious ownership" or a corrupt index, or its directory is missing or cannot be read; `git worktree prune` removes the entry of a deleted worktree), or the `--report-file` could not be written (the report has already been printed to stdout in that case). The cause is printed as one `Error: ...` line on stderr.

Like the other checks, this is a heuristic aid, not a guarantee — it only catches the specific patterns described above (uncommitted changes, `_*.md` notes, and backticked cross-references in a recognized path format).

A bare repository (`git clone --bare` with linked worktrees) has no main worktree to compare against: run from the bare repository itself, the audit stops with exit 2; run from one of its worktrees, it compares against the bare entry, so every `_*.md` note counts as missing from the main worktree, and Layer 2 is skipped.

---

### cephalo guard

`cephalo_guard.py` is no script to run yourself: it is a [Claude Code hook](https://code.claude.com/docs/en/hooks) that sees some of Claude's tool calls before they run and stops a few slips that the agent definitions forbid but models repeat. The definitions stay the rule: the guard checks a few of them, and a project without it works the same.

Setup installs it: it copies `templates/claude_settings.json` to `.claude/settings.json` where that file is missing, in a multi-project setup also into each sub-project, which Claude Code opens as a project of its own. An existing `.claude/settings.json` is kept; if it does not run the guard, setup's "Next steps" names it, and you merge the template's two hook entries into it by hand. The hook command runs the project's `scripts/cephalo_guard.sh`, which starts the guard with `py` on Windows and with `python3` elsewhere; in a multi-project setup a sub-project without one runs that of the folder above, which holds `00_Shared_Materials/`; another project does not. A project whose folder above someone else may write keeps its own `scripts/`: the marker keeps out an unrelated folder, not one someone sets up for it. Without Python, without the two scripts, or on Windows without Git Bash, every call passes unchecked: there Claude Code runs a hook command in PowerShell, which cannot read this one, and `"onFailure": "continue"` lets the call go on (Claude Code 2.1.295 or later; earlier versions run the hooks with the key in place). Claude Code runs a project's hooks only once you have trusted its folder in the dialog it shows at the first start.

| Rule | Stops | Instead |
|---|---|---|
| S1 | A shell command that writes a file's text: an inline `py -c` or `python3 -c` program that writes a file, a here-document, `echo` or `printf` into a file, `sed -i` and the like, a PowerShell content cmdlet, or a saved program that does so and is neither one of cephalo's scripts nor a script of the project in a `data/scripts/` folder of it (an analysis or deck script) | The Write or Edit tool |
| S2 | A write outside the project folder: `/tmp`, the system's temporary folder, the home folder, Claude Code's scratchpad. Claude Code's `~/.claude` folder passes for the main chat and an orchestrator (plans, memory, what you ask for there); another agent may write only in the agents' memory folder there, `~/.claude/agent-memory/` | `_scratch/<role>/` in the project |
| S3 | `python3 … \|\| py …`, which runs a finished report again, and `python3` on Windows where `py` exists | The command once, with `py` on Windows |
| S4 | A redirect into a file in the PowerShell tool, which writes UTF-16 | The redirect in the Bash tool (Git Bash) |
| S5 | A change to `.claude/settings.json` or `.claude/settings.local.json` (the project's or yours in `~/.claude/`) or to `scripts/`: a Write or Edit, or the common ways in the shell (a redirect, `cp`, `mv`, `rm`, `sed -i`, `git checkout`, a Python program), also from a script in `data/scripts/`, where only a path its Python code names counts (a string with a slash or backslash, a path `os.path.join` or `Path` builds from strings, also with a name after them or the home folder before them, or a string a `shutil` or `os` call takes as the path it removes, moves or copies to; a shell command's arguments count as in any command), read from the folder the command runs in (in a script that changes folder with `os.chdir` or runs a program in another one with `cwd=`, a relative path counts only if it names such a path from there, from the script's folder and from its data folder, which a relative path into `scripts/` never does: there only an absolute path into `scripts/` and the hook settings count) | You change these by hand |
| R5 | The main chat's or an orchestrator's Edit of a saved source-verifier report; after a Write of one, it asks for the read-back of the whole file, gives the saved file's counts (each kind of quotation mark among them) and warns for each German opening mark („) that the next quotation mark after it does not close as “ (ASCII quotes in pairs on one line inside it aside) | The report written again from the agent's answer |
| R6 | The main chat's or an orchestrator's Write or Edit of a report that the format-verifier writes itself | The format-verifier's report as it wrote it |
| P1 | Off unless you switch it on. A task prompt that narrows a check, tells an agent to leave out a finding, rates in advance what it will find, states the project's state ("already verified", "the user has decided") or keeps the agent from files its definition gives it: denied once, and the same prompt sent again passes | |

A denied call shows Claude a message that starts with `cephalo guard`, names the rule, the definition that holds it and what to do instead. Claude then goes on with the tool the message names; you see the message in the chat.

**Switching it off.** The guard reads two variables, which you set in `.claude/settings.local.json` (Git leaves this file out; create it if it is missing). They take effect in the next chat:

```json
{ "env": { "CEPHALO_GUARD_OFF": "all" } }
```

`"all"` switches every rule off, a list such as `"S1,S2"` the rules it names; `"CEPHALO_GUARD_ON": "P1"` switches P1 on. This is the way to switch it off for good (in a multi-project setup, in the sub-project you open in Claude Code): setup never copies or changes `.claude/settings.local.json`, but it installs `.claude/settings.json` again where it is missing, and names one without the guard in its "Next steps". To remove the hooks themselves, delete their two entries and keep the file (as `{}` if nothing else is left). Claude does not change these files or `scripts/` (rule S5): when a change is needed, it tells you.

The guard reads the tool call that Claude Code passes to it and, to check it, a script or patch the command runs (also one outside the project) or the report just saved; it uses no network: a network path (`\\server\share`, `//server/…`, a WebDAV address), a device (`COM1`, a file under `/dev`) or a file under `/proc` or `/sys` it judges by its name only and never opens; a project that itself lies on a share or under `/dev/shm` it reads like a local one, and so `~/.claude` on a share. A share reached through a drive letter or a mount point looks like a local folder to it. A call it cannot check within its limits (5 seconds, or a command of more than 512 KiB) passes, with its note. A hook that Claude Code stops at the timeout in `.claude/settings.json` (30 seconds) lets the call go on unchecked too, without a note: in the hook test of the ninth seminar trial run, on Windows, Claude Code stopped the hook at the 10 seconds of earlier versions on the first call of two sessions, and a trivial test hook beside it took as long, so the time went into starting the hook, not into the guard. A project set up before 1.4.6 keeps its `.claude/settings.json`: change both `"timeout": 10` there to 30 by hand, in a multi-project setup in each sub-project's too. The guard writes nothing but a small file per chat in a folder of its own in the system's temporary folder (`cephalo-guard-<user id>/`, which only you can write, on Windows `cephalo-guard/`), for P1 when it is on and to show a note once when it cannot read or check a call. A check takes about 50 ms on Linux; on Windows, the hook took at least about 0.26 s a check in the fourth seminar trial run and 0.28 s in the hook test before the release (medians of 30, measured inside its Git Bash shell, without the shell's own start; 0.34 s in Claude Code's debug log, which counts that start too), most of it the start of Python. With every rule off (`"all"`), `cephalo_guard.sh` does not start Python at all: a check then took 37 ms in that test.

## Troubleshooting

**`python3: command not found`** — the Python utility scripts (`abbreviations_extract.py`, `bibliography_check.py`, `verbatim_check.py`, `cross_session_audit.py`) are invoked directly with `python3` or `py`; on Windows, run them with `py` (see "Commands on Windows" above). On macOS before Monterey, you may need to install Python 3 via Homebrew. The shell scripts (`docx_postprocess.sh`, `extract_styleguide.sh`) handle this themselves: they probe for a *working* interpreter under `python3`, `python` and the Windows `py` launcher (this also catches the case where `python3` resolves to the dead Microsoft Store app-execution-alias stub on Windows) and print a clear error only if none works.

**`Error: python-docx not installed.`** (from `abbreviations_extract.py`, `bibliography_check.py`, and `verbatim_check.py` with a `.docx` chapter; the underlying import error is `ModuleNotFoundError: No module named 'docx'`) — install it: `pip install python-docx` (or `pip install -r requirements.txt`). If you installed `docx` instead, that is a different package: run `pip uninstall docx`, then `pip install python-docx`.

**`Error: neither pypdf nor pdftotext available for PDF extraction.`** (from `extract_styleguide.sh`; the underlying import error is `ModuleNotFoundError: No module named 'pypdf'`) — install it: `pip install -r requirements.txt` (not `pypdf[crypto]` alone: requirements.txt keeps `cryptography` below 49 on Intel Macs, where newer releases have no wheels and pip would try to build them). Alternatively, install `pdftotext` (poppler) as fallback. `verbatim_check.py` lists the PDF sources under "Not checked" with `pypdf not installed` for the same reason; the same `pip install -r requirements.txt` helps.

**`pypdf failed (cryptography>=3.1 is required for AES algorithm)`** (from `extract_styleguide.sh`) — the guideline PDF is AES-encrypted, typically copy protection with an empty open password, and pypdf was installed without its `[crypto]` extra. Run `pip install -r requirements.txt` again.

**`UnicodeEncodeError: 'charmap'`** on Windows — the Python scripts switch their output to UTF-8 at startup, so this should not appear with Python 3.9 or later. If it does, run `set PYTHONIOENCODING=utf-8` (cmd) or `$env:PYTHONIOENCODING = "utf-8"` (PowerShell) and try again.

**`bibliography_check.py` finds no bibliography section** — the script detects the section by common headers (Bibliography, References, Literaturverzeichnis, etc.), matched case-insensitively after stripping manually typed decimal numbering and trailing punctuation (so `7 Literaturverzeichnis` and `References:` are recognized out of the box). If your document uses a genuinely different heading word or a typed letter or Roman number (`A. Literaturverzeichnis`), add its exact text to `BIBLIOGRAPHY_HEADERS` near the top of the script.

**`docx_postprocess.sh` breaks the document** — this should not happen; the script preserves OOXML structure. If it does, please report the case. The script's safety model: it works entirely in a temporary directory and only replaces your original file in the very last step, after the new archive has been rebuilt successfully. If the script fails at any earlier point, your original file is untouched at its original path — but the temporary directory itself is deleted on exit either way, so it is not a recovery location. If a *successful* run produces a broken file, restore from your own backup or version control (keep one before running any batch post-processing on a final export).

**Git Bash on Windows says `bash: pdftotext: command not found`** — that is fine if you have a working Python 3 with `pypdf` installed; `pdftotext` is only an optional fallback. If Python itself is unavailable but `pdftotext` is on PATH, `extract_styleguide.sh` runs in a pdftotext-only mode instead (text extraction still works; the disguised-ZIP handling described above under "What it does" does not, since that path requires Python). The script only fails if neither `pypdf` (under a working Python 3) nor `pdftotext` is available.

---

## Contributing

All scripts are intentionally small and heuristic. If you add features, keep them:

- Cross-platform (Linux, macOS, Windows via Git Bash)
- Dependency-minimal (Python standard library + the two packages in `requirements.txt`)
- Safe against malicious inputs (see `extract_styleguide.sh` for ZipSlip handling)
