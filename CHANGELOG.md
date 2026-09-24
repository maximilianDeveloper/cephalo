# Changelog

All notable changes to cephalo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Dates follow ISO 8601 (`YYYY-MM-DD`).

---

## [1.0.0] — 2026-09-24

**First public release.** A browser-based setup assistant, a documentation and utility-script hardening pass, removal of hard-coded formatting rules from three agent definitions, a pre-publication review sweep (license text, distribution docs, GitHub project files), and a pre-publication security pass (see **Security** below). No workflow or template changes.

### Added

- **GitHub project files** — a minimal CI workflow (`.github/workflows/ci.yml`: script syntax/compile checks, workflow-YAML validation, and non-interactive setup smoke runs on Ubuntu and Windows), issue and pull-request templates aligned with `CONTRIBUTING.md`, and a `SECURITY.md` describing scope and the private reporting channel.
- **`docs/setup-wizard.html`** — a self-contained, offline setup assistant. Pick work type, structure, scaffolding, and platform, and it builds the exact `setup.ps1` / `setup.sh` command and previews the folder structure that will be created. It also offers a one-click **Download launcher** button that saves a small, preconfigured start script (`cephalo-setup.cmd` on Windows, `.command` on macOS, `.sh` on Linux) — save it into your cephalo folder and double-click to run setup without touching a terminal. Static HTML with no dependencies or network access; it generates commands and launcher scripts but never runs anything itself. Linked from `README.md` and `docs/QUICKSTART.md`.

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

### Documentation

- `docs/scripts.md` now documents `cross_session_audit.py` alongside the other four utility scripts, and its usage/behavior descriptions for `abbreviations_extract.py`, `bibliography_check.py`, `docx_postprocess.sh`, and `extract_styleguide.sh` are updated to match current script behavior, including the remaining known heuristic gap (multi-word institutional bibliography authors; single-word ones and numbered/punctuated bibliography headings are handled).
- `README.md` gains a **Responsible use** section (check your institution's AI rules, disclose your use, own every claim) and clearer early-stage wording.
- `README.md` quick start now names the acquisition paths (release archive, Code -> Download ZIP, `git clone`) and recommends `--target` for cloned copies; the Git FAQ explains that setup skips `git init` when a `.git` directory already exists. The Administrator note is scoped to multi-project setups (flat/long-form need no elevation), and an illustrative source-verifier finding shows what the tool actually produces. `CONTRIBUTING.md` and this changelog are linked from the README.
- Plagiarism-threshold wording harmonized: `docs/error_catalog.md` now states the same warning band (8-14 verbatim words) as the binding table in `checklists/plagiarism_protection.md`, whose worked example now quotes the real 10-word verbatim run.
- `docs/git_introduction.md` gains a "tell Git who you are" section (`git config --global user.name/user.email`), so a first-ever commit no longer fails unexplained with "Author identity unknown".
- `checklists/consistency.md` no longer hardcodes an institution-specific pagination scheme, body alignment, or presentation timing; these defer to `styleguide.md` keys like the rest of the checklists.
- Example tokens in scripts and docs are domain-neutral (`B2B` in the acronym examples; `WHO`/`OECD`/`Statistisches Bundesamt` as institutional-author examples).

### Changed

- `cross_session_audit.py` report output and inline documentation are now in English, matching the rest of the framework (behavior unchanged).
- Agent definitions (`writer-agent.md`, `format-verifier.md`, `data-agent.md`) and `checklists/format_rules.md` no longer hard-code institution-specific formatting rules (a first-person/voice ban, fixed title-page elements, a fixed pagination scheme, table-of-contents emphasis, caption placement, and two citation deviations). These now defer to `styleguide.md`; any concrete values that remain are kept only as explicitly institution-neutral illustrative defaults. This restores the framework's core principle that formatting rules live only in the generated `styleguide.md`, never hard-coded in prompts.

### Security

- **ZIP extraction is routed through `scripts/extract_styleguide.sh`** in `research-agent.md` and `style-resolver.md`. Both previously instructed a bare `unzip`, bypassing the script's `safe_extract_zip()`, which rejects entries carrying absolute paths or `..` components. A prepared archive — a style guide downloaded from anywhere — could otherwise have written outside the target directory.
- **Prompt-injection guardrails** added to `research-agent.md`, `source-verifier.md`, and `style-resolver.md`: source and guideline content is material to quote and summarize, never a directive. Text inside a PDF, ZIP, or e-book can be written to read like an instruction addressed to the agent; the agents now record such text as a flagged note and continue the original task instead of acting on it. `SECURITY.md` names this risk, but no agent definition had previously addressed it.
- **`requirements.txt` gained upper bounds** (`python-docx>=1.0.0,<2.0`, `pypdf>=3.0.0,<7.0`). An open range would silently pull in a new major release that changes the APIs these scripts rely on.

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
