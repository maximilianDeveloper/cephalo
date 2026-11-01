# CLAUDE.md

This file is the entry point for Claude Code when working in a cephalo project. It describes the system's architecture and where to find specific components.

## What is cephalo?

cephalo is a multi-agent system for academic writing. It coordinates specialized agents through the lifecycle of a scientific work — proposal, research, drafting, verification, formatting, defense.

See `README.md` for a full overview.

## Project structure

When a user opens a project in Claude Code, the structure depends on which project variant was set up. Three variants are supported:

### Flat structure (seminar papers, presentations, flat-variant theses)
```
project-root/
├── CLAUDE.md                    ← this file
├── .claude/agents/              ← agent definitions
├── workflows/                   ← workflow configurations
├── checklists/                  ← rule catalogs
├── templates/                   ← template files
├── scripts/                     ← utility scripts
├── docs/                        ← documentation
├── styleguide.md                ← extracted formatting rules (generated)
└── workspace/
    ├── sources/
    │   ├── _guidelines/         ← institutional guideline documents
    │   └── extracts/            ← structured source extracts
    ├── output/
    │   ├── chapters/            ← chapter drafts
    │   └── slides/              ← presentations only
    ├── methods/                 ← empirical master/dissertation only
    ├── data/                    ← empirical master/dissertation; presentations (chart data)
    │   ├── raw/                 ← read-only, never modified
    │   ├── processed/
    │   ├── scripts/             ← analysis scripts (R, Python, etc.)
    │   └── outputs/             ← generated tables and figures
    └── state.md                 ← current project state
```

### Long-form structure (bachelor / master theses)
```
project-root/
├── CLAUDE.md
├── [...agent files as above]
├── guidelines/                  ← institutional documents
├── styleguide.md                ← extracted formatting rules
├── 00_Status.md                 ← central status document
├── 00_Decisions.md              ← architectural decisions log (append-only)
├── 00_Feedback_log.md           ← cross-chapter learning
├── 01_Proposal/                 ← optional, see multi-project for full workflow
├── 02_Literature/               ← each phase has handover.md
├── 03_Theory_chapters/
├── 04_Methods/                  ← empirical works only
├── 05_Empirical/                ← empirical works only
├── 06_Discussion_Conclusion/
├── 07_Introduction/             ← written last
└── 08_Formal_Review/            ← formatting phase (Phase B)
```

### Multi-project structure (with proposal and defense)
```
project-root/
├── CLAUDE.md
├── [...agent files]
├── 00_Shared_Materials/
│   ├── guidelines/              ← shared institutional documents
│   └── styleguide.md            ← one styleguide for all sub-projects
├── 01_Proposal/                 ← independent sub-project, frozen after acceptance
├── 02_Main_Work/                ← independent sub-project, frozen after submission
└── 03_Defense/                  ← independent sub-project
```

Each sub-project has its own `00_Status.md`, `00_Decisions.md`, and phase directories. The sub-projects read the shared materials in `../00_Shared_Materials/` directly; a `shared/` link or copy in a sub-project, left from an earlier cephalo version, is not used.

## Agent locations

All agents are in `.claude/agents/`. There are three orchestrators:

- `orchestrator.md` — for flat structures
- `orchestrator-longform.md` — for long-form and multi-project structures
- `orchestrator-defense.md` — specialized for defense preparation, knows the main work is frozen

Non-orchestrator agents (`research-agent`, `writer-agent`, `source-verifier`, `format-verifier`, `style-resolver`, `methods-agent`, `data-agent`) are shared across all structures.

The orchestrators invoke these agents themselves through the `Agent` tool; the `Agent(...)` entry in each orchestrator's `tools:` line names the agents it is meant to call. A session can also run as an orchestrator: `claude --agent orchestrator-longform`. Claude Code enforces the `Agent(...)` list only in that mode; an orchestrator invoked as a subagent may call any agent. Seminar papers and presentations have no orchestrator: Claude in the main chat coordinates their agents, as the `main_session` block of the workflow file says.

Each agent definition includes its own file path conventions in a `File paths` section. Agents must be self-contained: Claude Code may pass this CLAUDE.md to subagents as well, but an agent definition must not depend on it.

## Workflow selection

Workflows are in `workflows/`. Each workflow is a YAML file that describes a sequence of agent invocations and validation steps.

