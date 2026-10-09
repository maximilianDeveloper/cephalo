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
  --reference-doc 08_Formal_Review/reference.docx \
  -o output.docx
```

Use your structure's `literature.bib` path from "Set up auto-export" (flat: `--bibliography workspace/sources/literature.bib`, `--reference-doc workspace/output/reference.docx`), and your styleguide's bibliography heading as `reference-section-title`. Without it, Pandoc adds the reference list without a heading, and `scripts/bibliography_check.py` cannot find the bibliography (exit 2). For the whole work, list the chapter files in document order instead of `chapter.md`. `--metadata title=""` keeps the `title:` of the chapter files' frontmatter out of the document: without it, Pandoc puts that title (with several files, the last chapter's) above the text as a document title.

cephalo's formatting phase exports with Pandoc also when the chapters cite in the styleguide's format and not by citekey: Pandoc sets Markdown headings and block quotes (`>`) in Word's heading and quote styles, which the format check and `scripts/verbatim_check.py` rely on. Without citekeys, leave out `--citeproc`, `--bibliography` and `--csl`; the reference list is then a file of its own, which the export lists after the chapter files ("The reference list" below).

**Prerequisite:** a CSL file matching your institution's citation style. APA 7 is the closest standard for many institutions; download from [zotero.org/styles](https://www.zotero.org/styles). For institution-specific deviations, you may need to edit the CSL.

Without Pandoc or such a CSL file, citekeys never become citations in your styleguide's form. The pre-check therefore records whether the chapters cite by citekey (`checklists/precheck.md`, section 6); if not, the writer-agent writes citations in the styleguide's format directly, and `literature.bib` still serves the research-agent's citekey check. In citekey form, a German prefix and locator work as usual (`[vgl. @mueller2019, S. 44]`), and a secondary citation whose original stays out of the bibliography carries the original as plain text: `[Weber 1922, S. 31, zit. nach @keller2018, S. 5]`.

For LaTeX users: biblatex with biber renders citekeys as well, for a PDF. The DOCX that cephalo's formatting phase checks comes from Pandoc.

### The reference document

The `--reference-doc` file carries the layout: page size, margins, the footer with the page number, and the paragraph styles; Pandoc takes all of these from it. Keep it in the project, as `08_Formal_Review/reference.docx` (flat: `workspace/output/reference.docx`), and build it from the values in `styleguide.md` with `scripts/build_reference_docx.py` (`docs/scripts.md`): it starts from Pandoc's own and sets the styles below, page size, margins, the page number and the title page's numbering. By hand, start from `pandoc -o 08_Formal_Review/reference.docx --print-default-data-file reference.docx` and adjust it in Word (Modify Style; Layout for page size and margins). The format check's layout findings are fixed there, by building it again with the corrected value, not in the chapter files.

Pandoc sets the text in these styles, so these are the ones to adjust:

| Style | Used for |
|---|---|
| `Normal` | the base of the others: font, size, line spacing |
| `First Paragraph` | the first paragraph after a heading |
| `Body Text` | every further paragraph (Pandoc's own has 9 pt before and after) |
| `Compact` | items of a tight list (a loose list, with blank lines between its items, gets `Body Text`) |
| `Block Text` | block quotes written with `>` (Pandoc's own is indented by 0.85 cm on both sides) |
| `Heading 1` to `Heading 4` | headings, as deep as `headings.max_depth` goes; with their character styles `Heading 1 Char` and so on |
| `Bibliography` | the reference list |
| `Footnote Text`, `Footnote Reference` | footnotes, and the number that marks them in the text |
| `Hyperlink` | links and URLs (Pandoc's own is blue) |
| `Table Caption`, `Image Caption`, `Captioned Figure` | captions and figures (`captions.*`) |
| `Title`, `Subtitle`, `Author`, `Date` | a title block from the metadata, if one is used |

Pandoc's own reference document takes the heading font and colour from the document theme: set both in the heading styles and in their character styles, the colour as `headings.color` gives it (Pandoc's own is blue). It has no page size, no margins and no page number: set them, and put a `PAGE` field into the footer, aligned as the styleguide says.

A reference list without citekeys (below, "The reference list") comes out in `First Paragraph` and `Body Text`. Give it the `Bibliography` style with a fenced div around its entries, below the heading:

```markdown
# References

