# Plagiarism Protection & Paraphrasing

**Purpose:** Binding checklist for writer-agent and source-verifier.

---

## 1. Thresholds for verbatim word runs

| Verbatim words | Status | Action |
|---|---|---|
| 1-4 | ✅ uncritical | no action |
| 5-7 | 🟡 polish | acceptable with citation, rewording recommended |
| 8-14 | ⚠️ plagiarism risk | MUST be reformulated |
| ≥ 15 | ❌ serious | MUST reformulate, or use as direct quote in quotation marks |

### Application by source-verifier

Step 8 of verification. `scripts/verbatim_check.py` counts the runs against the extracts' original quotes and the source PDFs: the orchestrator runs it before every chapter verification (in the seminar and presentation workflows, the user does), and the source-verifier rates the sentences from its report. Without the script, the source-verifier counts by eye against the original quote in the extract. A run that crosses a sentence boundary counts as one run; text in quotation marks or a block quote is a direct quote and is not counted.

**Example:**

Original (Author A, 2020, p. 975):
> "The central challenge is the particularly pronounced uncertainty inherent to this early phase."

Text in chapter:
> "The central challenge lies in the particularly pronounced uncertainty inherent to this early phase."

Analysis:
- "the particularly pronounced uncertainty inherent to this early phase" = 9 verbatim words → ⚠️ (8-14 band)
- Only "is" → "lies in" was changed; the sentence structure is transferred wholesale
- Overall rating: ⚠️ — Action: reformulate

---

## 2. Paraphrasing strategies (by effectiveness)

**Apply in this order** — synonym substitution is the weakest strategy and belongs at the end, not the beginning.

### Tier 1: Structural reformulation (most effective)

- Convert active ↔ passive
- Swap main and subordinate clauses
- Split one sentence into two (or merge two into one)
- Reorder lists
- Reverse cause / effect ("because X, therefore Y" → "Y is a consequence of X")

**Example:**

Original:
> "Information asymmetry impedes access to capital providers."

Paraphrase (structural):
> "Access to capital providers is impeded by information asymmetries."

### Tier 2: Convert number formats

- "seven of ten" → "70%"
- "approximately two-thirds" → "approximately 67%"
- "in the past ten years" (source published 2025) → "between 2015 and 2025" (count from the source's publication year, not from today)

No information loss, reliably reduces plagiarism software hits.

### Tier 3: Preserve term, rewrite the surrounding prose

Keep technical terms (changing them shifts terminology), but rewrite the descriptive prose.

**Example:**

Original:
> "Information asymmetry refers to the unequal distribution of information between contracting parties."

Paraphrase:
> "Information asymmetry describes a configuration in which one contracting party holds more information than the other."

### Tier 4: Synonym substitution (least effective)

- "essential" → "significant"
- "challenge" → "problematic situation"

**Important:** NEVER for technical terms. "Information asymmetry" is not a "challenge" — it is a technical term.

---

## 3. Limits of paraphrasing

### What paraphrasing must NOT do

1. **Preserve verbatim runs > 7 words** — even with a citation
2. **Shift meaning** — paraphrase must convey the same statement
3. **Replace technical terms with synonyms** — related terms often have related but distinct meanings (classic: uncertainty ≠ information asymmetry)
4. **Soften or strengthen judgments** — source says "as a rule"; the text must not turn this into "always"

### When to quote directly instead of paraphrasing

Use direct quotes for:
- Definitions established in their exact wording
- Legal language (statutes, contracts)
- Controversial statements where exact wording matters
- Particularly memorable formulations

Format: per `styleguide.md` (`in_text.format_direct`); example only: "[quote]" (Author, Year, p. X)

**Important:** Block quotes apply above a certain word count (check styleguide; typically from 40 words).

---

## 4. Common error patterns

### Pattern 1: Synonym substitution as the only strategy

Bad:
- Original: "The challenge consists in the uncertainty."
- "Paraphrase": "The problematic situation consists in the unpredictability."

More effective:
- "Uncertain market conditions represent a central challenge."

### Pattern 2: Plagiarism despite citation

Citation at the end does not save a verbatim run of 8+ words (here: 12):
> "...**consists in the pronounced information asymmetry between founders and potential capital providers** (cf. Author A et al., 2020, p. 975)."

If the bolded words appear verbatim in the original, the citation is NOT enough.

### Pattern 3: Term-slip via "paraphrasing"

Original: Author A speaks of "uncertainty".
"Paraphrase": Text writes "information asymmetry".

This is not a paraphrase — it is an incorrect term mapping. Flagged as ❌ by source-verifier (verification step 3).

---

## 5. Verification order by source-verifier

1. First Steps 1-7 (content verifications)
2. Then Step 8 (plagiarism check)
3. Then Step 9 (list-citation check)

If Step 8 returns ⚠️ or ❌ (both MUST be reformulated): writer-agent receives immediate feedback containing:
- Original quote (with its extract and quote ID, if it has one)
- Verbatim transferred passage (with the affected word run highlighted)
- Tier suggestion (which paraphrasing tier should be applied)