| Work type | Flat variant | Long-form variant |
|-----------|--------------|-------------------|
| Seminar paper | `seminar_2agent.yaml` | (not applicable — too small) |
| Presentation | `presentation_3agent.yaml` | (not applicable) |
| Bachelor thesis | `bachelor_5agent.yaml` | `bachelor_5agent_longform.yaml` |
| Master thesis | `master_7agent.yaml` | `master_7agent_longform.yaml` |

Multi-project setups additionally use:
- `proposal_workflow.yaml` for the proposal sub-project
- `defense_workflow.yaml` for the defense sub-project
- The main work sub-project uses the corresponding long-form workflow

## Style and formatting rules

**Critical architectural principle:** Formatting rules (citation format, page numbering, heading sizes, etc.) are not hardcoded in agent prompts. They live in `styleguide.md`, which is generated by the `style-resolver` agent from whatever institutional guidelines the user provides.

Agents consult `styleguide.md` as their single source of truth for formatting. If `styleguide.md` lacks a rule, the agent flags this rather than guessing.

The `style-resolver` runs once per project during setup (or when guidelines change). See `.claude/agents/style-resolver.md` for details.

## The content / formatting phase split

Long-form works go through two distinct phases:

**Phase A (Content):** Writer and source-verifier agents (capable models) iterate on substance until the chapters are stable. Before each chapter verification, the orchestrator runs `scripts/verbatim_check.py`, which counts the verbatim word runs the source-verifier rates.

**Phase B (Formatting):** format-verifier and utility scripts (fast models) iterate on presentation, citations, bibliography and abbreviation checks. The writer agent is dormant unless a real content issue surfaces.

This split keeps Phase B cheap, provided the Phase B chats run on a fast main model: `format-verifier` and the orchestrators inherit the chat's model. How much it saves on a whole thesis has not been measured. See `docs/phase_separation.md`.

## Mechanical guardrails

Setup installs a Claude Code hook, the cephalo guard (`scripts/cephalo_guard.py`, run from `.claude/settings.json` through `scripts/cephalo_guard.sh`; the template is `templates/claude_settings.json`). It sees some tool calls before they run and denies a few slips the definitions forbid: a shell command that writes a file's text, a write outside the project, `python3` on Windows, a redirect in the PowerShell tool, `state_check.py` through a pipe, the coordinator's edit of a saved report and the main chat's next agent call before it has read a report it saved back whole; and, as a rule of its own, a change to the hook settings or to `scripts/`, which only the user makes. A denial names the rule, the definition that holds it and what to do instead: do that, with the tool it names, and do not get around the check. The definitions stay the rule, and no agent definition may depend on the guard: a project without it works the same. The user switches rules off in `.claude/settings.local.json` (`docs/scripts.md`, "cephalo guard").

## Universal rules (apply in every project)

1. **Preserve original quotes, not just page numbers.** Source extracts must contain verbatim text, enabling downstream verification.
2. **Technical terms are sacred.** If a source uses term *X*, the text must also use *X* — not a synonym the source does not use.
3. **Inspect file contents, not filenames.** Institutional source documents sometimes have misleading names.
4. **`styleguide.md` is the truth for formatting.** No hardcoded rules in agent prompts.
5. **A citation without an accessible source is not a citation.** The setup checklist verifies source accessibility.

## When to ask the user

Agents should ask rather than guess when:

- A guideline rule is ambiguous or contradictory in the source documents
- A source is cited in the text but the underlying file is not accessible
- A decision would have cross-chapter implications (always log in `00_Decisions.md`; flat projects: the decision log in `workspace/state.md`)
- The setup has open `❓` items in `styleguide.md` (`[content]` items block drafting, `[format]` items block the formatting phase)

## Platform caveats

### Encoding on Windows consoles

The Python scripts print Unicode symbols (`⚠️`, `✅`). On German Windows installations with CP1252 consoles, this would raise `UnicodeEncodeError`. The scripts reconfigure stdout to UTF-8 at startup, which handles this. They need Python 3.9 or later; if you see `UnicodeEncodeError` anyway, set `PYTHONIOENCODING=utf-8` and run again.

## Reference

Full specification: see `docs/` directory. Architecture philosophy: see `README.md`.
