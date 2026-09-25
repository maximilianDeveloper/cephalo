# Changelog

All notable changes to cephalo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates follow ISO 8601 (`YYYY-MM-DD`).

---

## [1.0.0] — 2026-09-24

**First public release.** A browser-based setup assistant, a documentation and utility-script hardening pass, removal of hard-coded formatting rules from three agent definitions, a pre-publication review sweep (license text, distribution docs, GitHub project files), and a pre-publication security pass (see **Security** below). A final pre-release audit then fixed bugs in both setup scripts, the setup assistant and all five utility scripts, closed further security and privacy gaps, brought workflows, checklists, templates and agents in line with the styleguide-only principle, and widened CI coverage.

### Added

- **GitHub project files** — a minimal CI workflow (`.github/workflows/ci.yml`: script syntax/compile checks, workflow-YAML validation, and non-interactive setup smoke runs on Ubuntu and Windows), issue and pull-request templates aligned with `CONTRIBUTING.md`, and a `SECURITY.md` describing scope and the private reporting channel.
- **`docs/setup-wizard.html`** — a self-contained, offline setup assistant. Pick work type, structure, scaffolding, and platform, and it builds the exact `setup.ps1` / `setup.sh` command and previews the folder structure that will be created. It also offers a one-click **Download launcher** button that saves a small, preconfigured start script (`cephalo-setup.cmd` on Windows, `.command` on macOS, `.sh` on Linux) — save it into your cephalo folder, then double-click it (Windows) or run it with `bash` from a terminal (macOS/Linux: a downloaded file is not executable). Static HTML with no dependencies or network access; it generates commands and launcher scripts but never runs anything itself. Linked from `README.md` and `docs/QUICKSTART.md`.
- **`.gitattributes`** — keeps the shell scripts LF in every checkout (`*.sh text eol=lf`), so a Windows clone with `core.autocrlf=true` no longer breaks `setup.sh` and the helper scripts under WSL or Git Bash. Both setup scripts now append their Git LFS rules to an existing `.gitattributes` (without duplicates on re-runs), so generated projects keep them.
- **`templates/styleguide.md`** — slots for rules the agents already defer to: `title_page.*`, `captions.*` (table, figure and source placement) and `numbers.decimal_separator`.
- **CI coverage** — the Ubuntu job now also runs the utility scripts on generated files (exit codes, one-line errors, hyphenation, disguised ZIPs and path traversal), checks agent definitions, workflow references and the archive-extraction rule, re-runs setup to guard state files and the generated `.gitignore`/`.gitattributes`, tests more invalid arguments, menu hints and step numbering, the LF rule in an autocrlf clone, and the setup assistant's JavaScript. `bash -n` now checks each shell script (it had parsed only the first). The Windows job now also checks `setup.ps1` under Windows PowerShell 5.1 for its UTF-8 BOM, flat and multi-project runs (including `shared/`), the Git LFS rules, a re-run that keeps an edited `00_Status.md`, a target with `[ ]` in its name, and exit 2 on closed stdin.

### Fixed

