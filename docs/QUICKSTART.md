# Quickstart

This is a 5-minute onboarding for a new project. It assumes you have already extracted the cephalo package.

**Tip:** if you would rather not assemble the command by hand, open [`setup-wizard.html`](setup-wizard.html) in any browser. It builds the exact command for your system from a few clicks and previews the resulting folders — fully offline, and it runs nothing itself. A walkthrough with screenshots: [`setup_guide.md`](setup_guide.md).

For full architecture and concepts, see `README.md`.

---

## Step 0: Decide where your project lives

When you run the setup script, it will ask where to create the project. You have two options:

1. **Here** — the project is created inside the extracted cephalo folder itself. Fast, but the folder will keep its download name (e.g. `cephalo-1.0.0/` or `cephalo-main/`), which is not a great name for your thesis.
2. **In a different directory** — enter a path like `~/Documents/Bachelorarbeit_KMU_OSS`. The cephalo template is copied there, and the project is created inside. At the end, the script offers to delete the original download.

Option 2 is recommended for real work. Option 1 is fine for quick testing.

Non-interactive (in a terminal, `setup.sh` still offers to delete the template folder at the end; append `</dev/null` to skip that):
```bash
./setup.sh "Bachelor thesis" "Long-form" full --target ~/Documents/Bachelorarbeit
```
```powershell
.\setup.ps1 -WorkType "Bachelor thesis" -Structure "Long-form" -Scaffolding full -Target ~\Documents\Bachelorarbeit -NonInteractive
```

Why this matters: Claude Code needs the agent files (`.claude/`, `workflows/`, etc.) and your project content in the *same* directory. That is why the template is copied rather than just the project folder being created somewhere else — everything has to coexist.

---

## Step 1: Verify your setup

After running the setup script, your project directory should contain:

- The agent files (`.claude/`, `workflows/`, `checklists/`, `templates/`, `scripts/`, `docs/`)
- The structure for your chosen variant (see your setup output)
- A `.git` directory (Git initialized)
- `.gitignore` and `.gitattributes`

Open the project directory in Claude Code (desktop app or CLI).

For multi-project setups: open the **sub-project** you're currently working on (e.g., `01_Proposal/`), not the root directory. Otherwise Claude sees all three projects at once, which is confusing.

---

## Step 2: Place your guidelines

Drop your institution's documents into the guidelines directory. Depending on your structure:

| Structure | Path |
|-----------|------|
| Flat | `workspace/sources/_guidelines/` |
| Long-form | `guidelines/` |
| Multi-project | `00_Shared_Materials/guidelines/` |

What to include:
- Citation guide (mandatory)
- Formatting / writing guidelines (mandatory)
- Examination regulations (recommended)
- Plagiarism prevention guide (recommended)
- Course-specific assignment briefing (recommended)

If you don't have one of these yet, that's fine — the style-resolver will flag missing rules as `❓` for you to clarify later.

---

## Step 3: Run the style-resolver

In Claude Code, send this prompt:

```
Please invoke the style-resolver agent. Extract the formatting and 
citation rules from the guidelines directory into styleguide.md. 
List any open questions for me to resolve before we proceed.
```

The resolver will:
1. Read your guidelines
2. Produce `styleguide.md` at the project root (or `00_Shared_Materials/styleguide.md`)
3. Flag ambiguous or missing rules as `❓`
4. (For minimal-scaffolding setups) propose additional directories based on what your guidelines require

Each `❓` item is tagged. Resolve the `[content]` items (voice, evaluative wording, citation wording, length, outline depth, and the number formats, resolution and captions of tables and figures) before the first chapter is drafted: their answers change what the agents write. The `[format]` items (fonts, margins, pagination, title page, ...) only need an answer before the formatting phase. Resolving usually means asking your supervisor about the ambiguous points.

---

## Step 4: Begin chapter work

Choose your workflow based on your project type:

| Type | Workflow file |
|------|---------------|
| Seminar paper | `workflows/seminar_2agent.yaml` |
| Presentation | `workflows/presentation_3agent.yaml` |
| Bachelor thesis (flat) | `workflows/bachelor_5agent.yaml` |
| Bachelor thesis (long-form) | `workflows/bachelor_5agent_longform.yaml` |
| Master thesis (flat) | `workflows/master_7agent.yaml` |
| Master thesis (long-form) | `workflows/master_7agent_longform.yaml` |
| Proposal sub-project | `workflows/proposal_workflow.yaml` |
| Defense sub-project | `workflows/defense_workflow.yaml` |

Open the chosen workflow file once to understand the phase structure. Then start a chat for the first chapter.

If your workflow uses an orchestrator (all except seminar paper and presentation), start each chat by asking Claude to invoke it: `orchestrator` (flat), `orchestrator-longform` (long-form, and the proposal and main-work sub-projects) or `orchestrator-defense` (defense sub-project). The orchestrator calls the specialist agents itself. In the CLI you can instead start the session as the orchestrator, e.g. `claude --agent orchestrator-longform`; use that mode if the orchestrator reports that it cannot call other agents.