::: {custom-style="Bibliography"}
Author, Anna (2020): Title. Place: Publisher.

Writer, Ben (2018): Title. In: Journal 12 (3), pp. 1–20.
:::
```

The div is markup, not wording: added to a reference list written without it, it is a format-only change.

### The reference list

With citekeys, Pandoc writes the reference list from `literature.bib` (`--citeproc`). Without them, in a bachelor or master thesis, the reference list is a file of its own, `08_Formal_Review/bibliography.md` (flat: `workspace/output/bibliography.md`), which every export lists after the chapter files and before an appendix, if there is one; the chapter files carry none. The orchestrator writes it at the start of Phase B:

- one entry for each source whose extract names a chapter under **Used in**, with the data under the extract's "Bibliographic info", which the source-verifier checked in Phase A (and `literature.bib`, if there is one); no other source, and no data from anywhere else;
- as the `bibliography.*` rules of `styleguide.md` say (entry patterns, authors, editions, DOI and URL, italics, sort order), under the styleguide's heading at the level of a chapter heading (`#`, Word's Heading 1), inside the `Bibliography` div above;
- a source the styleguide keeps out (`bibliography.secondary_original`, such as the original of a secondary citation) stays out.

A seminar paper and the proposal have no Phase B. Without citekeys, the writer-agent writes their reference list as the last section of the last chapter file (proposal: of `03_Drafting/proposal_draft.md`): one entry for each source the text cites, as the `bibliography.*` rules of `styleguide.md` say, under the styleguide's heading at the level of a chapter heading, inside the `Bibliography` div.

`scripts/bibliography_check.py` on the export then shows whether cited and listed authors match, and the format-verifier checks the patterns.

### The title page

Pandoc writes no title page of its own. Write it as a Markdown file in the project, `08_Formal_Review/title_page.md` (flat: `workspace/output/title_page.md`), and list it first, before the chapter files, when you call Pandoc. Its contents come from `styleguide.md` (`title_page.*`); what the user has not given yet stays a placeholder such as `[Name]`. Set its lines in the styles `Title`, `Subtitle`, `Author` and `Date` (or in styles of your own, which Pandoc adds to the document) with fenced divs, and end it with a page break. A table of contents goes into the same file, as a Word field after the title page, with the levels of `headings.max_depth` (`\o "1-3"`); Word fills it in when the user updates the fields (Ctrl+A, then F9, a step of the workflows' submission). Do not use Pandoc's `--toc`: Pandoc places its table of contents before all text, so before the title page.

````markdown
::: {custom-style="Title"}
Title of the work
:::

::: {custom-style="Author"}
[Name], [Matrikelnummer]
:::

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Table of contents: update the fields in Word</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```
````

The level formatting of the table of contents (`headings.toc_emphasis`) comes from the styles `TOC 1` to `TOC 3`, which Word adds to the document when it fills the field in.

The page numbers follow `pagination.title_page` in `styleguide.md`, and Pandoc takes the settings for them from the reference document:

- **Counted but not shown:** give the reference document a different first page (Word: Layout, Page Setup, Layout tab, "Different first page"; in its XML `w:titlePg`), with no page number in the first-page footer. The first text page then shows 2.
- **Not counted:** in addition, start the page numbering at 0 (Word: Insert, Page Number, Format Page Numbers, "Start at" 0; in its XML `<w:pgNumType w:start="0"/>`). The first text page then shows 1.

Who edits the XML of the reference document keeps the order of the section properties (`w:sectPr`), which Word expects: `w:pgNumType` follows `w:pgSz` and `w:pgMar`, and `w:titlePg` follows `w:pgNumType`. A table of contents after the title page counts like a text page: with one page of it, the first text page shows 3, or 2 if the title page is not counted.

Front matter numbered in Roman numerals (`pagination.front_matter`) needs a section of its own, which a reference document cannot give. The user sets it in Word in the final DOCX, after the final export (a step of the workflows' submission); until then the format check lists it as an open manual step, not as a finding to fix.

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