- **`LICENSE`** — restored the verbatim Apache-2.0 text: Section 6 was missing "reasonable and customary use in", and Section 9 read "Accepting Warranty or Support" instead of "Accepting Warranty or Additional Liability" (heading and closing sentence). The shipped file now matches the canonical text from apache.org, with only the appendix copyright line filled in.
- **`bibliography_check.py`** — middle authors of 3+-author entries (`Dawson, R., Ellis, S., & Fowler, T.`) are now extracted, removing a false positive where a visibly listed co-author was reported as "cited but not in bibliography".
- **`setup.ps1`** — when all three configuration values are supplied as parameters, they are validated **before** the `-Target` template copy: a typo like `-Structure Langform` now fails fast instead of leaving a stray template copy at the target (which then also blocked the corrected non-interactive retry with "Refusing to copy into non-empty directory").
- **`setup.sh`** — the "Next steps" summary numbers its steps contiguously on full-scaffolding runs (previously it printed 1, 2, 4).
- **Both setup scripts** — interactive menus now answer invalid input with "Please enter a number between 1 and N." instead of silently re-prompting.
- **`docx_postprocess.sh` / `extract_styleguide.sh`** — both understand `-h`/`--help` now; the pdftotext-only fallback of `extract_styleguide.sh` distinguishes ZIP archives disguised as PDFs from merely corrupt files; `docx_postprocess.sh` no longer reassigns the standard `TMPDIR` environment variable for its work directory.
- **`setup.ps1`** — `.\setup.ps1 ... -Target ...` no longer requires answering interactive prompts when `-NonInteractive` is passed; documented non-interactive examples in `README.md` and `docs/QUICKSTART.md` now include the switch so they run unattended as advertised.
- **`setup.sh`** — supplying all three positional arguments (work type, structure, scaffolding) is now genuinely non-interactive: the confirmation prompt is skipped and the run succeeds with closed stdin (CI, scripts), matching the documented examples.
- **`docx_postprocess.sh`** — no longer requires `zip` (only `unzip` and a working Python 3 are needed; re-zipping was already done with Python's `zipfile` module, so the dependency check was a leftover). This removes the most common Windows/Git Bash onboarding blocker for this script. The interpreter check now probes for a *working* Python under both `python3` and `python`, catching the case where `python3` resolves to a dead Microsoft Store app-execution-alias stub. Auto-hyphenation detection now correctly treats an explicitly-disabled element (`w:val="0"`/`"false"`/`"off"`) as disabled and rewrites it, instead of mistaking it for already-enabled.
- **`abbreviations_extract.py`** — footnotes and endnotes are now actually read (previously silently skipped due to an unsupported python-docx access pattern). Dotted abbreviations no longer lose their last segment (`U.S.A.` now normalizes fully to `USA` instead of truncating to `US`). All-caps acronyms containing digits, or up to 8 characters long, are now recognized (`B2B`, `CO2`, `5G`, `BENELUX`).
- **`bibliography_check.py`** — surnames starting with Ä/Ö/Ü are now recognized on the bibliography side, matching the in-text side (previously such entries were silently invisible to the check). Year-suffix citations (`Schulz (2022a)`, `(Wagner, 2022a)`) are now recognized in narrative form, not just parenthetical. Name-prefix matching now also covers `van den`, `ter`, and `ten`. The German citation lead-words `siehe` and `nach` are now recognized alongside the already-supported `vgl.`/`cf.`/`see`. `--help` now prints usage instead of a confusing "file not found" error; a corrupted or non-DOCX file now produces a clear one-line error instead of a raw traceback.
- **`cross_session_audit.py`** — main-worktree detection now trusts git's own guarantee (the first entry of `git worktree list --porcelain` is always the main worktree) instead of an unreliable path-based heuristic, fixing misidentification when the repository's own path contains a `worktrees` path segment. A nonexistent or invalid `--repo-root`, or a missing `git` binary, now produces a clear one-line error instead of a raw traceback. Operational errors (e.g. not a git repository) now exit with code 2, distinct from exit code 1 for findings, so CI/hooks can tell the two apart. The reference-validation layer now also recognizes `workspace/...`-prefixed paths, covering flat-structure projects.
- **`setup.sh`** (pre-release audit) — unknown or misspelled options (`--taget`), an empty `--target=` and a fourth positional argument now exit 2 before anything is created instead of setting up the template folder itself; `-h`/`--help` works anywhere. The target is canonicalized before the inside-template check: `--target ../Thesis` is no longer falsely rejected, and targets that reach into the template through a symlink or a `..` detour are refused instead of copying the template into itself. Only `~` and `~/` are expanded (`~Documents/Thesis` no longer becomes a sibling of the home folder). A failing template copy shows tar's error and exits 3. A failing `shared/` copy fallback or `git lfs install` only warns. "Proceed?" accepts `Y`/`yes`/`J`/`ja`, and Ctrl+D at a prompt selects its safe default. `--target` copies skip `venv/` and nested virtual environments. An exported `CDPATH` no longer misroutes the multi-project links. An invalid work type lists the valid options readably, and after a multi-project setup the summary says to open a sub-project, not the root. After a `--target` run, the summary names the project folder and prints a `cd` line: the calling shell is still in the template folder, which the steps ("Open this directory", `git add .`) do not mean and which the same summary suggests deleting.
- **`setup.ps1`** (pre-release audit) — the template check now also requires `setup.ps1` itself and real `.claude`/`templates` directories, so running the script by path from the user profile (which often has `.claude\` and a `Templates` folder) no longer scaffolds into the home directory. With `-NonInteractive`, missing values are rejected (exit 2) before the `-Target` copy. A relative `-Target` is resolved against the current PowerShell location, not the directory PowerShell was started in. Copying into a confirmed non-empty `-Target` no longer deletes the user's own `venv`/`.venv`/`__pycache__` folders or `.claude\settings.local.json`. Closed stdin without `-NonInteractive` exits 2 instead of looping forever or reporting "Cancelled.". "Proceed?" accepts `yes`/`ja` like `setup.sh`. The template is copied to `-Target` only after "Proceed?" (as in `setup.sh`), so answering "n" no longer leaves a full copy behind that blocks the corrected retry, and the summary shows the target. Paths containing `[ ]` (e.g. `Thesis [final]`) are no longer read as wildcard patterns; such a `-Target` failed with exit 3 after the copy. When `New-Item` cannot create a multi-project `shared/` link (Windows PowerShell 5.1 requires elevation for it even with Developer Mode on), setup now retries with `mklink`, for which Developer Mode is enough, before falling back to copies.
- **Both setup scripts** — the setup-assistant launcher (`cephalo-setup.*`) and the template's own `.github/` are no longer copied into a `--target`/`-Target` project; the launcher contains the absolute path it was generated for, and `.github/` would run cephalo's CI in every thesis repository pushed to GitHub (`docs/git_introduction.md` says to delete it for in-place setups).
- **`docs/setup-wizard.html`** — the Windows launcher no longer swallows the closing quote and `-NonInteractive` when the target ends in a backslash, and it switches to UTF-8 (`chcp 65001`) so targets with umlauts are not mangled into a different folder. Targets starting with `~-`, `~+` or `~<digits>` are quoted in the bash command. The launchers report a failed setup instead of "Done". After back/forward navigation the command follows the options the browser restored. The embedded README and QUICKSTART are re-rendered from the current Markdown, without the README's link to the wizard itself, which was dead from `docs/`.
- **`docx_postprocess.sh`** — Word-saved documents no longer fail with "ZIP does not support timestamps before 1980" in time zones such as Asia/Singapore; `<w:autoHyphenation/>` is inserted at its schema position (after `<w:defaultTabStop/>`); a failed re-zip no longer leaves a partial `<document>.docx.new` behind. An existing element in open/close form (`<w:autoHyphenation ...></w:autoHyphenation>`) is recognized instead of duplicated, and a document whose settings element cannot be located (e.g. a namespace prefix other than `w:`) now fails with an error instead of reporting "Auto-hyphenation enabled." unchanged. `.DOCX` is accepted, and passing more than one file (e.g. a glob) is refused instead of silently processing only the first. The patched file keeps the original's permission bits instead of becoming readable by everyone.
- **`extract_styleguide.sh`** — a corrupt, encrypted or unsupported ZIP disguised as a PDF is reported for that file and the run continues; a PDF that pypdf cannot read on any page (e.g. AES-encrypted) is reported with the real error and handed to `pdftotext` instead of being called "scanned". `pdftotext` is called with `-enc UTF-8`: the xpdf build (common on Windows) writes Latin-1 by default, which crashed the run on the first umlaut when pypdf was missing. `.txt` files inside a disguised ZIP that are not UTF-8 are read as Windows-1252 instead of losing their umlauts. Text files in the output directory that a run did not write (left over from an earlier run) are listed, so stale guideline text does not reach the style-resolver unnoticed.
- **`docx_postprocess.sh` / `extract_styleguide.sh`** — the interpreter probe also tries the Windows `py` launcher, which a default python.org install puts on PATH instead of `python`.
- **`abbreviations_extract.py`** — acronyms in footnotes/endnotes that Word split across runs are no longer cut apart (`UNESCO` became `UNES` + `CO`); every unreadable input gives a one-line error; the common-abbreviation filter compares case-sensitively, so real acronyms such as `MR`, `NO` or `CO` are no longer dropped because of entries like "Mr", "no" or "Co" (all-caps forms such as `PHD` are now listed too); decomposed umlauts are normalized (`ÖPNV` no longer becomes `PNV`).
- **`bibliography_check.py`** — every unreadable input (a ZIP that is not a Word file, a damaged document, a directory) now gives one line and exit 2, never a traceback or exit 1, which means findings. Recognized now: narrative citations with a page locator (`Müller (2020, S. 15)`, `Smith (2020: 15)`), `u. a.` like `et al.`, typographic apostrophes (`O’Brien`) and letters of any script in surnames, name particles and capitalized lead words (`(Vgl. Smith 2020)`) in parentheses, slash-separated authors in parentheses, and possessives (`Smith's (2020)`). Months and structural words in parentheses (`(März 2021)`, `(Tabelle 3, 2020)`) and prose fragments (`(eigene Darstellung, 2024)`, `Deutschland (2020: 5,9 %)`) are no longer reported as authors, while acronyms and surname-like words in parentheses still count. Text is NFC-normalized; `--help` works under `python -OO`. The bibliography now ends at the next top-level heading that is not itself a bibliography heading (an appendix, the declaration of authorship): a signature line such as `Ort, Datum` is no longer reported as an uncited author, and citations in the appendix count. Of several matching headings the highest-level one starts the bibliography, so a body sub-heading such as `3.2 Sources` no longer does.
- **`cross_session_audit.py`** — a worktree that cannot be inspected (dubious ownership, corrupt index, unreadable) or an unwritable `--report-file` now gives a one-line error and exit 2 instead of a "clean" result or a traceback with exit 1. Run from a git hook, it no longer passes the hook's `GIT_DIR`/`GIT_INDEX_FILE` to its git calls; it reads other worktrees with `git --no-optional-locks status` so it does not take their `index.lock`; references into any two-digit `NN_` directory are checked; `python -OO` no longer crashes it. File names with umlauts appear as they are instead of as octal escapes, and a quoted source line that is itself a table row no longer splits the dangling-refs table.

### Documentation

- `docs/scripts.md` now documents `cross_session_audit.py` alongside the other four utility scripts, and its usage/behavior descriptions for `abbreviations_extract.py`, `bibliography_check.py`, `docx_postprocess.sh`, and `extract_styleguide.sh` are updated to match current script behavior, including the remaining known heuristic gaps (multi-word institutional bibliography authors, and citations without a year such as `o. J.` or `n.d.`; single-word institutional authors and numbered/punctuated bibliography headings are handled).
- `README.md` gains a **Responsible use** section (check your institution's AI rules, disclose your use, own every claim) and clearer early-stage wording.
- `README.md` quick start now names the acquisition paths (release archive, Code -> Download ZIP, `git clone`) and recommends `--target` for cloned copies; the Git FAQ explains that setup skips `git init` when a `.git` directory already exists. The Administrator note is scoped to multi-project setups (flat/long-form need no elevation), and an illustrative source-verifier finding shows what the tool actually produces. `CONTRIBUTING.md` and this changelog are linked from the README.
- Plagiarism-threshold wording harmonized: `docs/error_catalog.md` now states the same warning band (8-14 verbatim words) as the binding table in `checklists/plagiarism_protection.md`, whose worked example now quotes the real 9-word verbatim run.
- `docs/git_introduction.md` gains a "tell Git who you are" section (`git config --global user.name/user.email`), so a first-ever commit no longer fails unexplained with "Author identity unknown".
- `checklists/consistency.md` no longer hardcodes an institution-specific pagination scheme, body alignment, or presentation timing; these defer to `styleguide.md` keys like the rest of the checklists.
- Example tokens in scripts and docs are domain-neutral (`B2B` in the acronym examples; `WHO`/`OECD`/`Statistisches Bundesamt` as institutional-author examples).
- Pre-release audit: `docs/QUICKSTART.md` describes the missing-styleguide case correctly, names `workspace/state.md` for flat migrations, keys its troubleshooting on the messages the scripts print, and names the extracted archive `cephalo-1.0.0/`; `CONTRIBUTING.md`'s release-checklist commands run as written and match CI; `docs/scripts.md` states what each script reads, that the bibliography check compares surnames (not years), and uses the audit report's layer numbering; `docs/multiproject_structure.md`'s re-sync snippets skip real links (on Windows PowerShell 5.1 the old one could empty `00_Shared_Materials`); `docs/phase_separation.md` and the flat thesis workflows say that the Phase B saving needs a fast main model, since `format-verifier` inherits the chat's model. The advice after the multi-project symlink fallback now says to delete the `shared/` copies before re-running setup.

### Changed

- `cross_session_audit.py` report output and inline documentation are now in English, matching the rest of the framework (behavior unchanged).
- Agent definitions (`writer-agent.md`, `format-verifier.md`, `data-agent.md`) and `checklists/format_rules.md` no longer hard-code institution-specific formatting rules (a first-person/voice ban, fixed title-page elements, a fixed pagination scheme, table-of-contents emphasis, caption placement, and two citation deviations). These now defer to `styleguide.md`; any concrete values that remain are kept only as explicitly institution-neutral illustrative defaults. This restores the framework's core principle that formatting rules live only in the generated `styleguide.md`, never hard-coded in prompts.
- **Workflows** (pre-release audit) — `scripts/docx_postprocess.sh` runs only when `styleguide.md` sets `document.hyphenation` to automatic (also in `format-verifier.md`, `orchestrator.md` and the checklists). Phase B produces the DOCX before the DOCX-only scripts run (new step B.0 in the flat bachelor/master workflows). Phase 0 of the long-form, proposal and defense workflows verifies what setup created and warns never to run `git init` inside a sub-project. The proposal runs its own materials pre-check, the A→B transition criteria match `docs/phase_separation.md`, the defense closure tag is `defense_passed_<date>`, and the remaining hard-coded style values (pronoun ban, talk length, pie-chart decimals, outline depth) defer to the styleguide or the assignment.
- **Checklists and agents** (pre-release audit) — `checklists/format_rules.md` now really defers title-page elements and the pagination scheme to `styleguide.md` (as claimed above) and its page-range and pronoun greps find what they are meant to find; `data-agent.md` no longer falls back to APA 7 silently; agents name the template's styleguide keys; `orchestrator-defense.md` no longer prefixes paths with `03_Defense/` and reads `styleguide_override.md`; `orchestrator-longform.md` allows the proposal's DOCX locations; `methods-agent.md` uses a `methods_` filename prefix (a colon is invalid on Windows) and knows where `design.md` goes; `orchestrator.md` takes loop limits from the workflow. Agents used in multi-project sub-projects name the paths as seen from there: the styleguide is `shared/styleguide.md`, and `checklists/`, `scripts/`, `templates/` and `workflows/` are one level up.

### Security

- **ZIP extraction is routed through `scripts/extract_styleguide.sh`** in `research-agent.md` and `style-resolver.md`. Both previously instructed a bare `unzip`, bypassing the script's `safe_extract_zip()`, which rejects entries carrying absolute paths or `..` components. A prepared archive — a style guide downloaded from anywhere — could otherwise have written outside the target directory. The agents and `checklists/precheck.md` now also rule out every other extractor (`tar`, `7z`, Python `zipfile`, PowerShell `Expand-Archive`), the research-agent runs the script on a scratch folder with an explicit output folder, and CI guards against a regression.
- **Prompt-injection guardrails** added to all ten agent definitions: source and guideline content is material to quote and summarize, never a directive, and the same holds for the extracts, data files, handovers and agent reports the other agents read. Text inside a PDF, ZIP, or e-book can be written to read like an instruction addressed to the agent; the agents now record such text as a flagged note and continue the original task instead of acting on it. `style-resolver.md` lists it as a labelled "not a rule" open question, never in a rule section of `styleguide.md`; `source-verifier.md` labels it as instruction-like content rather than a citation issue. `SECURITY.md` names this risk, but no agent definition had previously addressed it.
- **`requirements.txt` gained upper bounds** (`python-docx>=1.0.0,<2.0`, `pypdf>=3.0.0,<7.0`). An open range would silently pull in a new major release that changes the APIs these scripts rely on.
- **`docs/setup-wizard.html`: PowerShell quoting** — the generated command now also doubles the typographic single quotes U+2018–U+201B, which PowerShell treats as quote characters. A target containing one could end the quoted path and run the rest of the field as PowerShell commands; an ordinary folder name with an autocorrected apostrophe (`O’Brien`) broke the command.
- **`docx_postprocess.sh` refuses documents containing symbolic links.** unzip restores symlink entries, so a crafted `.docx` could make the re-zipped document embed arbitrary local files (e.g. an SSH key) or make the settings patch write outside the work directory.
- **`extract_styleguide.sh` caps disguised ZIPs** at 512 MiB unpacked and 10,000 entries ("Blocked (security)"), so a small crafted archive can no longer fill the disk or memory.
- **Personal data in generated projects** — `.gitignore` (and the copy both setup scripts write) now keeps all of `data/raw/` and `data/processed/` out of Git, as the workflows promise, instead of only `*.csv`/`*.xlsx` and `*_personal*`/`*_identified*` names (interview transcripts or SPSS files could be committed); the `data/processed/.gitkeep` placeholder is now actually committed. LibreOffice lock files (`.~lock.*#`, which record user and host name) and Word `~WRL*.tmp` files are ignored too.
- **CI** runs with a read-only `GITHUB_TOKEN` (`permissions: contents: read`) and a 15-minute job timeout.

---

## [6.3.0] — 2026-04-22

Licensing, state-file harmonization, and one structural polish. This is the last release before the public 1.0.0.

### Added

- **`LICENSE`** — Apache License 2.0, in full. cephalo is now officially licensed and ready for public distribution. Apache 2.0 was chosen over MIT for the explicit patent grant, which matters more for academic-tooling contexts where contributors may hold patents on methodology-adjacent work.
- **Copyright line** in the `LICENSE` appendix as "cephalo contributors" rather than an individual, reflecting the collaborative iteration history. Substitute with your name when tagging for initial release if preferred.

### Changed

- **State-file convention in flat workflows** is now consistently `workspace/state.md` throughout `bachelor_5agent.yaml` and `master_7agent.yaml`. Prior versions mixed `00_Status.md` (a long-form convention) into flat workflows — a historical leakage from when these workflows were derived from their long-form counterparts. The long-form workflows retain `00_Status.md` / `00_Decisions.md` / `00_Feedback_log.md` as intended. This resolves the last dangling item from the v6.2.1 changelog's "out of scope" section.
- **`rollback_b_to_a` block position** in flat `bachelor_5agent.yaml` and `master_7agent.yaml` is now a sub-key of `phase_transition_a_to_b` (matching the long-form structure), rather than a sibling top-level key. This resolves finding n1 from the v6.2.1 review: the two families of workflows now have the same nesting for this block.
- **`README.md`** License section filled in with the chosen license, replacing the "to be determined" placeholder.
- **`CONTRIBUTING.md`** License section similarly finalized, with a short note on why Apache 2.0 was preferred over MIT.

### Rationale for release cut

With v6.3.0, the last three dangling items from the v6.2.1 review are resolved:
1. The state-file inconsistency in flat workflows (flagged as "out of scope" in v6.2.1).
2. The structural asymmetry in the `rollback_b_to_a` block (new finding n1).
3. The missing license.

Any further iteration would be post-1.0.0, driven by actual usage rather than by internal review. The public release is now the correct next step.

---

## [6.2.1] — 2026-04-22

Patch release addressing findings from the v6.2 technical review.

### Fixed

- **Critical: `styleguide.md` path divergence in flat workflows.** Four flat workflows (`seminar_2agent`, `presentation_3agent`, `bachelor_5agent`, `master_7agent`) instructed the style-resolver to write `workspace/styleguide.md`, while all agents (orchestrator, writer-agent, format-verifier, style-resolver) and `CLAUDE.md` expected `styleguide.md` in the project root. A flat-structure user following the workflow would end up with the styleguide in a location no agent reads. All seven affected lines across the four workflows now use the root path consistently.
- **Escalation-stub references in long-form and defense orchestrators.** In v6.0, the feedback-loop escalation semantics in `orchestrator-longform.md` and `orchestrator-defense.md` were collapsed to stub references pointing at `orchestrator.md`. This violated the self-contained-agents principle documented in `CONTRIBUTING.md`: a sub-agent cannot automatically see other agent files at runtime. Both files now spell out the three escalation options (abort / manual_fix / force_continue) inline, with path references appropriate to each workflow type (`00_Status.md` / `00_Decisions.md` for long-form and defense, `workspace/state.md` for flat).
- **Key/file-name mismatch in `proposal_workflow.yaml` and `defense_workflow.yaml`.** The `agents:` block used the key `orchestrator:` while the file pointed to `orchestrator-longform.md` / `orchestrator-defense.md`. v5.0.0 fixed this for `bachelor_5agent_longform` and `master_7agent_longform` but missed these two. Keys and all `agent:` / `agents: [...]` references are now consistent.
- **Missing `rollback_b_to_a` block in flat `bachelor_5agent` and `master_7agent`.** Both flat workflows have explicit Phase A and Phase B, but no documented rollback procedure for the case where a Phase B verification surfaces a genuine content issue. The block from the long-form versions has been adapted (referencing `00_Status.md`) and added to both.
- **`setup.ps1`**: `git init` and `git lfs install` were in the same `try/catch`, so a missing LFS masked as a general git failure. Now separate: each is checked with `Get-Command` independently; missing LFS produces a gray info line, not a yellow warning. Matches the existing differentiation in `setup.sh`.

### Changed

- **`presentation_3agent.yaml`** description now explicitly states "No orchestrator — user drives manually", matching the note in `seminar_2agent.yaml`. This resolves an asymmetry where two orchestrator-less workflows documented their nature differently.
- **`checklists/format_rules.md`** Fallback section expanded with a short preamble explaining the relationship to the format-verifier's "do not guess" rule. The fallbacks are pre-declared typographic minima for users without institutional guidelines; they are distinct from runtime guessing and remain transparently documented.
- **`checklists/precheck.md`** — the `zip`/`unzip` requirement line now explicitly notes that Git Bash on Windows ships only `unzip`, not `zip`, with install pointers to MSYS2 and Scoop. Catches a setup-time confusion that surfaced during the v6.1 review.
- **`orchestrator-longform.md`** — `templates/styleguide.md` added to the templates list (was omitted in v6.0).
- **`docs/QUICKSTART.md`** — updated the release-folder name example to `cephalo-v6.2.1/`, matching the SemVer form used in the changelog.

### Out of scope (acknowledged but not changed)

- Workflow YAMLs for flat bachelor/master reference `00_Status.md` (a long-form convention) rather than `workspace/state.md`. The v6.2.1 rollback block was added consistently to the existing convention rather than triggering a broader state-file cleanup. A larger harmonization is candidate for v6.3.
- Several pre-existing minor inconsistencies (redundant `.strip()` in `abbreviations_extract.py`, asymmetric author comparison in `bibliography_check.py`) are documented in the tester's report but left in place; they are benign and changing them would risk regressions without corresponding benefit.

---

## [6.2.0] — 2026-04-22

First genuine feature release after the v3→v6.1 hardening series. Users can now choose where their project lives, instead of being forced to work inside the extracted cephalo folder.

### Added

- **Target directory selection** in both setup scripts. After a fresh extraction of cephalo, users can now decide at setup time where the project should be created, instead of working directly inside the download folder.
  - **`setup.sh`**: new `--target PATH` flag. If the flag is omitted and the run is interactive, the script asks: *"Where should the project be created? [1] Here / [2] Choose a different directory"*. On choice 2 it prompts for a path. Tilde expansion (`~/Documents/...`) is supported.
  - **`setup.ps1`**: analogous `-Target` parameter and interactive prompt. Tilde expansion uses `$env:USERPROFILE`.
- When a target is chosen, the cephalo template is **copied** into it (via `tar`-pipe on bash / `Copy-Item` on PowerShell, excluding any `.git`). The script then `cd`s into the target and continues the regular setup flow. At the end, the user is asked whether to delete the original folder — a safety check verifies that the folder still looks like a cephalo template before deleting.
- **Edge cases handled:**
  - Target path does not exist: created (including missing parent directories).
  - Target path is a non-empty directory: interactive confirmation required; non-interactive mode refuses and exits 2.
  - Target path equals current location: falls back to "proceed here" with a note.
  - Target path is an existing file (not a directory): exits 2 with an error.
- **`--help`** text in `setup.sh` updated to document the `--target` flag with examples.

### Changed

- **Setup prologue** now implicitly confirms to the user that the project will be created in the location they chose, reducing the "wait, where are my files?" moment that motivated this release.

### Rationale

The original design assumed users would work inside the extracted cephalo folder. In practice, people extract to Downloads and then ask where their thesis is. The new target flow lets users pick a sensible location (e.g., `~/Documents/Bachelorarbeit_KMU_OSS`) at setup time, without breaking the "agents and project content in the same directory" invariant that Claude Code requires.

---

## [6.1.3] — 2026-04-21

Fixes a user-visible regression in the setup experience on Windows.

### Fixed

- **`setup.sh` and `setup.ps1`** — on Windows, launching the setup script via double-click or "Run with PowerShell" opens a dedicated terminal window that auto-closes when the script exits. This made Ctrl+C feel like a crash: the window just disappeared, no message, no trace. Both scripts now install interrupt handlers that print a clear cancellation message ("Setup cancelled — already-created directories remain in place") and pause before the window closes. A pause at successful exit keeps the window open for users who started via double-click. Non-interactive / CI / piped runs skip the pause as before.

### Added

- **Prologue hint** in both setup scripts: users are now told up front that Ctrl+C cancels cleanly and that already-created directories will be skipped on the next run.

### Changed

- **`CONTRIBUTING.md`** release checklist gained an explicit SIGINT/Ctrl+C test step: "on Windows Git Bash, double-click setup.sh and press Ctrl+C before the first prompt; confirm that a cancellation message appears and the window stays open for reading".

---

## [6.1.2] — 2026-04-21

Documentation-only patch.

### Fixed

- **`CHANGELOG.md`** — the `## [6.1.0] — 2026-04-21` version header was missing between the v6.1.1 and v6.1.0 content, leaving the v6.1.0 notes orphaned as prose under the preceding `---` rule. Restored.

---

## [6.1.1] — 2026-04-21

Patch release after an end-to-end platform test on Windows + Git Bash revealed a silent fallback bug in the setup script.

### Fixed

- **`setup.sh` `create_symlink`** — on Git Bash (MinGW64) without `MSYS=winsymlinks:nativestrict` or elevated privileges, `ln -s` silently produces a directory copy instead of a real symlink and returns exit code 0. The previous code reported this as a successful symlink, leaving multi-project users with silent state drift: updates to `00_Shared_Materials/` appeared to propagate but did not. The function now verifies that a real symlink emerged (`[ -L ... ]`) and, if not, explicitly warns the user with remediation steps (Developer Mode, `MSYS=winsymlinks:nativestrict`, link to the re-sync snippet in the docs). The PowerShell setup script already had this behavior; now both scripts are consistent.
- **`docx_postprocess.sh`** — the error message for missing `zip`/`unzip` previously said "or Git Bash on Windows" as an install hint, but Git Bash ships only `unzip`, not `zip`. Message now explicitly recommends MSYS2 (`pacman -S zip`) or Scoop (`scoop install zip`).

### Added

- **`CONTRIBUTING.md`** — release checklist with explicit runtime-test matrix (Linux, macOS, Windows+Git Bash, Windows+PowerShell). This is the practice whose absence allowed the symlink bug to reach v6.1.
- **Git Bash diagnostic commands** in `CLAUDE.md` "Platform caveats" and in `docs/multiproject_structure.md` — `readlink shared` and a Bash re-sync snippet parallel to the existing PowerShell snippet.
- **Windows `zip` note** in `docs/scripts.md` — explicit callout that Git Bash doesn't ship with `zip`, with install options.

### Changed

- **`CLAUDE.md` "Platform caveats"** reorganized to cover both Windows shells side-by-side, making the behavioral difference between PowerShell's explicit failure and Git Bash's silent fallback visible.
- **`docs/multiproject_structure.md`** Windows section expanded with Git-Bash-specific diagnostic and re-sync commands.

---

## [6.1.0] — 2026-04-21

Polish release after three rounds of external review. The `bibliography_check.py` script now reliably handles German academic prose; the escalation behavior is discoverable from every orchestrator; internal consistency is improved.

### Fixed

- **`bibliography_check.py`** — the false-positive filter for German non-author capitalized words (months, document references, supranational bodies) was applied only to the narrative-without-parentheses pattern in 6.0, not to the narrative-with-parentheses pattern. Constructions like `"Die EU (2020) beschloss..."` or `"Das Kapitel (2020) zeigt..."` produced bogus "authors" in the minus-test report. Both patterns now share a single module-level `GERMAN_NON_AUTHOR_CAPS` constant and apply the same filter.
- **`bibliography_check.py`** — removed a duplicated comment line left over from an earlier refactor.

### Added

- **Escalation behavior stub** in `orchestrator-longform.md` and `orchestrator-defense.md` pointing to the canonical description in `orchestrator.md`. Readers of a single orchestrator file now find the information without cross-referencing.
- **Expanded stopword list** in `bibliography_check.py`: now also filters `Quartal`, `Semester`, `Halbjahr`, `DDR`, `BGH`, `BVerfG`, `BGB`, `StGB`, `HGB`, `GG`, `ZPO`, `StPO`, `Phase`, `Fall`, `Teil`, `Band`, `Heft`, `Auflage`, `Studie`, `Untersuchung`, `Forschung`, `Arbeit`, `Fußnote`. These are the German academic capitalized nouns most likely to be misread as surnames when they appear before a year in parentheses.

### Changed

- Non-flat workflow YAMLs (`bachelor_5agent_longform`, `master_7agent_longform`, `defense_workflow`, `proposal_workflow`) now carry a clarifying comment on the `feedback_loop_escalation` stub, stating that the canonical definition applies to all orchestrators.

---

## [6.0.0] — 2026-04-21

Substantial round of fixes to `bibliography_check.py` for German-language users, consistency improvements across workflows, and tighter feedback-loop semantics.

### Fixed

- **`bibliography_check.py`** — German author-year citations without a comma (`"Schmidt 2020, S. 15"`) were producing false positives on ordinary prose like `"Im Jahr 2020..."`, `"Die EU 2020..."`, `"Januar 2020..."`. Replaced with a strict two-layer heuristic: the bare-narrative pattern now requires a page reference (`S.`/`p.`/`pp.`) to accept a match, and a stopword list filters known German non-author capitalized words as a safety net.
- **`feedback_log.md` template** — example entries were on the same heading level as real entries, so they appeared as peers in IDE navigators. Restructured so the examples are `###` children under a `##` "DELETE THIS ENTIRE SECTION BEFORE USE" parent. Deleting the parent removes the entire block cleanly.
- **`orchestrator-defense.md`** — chat start ritual no longer delegates to `orchestrator-longform`; the five mandatory reads are now stated explicitly in the file.
- **`defense_workflow.yaml`** — Phase 0 now creates `00_Feedback_log.md` from the template, matching what the setup scripts produce and what the orchestrator writes into.
- **`docs/scripts.md`** — stale "Python 3.7" reference in the troubleshooting section corrected to 3.9 (matches the rest of the project).
- **`docs/reference_management.md`** — setup checklist now has separate entries for Zotero and Citavi users, plus tool-agnostic items. Previously the checklist only covered Zotero even though Citavi had a full setup section.
- **`format-verifier.md`, `writer-agent.md`** — "Phase B (formatting)" → "Phase B (Formatting)" for parity with "Phase A (Content)".
- **`orchestrator-longform.md`** — `feedback_log.md` added to the templates list.

### Changed

- **Workflow naming** unified: all four workflow files that contain a phase-A-to-B transition now use the key `phase_transition_a_to_b`. Previously the flat variants used the shorter `phase_transition` while long-form variants used `phase_transition_a_to_b`, causing drift.
- **Feedback-loop escalation** factored out: each workflow YAML now carries a minimal stub referring to `orchestrator.md` rather than duplicating the full behavior. Reduces drift risk when the escalation behavior evolves.
- **Seminar workflow** — `force_continue_suggested_limit: 3` now explicitly set (shorter works shouldn't encourage raising to 5). `orchestrator.md` reads this key and adapts its suggested limit accordingly; other workflows fall back to the default.
- **`setup.ps1`** confirmation prompt now reads `Proceed? (y/j = yes, n = no)` for parity with `setup.sh`.

---

## [5.0.0] — 2026-04-21

Second major round of fixes, addressing the external reviewer's 6 critical and 31 medium findings from v4. This is where cephalo moved from "works if you're careful" to "works in realistic conditions".

### Added

- **`docs/scripts.md`** — full end-to-end documentation for all four utility scripts, including installation, cross-platform usage, and troubleshooting.
- **`templates/feedback_log.md`** — canonical template for `00_Feedback_log.md`, with example entries illustrating the expected format.
- **Platform caveats section** in `CLAUDE.md` — explicit Windows symlink requirement (Administrator OR Developer Mode), diagnostic command (`Get-Item shared | Select-Object LinkType`), fallback behavior on failure.
- **`feedback_loop_escalation:` block** in all 8 workflows — documents what happens when `feedback_loop_max` is reached (abort / manual_fix / force_continue).
- **`rollback_b_to_a:` block** in long-form bachelor and master workflows — documents how to pause Phase B and reactivate Phase A when a genuine content issue surfaces during formatting.
- **`condition: empirical == true`** on methods and empirical phases in the master workflows — theoretical master theses cleanly skip these phases.
- **Citavi setup section** in `docs/reference_management.md` — full parallel to the existing Zotero section.
- **FAQ entries** in `README.md` for the two most common Windows/institutional gotchas (symlinks requiring permissions; what to do when an institution has no citation guide).
- **Troubleshooting block** in `docs/QUICKSTART.md` for common setup failures.
- **Explicit chat closure ritual** (five steps) in `orchestrator.md` and `orchestrator-defense.md`. Previously the flat orchestrator had no ritual at all; the defense orchestrator delegated to a different file.
- **`--help`** flag and positional-argument validation in `setup.sh`.
- **Encoding guard** in both Python scripts — reconfigures stdout to UTF-8 at startup, preventing `UnicodeEncodeError` on Windows consoles with CP1252.
- **`requirements.txt`** — pinned dependencies (`python-docx>=1.0.0`, `pypdf>=3.0.0`).

### Fixed

- **`bibliography_check.py`** — lead-author and narrative patterns now recognize hyphenated surnames (`Müller-Schmidt`), name prefixes (`van der Berg`, `de la Rosa`, `von Wagner`), and `et al.` narrative citations (`Brown et al. (2021)`). Previously these were silently dropped.
- **`abbreviations_extract.py`** — regex now uses explicit German uppercase class `[A-ZÄÖÜ]`, catching `ÖPNV`, `AfD`, and similar. `COMMON_ABBREVIATIONS` filter normalizes both sides identically (strip dots, uppercase), fixing a silent no-op bug.
- **`abbreviations_extract.py`** — extraction now reads paragraphs, tables (including nested), headers, footers, and footnotes. Previously only the main-body paragraphs were scanned.
- **`docx_postprocess.sh`** — full rewrite. Replaced non-portable `sed -i` invocations with Python, and replaced `zip -r` with Python's `zipfile` module to ensure `[Content_Types].xml` is the first entry and stored uncompressed (as OOXML requires). Earlier versions produced DOCX files that some Word installations refused to open.
- **`extract_styleguide.sh`** — full rewrite. Removed dependence on `file -b` (not present in Git Bash on Windows) and glob-star, and added ZipSlip hardening for archived PDFs with traversal paths. Now pure-Python via `pypdf` with `pdftotext` as optional fallback.
- **Two workflows (`defense_workflow`, `proposal_workflow`) had invalid YAML** — numbered inline lists within a YAML sequence were being parsed as mappings. YAML loaders raised `ScannerError`, which in turn caused earlier reference-integrity checks to silently skip these files. Replaced with flat string values.
- **`bachelor_5agent_longform.yaml`, `master_7agent_longform.yaml`** — the `agents:` block declared key `orchestrator` but the phases invoked `orchestrator-longform`. Keys now match invocations.
- **`style-resolver`** — now declared in the `agents:` block of all 8 workflows. Previously invoked from within phases but not declared, so strict reference-integrity checks flagged it.
- **`proposal_workflow.yaml`** — `format-verifier` is now declared in the `agents:` block (previously invoked but undeclared).
- **`setup.sh`** — string `"statusard"` (from a botched sed edit in an earlier version) corrected to `"Standard"`.
- **`setup.sh`** — `"dissertation"` / `"Dissertation"` case inconsistency resolved. Both the prompt and the workflow-selection branch now use `"Dissertation"`.
- **`setup.sh`** — `ask_choice` function now handles EOF cleanly (non-interactive runs print a usage hint and exit 2 instead of looping forever).
- **`setup.sh`** — `git init` failure is no longer silently discarded; the script reports a clear message and suggests manual invocation.
- **`setup.sh`, `setup.ps1`** — `Master thesis` and `Dissertation` flat setups now create `workspace/methods/` and `workspace/data/{raw,processed,scripts,outputs}/` directories. Previously the configuration referenced these paths but the setup scripts didn't create them.
- **`setup.sh`, `setup.ps1`** — `.gitkeep` created in `03_Defense/05_Rehearsals/` in both scripts (parity fix).
- **`setup.ps1`** — `$NonInteractive` flag is now respected at the `Proceed?` prompt. Previously the flag was declared but ignored in one code path.
- **`setup.ps1`** — long-form structure matching changed from exact string (`-eq "Long-form (phase-based...)"`) to prefix-match (`-match "^Long-form"`), consistent with the multi-project branch.
- **`setup.ps1`** — UTF-8 writes now go through a `Write-Utf8NoBom` helper that uses `[System.IO.File]::WriteAllText` with `UTF8Encoding $false`. Previously `Set-Content -Encoding UTF8` wrote a BOM on PowerShell 5.1, which caused Git hooks and Linux tools to stumble.
- **`setup.ps1`** — removed dead conditional `$MainName = if (...) { "02_Main_Work" } else { "02_Main_Work" }`.
- **Cross-cutting**: `Phase A` / `Phase B` capitalization unified (was inconsistently mixed across prose files).

### Changed

- **`feedback_log.md` template** is now copied by the setup scripts on Long-form and Multi-project runs, replacing the earlier one-line stub (`echo "# Feedback Log" > ...`).
- **Numerous agent files** — `File paths` sections expanded to include all files the agent writes to (previously some paths were referenced only in the body).
- **`methods-agent.md`** — path convention changed from the non-existent `workspace/sources/methods/` to a prefix-based convention (`methods_mayring_2014.md` inside the shared `workspace/sources/`).
- **`format-verifier.md`** — lost the `Edit` tool privilege; verifiers only read and report, they do not edit.
- **Workflow: `master_7agent_longform`** — gained a `consistency_check:` block matching the flat-master variant.
- **Workflow: `bachelor_5agent`** — `phase_transition_a_to_b` now has an explicit `verification_method:` describing how the orchestrator should check each criterion.

### Removed

- **Dead assignment** `part = doc.part.package.parts` in `abbreviations_extract.py`.

---

## [4.0.0] — 2026-04-21

First round of external review and fixes. Addressed the critical bugs from the v3 audit.

### Added

- **`requirements.txt`** with `python-docx` and `pypdf`.
- **Institution-specific legacy predecessor (v2)** preserved privately as a production fallback. (Separate artifact; not part of the cephalo tree.)

### Fixed

- **`setup.sh`** — numerous v3 bugs: corrupted string literals from earlier sed passes, case-sensitivity mismatches, positional-argument handling.
- **`docx_postprocess.sh`** — portable across macOS and Linux (`sed -i` behavior differs).
- **`extract_styleguide.sh`** — safer handling of archived-PDF inputs.

### Changed

- All agent files: `DATEIPFADE` sections (German, legacy from v2) translated to `File paths` (English). Documentation file in `CLAUDE.md` updated to match.

---

## [3.0.0] — 2026-04-21

Initial open-source release of cephalo. Rewrite of an institution-specific, German-language v2 predecessor into an institution-agnostic, English-language form.

### Added

- 10 agent definitions (orchestrator, orchestrator-longform, orchestrator-defense, research, writer, source-verifier, format-verifier, style-resolver, methods, data).
- 8 workflow configurations (seminar, presentation, bachelor flat+longform, master flat+longform, proposal, defense).
- 4 checklists (precheck, format rules, consistency, plagiarism protection).
- 5 templates (status, decisions, handover, feedback log placeholder, styleguide).
- 4 utility scripts (style guide extraction, DOCX post-processing, abbreviations extraction, bibliography check).
- Documentation (QUICKSTART, error catalog, phase separation, long-form structure, multi-project structure, reference management, git introduction).
- Setup scripts for Linux/macOS (`setup.sh`) and Windows (`setup.ps1`).

### Design principles (carried over from v2)

- **Institution-agnostic via `style-resolver`** — citation conventions are extracted from institutional guidelines at setup, not hardcoded in prompts.
- **Phase separation** — content work (Phase A, capable models) and formatting work (Phase B, fast models) run with different agent activation, reducing cost ~60-70% against naive use throughout.
- **Self-contained agents** — Claude Code sub-agents cannot read `CLAUDE.md`, so each agent declares its own file paths and mandatory-read behavior.
- **Structural isolation of guidelines** — the `_guidelines/` underscore prefix keeps institutional rule documents separate from citable source literature.

---

## About the pre-release iteration

v3.0.0, v4.0.0, v5.0.0, v6.0.0, and v6.1.0 were released on the same day as a compressed iteration cycle in collaboration with an external reviewer. The version numbers reflect the scale of change at each step (major refactors vs. patch-level polish) rather than calendar time. Subsequent releases will follow a more conventional cadence.
