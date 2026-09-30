# Long-Form Project Structure

This document describes the long-form variant of cephalo's project structure: phase-based directories, central state files, and the chat closure ritual.

For shorter works (seminar papers, presentations), use the flat structure instead — see the corresponding workflow files.

For projects with separate proposal and defense sub-projects, see `multiproject_structure.md`.

---

## Why a long-form structure?

A bachelor or master thesis runs for months. Over that time:

- The chat history is far longer than any single context window can hold
- Multiple chats happen per chapter, often days or weeks apart
- The author needs to know exactly where they left off
- Decisions made in week 3 must remain accessible in week 20
- The chapter outline shifts as understanding deepens

A flat structure (single `workspace/` directory with chapter files) handles small projects well but loses fidelity at this scale. The long-form structure formalizes the patterns that emerge in long projects.

---

## Directory layout

```
project/
├── CLAUDE.md
├── .claude/agents/                    (10 agents)
├── workflows/                         (workflow configurations)
├── checklists/                        (rule catalogs)
├── templates/                         (template files)
├── scripts/                           (utility scripts)
├── docs/                              (documentation)
│
├── 00_Status.md                       ← central state file (mandatory)
├── 00_Decisions.md                    ← architectural decisions log (append-only)
├── 00_Feedback_log.md                 ← cross-chapter learning log
│
├── styleguide.md                      ← extracted by style-resolver
├── guidelines/                        ← institutional documents
│
├── 01_Proposal/                       (optional — see multiproject for full proposal)
├── 02_Literature/
│   ├── handover.md
│   ├── README.md
│   ├── literature.bib                 (if reference manager integrated)
│   ├── extracts/                      (one .md per source)
│   └── sources/                       (PDFs, etc.)
│
├── 03_Theory_chapters/
│   ├── handover.md
│   ├── README.md
│   ├── chapter_2_*.md
│   ├── chapter_3_*.md
│   └── ...
│
├── 04_Methods/                        (master / empirical only)
│   ├── handover.md
│   ├── README.md
│   ├── design.md
│   └── methods_chapter.md
│
├── 05_Empirical/                      (master / empirical only)
│   ├── handover.md
│   ├── README.md
│   ├── empirical_chapter.md
│   └── data/
│       ├── raw/                       (read-only, never commit personal data)
│       ├── processed/
│       ├── scripts/
│       └── outputs/
│
├── 06_Discussion_Conclusion/
│   ├── handover.md
│   ├── README.md
│   ├── discussion.md
│   └── conclusion.md
│
├── 07_Introduction/                   (written LAST)
│   ├── handover.md
│   ├── README.md
│   └── introduction.md
│
├── 08_Formal_Review/                  (Phase B)
│   ├── handover.md
│   ├── README.md
│   ├── format_reports/
│   └── submissions/
│       └── v_<tag>_<date>.docx
│
├── .gitignore
├── .gitattributes
└── .git/
```

---

## The three central state files

These files live at the project root and form the project's "memory across chats."

### `00_Status.md`

The dashboard. Updated at every chat closure. Contains:

- Project metadata (type, target submission date, current phase)
- Research question
- Chapter status table (what's done, what's pending)
- Page budget tracking
- Open project-wide issues
- Handover chronology

See `templates/status.md`.

### `00_Decisions.md`

Append-only log of architectural and methodological decisions. Each entry has a date, what changed, why, and what's affected.

Why append-only: decisions are part of the project's history. If you overwrite, you lose the trail of why things ended up the way they did. Bad for the thesis defense, where you may be asked to justify changes.

See `templates/decisions.md`.

### `00_Feedback_log.md`

Cross-chapter learning. When a recurring pattern appears (e.g., "writer-agent tends to substitute synonyms in section openings"), log it here. In future chats the orchestrator reads it and passes each entry on to the agents its scope names, so they avoid repeating the pattern.

Append-only: one short entry per pattern (date, where observed, pattern, countermeasure, scope), in chronological order. See `templates/feedback_log.md`.

---

## Phase directories

Each phase gets its own directory with:

