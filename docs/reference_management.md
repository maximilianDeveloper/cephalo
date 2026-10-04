# Reference Management

**Audience:** authors without prior experience using a reference manager (Zotero, Citavi, Mendeley, EndNote, etc.).

This document describes how cephalo integrates with reference managers, primarily through BibTeX export. Examples use Zotero because it is free, cross-platform, and open source — but any tool that exports BibTeX works.

---

## Why a reference manager?

Once your project crosses ~15 sources, manual bibliography management starts to break down:

- Inconsistent author name spellings ("Smith, J." vs. "Smith, John")
- Duplicate or near-duplicate entries
- Edition number drift (cited as 8th edition in Ch. 2, 9th in Ch. 5)
- Bibliography format must be re-done manually if the styleguide changes
- "I cited this somewhere — but where?"

A reference manager solves all of these by being the single source of truth for bibliographic data. Citation styles can be regenerated on demand. Duplicates are detected. Updates propagate everywhere.

---

## Setup with Zotero

### 1. Install Zotero

[zotero.org/download](https://www.zotero.org/download) — desktop application for Windows, macOS, Linux.

Optional: install the **Zotero Connector** browser extension. It captures bibliographic data from web pages with one click (publisher pages, JSTOR, library catalogs, etc.).

### 2. Install Better BibTeX

Better BibTeX is a Zotero plugin that produces clean, stable BibTeX exports. The default Zotero BibTeX export is workable; Better BibTeX is significantly better.

[github.com/retorquere/zotero-better-bibtex/releases/latest](https://github.com/retorquere/zotero-better-bibtex/releases/latest) — download the `.xpi` file, install via Zotero: Tools -> Plugins -> gear icon -> Install Plugin From File.

### 3. Configure citekeys

Citekeys are the short identifiers used in your text (e.g., `smith2020`). In Zotero with Better BibTeX:

- Edit -> Settings (macOS: Zotero -> Settings) -> Better BibTeX -> Citation keys
- Set the citation key formula (recommended: `[auth:lower][year]` -> `smith2020`)
- For multiple works by same author/year: add disambiguator (`[auth:lower][year][shorttitle]`)

### 4. Create a project collection

In Zotero:
- File -> New Collection
- Name it after your project (e.g., "Bachelor thesis 2026")

Add sources to this collection as you find them.

### 5. Set up auto-export

This is the key integration step. Zotero will continuously export the collection as BibTeX whenever it changes.

In Zotero:
- Right-click your collection -> Export Collection
- Format: Better BibTeX
- Check: "Keep updated" (this enables continuous auto-export)
- Save to: the project's literature path
  - Flat: `workspace/sources/literature.bib`
  - Long-form: `02_Literature/literature.bib`
  - Multi-project main work: `02_Main_Work/02_Literature/literature.bib`

From this point on, every time you change a source in Zotero, the `.bib` file updates automatically.

---

## How cephalo uses BibTeX

### Citekeys in extracts

The research-agent stores extracts as `extracts/<citekey>.md` — one file per source, named by citekey. This makes it trivial to find the extract for any cited source.

Example: `02_Literature/extracts/smith2020.md`

### Citekeys in chapter text

The writer-agent uses citekeys in citations within chapter drafts:

```markdown
Information asymmetry impedes access to capital providers [@smith2020, p. 975].
```

When exporting to the final document (DOCX or PDF), citekeys are resolved to the styleguide-compliant citation format via a citation processor: Pandoc, which cephalo's formatting phase uses for the DOCX export, or LaTeX with biblatex for a PDF.

### Bibliography generation

The bibliography is generated from `literature.bib` using a CSL (Citation Style Language) file matching your institution's citation style. The format-verifier checks the generated bibliography against the styleguide.

---

## Capturing sources cleanly

The quality of your bibliography depends entirely on the quality of your Zotero entries. A few practical rules:

### Verify every imported entry

The Zotero Connector imports entries automatically, but the data is sometimes wrong (missing edition number, wrong author order, missing DOI). After every import, open the entry and verify against the source itself.

### Use stable citekeys

Once you've started citing a source as `smith2020`, don't rename it. Citekeys are referenced everywhere — extract filenames, chapter texts, decision logs. Renaming breaks references.

### Tag for organization

Use Zotero tags to track:
- Which chapter(s) the source is used in (`chapter:3`, `chapter:5`)
- Source type (`empirical`, `theoretical`, `methods`)
- Status (`verified`, `to_read`, `excluded`)

---

## Special cases

### Secondary citations

Zotero does not distinguish between primary and secondary citations. That remains the source-verifier's responsibility (see `.claude/agents/source-verifier.md`, check step 5).

In the Zotero entry's "Extra" field, you can note: "Secondary citation in Author A 2021, p. 81 — primary source Author B 2006 is accessible".

### Different editions of the same work

Each edition is a separate Zotero entry. Citekey convention: `author2020edN` (e.g., `kotler2020ed16`).

In your text, always cite the edition you actually consulted. The bibliography lists exactly that edition. The format-verifier flags inconsistencies (cited as edition 8 in one place, edition 9 in another).

### E-books and pagination

E-book pagination differs from print. In the Zotero entry, the "Edition" field can include format ("8th ed., e-book").

In the research-agent's extract, record which version was consulted and which page numbers are cited (print vs. e-book). For the bibliography, list the print edition unless you only have access to the e-book.

### Sources behind paywalls

If a source is in a database (JSTOR, ProQuest, SpringerLink), Zotero captures the metadata. The actual PDF goes into Zotero as an attachment.

Do not commit institutional-database PDFs to a public Git repository (copyright). Keep them local, or use Zotero's cloud sync (zotero.org account, free up to 300 MB).

---

## Citation processor pipeline

The path from `chapter.md` (with `[@smith2020, p. 975]` citations) to a DOCX with formatted citations and bibliography:

```
chapter.md   -->  Pandoc with CSL  -->  document.docx
                  ^
                  literature.bib + style.csl
```

For Pandoc:

```bash
pandoc chapter.md \
  --citeproc \
  --bibliography 02_Literature/literature.bib \
  --csl path/to/style.csl \
  --metadata reference-section-title="References" \
  --metadata title="" \
  --reference-doc template.docx \
  -o output.docx
```

Use your structure's `literature.bib` path from "Set up auto-export" (flat: `--bibliography workspace/sources/literature.bib`), and your styleguide's bibliography heading as `reference-section-title`. Without it, Pandoc adds the reference list without a heading, and `scripts/bibliography_check.py` cannot find the bibliography (exit 2). For the whole work, list the chapter files in document order instead of `chapter.md`. `--metadata title=""` keeps the `title:` of the chapter files' frontmatter out of the document: without it, Pandoc puts that title (with several files, the last chapter's) above the text as a document title.

cephalo's formatting phase exports with Pandoc also when the chapters cite in the styleguide's format and not by citekey: Pandoc sets Markdown headings and block quotes (`>`) in Word's heading and quote styles, which the format check and `scripts/verbatim_check.py` rely on. Without citekeys, leave out `--citeproc`, `--bibliography` and `--csl`; the reference list then comes from the chapter files.

The `--reference-doc` file carries the layout: fonts, sizes, margins, page size and the paragraph styles. Set it up once per styleguide (start from `pandoc -o template.docx --print-default-data-file reference.docx` and adjust its styles in Word); the format check's layout findings are fixed there, not in the chapter files.

**Prerequisite:** a CSL file matching your institution's citation style. APA 7 is the closest standard for many institutions; download from [zotero.org/styles](https://www.zotero.org/styles). For institution-specific deviations, you may need to edit the CSL.

Without Pandoc or such a CSL file, citekeys never become citations in your styleguide's form. The pre-check therefore records whether the chapters cite by citekey (`checklists/precheck.md`, section 6); if not, the writer-agent writes citations in the styleguide's format directly, and `literature.bib` still serves the research-agent's citekey check. In citekey form, a German prefix and locator work as usual (`[vgl. @mueller2019, S. 44]`), and a secondary citation whose original stays out of the bibliography carries the original as plain text: `[Weber 1922, S. 31, zit. nach @keller2018, S. 5]`.

For LaTeX users: biblatex with biber renders citekeys as well, for a PDF. The DOCX that cephalo's formatting phase checks comes from Pandoc.

---

## Common errors

### Citekey drift

You start citing as `smith2020`. Months later, you rename to `smith2020economics`. Suddenly old chapters break.

**Prevention:** decide on a citekey convention at project start, and stick to it.

### Forgetting to enable auto-export

You do everything right in Zotero, but `literature.bib` never updates. Reason: auto-export was not enabled.

**Prevention:** verify the file timestamp updates after a Zotero change.

### Mixing editions silently

You cite Smith (2020, 8th ed.) in Ch. 2 and Smith (2020, 9th ed.) in Ch. 5 because you used different library copies. Page numbers are different. Bibliography lists one edition.

**Prevention:** treat each edition as a separate Zotero entry. The format-verifier catches the inconsistency in Phase B.

### Personal data in shared `.bib` file

If your bibliography includes personal communications ("Interview with X, 2026-02-15"), and the `.bib` file is committed to a public repo: the interview subject's name leaks.

**Prevention:** store personal communications in a separate, gitignored file. Reference them in the text without exposing identifying details.

---

## Alternatives to Zotero

| Tool | Strengths | Notes |
|------|-----------|-------|
| **Zotero** | Free, open source, BibTeX via Better BibTeX | Recommended baseline |
| **Citavi** | Strong note-taking integration, widely used at German universities | Windows-primary (Mac via browser); commercial with free Basis version |
| **Mendeley** | Cloud sync built in | Owned by Elsevier; has had data policy concerns |
| **EndNote** | Institutional standard at many universities | Commercial, but often free for students via institution |

cephalo only requires that the tool can export valid BibTeX and that citekeys are stable. Any of these work.

---

## Setup with Citavi

Citavi is widely used in German-speaking academia and has strong note-taking features. The integration with cephalo works the same way as Zotero: export BibTeX, point cephalo at the `.bib` file.

### 1. Install Citavi

[citavi.com](https://citavi.com) — Citavi Free (up to 100 entries per project) or the institutional license many universities provide.

### 2. Configure citekey style

In Citavi, citekeys are called "Short Titles":

1. Tools -> Options -> Citation
2. Set the Short Title format to `{Author}{Year}` (author lowercase, year 4 digits)
3. Apply to all existing entries

This produces citekeys like `schmidt2020` that align with the examples in cephalo's documentation.

### 3. Export BibTeX

Citavi has no auto-export equivalent to Zotero's Better BibTeX. The workflow is manual but straightforward:

1. File -> Export
2. Choose "BibTeX"
3. Select all references (or filter to the project's collection)
4. Save as `literature.bib` in:
   - `workspace/sources/literature.bib` (flat structure)
   - `02_Literature/literature.bib` (long-form)
   - `02_Main_Work/02_Literature/literature.bib` (multi-project)

**Re-export after every meaningful change.** A good habit: before starting a cephalo chat, re-export.

### 4. Verify BibTeX quality

Citavi's BibTeX output is generally clean. Two fields to double-check after the first export:

- **Author order** — Citavi sometimes alphabetizes authors; ensure the original order is preserved
- **Special characters** — German umlauts should appear as `ä ö ü ß`, not LaTeX escapes (`\"a`). Configure in export settings if needed.

### Trade-off vs. Zotero

Citavi wins on note-taking and knowledge organization (especially for long projects). Zotero wins on automation (Better BibTeX auto-sync) and cross-platform support. For a typical bachelor or master thesis, either is fine. If you already use Citavi at your institution, there is no reason to switch.

---

## Setup checklist

For long-form or multi-project setups.

**If you use Zotero:**

- [ ] Zotero installed
- [ ] Better BibTeX installed
- [ ] Citekey formula configured
- [ ] Project collection created in Zotero
- [ ] Auto-export to `literature.bib` enabled and verified
- [ ] CSL file for the institution's citation style available
- [ ] Pandoc available (the DOCX export of the formatting phase needs it; LaTeX only for a PDF of your own)
- [ ] First test: add one source to Zotero, verify `literature.bib` updates, generate a small DOCX with one citation

**If you use Citavi:**

- [ ] Citavi installed
- [ ] Short Title (citekey) format configured to `{Author}{Year}`
- [ ] Project collection / Citavi project created
- [ ] First BibTeX export to `literature.bib` completed
- [ ] Export settings verified: author order preserved, umlauts as `ä ö ü ß` (not LaTeX escapes)
- [ ] CSL file for the institution's citation style available
- [ ] Pandoc available (the DOCX export of the formatting phase needs it; LaTeX only for a PDF of your own)
- [ ] Habit established: re-export `literature.bib` before each cephalo chat
- [ ] First test: add one source, re-export, generate a small DOCX with one citation

**Regardless of tool:**

- [ ] `literature.bib` lives at the location the workflow expects (see the relevant structure doc)
- [ ] `literature.bib` is under Git version control (or explicitly excluded with rationale)
- [ ] Citekeys are stable and match the convention used in source extracts

If all applicable boxes check out, you have a stable end-to-end pipeline from your reference manager to formatted output.
