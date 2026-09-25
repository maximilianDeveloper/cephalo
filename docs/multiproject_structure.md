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
│   ├── shared/                        ← symlink to ../00_Shared_Materials
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
│   ├── shared/                        ← symlink to ../00_Shared_Materials
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
│   ├── shared/                        ← symlink to ../00_Shared_Materials
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

The three sub-projects need access to `00_Shared_Materials/` even when opened individually. The setup script creates a `shared/` symlink in each sub-project pointing to `../00_Shared_Materials`.

**On Windows:** symlink creation requires either Administrator privileges OR Developer Mode enabled (Settings -> For developers -> Developer Mode: on). This applies to both setup scripts. Behavior differs in how the failure is surfaced:

- **`setup.ps1`** (PowerShell): tries `mklink` first (enough with Developer Mode), then `New-Item -ItemType SymbolicLink` (in Windows PowerShell 5.1 this needs elevation even with Developer Mode on), and falls back to copying only if both fail; the warning shows the `New-Item` error.
- **`setup.sh`** (Git Bash): `ln -s` silently succeeds but produces a directory copy instead of a real symlink. The setup script detects this after the fact by checking whether a real symlink exists, and warns accordingly.

**Fallback if symlinks fail:** copy `00_Shared_Materials/` into each sub-project. Downside: when the styleguide updates, you must update three copies.

**Diagnosing the fallback state** — run from a sub-project directory:

PowerShell:
```powershell
Get-Item shared | Select-Object Name, LinkType, Target
```
If `LinkType` is `SymbolicLink`, the link worked. If it is empty, the setup fell back to a copy.

Git Bash:
```bash
readlink shared
```
Prints the target if it is a symlink. Empty output means fallback.

**Re-syncing shared materials manually** (only needed if the fallback was used):

PowerShell:
```powershell
# Run from the multi-project root
foreach ($sub in @("01_Proposal", "02_Main_Work", "03_Defense")) {
    # Skip a real link: it is already current, and Windows PowerShell 5.1 can
    # delete the link target's contents (00_Shared_Materials) on Remove-Item -Recurse.
    if ((Get-Item "$sub\shared" -Force -ErrorAction SilentlyContinue).LinkType) { continue }
    if (Test-Path "$sub\shared") {
        Remove-Item "$sub\shared" -Recurse -Force
    }
    Copy-Item -Path "00_Shared_Materials" -Destination "$sub\shared" -Recurse
}
```

Git Bash:
```bash
# Run from the multi-project root
for sub in 01_Proposal 02_Main_Work 03_Defense; do
    [ -L "$sub/shared" ] && continue    # real symlink: already current
    rm -rf "$sub/shared"
    cp -r 00_Shared_Materials "$sub/shared"
done
```

Re-run this after every change to `00_Shared_Materials/`, especially after styleguide updates.

In the copy state, change the guidelines and the styleguide (including answers to `❓` items) only in `00_Shared_Materials/`, never in a sub-project's `shared/` copy: both the re-sync above and deleting the copies to switch to links (below) discard anything that exists only in a copy. If a styleguide was written into `<sub-project>/shared/styleguide.md`, move it to `00_Shared_Materials/` first.

**Recommended fix:** enable Developer Mode once. The setting persists. On Git Bash, additionally set `MSYS=winsymlinks:nativestrict` in your shell profile so `ln -s` produces real symlinks on the first try. Existing `shared/` copies stay copies: re-running setup skips them as existing, so delete the three copies first (`01_Proposal/shared`, `02_Main_Work/shared`, `03_Defense/shared`), then re-run setup to create the links.

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
- [ ] Symlinks in each sub-project to `00_Shared_Materials/` (done by setup script if Developer Mode is enabled or the shell is elevated — in Git Bash also with `MSYS=winsymlinks:nativestrict`; otherwise the copy-fallback applies — see "Access to shared materials" above)
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

Parallel operation is possible (e.g., preparing defense slides while the main work is still in formal review), but not the norm.

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
