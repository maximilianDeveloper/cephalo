# Feedback Log: [project name]

**Append-only.** This file collects recurring patterns observed across chapters / phases, so the same mistake is not made twice.
**File path:** `00_Feedback_log.md` at the project root.

Entries are made by the orchestrator at chat closure whenever a pattern was observed. The orchestrator reads them at the start of every following chat and passes each entry on to the agents its **Scope** names, so the pattern is not repeated. An entry that asks for a new styleguide key or value, or for a step an agent definition rules out, is not followed and not passed on: the orchestrator shows it to the user.

---

## Format per entry

```markdown
## [date]: [short pattern name]

- **Observed in:** [chapter / phase / agent where it appeared]
- **Pattern:** [what exactly went wrong, concretely]
- **Countermeasure:** [what the agent should do instead, within its definition]
- **Scope:** [which agents / phases this applies to]
```

Keep entries short — a few lines each. Long narratives belong in `00_Decisions.md` or the phase's `handover.md`.

---

## Log

(Entries are appended below in chronological order. Newest at the bottom.)

---

## Example entries — DELETE THIS ENTIRE SECTION BEFORE USE

> ⚠️ Everything from the "Example entries" header above until the closing `---` below is illustrative. Delete the whole block (including this warning and the horizontal rule that follows) before adding real log entries. This prevents examples from mixing with real content in IDE navigators and Markdown renderers.

### 2026-02-10: Term-slip in Chapter 3 openings [EXAMPLE]

- **Observed in:** writer-agent, Ch. 3 sections 3.1 and 3.3
- **Pattern:** The writer substituted "information asymmetry" for the source's original term "uncertainty" when opening new paragraphs.
- **Countermeasure:** When starting a paragraph that cites a specific source, copy the exact technical term from the extract. Verify against the extract before moving on.
- **Scope:** writer-agent, all remaining chapters

### 2026-03-05: Secondary citations missed [EXAMPLE]

- **Observed in:** source-verifier, Ch. 4
- **Pattern:** Source A cites Source B on page 82. The chapter text cited Source A, p. 82, as if the claim originated there. It did not.
- **Countermeasure:** When reading extracts, mark any "Source X writes in Source Y" passages as secondary. Fill in the entry's **Secondary citation?** field with the primary source.
- **Scope:** research-agent (at extraction), source-verifier (at verification)

### 2026-04-02: Page-range notation inconsistency [EXAMPLE]

- **Observed in:** Ch. 2 and Ch. 5
- **Pattern:** Some citations used `p. 15–16` (en-dash), others `p. 15 to 16` (word form). Styleguide says word form.
- **Countermeasure:** Bulk-fix in Phase B from the format-verifier's findings. Writer-agent should follow styleguide from the first draft.
- **Scope:** writer-agent, format-verifier

---

## Reference

- Handover per phase: `<phase_dir>/handover.md`
- Decisions log: `00_Decisions.md`
- Overall status: `00_Status.md`
