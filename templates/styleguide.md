# Styleguide for [project name]

**This template is filled by the style-resolver agent.**
**After extraction, clarify all open ❓ items with the supervisor: `[content]` items before any chapter is drafted, `[format]` items before the formatting phase (Phase B).**
**File path:** `styleguide.md` at the project root (or 00_Shared_Materials/styleguide.md in multi-project setups).

---

## Metadata

- **Source documents extracted from:**
  - [list each source document with path]
- **Citation guide version:** [if available]
- **Formatting guidelines version:** [if available]
- **Extraction date:** [YYYY-MM-DD]
- **Last reviewed by user:** [YYYY-MM-DD or "pending"]

---

## In-text citations (`in_text.*`)

- **`format_indirect`:** [e.g., `(Author, Year, p. X)` or `(cf. Author, Year, p. X)`]
- **`format_direct`:** [e.g., `"quote" (Author, Year, p. X)`]
- **`et_al.threshold`:** [e.g., 3 — use et al. from N authors onward]
- **`page_for_indirect`:** [required / optional / forbidden]
- **`cf_prefix`:** [required / optional / forbidden]
- **`nbsp_before_page`:** [yes / no — non-breaking space before page number]
- **`page_range`:** [`15-16` or `15–16` (en-dash) or `15 to 16` or other]
- **`multiple_sources`:** [several sources in one citation: separator and order, e.g., `(Müller 2019; Schmidt/Weber 2021)`]
- **`two_authors`:** [e.g., `Schmidt/Weber`, `Schmidt & Weber` or `Schmidt und Weber`]
- **`same_author_year`:** [e.g., `2019a`, `2019b`]
- **`no_date`:** [e.g., `o. J.` or `n.d.`]
- **`no_page_locator`:** [sources without page numbers, such as web pages: section, paragraph or nothing]
- **`secondary_citation`:** [e.g., `(Weber 1922, S. 31, zit. nach Keller 2018, S. 5)`; see also `bibliography.secondary_original`]
- **`repeated_citation`:** [a source cited again right after its previous citation: repeat the full citation / `ebd.` or `ibid.`, with the page where it differs, e.g., `(ebd., S. 14)` / a short form, e.g., the page alone]

---

## Bibliography (`bibliography.*`)

- **`heading`:** [heading of the reference list, e.g., Literaturverzeichnis or References]
- **`entry_patterns`:** [one pattern per source type: book, journal article, chapter in an edited volume, web source, ...; e.g., `Surname, I. (Year): Title. Place: Publisher.`]
- **`multiple_authors`:** [how co-authors are joined, and how many are listed before "et al."]
- **`secondary_original`:** [list the original of a secondary citation as well / list only the source read]
- **`alignment`:** [left / justified]
- **`hanging_indent`:** [e.g., 1.27 cm or 0.5 in]
- **`line_spacing`:** [e.g., 1.0 or 1.5]
- **`sort_order`:** [alphabetical by author, chronological for same author, etc.]
- **`oxford_comma`:** [yes / no — comma before "&" or "and" in author lists]
- **`first_edition`:** [name / omit]
- **`series_titles`:** [include / omit]
- **`doi`:** [always include / when available / omit]
- **`url`:** [include for online sources / omit if DOI present]
- **`access_date`:** [include / omit — common deviation from APA 7]
- **`italics`:** [book and journal titles / journal titles only / none]

---

## Document formalia (`document.*`)

- **`page_count`:** [e.g., 30-40 (range) or 35 (target)]
- **`margins`:** [e.g., 2.5 cm all sides, or 2.5 cm top/bottom and 3.0 cm left/right]
- **`hyphenation`:** [automatic / manual / off]
- **`page_size`:** [A4 / Letter]
- **`figure_resolution`:** [e.g., 300 dpi for print]

---

## Body text (`body.*`)

- **`font`:** [e.g., Arial, Times New Roman]
- **`size`:** [e.g., 11 pt]
- **`line_spacing`:** [e.g., 1.5]
- **`alignment`:** [justified / left]
- **`paragraph_spacing`:** [e.g., 6 pt after paragraph]

---

## Footnotes (`footnotes.*`)

- **`font`:** [e.g., Arial]
- **`size`:** [e.g., 10 pt]
- **`line_spacing`:** [e.g., 1.0]

---

## Headings (`headings.*`)

- **`numbering`:** [e.g., decimal (1.1, 1.2.3) or letter (A.1) or none]
- **`max_depth`:** [e.g., 3 levels]
- **`level_1.size`:** [e.g., 16 pt]
- **`level_1.weight`:** [bold / regular]
- **`level_2.size`:** [e.g., 14 pt]
- **`level_2.weight`:** [bold / regular]
- **`level_3.size`:** [e.g., 12 pt]
- **`level_3.weight`:** [bold / regular]
- **`color`:** [e.g., black, on all levels]
- **`toc_emphasis`:** [table of contents: e.g., level 1 bold, deeper levels regular]

