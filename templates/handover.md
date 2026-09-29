# Handover — [phase / chapter], [date]

**Fill out this template at the END of every chat in a long-form phase.**
**File path:** `<phase_directory>/handover.md` (overwrites the previous handover for this phase).

This document is the bridge between chats. The orchestrator at the start of the next chat reads this file first to recover context.

**Active agents in this phase:** [e.g., writer-agent, source-verifier]
**Content/form phase:** [A: content / B: form]

---

## What was achieved in this chat?

[Concrete artifacts produced. Reference files by path.]

- Drafted Ch. 3.1 (`03_Theory_chapters/chapter_3_framework.md`, lines 1-145)
- Verified extracts for sources A, B, C (`02_Literature/extracts/`)
- ...

---

## Open issues

### Technical

- [ ] [open technical issue, e.g., "Bibliography minus-test reports 2 unused entries"]
- [ ] ...

### Content

- [ ] [open content issue, e.g., "Section 3.2 needs additional source for claim about X"]
- [ ] ...

---

## Decisions made (logged separately in 00_Decisions.md)

- [Brief reference to any new entry in `00_Decisions.md`]

---

## Blockers

[External blockers preventing further progress, e.g., waiting for supervisor response, source not yet acquired]

- None / [list]

---

## Next chat: recommended start prompt

[Copy-paste-ready prompt for the next chat. Should reference this handover file and state the next concrete task.]

```
This is a continuation of the [project name] long-form workflow.
Invoke the orchestrator-longform agent for it (defense sub-project: orchestrator-defense).

Please read:
- 00_Status.md
- <phase_directory>/handover.md (this handover)
- 00_Decisions.md
- 00_Feedback_log.md
- styleguide.md (multi-project sub-project: ../00_Shared_Materials/styleguide.md)

Today's task per handover: [specific task here]

Confirm understanding, then proceed.
```

---

## Changed files (Git diff summary)

[Output of `git status --short` (it lists new, still untracked files) and `git diff --stat HEAD`, edited for clarity]

```
03_Theory_chapters/chapter_3_framework.md | +145 lines
02_Literature/extracts/source_a.md        |  +38 lines
02_Literature/extracts/source_b.md        |  +42 lines
00_Status.md                              |    edited
```

---

## Items for 00_Feedback_log.md

[Recurring patterns observed in this chat that should be added to the cross-chapter feedback log]

- [observation, e.g., "Writer-agent tends to substitute synonyms for technical terms in section openings — verify Ch. 4 carefully"]
- [or: "None"]

---

## Suggested Git commit

(In a multi-project sub-project: `git add -A`, so that changes in `../00_Shared_Materials/` are included, and the sub-project as prefix, e.g. `main/[phase]: ...`; see `docs/multiproject_structure.md`.)

```bash
git add .
git commit -m "[phase]: [brief description]"
```

Example:
```bash
git add .
git commit -m "theory: chapter 3.1 complete, sources A-C verified"
```
