# Error Catalog

Common errors observed across many revisions of academic work. Each entry describes the pattern, the consequence, and the agent / check step responsible for catching it.

This catalog is the empirical foundation for the verification steps the agents perform. The entries are deliberately concrete — abstract rules are easier to forget than worked examples.

---

## Top 10 by frequency

| Rank | Error type | Agent | Check step |
|------|-----------|-------|-----------|
| 1 | Paraphrase too close to source (plagiarism risk) | source-verifier | Step 8 |
| 2 | List citation with incorrect page range | source-verifier | Step 9 |
| 3 | Term mismatch between text and source | source-verifier | Step 3 |
| 4 | Incorrect citation convention | format-verifier | styleguide |
| 5 | Missing page numbers for paraphrased citations | format-verifier | styleguide |
| 6 | Forbidden pronoun | format-verifier | styleguide |
| 7 | Secondary citation where primary is accessible | source-verifier | Step 5 |
| 8 | Missing partial citations in multi-part sentences | source-verifier | Step 1 |
| 9 | Unsupported causal claims | source-verifier | Step 6 |
| 10 | Incorrect edition number | source-verifier / format-verifier | consistency A.5 / Step 3 |

---

## 1. Paraphrase too close to source

The text reformulates a source passage but keeps too many original words in the same order. Even with a citation, this triggers plagiarism software.

**Bad paraphrase:** preserves 12+ verbatim words from the source, only swapping minor connectors.

**Good paraphrase:** restructures the sentence (active vs. passive, clause inversion), preserves technical terms, replaces non-technical wording.

**Threshold:** verbatim runs longer than 7 words (8-14) from the same source flag a warning; 15+ flags an error. For the full band table and special cases, see `checklists/plagiarism_protection.md`.

---

## 2. List citation with incorrect page range

A list of items receives a single citation with a page range that does not actually cover all items.

**Bad:** "...land, buildings, machinery, operating costs, and reserves (Author A, 2024, pp. 309–313)" — when the actual locations span pp. 307, 309, 310, 312, 313 (the cited range starts at 309, missing p. 307).

**Good:** itemized locations per element of the list.

---

## 3. Term mismatch between text and source

The text uses a related but distinct technical term that the source does not use.

**Example:** Source says "uncertainty" (no information available to anyone). Text says "information asymmetry" (one party knows more than another). These are conceptually different.

**Detection:** the research-agent must record both "terms IN source" and "terms NOT IN source" lists. The source-verifier checks the text against these.

---

## 4. Incorrect citation convention

The text uses a citation format that does not match the institution's style guide.

Common errors: en-dash vs. hyphen in page ranges, Oxford comma when forbidden, "p." vs. "S." vs. nothing, missing non-breaking space before page number.

**Detection:** format-verifier reads rules from `styleguide.md`.

---

## 5. Missing page numbers for paraphrased citations

APA 7 does not require page numbers for paraphrases. Many European institutions do.

**Detection:** format-verifier reads the page-number policy from `styleguide.md`. The style-resolver extracts this from institutional examples — APA examples often omit page numbers, which can mislead the resolver. Verify the extracted policy.

---

## 6. Forbidden pronouns

Most academic style guides forbid first-person and impersonal pronouns ("I", "we", "one", "you" or their equivalents in other languages).

**Detection:** format-verifier with a styleguide-configured list of forbidden pronouns. Detection is mechanical; the writer-agent should avoid these from the start.

---

## 7. Secondary citation where primary is accessible

Source A on page X cites Source B. The text cites this as if it were Source A's own claim, ignoring that B exists and is accessible.

**Bad:** Citing Author A (2021), where Author A is itself citing Author B (1984), and Author B is in the institutional library.

**Good:** Cite Author B directly. If B is inaccessible: "(Author B, 1984, as cited in Author A, 2021, p. 81)".

**Detection:** research-agent must mark secondary citations in extracts. Source-verifier rechecks.

---

## 8. Missing partial citations in multi-part sentences

A sentence makes two or three substantive claims, with a single citation at the end. The reader cannot tell which claim is supported.

**Bad:** "Start-up financing differs from regular finance, requires specialized intermediaries, and faces higher capital costs (Author A, 2020, p. 980)."

**Good:** "Start-up financing differs from regular finance (Author A, 2020, p. 980). It requires specialized intermediaries (Author B, 2024, p. 245) and faces higher capital costs (Author C, 2019, p. 12)."

---

## 9. Unsupported causal claims

The text asserts a causal relationship the source does not support.

**Source:** "Firms that grow rapidly tend to attract more venture capital."
**Bad text:** "Rapid growth causes increased venture capital availability."

"Tend to attract" describes a correlation; "causes" asserts causation.

**Indicators of trouble:** "Therefore...", "This explains why...", "As a result...", "Consequently..." — often appear when the writer has interpreted beyond the source.

---

## 10. Incorrect edition number

The text cites a source as edition X in some places and edition Y in others. The bibliography lists yet a third edition.

**Why this happens:** Library copies, e-book versions, and physical copies are often different editions with different page numbers.

**Detection:** source-verifier with `checklists/consistency.md` (A.5, after every second chapter; the orchestrator repeats the checklist in the final check), and format-verifier in Phase B (edition consistency, step 3 of its checks). Look for: same author with different years across the document, bibliography year not matching in-text year, mixed editions in the bibliography itself.

---

## Cross-cutting traps

### File disguise

Institutional source files sometimes have misleading names. A `.pdf` file may actually be a ZIP archive containing JPEG scans. The research-agent must inspect file contents (`file <path>`), not trust filenames.

### E-book vs. print pagination

E-book page numbers often differ from print pagination. The research-agent must record which version is being cited and use print pagination when available — this is what the bibliography typically lists.

### Hidden page break differences

Two PDF copies of the same source may have different page breaks. When the research-agent records p. 87 from an e-book, the source-verifier may not be able to confirm without access to the same copy.

**Mitigation:** record verbatim quotes alongside page numbers. If the page differs, the quote allows the verifier to find the actual location.

---

## Continuous improvement

When an agent catches an error not represented above, append it. Each entry should contain:

- The pattern (in one sentence)
- A bad example
- A good example
- The detection step (which agent, which step)

Over time, the catalog becomes the institutional memory of the project.