For long-form projects, follow the **chat closure ritual** at the end of every chat: update `00_Status.md`, write the phase's `handover.md`, suggest a Git commit. The orchestrator will guide you.

---

## Step 5: Read these next

In order:

1. **`docs/error_catalog.md`** — the top errors this system catches. Knowing them in advance saves work.
2. **`docs/phase_separation.md`** — how cephalo separates Content (Phase A) from Formatting (Phase B), and why.
3. **`docs/longform_structure.md`** — if you're using long-form structure.
4. **`docs/multiproject_structure.md`** — if you're using multi-project structure.
5. **`docs/git_introduction.md`** — if Git is new to you.
6. **`docs/reference_management.md`** — if you're using Zotero, Citavi, or another reference manager.

---

## Common first-day mistakes

### Skipping the style-resolver

If you skip step 3, there is no `styleguide.md`: the orchestrator stops to run the style-resolver first, the format-verifier stops, and the writer can only flag formatting questions instead of applying rules (the typographic fallbacks in `checklists/format_rules.md` apply only to an existing but incomplete styleguide). Always run the resolver first.

### Trusting filenames

Institutional course files sometimes have misleading names. A `.pdf` may actually be a ZIP archive of JPEGs. The research-agent should inspect file contents, not filenames. If you upload sources manually, verify what's actually inside.

### Ignoring open `❓` items

`❓` items in `styleguide.md` mean "I don't know". Open `[content]` items stop drafting; open `[format]` items stop the formatting phase, and until then the format-verifier keeps flagging the same issues. Resolve early.

### Working in the multi-project root

For multi-project setups, open the active sub-project (`01_Proposal/`, `02_Main_Work/`, or `03_Defense/`) in Claude Code. Opening the root exposes all three to the agent at once, which leads to confusion and unintended edits across sub-projects.

---

## Migration from existing work

If you already have a draft (in Word, Markdown, etc.):

1. Run setup as above
2. Place existing chapters in the appropriate phase directories (long-form) or `workspace/output/chapters/` (flat), as Markdown or plain text: the agents cannot open `.docx` files (in Word: Save As -> Plain Text, or `pandoc chapter.docx -o chapter.md`)
3. Create an initial `00_Status.md` (long-form) or `workspace/state.md` (flat) summarizing where you stand
4. Run the style-resolver
5. Start a chat asking the source-verifier to verify your existing chapters

The agents work with what's already there. You don't need to rewrite anything that already exists.

---

## Troubleshooting

**`./setup.sh: Permission denied`** — the script needs the execute bit: `chmod +x setup.sh`.

**macOS: a downloaded script cannot be opened (unverified developer)** — macOS blocks a double-click on scripts downloaded with a browser, so nothing has run. Click OK. For this reason `setup-wizard.html` offers no launcher for macOS: click **Copy** there, paste the command into Terminal and press Enter, as step 5 of [`setup_guide.md`](setup_guide.md) shows.

**Windows: the downloaded launcher cannot be opened (Internet security settings)** — Windows blocks a `.cmd` file downloaded with the browser, so nothing has run. Right-click `cephalo-setup.cmd`, choose **Properties**, tick **Unblock** at the bottom of the **General** tab and click **OK**, then double-click it again (step 6 of [`setup_guide.md`](setup_guide.md)). In PowerShell, `Unblock-File "$HOME\Downloads\cephalo-setup.cmd"` does the same for a launcher in Downloads. The launcher cannot do this itself, since Windows does not run it while the file is blocked; clicking **Copy** in `setup-wizard.html` and pasting the command into PowerShell needs no unblocking.

**`setup.ps1 cannot be loaded because running scripts is disabled`** — PowerShell's execution policy. Allow this session only:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\setup.ps1
```

**`git: command not found`** (or `! Git not installed.` / `! Git not available` in the setup output) — install Git. On Windows: download Git for Windows (includes Git Bash, which is needed for the `.sh` helper scripts). On Linux/macOS: `apt install git` / `brew install git`. Setup creates no repository without Git (`git add .` then fails with `not a git repository`): afterwards, re-run setup with the same choices in the project folder (for multi-project, the root, not a sub-project).

**`Error: python-docx not installed.`** (or `ModuleNotFoundError: No module named 'docx'`) — the Python utility scripts need their dependencies. From the project root: `pip install -r requirements.txt`. If you installed `docx` instead, that is a different, abandoned package: run `pip uninstall docx`, then `pip install python-docx`.

**Setup finishes but no workflow is mentioned** — check the script output. The last lines name the active workflow. Invalid arguments make the script exit with an error message naming the valid options — fix the argument and re-run.

**Something else went wrong** — re-run with verbose output: `bash -x setup.sh` (Linux/macOS) or add `-Verbose` to the PowerShell invocation. Open an issue with the output.

---

## Getting help

- For architecture questions: `README.md`
- For specific agent behavior: `.claude/agents/<agent-name>.md`
- For workflow details: `workflows/<workflow>.yaml`
- For known issues: `docs/error_catalog.md`
- For script installation and usage: `docs/scripts.md`
