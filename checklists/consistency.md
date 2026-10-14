# Consistency Check

**Purpose:** Verifies consistency within and between chapters.
**Executed by:** source-verifier (cross-chapter checks; in a seminar paper also the final check of Part A and B.2-B.3), orchestrator (final check).
**When:** After every second chapter, plus a final check before submission.

---

## Part A: Cross-chapter consistency (during Phase A)

To be performed by source-verifier after every second chapter.

### A.1 Cross-references

- [ ] Does Ch. X correctly refer to definitions from Ch. Y?
- [ ] Are chapter previews in the introduction (if already written) consistent with actual chapters?
- [ ] Do referenced page numbers (e.g., "as shown in Ch. 2.1, p. 5") still apply?
  - After reorderings or cuts: update references
  - Before submission: manually verify all cross-references

### A.2 Self-plagiarism

- [ ] No verbatim overlaps between chapters (except for definitions intentionally repeated)
- [ ] **Especially between introduction and conclusion:** the conclusion must use its own wording, not paraphrase the introduction
- [ ] The research question is quoted verbatim only once (in the introduction); afterwards only referenced

### A.3 Argumentative thread

- [ ] Is a clear thread visible across chapter boundaries?
- [ ] Do transition sentences at chapter ends connect to the next chapter's opening?
- [ ] No content jumps or gaps between chapters?

### A.4 Term usage

- [ ] Are technical terms used **identically** across all chapters?
  - Typical error: Ch. 2 uses "uncertainty", Ch. 3 uses "information asymmetry" — if both mean the same thing, unify the term
- [ ] No contradictory statements between chapters?
  - Typical error: Ch. 2 defines X as Y; Ch. 5 treats X as Z
- [ ] Abbreviations introduced at first occurrence?

### A.5 Edition consistency (for referenced books)

- [ ] Same author/title cited as the same edition across all chapters?
  - Typical error: Ch. 2 cites edition 8 (p. 145), Ch. 5 cites edition 9 (p. 162). Page numbers differ between editions — mixing them invalidates the citation.
- [ ] Bibliography edition number matches the edition actually consulted?
- [ ] No conflicting entries for the same title in the bibliography (two entries, different editions)?
- [ ] E-book and print edition not silently mixed? If both were consulted, decide on one and note in the bibliography.

---

## Part B: Full-document final check (before submission)

To be performed on the exported document, after the last written chapter (introduction, written last) and the formatting phase: in the flat workflows the closing step F.1, in the long-form workflows the submission step. A seminar paper (`seminar_2agent`) has no formatting phase: in its closing step F.1, the source-verifier checks Part A and B.2-B.3 on the chapter files and the reference list before the export; B.1, B.4 and B.7 come from the format rounds and the user.

### B.1 Indexes

- [ ] **Table of contents** updated (in Word: Ctrl+A then F9)
- [ ] **List of abbreviations:** ONLY abbreviations actually used in the text
  - Automation: `scripts/abbreviations_extract.py`
- [ ] **Bibliography:**
  - All cited sources present
  - No unused entries
  - Automation: `scripts/bibliography_check.py` (minus-test)
- [ ] **List of tables** (if empirical): updated, all tables numbered
- [ ] **List of figures** (if empirical): updated, all figures numbered
- [ ] **List of appendices** (if appendices exist): updated

### B.2 Consistency: introduction <-> body

- [ ] **Introduction reflects the actual content**
  - Research question matches the conclusion?
  - Outline of the work matches the real chapter structure?
  - Methodological framing matches the methods chapter?
- [ ] Introduction contains no claims not delivered later

### B.3 Consistency: body <-> conclusion

- [ ] **Conclusion answers the research question** — does not evade, does not expand the topic
- [ ] Core claims in the conclusion are covered by the body (no new, unsupported assertions)
- [ ] **No self-plagiarism** between introduction and conclusion

### B.4 Formal compliance

- [ ] Page count within range (styleguide.md -> `document.page_count`)
- [ ] Title page fully filled in (no placeholders!)
- [ ] Pagination matches the styleguide (`pagination.front_matter` / `pagination.main_text` / `pagination.position` — see `checklists/format_rules.md`)
- [ ] Hyphenation as specified (styleguide: `document.hyphenation`; in Word: Layout -> Hyphenation)
- [ ] Body alignment matches the styleguide (`body.alignment`)
- [ ] Styleguide check complete (see `checklists/format_rules.md`)

### B.5 Three-way consistency check (presentations only)

- [ ] PPTX <-> PDF export <-> speaker notes contain identical numbers, quotes, statements
- [ ] Pie chart percentages: the labelled values sum to 100% (one decimal, e.g. "0.0%", narrows rounding gaps but does not remove them; note any rounding)
- [ ] Timing test: presentation within the target range your institution or course specifies (check the assignment briefing / styleguide)

### B.6 Git status (long-form / multi-project)

- [ ] `git status` shows no uncommitted changes (everything committed)
- [ ] Final tag set: e.g., `git tag v_final_<date>` or `work_submitted_<date>`
- [ ] DOCX export in `submissions/` committed (via LFS)

### B.7 Manual final check

- [ ] **Visually review printout / PDF** — character errors and bad line breaks are often invisible in Word
- [ ] Mentally rehearse defending each sentence: "Can I justify this?"
- [ ] Declaration of academic integrity signed (if required)
- [ ] Appendix complete (for empirical work: data extracts, codebook, scripts)

---

## Part C: After submission

- [ ] Git tag for final state set
- [ ] Backup of submission (local + cloud)
- [ ] In multi-project structure: `02_Main_Work/` frozen by its submission tag (`v_final_<date>` or `work_submitted_<date>`, which `03_Defense/` checks)
- [ ] Project retrospective: what worked? what didn't? Record it in the project's feedback log (`00_Feedback_log.md`; flat: `workspace/feedback.md`); to keep general patterns for the next project, add them to `docs/error_catalog.md` in your cephalo template folder (a framework update replaces the project's copy of `docs/`)

---

## Output format

The source-verifier or orchestrator returns a structured report:

```markdown
## Consistency check [Part A / Part B]

**Performed:** [date]
**Scope:** [Ch. 2-4 / full document]

### Results

| Category | Status | Findings |
|----------|--------|----------|
| A.1 Cross-references | ✅ / ⚠️ / ❌ | ... |
| A.2 Self-plagiarism | ✅ / ⚠️ / ❌ | ... |
| A.3 Argumentation | ✅ / ⚠️ / ❌ | ... |
| A.4 Terms | ✅ / ⚠️ / ❌ | ... |
| A.5 Editions | ✅ / ⚠️ / ❌ | ... |

### Detailed findings

[Per ⚠️ or ❌: precise location, problem description, proposed fix]

### Recommendation

✅ Work can proceed
⚠️ Minor adjustments recommended (non-blocking)
❌ Correction required before continuing
```

---

## Reference

- Error catalog: `docs/error_catalog.md`
- Format checklist: `checklists/format_rules.md`
- Plagiarism protection: `checklists/plagiarism_protection.md`
