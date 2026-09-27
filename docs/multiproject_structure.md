# Multi-Project Structure

This document describes the multi-project variant of cephalo's project structure: separate sub-projects for proposal, main work, and defense, sharing one set of materials.

For single long-form projects, see `longform_structure.md`.

---

## When to use multi-project

A bachelor or master thesis often consists of three distinct examination assignments:

| Sub-project | Purpose | Audience | Submission | Frozen after |
|-------------|---------|----------|------------|--------------|
| **Proposal** | Application to supervisor, structural plan | Supervisor | Before main work begins | Acceptance |
| **Main work** | The actual scholarly work | Examination office | Submission deadline | Submission |
| **Defense** | Oral defense, discussion of results | Examining committee | Defense date | (oral; no freeze) |

Each has different goals, different audiences, and different freeze points. Treating them as one project creates two specific problems:

1. **Temptation to retroactively edit the proposal** to match what the work became. Academically problematic.
2. **Mixing references** — the defense should work from the *submitted* version of the work, not a "what I'd write today" version.

The multi-project structure makes the temporal separation structural: each sub-project is a separate scope, with its own state files and freeze point. Shared materials (citation guide, formatting rules) live in one place and are used by all three.

---

## Directory layout

```
project_root/                          ← Git repo root (one repo for all)
│
├── CLAUDE.md
├── .claude/agents/
├── workflows/
├── checklists/
├── templates/
├── scripts/
├── docs/
│
├── 00_Shared_Materials/               ← shared by all three sub-projects
│   ├── guidelines/
│   ├── course_materials/
│   ├── styleguide.md                  (one styleguide for all)
│   └── README.md
│
├── 01_Proposal/                       ← sub-project 1
│   ├── 00_Status.md
│   ├── 00_Decisions.md
│   ├── 00_Feedback_log.md
│   ├── 01_Research/
│   ├── 02_Outline/
│   ├── 03_Drafting/
│   └── 04_Submission/
│       └── proposal_final_<date>.docx
│
├── 02_Main_Work/                      ← sub-project 2
│   ├── 00_Status.md
│   ├── 00_Decisions.md
│   ├── 00_Feedback_log.md
│   ├── 01_Proposal_Reference/         ← copy of accepted proposal (read-only)
│   ├── 02_Literature/
│   ├── 03_Theory_chapters/
│   ├── 04_Methods/                    (master / empirical only)
│   ├── 05_Empirical/                  (master / empirical only)
│   ├── 06_Discussion_Conclusion/
│   ├── 07_Introduction/
│   └── 08_Formal_Review/
│       └── submissions/
│           └── v_final_<date>.docx
│
├── 03_Defense/                        ← sub-project 3
│   ├── 00_Status.md
│   ├── 00_Decisions.md
│   ├── 00_Feedback_log.md
│   ├── 01_Slides/
│   ├── 02_Speaker_Notes/
│   ├── 03_Defense_Prep/
│   ├── 04_Handout/
│   ├── 05_Rehearsals/
│   └── 06_Defense_Day/
│
├── .gitignore
├── .gitattributes
└── README.md                          ← cephalo's README (replaced on template updates)
```

The `01_`, `02_`, `03_` numbering enforces meaningful sort order: proposal first (chronologically), main work next, defense last.

---

## The three sub-projects in detail

### Sub-project 1: Proposal

**Purpose:** Application to the supervisor. Demonstrates that you've grasped the research question and have a realistic plan.

**Typical size:** 3-5 pages.
**Workflow:** `proposal_workflow.yaml`

**Phases within the proposal sub-project:**
1. `01_Research` — initial literature scan, identify research gap
2. `02_Outline` — chapter structure, methodological framing
3. `03_Drafting` — proposal text
4. `04_Submission` — final version for the supervisor

**Important:** After acceptance, the proposal is "frozen". A copy of the final proposal goes into `02_Main_Work/01_Proposal_Reference/` — there it is reference, no longer a working document.

### Sub-project 2: Main Work

**Purpose:** The actual scholarly work.

**Workflow:** `bachelor_5agent_longform.yaml` or `master_7agent_longform.yaml`

**Special characteristic:** the proposal is read-only in `01_Proposal_Reference/`. When the work deviates from the proposal (which is normal), document the deviation in `00_Decisions.md` — not by editing the proposal itself.

