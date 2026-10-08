# cephalo

**A multi-agent system for scientific writing.**

cephalo helps students and researchers produce high-quality academic work by orchestrating specialized AI agents through the lifecycle of a thesis, paper, or presentation. The system enforces source fidelity, plagiarism-safe paraphrasing, and consistent formatting — adapted dynamically to whatever citation guidelines and institutional rules apply to the user.

The name is short for *cephalopod* — one orchestrator, many specialized arms (more on the name at the end of this file).

**Getting started:** [`docs/setup_guide.md`](docs/setup_guide.md) shows the setup step by step, with screenshots and without command-line knowledge; the Quick start below describes the same in text.

---

## Status

**Early stage.** The system has been developed and refined through actual coursework (bachelor-level) across multiple projects and iterations. It works and is stable enough to use productively — expect the rough edges typical of an early release, and please report them via the project's GitHub issues.

**What the trial runs cover.** Besides CI on Linux, macOS and Windows, the releases were tried out in unattended trial runs on Windows with fictional material, the student played by a second model: the bachelor workflow in the flat structure (three runs) and in the long-form structure (four runs, each through the content phase and a formatting phase on a fast model). Not yet through such a run: the master workflows with the methods-agent and data-agent, the multi-project structure with proposal and defense, seminar papers and presentations, and an agent run on macOS.

If you are reading this as an early adopter: welcome. Feedback and improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how to report issues and contribute. Changes are tracked in [CHANGELOG.md](CHANGELOG.md).

---

## What cephalo does

You point cephalo at a writing project — a seminar paper, a thesis, a conference presentation — and it helps you work through it systematically. Concretely:

- **Agents read your sources** and produce structured extracts with original quotes, page numbers, and term-usage notes
- **Agents write draft sections** based on those extracts, adhering to whatever style guide your institution mandates
- **Agents verify claims** sentence-by-sentence against the original sources, catching paraphrasing errors, secondary citations, and plagiarism risks
- **Agents enforce formatting** dynamically — citation styles, page numbering, bibliography conventions — based on guideline documents you provide
- **You stay in control** of research questions, outlines, methodological choices, and all substantive editorial decisions

cephalo is a sparring partner and a mechanic, not an author. Every sentence in the final work remains yours to defend.

To make that concrete, this is the kind of finding the source-verifier produces (illustrative example):

```
[source-verifier] chapter2_draft.md, sentence 14:
  Text:   "Transaction costs fall significantly for small firms."
  Source: Example & Author (2021, p. 43): "transaction costs decline
          moderately for small and medium-sized firms"
  Issue:  overstatement ("significantly" vs. "moderately"); scope
          narrowed (SMEs -> small firms). Suggest aligning the wording.
```

---

## What makes it different

**Dynamic guideline extraction.** Most writing tools hardcode citation rules (APA, Chicago, etc.). cephalo reads whatever style guide your institution gives you — however idiosyncratic — and extracts the rules into a structured configuration. If the rules change, you update the document; the agents update themselves.

**Phase separation.** Content quality stabilizes well before formatting does. cephalo formalizes this: a Content phase uses capable, expensive models; a Formatting phase uses fast, cheap models. This cuts costs significantly without sacrificing quality, provided the formatting chats really run on a fast model (see `docs/phase_separation.md`).

**Source fidelity as first-class concern.** The most valuable agent in the system is the source verifier — catching subtle errors like "your text says *X*, but the source says *Y* (close but not identical)." These errors are invisible without a dedicated review pass, and they are the difference between good and publishable work.

**Project-scale awareness.** A seminar paper needs different structure than a dissertation. cephalo offers workflow variants for:
- Small works (seminar papers, presentations)
- Medium works (bachelor theses)
- Long-running works (master theses, dissertations) — with phase-based directories, handover rituals, Git versioning, and reference manager integration

Dissertations do not currently have their own dedicated workflow; cephalo uses `master_7agent_longform.yaml` (flat structure: `master_7agent.yaml`) as the closest match and expects adaptation (more phases, longer timeline, possibly multiple sub-projects per chapter). A native dissertation workflow may be added in a future version.

---