- **`handover.md`** — updated at every chat closure for this phase. The next chat in this phase reads this first.
- **`README.md`** — entry document; what is this phase's goal?
- **Phase-specific files** — chapter drafts, extracts, data, etc.

The phase numbering (01, 02, ...) reflects rough chronology, not strict ordering. You may work in multiple phases concurrently (e.g., literature in phase 02 while drafting in phase 03).

### Phase 01_Proposal

Optional within a long-form project. Use this only if you don't have a separate proposal sub-project (multi-project structure).

### Phase 02_Literature

Most front-loaded work happens here:
- Reference manager collection built
- `literature.bib` exported
- One extract per source in `extracts/<citekey>.md`
- All extracts verified by source-verifier

### Phase 03_Theory_chapters

The bulk of writing. One chapter per file, with the workflow's per-chapter procedure.

### Phase 04_Methods (master / empirical only)

Methods chapter, written by methods-agent. Output: `methods_chapter.md`. Precondition: `design.md` exists with the methodological design decision.

### Phase 05_Empirical (master / empirical only)

Empirical chapter, written by writer-agent based on data-agent outputs. Strict raw-data separation:

- `data/raw/` is read-only. Never modify. Never commit personal data (handled via `.gitignore`).
- `data/processed/` and `data/outputs/` are managed by the data-agent.
- `data/scripts/` contains analysis scripts (R, Python, SPSS syntax). Version-controlled.

### Phase 06_Discussion_Conclusion

Synthesis. Two files: `discussion.md` and `conclusion.md`.

### Phase 07_Introduction

**Always written last.** Why: the introduction must reflect the actual content of the work, not the planned content. Plans drift; introductions written first need rewriting anyway.

### Phase 08_Formal_Review

Phase B. Format-verifier and build scripts only. Milestones export to `submissions/`.

---

## The chat closure ritual

At the end of every long-form chat, the orchestrator performs:

1. **Update `<current_phase>/handover.md`** — what was done, open issues, decisions, next chat's recommended start prompt
2. **Update `00_Status.md`** — chapter status table, page count, handover chronology
3. **Append to `00_Decisions.md`** if a new architectural decision was made
4. **Append to `00_Feedback_log.md`** if a recurring pattern was observed
5. **Suggest a Git commit** — message follows the `phase: description` convention

This ritual is not optional. Skipping it means the next chat starts blind. The orchestrator's prompt at chat start explicitly reads these files; if they're stale, the orchestrator works with stale information.

---

## Chat start ritual

At the beginning of every chat, the orchestrator reads:

1. `00_Status.md` — overall state
2. `<current_phase>/handover.md` — last state of this phase
3. `00_Decisions.md` — historical decisions
4. `styleguide.md` — formatting rules
5. `00_Feedback_log.md` — recurring patterns

It then summarizes to the user:

```
## Status check

Current phase: ...
Last handover: ...
Open issues per handover: ...
External blockers: ...
Today's task per handover: ...

Understood — shall I proceed with that?
```

Wait for the user's confirmation before doing actual work. This catches the case where the user wants to do something different than the handover suggested.

---

## Setup checklist for new long-form project

One-time at project start:

- [ ] Run setup script with structure = "Long-form"
- [ ] Place institutional guidelines in `guidelines/`
- [ ] Initialize Git (done by setup script)
- [ ] Run style-resolver to produce `styleguide.md`
- [ ] Resolve the `❓ [content]` items in `styleguide.md` (the `[format]` items before Phase B)
- [ ] Configure reference manager: collection created, BibTeX export to `02_Literature/literature.bib`
- [ ] Initial `00_Status.md` filled with project metadata, research question, page budget
- [ ] First commit: `meta: initial setup`

After that, every chat follows the start and closure rituals.

---

## When to use long-form vs. flat

**Use long-form when any of these apply:**
- Project will run > 4 weeks
- More than 10 chats expected
- Multiple co-authors (not yet supported, but structure prepares for it)
- Empirical work with raw data
- You expect to need to revisit decisions made weeks earlier

**Use flat when:**
- Seminar paper, presentation, short essay
- Single-session or few-session project
- No empirical component
- You're learning the system on a small project before scaling up

When in doubt, use long-form. The overhead is small; the benefits compound.