### Sub-project 3: Defense

**Purpose:** Preparation for the oral defense. Unlike the proposal and main work, the *output* is not a document — it is your performance in the exam. The files (slides, notes, cheat sheets) are tools, not the assignment itself.

**Workflow:** `defense_workflow.yaml`

**Phases:**
1. `01_Slides` — PPTX presentation
2. `02_Speaker_Notes` — what to say per slide
3. `03_Defense_Prep` — anticipate critical questions, know weaknesses of your own work
4. `04_Handout` — optional two-page summary
5. `05_Rehearsals` — practice runs
6. `06_Defense_Day` — final checklist, emergency notes

**Important:** the defense happens AFTER submission. The work is frozen at this point — you cannot change it. Defense preparation works from the submitted version.

---

## `00_Shared_Materials/` — shared usage

This directory lives once at the top level and is read by all three sub-projects. No duplicates.

### Contents

- **`guidelines/`** — institutional documents (citation guide, formatting rules, examination regulations)
- **`course_materials/`** — supplementary course material (syllabi, lecture slides). The assignment briefing and the examination regulations go into `guidelines/`: the pre-check and the style-resolver read only that folder.
- **`styleguide.md`** — one styleguide for all sub-projects

### The style-resolver in multi-project setups

The style-resolver runs **once per institution / course**, not once per sub-project. The output (`styleguide.md`) lives in `00_Shared_Materials/styleguide.md`.

The three sub-project orchestrators read this central styleguide. When the institution updates its citation guide:

1. Place the new version in `00_Shared_Materials/guidelines/`
2. Run the style-resolver again
3. Git commit: `meta: styleguide updated to guideline version 2.1`
4. All three sub-projects automatically use the new version

### Conflict case: differing requirements

If, for example, the defense uses a different citation convention (rare but possible), use a sub-project-specific override file:

```
03_Defense/
└── styleguide_override.md       ← sub-project-specific deviations
```

The defense orchestrator then reads:
1. First `00_Shared_Materials/styleguide.md`
2. Then `03_Defense/styleguide_override.md` as supplement

**Rule:** use override only when there is a real, documented deviation. By default, the central styleguide applies.

---

## Git setup for multi-project

**One Git repo for the project root.** All three sub-projects and the shared materials are part of the same repo.

The setup script handles `.gitignore` and `.gitattributes` automatically. Commit conventions extend the standard format with a sub-project prefix:

```
proposal/research: initial literature scan complete
proposal/submission: final version v1 sent to supervisor
main/theory: chapter 3 first draft
main/formal: bibliography minus-test passed
defense/slides: structure draft, 12 slides
defense/prep: critical questions catalogued
meta: styleguide updated to guideline version 2.1
meta: proposal copied to main/01_Proposal_Reference/
```

Sub-project prefix: `proposal`, `main`, `defense`, or `meta` for cross-project changes.

### Tags for milestones

```bash
git tag -a proposal_accepted_<date> -m "Proposal accepted by supervisor"
git tag -a work_submitted_<date> -m "Main work officially submitted"
git tag -a defense_passed_<date> -m "Defense passed"
```

---

## Working in Claude Code

**Don't open the project root in Claude Code.** Open the active sub-project:

| Active phase | Open in Claude Code |
|--------------|---------------------|
| Working on proposal | `01_Proposal/` |
| Working on main work | `02_Main_Work/` |
| Working on defense | `03_Defense/` |

**Why:** Claude Code uses the opened directory as context. Opening the root exposes all three sub-projects at once — distraction and risk (e.g., accidentally editing the frozen proposal while writing the main work).

### Access to shared materials

The three sub-projects read the shared materials one level up, in `../00_Shared_Materials/` (guidelines, course materials, styleguide), just as they read the framework folders `../templates/`, `../checklists/`, `../scripts/` and `../workflows/`. No link or copy is involved: a change to the styleguide reaches all three sub-projects at once, on every system, and Windows needs neither Developer Mode nor an elevated shell. Claude Code, opened on a sub-project, may ask for permission before it reads or writes files outside that folder; allow it. For reading, one of the prompt's options allows `00_Shared_Materials/` for the whole project, so Claude Code does not ask again for each file.