## Responsible use

cephalo is a writing *assistant*, not a ghostwriter. It reads sources, drafts from them, checks citations, and enforces formatting — but the research questions, the argument, and every final sentence are yours, and yours to defend.

Before using it for graded or published work:

- **Check your institution's rules on AI assistance.** They vary widely and they change. What is permitted for one course or degree may be forbidden for another.
- **Disclose your use** where your institution asks for it — many now require a short declaration. Be specific about what the tool did.
- **Own every claim.** Verify each source yourself and make sure you can explain and defend every sentence in an oral exam or review. The source-verifier reduces errors; it does not absolve you of them.

Used this way, cephalo makes you a more rigorous writer. Used to hand in text you cannot stand behind, it will not serve you well — and neither will the examiner.

---

## Requirements

- **Claude Code** (desktop app or CLI) with a paid Anthropic subscription
- **Git** installed (for versioning, recommended for theses)
- **Pandoc** for the Word export in the formatting phase (free; on Windows `winget install --id JohnMacFarlane.Pandoc`, on macOS `brew install pandoc`)
- **Optional:** Zotero or Citavi for bibliographic data (recommended for 15+ sources)

No programming knowledge required for basic use. Scripts are optional.

---

## Quick start

**Step by step with screenshots:** [`docs/setup_guide.md`](docs/setup_guide.md) walks through steps 1 and 2 with the setup assistant.

### 1. Download and extract

Get cephalo from the project's GitHub page — a release archive from the Releases page, or **Code -> Download ZIP** — and unzip it anywhere; `git clone <repo-url>` works too. The setup script will ask you at launch time where your project should live.

If you cloned instead of unzipping: use a `--target` path in step 2, so your project starts with its own fresh Git history instead of sitting on top of cephalo's.

**New here? Prefer a visual start.** Open [`docs/setup-wizard.html`](docs/setup-wizard.html) in any browser — answer a few questions and it builds the exact setup command for your system and previews the folders it will create. It is fully offline and runs nothing; you copy the command and run it yourself in the next step.

### 2. Run the setup script