---

## Pagination (`pagination.*`)

- **`title_page`:** [counted but not shown / not counted]
- **`front_matter`:** [Roman numerals (I, II, … or i, ii, …) / counted but not shown / Arabic, like the main text / none (not counted, no number shown)]
- **`main_text`:** [Arabic from the introduction on, continuing the count / Arabic from the introduction on, starting at 1 / continuous]
- **`back_matter`:** [like the main text / Roman numerals, continuing the front matter's count / a count of its own from 1 (Arabic, or Roman: I or i) / no number shown] (the reference list, an appendix and what follows them)
- **`position`:** [bottom center / bottom right / top right]

---

## Title page (`title_page.*`)

- **`elements`:** [required entries — e.g., institution, exam type, title, author, student ID, supervisor, date]
- **`decoration`:** [logo/decoration allowed / forbidden]

---

## Tables and figures (`captions.*`, `numbers.*`)

- **`captions.table_position`:** [above / below the table]
- **`captions.figure_position`:** [above / below the figure]
- **`captions.source_position`:** [e.g., below the table or figure]
- **`numbers.decimal_separator`:** [`.` / `,`]
- **`numbers.p_values`:** [notation, e.g., `p < .001` (APA) or `p < 0.001`]

---

## Style rules (`style.*`)

- **`forbidden_pronouns`:** [list — e.g., "I", "we", "one", "you" or local-language equivalents]
- **`forbidden_evaluative`:** [optional list — e.g., "remarkable", "particularly noteworthy"]
- **`block_quote_word_threshold`:** [e.g., 40 words]
- **`block_quote_format`:** [e.g., indented 1 cm, 10 pt, single-spaced, without quotation marks; and where its citation stands, inside the quote after its last sentence or after the quote]
- **`quote_alterations`:** [e.g., insertions in square brackets, omissions as `[...]`, added emphasis marked, a quote within a quote in single quotation marks]
- **`emphasis`:** [italic only / bold allowed / underline forbidden / etc.]
- **`footnotes`:** [allowed / discouraged / forbidden]

---

## Institutional deviations from APA 7 (if applicable)

[Document any institution-specific rules that diverge from standard APA 7. This is often where the most surprising rules live.]

- [e.g., page numbers required for indirect citations]
- [e.g., access date forbidden]
- [e.g., specific Oxford comma policy]
- [...]

---

## Open questions (`❓`)

[List of items the resolver could not unambiguously extract. Each item is tagged:
`[content]` — the answer changes what is written or produced in Phase A: voice and pronouns, evaluative wording, the direct-quote threshold, how quotes may be altered, what may go into footnotes, the "cf." prefix and page numbers for paraphrases, the page count, the outline depth, and the decimal separator, p-value notation, figure resolution and caption placement (built into tables and figures in Phase A). Resolve with the supervisor before any chapter is drafted.
`[format]` — the answer changes only how the text is set: fonts, spacing, margins, pagination, title page, bibliography layout, citation punctuation. Resolve before the formatting phase (Phase B).
An entry here without a tag counts as `[content]`. A `❓` next to a rule above only points to its entry here.
Two kinds: a rule the guidelines state in two ways or unclearly gets an entry of its own, with the passages and readings; rules the guidelines do not cover at all are grouped, one entry per section and tag, listing their keys.]

- [ ] ❓ [content] `style.block_quote_word_threshold` — [contradictory or unclear: the passages and the competing readings, with their places in the source documents]
- [ ] ❓ [format] `in_text.page_range` — [...]
- [ ] ❓ [content] Style rules — not covered by the guidelines: `style.forbidden_pronouns`, `style.forbidden_evaluative`
- [ ] ❓ [format] Footnotes — not covered by the guidelines: `footnotes.font`, `footnotes.size`, `footnotes.line_spacing`

---

## Resolved questions

[Former open questions, moved here when the answer was written into the rule above (see "Recording answers to open questions" in `.claude/agents/style-resolver.md`). Only entries under "Open questions" block drafting or formatting.]

- [x] [content] `style.forbidden_pronouns` — [answer] [supervisor, via the user, YYYY-MM-DD]
- [x] [content] `numbers.p_values` — n/a — does not occur in this work; reopen if it occurs [user, YYYY-MM-DD]
- [x] [format] Footnotes — as the body text, but 10 pt and single-spaced [provisional, user, YYYY-MM-DD]

---

## Version history

| Date | Version | Change | By |
|------|---------|--------|-----|
| YYYY-MM-DD | 1.0 | Initial extraction | style-resolver |
| YYYY-MM-DD | 1.1 | Resolved ❓ on page-range notation | user (after supervisor input) |