**Projects set up with an earlier cephalo version** have a `shared/` link or copy in each sub-project (in a clone without symlink support, a small text file of that name). The agents no longer use it, and re-running setup names it in "Next steps": delete the three `shared/` entries in Explorer or Finder, which removes a link without touching `00_Shared_Materials/`. On the command line, deleting a link can delete the contents of `00_Shared_Materials/` too, for example `rm -rf 01_Proposal/shared/` (with the trailing slash) or `Remove-Item -Recurse` in Windows PowerShell 5.1. If an entry is a copy, first move anything you changed there (for example a styleguide written into `<sub-project>/shared/styleguide.md`) to `00_Shared_Materials/`.

### Agent assignment per sub-project

| Sub-project | Orchestrator | Workflow config |
|-------------|--------------|-----------------|
| Proposal | `orchestrator-longform` | `proposal_workflow.yaml` |
| Main work | `orchestrator-longform` | `bachelor_5agent_longform.yaml` or `master_7agent_longform.yaml` |
| Defense | `orchestrator-defense` | `defense_workflow.yaml` |

---

## Central vs. sub-project-specific state files

Each of the three sub-projects has its **own** state files:

- `01_Proposal/00_Status.md`
- `02_Main_Work/00_Status.md`
- `03_Defense/00_Status.md`

This is intentional, because the sub-projects are independent units. Cross-references are made explicit:

**Example: decision log in the main work**

```markdown
## 2026-05-15: Deviation from proposal outline

- **Old (proposal):** Ch. 3 covers signaling and agency theory
- **New (main work):** Ch. 3 covers only agency theory; signaling dropped
- **Rationale:** depth beats breadth; signaling would have been < 1 page
- **Affected:** Ch. 3, conclusion, introduction
- **Proposal reference:** see 01_Proposal_Reference/proposal_final_2026-03-15.docx, outline p. 4
```

The reference to `01_Proposal_Reference/` makes clear: the proposal is referenced, not modified.

---

## Setup checklist for new multi-project

One-time at project start:

- [ ] Run setup script with structure = "Multi-project"
- [ ] Place institutional guidelines in `00_Shared_Materials/guidelines/`
- [ ] Place supplementary course material in `00_Shared_Materials/course_materials/` (the assignment briefing belongs in `guidelines/`)
- [ ] Initialize Git (done by setup script)
- [ ] Run style-resolver once -> `00_Shared_Materials/styleguide.md`
- [ ] Reference manager collection for the main work, auto-export to `02_Main_Work/02_Literature/literature.bib`
- [ ] Initial `00_Status.md` in all three sub-projects (done by setup script from templates)
- [ ] Project overview in a root file of your own (e.g. `00_Project_overview.md`): the root `README.md` is cephalo's and is replaced when you update the template

Per sub-project start:
- [ ] Choose sub-project-specific workflow
- [ ] First chat in the first phase of the sub-project

---

## Typical timeline

```
Months 1-2: Proposal sub-project active
├── Proposal written
├── Submitted to supervisor
├── Optional revision
└── Acceptance -> proposal frozen

Months 3-8: Main work sub-project active
├── Proposal copy moved to 01_Proposal_Reference/
├── Literature, chapters, empirical work
├── Formal review phase
├── Submission
└── Main work frozen

Months 8-9: Defense sub-project active
├── Slides built from submitted main work
├── Defense preparation
└── Defense

Generally only one sub-project is active at a time.
```

Parallel operation is the exception, and the defense cannot overlap the main work: `defense_workflow.yaml` step 0.1 stops until the main work's submission tag (`v_final_<date>` or `work_submitted_<date>`) exists.

---

## Master / dissertation projects

The structure works analogously for master theses and dissertations:

```
project_root/
├── 00_Shared_Materials/
├── 01_Proposal/
├── 02_Main_Work/                   ← named the same way
└── 03_Defense/
```

For dissertations, additional sub-projects may be added (e.g., `04_Publications/` for papers written in parallel), but the principle is the same.

---

## References

- Long-form basics: `docs/longform_structure.md`
- Proposal workflow: `workflows/proposal_workflow.yaml`
- Defense workflow: `workflows/defense_workflow.yaml`
- Git introduction: `docs/git_introduction.md`
