# Phase Separation: Content (A) -> Form (B)

This document describes how cephalo separates content work from formatting work into two distinct phases, and why this separation matters.

---

## The problem

In a long writing project (bachelor or master thesis), three categories of revisions accumulate over time:

1. **Content revisions** — improving claims, adding sources, sharpening arguments
2. **Format revisions** — adjusting citation format, page layout, bibliography entries
3. **Mixed revisions** — fixing both at once, often introducing new issues

The third category is the most expensive. When the writer-agent (a capable, costly model) is invoked for what turns out to be a comma fix, you pay top model rates for trivial work. When the writer is invoked for content but accidentally re-formats existing prose, you create new format issues.

---

## The solution: phase separation

cephalo splits the project lifecycle into two distinct phases:

### Phase A: Content

- **Active agents:** writer-agent (capable model), source-verifier (capable model), research-agent, orchestrator
- **Script:** `scripts/verbatim_check.py`, run by the orchestrator before each chapter verification: a content check, which counts the verbatim word runs the source-verifier rates in step 8
- **Goal:** content-stable chapters
- **Start condition:** no open `❓ [content]` items in `styleguide.md` (voice, evaluative wording, citation wording, length); `❓ [format]` items may stay open until the A → B transition
- **Iterations:** typically 30-50 per project
- **Format-verifier role:** flag only critical format errors that would mask content issues; defer the rest

### Phase B: Form

- **Active agents:** format-verifier (fast model), orchestrator, build scripts
- **Goal:** format-compliant final document
- **Iterations:** typically many small passes
- **Writer-agent role:** deactivated; activated only for genuine content corrections that surface during formatting

---

## Why this matters

### Cost reduction

Format work uses fast (cheap) models exclusively, provided Phase B really runs on a fast model (see the next paragraph). A fast model costs a fraction of a capable one; how much this saves on a whole thesis has not been measured. In the long-form trial runs, with one short chapter and one or two format rounds each, the Phase B chats on Sonnet cost 4–6 USD at list prices, about a tenth of the run.

The saving depends on how you run Phase B: `format-verifier` and the orchestrators are defined with `model: inherit`, so they use whatever model the main chat runs. Start Phase B chats on a fast model (for example with `/model`), or pin `format-verifier` to a fast model in its frontmatter; otherwise Phase B runs on your default model. Fast models in this sense are Sonnet and Haiku (`/model sonnet`, `/model haiku`); Phase A needs a capable model such as Opus.

### Quality stability

Content work uses capable models because the judgment required (paraphrasing, source fidelity, term selection) genuinely needs them. Format work uses fast models because the judgment required (does this comma match the styleguide?) doesn't.

### Avoiding regression

When the writer is dormant during Phase B, format fixes don't accidentally rewrite content. The number of "fixed one thing, broke another" cycles drops dramatically.

---

## Transition criteria (A -> B)

The orchestrator transitions the project from A to B when:

1. **All chapters complete** — body, conclusion, AND introduction (introduction is always last)
2. **Source verification ✅** — every chapter passed sentence-by-sentence verification
3. **No outstanding ⚠️, ❌ or ❓ content items** — all flagged content issues resolved (a 🟡 polish flag does not block)
4. **Last 3 iterations were format-only** — empirical signal that content has stabilized: in the last three commits, the changes to the chapter files touched only styleguide-governed items (citations, typography, spacing); state, handover and report files aside. This is not the loop count of the orchestrators, which counts the revisions after findings, each followed by a new verification
5. **All `❓` items in `styleguide.md` resolved** — no open formatting questions

When all criteria are met, the orchestrator:
- Sets `00_Status.md` (long-form) or `workspace/state.md` (flat) -> phase: B
- Deactivates the writer-agent
- Activates the format-verifier as the lead agent
- Begins phase 08_Formal_Review (long-form) or the flat workflow's Phase B steps (`phase_B_form`, then its closing checklist)

### Waiving a criterion

The user may waive criterion 1 (all chapters complete) for chapters the work will not contain, for example the introduction of a practice work, but not for chapters still to be written; and criteria 4 (format-only iterations) and 5 (styleguide questions) for a reason of their own. The orchestrator asks for that reason and proposes none: the waiver is the user's decision, and a reason ready to accept turns it into the orchestrator's. It then records in the decision log (`00_Decisions.md`; flat: `workspace/state.md`) which criteria are waived and why, and transitions. Open `❓ [format]` items in `styleguide.md` are answered at the start of Phase B, before any format work. Criteria 2 (source verification) and 3 (open content items) cannot be waived, nor, in empirical works, the consistency of the methods and data chapters that the master workflows add: while any chapter has an open ⚠️, ❌ or ❓, the project stays in Phase A.

---

## When to roll back from B to A

Sometimes a format pass surfaces a real content issue (e.g., a missing citation reveals a missing claim in the source). When this happens:

1. Pause Phase B
2. Re-activate the writer-agent for the specific fix
3. Run `scripts/verbatim_check.py` on the chapter, then source-verifier on the affected passage
4. Document the rollback in `00_Decisions.md` (long-form) or `workspace/state.md` (flat)
5. Resume Phase B

Rollbacks should be rare. If they happen often, the project transitioned to B prematurely — the criteria above were not actually met.

---

## What "format-only" means

In Phase B, the format-verifier handles:

- Bibliography minus-test (`scripts/bibliography_check.py`)
- List-of-abbreviations derivation (`scripts/abbreviations_extract.py`)
- Pronoun and forbidden-wording checks
- Page-range notation consistency
- Et al. rule consistency
- Edition number consistency across the document
- The hyphenation flag of the export, only if the styleguide's `document.hyphenation` is automatic (the orchestrator sets it with `scripts/docx_postprocess.sh` right after each export)

What it does NOT do:
- Add or remove citations
- Reformulate sentences
- Fix factual errors

These remain Phase A operations.

---

## Practical phase markers

In `00_Status.md`, mark the current phase explicitly:

```markdown
- **Current overall phase:** A
```

becomes

```markdown
- **Current overall phase:** B (transitioned 2026-04-15)
```

This tells the next chat (and the agents within it) immediately what to do and what not to do.

---

## Common errors around phase separation

### Premature transition to B

Symptom: many B -> A rollbacks within the first week of Phase B.
Cause: criteria 1-4 were not actually met; the writer was tired and pushed for transition.
Fix: hold off on transition. Spend more time in A until the "format-only iterations" signal is genuine.

### Resisting transition

Symptom: project stays in A for weeks past the actual stability point. Cost compounds.
Cause: writer feels content could always be slightly better; perfectionism.
Fix: trust the criteria. If they're met, transition. Polish work is a Phase B concern.

### Mixing in Phase B

Symptom: format passes accidentally include sentence rewrites.
Cause: format-verifier overstepping its role, or user prompting for content changes during a format pass.
Fix: keep prompts narrowly scoped to format. If a content issue surfaces, document it, finish the format pass, then handle the content issue in a dedicated A-rollback chat.