**Windows (PowerShell):**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\setup.ps1
```

**macOS / Linux / Git Bash:**

```bash
chmod +x setup.sh
./setup.sh
```

The script asks four questions:
- **Where should the project be created?** — here, inside the extracted cephalo folder itself (e.g. `cephalo-1.0.0/` in your Downloads), or a target path you specify (e.g. `~/Documents/Bachelorarbeit_OSS`). A target path is recommended for real work; the cephalo template is copied there and the project is created inside.
- What kind of work is this? (seminar paper, presentation, thesis, dissertation)
- What project structure? (flat, long-form, multi-project)
- How much structure should be pre-created? (standard scaffolding, or minimal — the rest is added later based on your guidelines)

For non-interactive runs, pass the answers as arguments. Run in a terminal with `--target`, `setup.sh` still offers to delete the template folder at the end; append `</dev/null` to skip that as well:

```bash
./setup.sh "Bachelor thesis" "Long-form" full --target ~/Documents/Thesis_OSS
```
```powershell
.\setup.ps1 -WorkType "Bachelor thesis" -Structure "Long-form" -Scaffolding full -Target ~\Documents\Thesis_OSS -NonInteractive
```

### 3. Drop your institution's guidelines into place

Depending on your chosen structure:

- Flat: `workspace/sources/_guidelines/`
- Long-form: `guidelines/`
- Multi-project: `00_Shared_Materials/guidelines/`

Add whatever your institution provides: citation guide, formatting rules, examination regulations, etc. Also optionally course-specific materials (syllabi, assignment descriptions).

### 4. Open the project in Claude Code and invoke the style resolver

Open the project root (or, for multi-project setups, the sub-project you're working on) in Claude Code. Run the first prompt:

```
Please invoke the style-resolver agent. Extract the formatting 
and citation rules from the guidelines directory into styleguide.md. 
List any open questions for me to resolve before we proceed.
```

The resolver produces a structured `styleguide.md`. Open questions are marked `❓` and tagged: resolve the `[content]` ones (voice, citation wording, length — usually by asking your supervisor) before content work begins; the `[format]` ones (fonts, margins, pagination, ...) can wait until the formatting phase.

### 5. Begin writing

Use the workflow that matches your project. See `docs/QUICKSTART.md` for detailed chapter-by-chapter instructions.

---

## Project structure variants

Three structures, chosen at setup time based on the scale of your work:

### Flat (seminar papers, presentations)

```
project/
├── .claude/agents/
├── workflows/
├── [...other agent files]
├── workspace/
│   ├── sources/
│   │   ├── _guidelines/
│   │   └── extracts/
│   ├── output/
│   │   ├── chapters/
│   │   └── slides/        (presentations)
│   └── data/              (presentations: chart data)
└── styleguide.md
```

Everything in one directory, one chat per chapter, state file as bridge between chats.

### Long-form (bachelor and master theses)

```
project/
├── [...agent files]
├── guidelines/
├── 00_Status.md
├── 00_Decisions.md
├── 00_Feedback_log.md
├── 01_Proposal/                    (optional within long-form)
├── 02_Literature/
├── 03_Theory_chapters/
├── 04_Methods/                     (if applicable)
├── 05_Empirical/                   (if applicable)
├── 06_Discussion_Conclusion/
├── 07_Introduction/                (written last)
└── 08_Formal_Review/               (formatting phase — see docs/phase_separation.md)
```

Phase-based directories, per-phase handover documents, centralized state management. Git and reference manager recommended.

### Multi-project (long works with proposal and defense)

```
project/
├── [...agent files]
├── 00_Shared_Materials/
│   └── guidelines/
├── 01_Proposal/
├── 02_Main_Work/
└── 03_Defense/
```

Three independent sub-projects sharing one set of materials. Each sub-project has its own state, its own workflow, its own freeze point. The proposal is frozen after acceptance. The main work is frozen after submission. The defense works from both as read-only references.

---

## The agents

| Agent | Role | Default model |
|-------|------|---------------|
| `orchestrator` | Coordinates flat-structure workflows | inherit |
| `orchestrator-longform` | Coordinates long-form / multi-project workflows | inherit |
| `orchestrator-defense` | Specializes in defense preparation | inherit |
| `research-agent` | Reads sources, produces structured extracts | inherit |
| `writer-agent` | Produces prose from extracts, enforces style | opus |
| `source-verifier` | Sentence-by-sentence verification, plagiarism check | opus |
| `format-verifier` | Checks document against styleguide | inherit |
| `style-resolver` | Extracts rules from institutional guidelines | opus |
| `methods-agent` | Research design for empirical work | opus |
| `data-agent` | Tables, statistics, numerical consistency | opus |

*Model assignment.* `inherit` means the agent uses whatever model the main chat is using — typically the user's default. `opus` means the agent is pinned to the strongest available model regardless of the main chat's setting, because the role requires careful judgment (paraphrasing, source fidelity, methodological reasoning). You can override these per project by editing the agent's frontmatter.

---

## Documentation roadmap

Read in this order if new:

1. **README.md** (this file) — overview
2. **docs/QUICKSTART.md** — 5-minute onboarding for a new project
3. **docs/setup_guide.md** — the setup assistant step by step, with screenshots
4. **docs/error_catalog.md** — common writing errors this system catches
5. **docs/phase_separation.md** — how the Content / Formatting phase split works
6. **docs/scripts.md** — the optional utility scripts (guideline extraction, a count of verbatim word runs against the sources, bibliography and abbreviation checks, DOCX post-processing)

For thesis-scale projects:

7. **docs/longform_structure.md** — long-form project organization
8. **docs/multiproject_structure.md** — when to split into sub-projects
9. **docs/git_introduction.md** — versioning for beginners
10. **docs/reference_management.md** — Zotero/Citavi integration

---

## FAQ

### Is cephalo specific to any institution?

No. The style-resolver agent extracts rules from whatever guideline documents you provide. Tested primarily with German-language university guidelines, but the architecture makes no assumption about language, citation style, or institutional conventions. (The optional utility scripts ship with English/German detection heuristics, which are easy to extend — they tell you how when it matters.)

### Does cephalo do the writing for me?

No. It helps you write. You provide research questions, outlines, sources, and final editorial judgment. The agents extract, draft, verify, and format — but the intellectual substance remains yours. Every sentence should be defendable by you in an oral examination.

### What happens if I already have a work-in-progress?

You can import an existing project. See `docs/QUICKSTART.md` for migration steps. Typically: place existing chapters in phase directories, create a Status document summarizing current state, invoke the style-resolver on your institution's guidelines, continue.

### Does this work without Git?

For small works (seminar papers), yes. For theses, you will regret not using Git by month three. The setup script initializes a repository automatically — unless the folder already is one: if you cloned cephalo instead of downloading the ZIP, set up with `--target` so your thesis gets its own fresh history instead of sitting on top of cephalo's. `docs/git_introduction.md` explains the three commands you need: `status`, `add`, `commit`.

### Why do I have to unblock the launcher on Windows, and why is there none for macOS?

Both systems mark every file a browser downloads. Windows then refuses to open the setup assistant's `cephalo-setup.cmd` and says it cannot be opened; macOS refuses a double-click on a downloaded script (unverified developer). The launcher cannot lift this itself: as long as the mark is set, it never runs. Only signed software from a registered developer passes this check, and cephalo ships scripts, not signed programs. So on Windows, unblock the launcher once (right-click it, choose **Properties**, tick **Unblock**, click **OK**), and on macOS the assistant offers no launcher at all. The simplest way needs no download on either system: click **Copy** in the setup assistant, paste the command into PowerShell or Terminal and press Enter. [`docs/setup_guide.md`](docs/setup_guide.md) shows both ways with screenshots (steps 5 and 6).

### How much does it cost?

cephalo itself is free. You pay for the Claude Code subscription (standard Anthropic pricing). Typical thesis projects use a mix of expensive and cheap models, with the phase separation feature cutting total costs by an estimated 60–70% versus naive use of the capable model throughout. This is an estimate for a whole thesis, not a measurement: in the trial runs, with one short chapter each, the formatting phase on a fast model made up only about a tenth of the cost, so they could not show such a saving. The saving needs the formatting-phase chats to run on a fast model (e.g. switch with `/model`): the formatting agents inherit the chat's model.

### Can I contribute?

This is an early project. Feedback on the agent definitions, workflow configurations, and error catalog is welcome — [CONTRIBUTING.md](CONTRIBUTING.md) explains how. Specifically: if your institution's style guide produces unusual results with the style-resolver, a sample (anonymized) plus the problematic output is valuable.

### My institution has no citation guide — what should I put in `styleguide.md`?

Two options:

1. **Ask.** Contact the program coordinator or your supervisor. Institutions nearly always have conventions, just sometimes not written down. A short email often yields the information faster than searching.
2. **Adopt a published standard.** If nothing exists, APA 7 is the safest default for social sciences and business; Chicago for humanities; IEEE for engineering. Document the choice explicitly in `00_Decisions.md`: "Institution provides no style guide; adopting APA 7 as default." Then extract that standard into `styleguide.md` using the style-resolver (most published standards have PDFs available).

Either way, the `styleguide.md` file must exist and be explicit. Agents will not improvise.

---

## Credits

Developed through real coursework at a German distance-learning university. The error catalog and workflow patterns reflect patterns observed across dozens of revisions of actual student work. Mistakes made during development became the rules enforced by the agents.

---

## License

cephalo is licensed under the Apache License 2.0. See `LICENSE` for the full text.

In short: you may use, modify, and redistribute cephalo, including commercially. You must preserve the license and attribution. Modifications must be marked. The Apache 2.0 patent grant protects you from patent claims by contributors. There is no warranty — cephalo is provided as-is.

---

## A note on the name

*Cephalo* (from Greek κεφαλή, *kephalē*, "head"; also the root of "cephalopod") refers to organisms with centralized intelligence distributed across specialized arms. Octopuses are the canonical example. The metaphor is intentional: one orchestrator coordinates many agents, each tuned for a specific task, all reaching toward the same goal.

It also happens to be a short, pronounceable name in most languages. That matters.
