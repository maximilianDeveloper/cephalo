# Contributing to cephalo

cephalo is an early open-source project. Contributions, bug reports, and review feedback are welcome.

## Reporting issues

When reporting a bug, please include:

- cephalo version (see `CHANGELOG.md` or the git tag)
- Platform and shell (e.g., "Windows 11 + Git Bash", "macOS 14 + zsh", "Ubuntu 22.04 + bash")
- Exact command that triggered the issue
- Full output, not just the error message
- What you expected to happen vs. what actually happened

Issues that are "something feels off" without reproduction steps are valued, but usually need a back-and-forth to pin down. Reproducible reports get fixed faster.

## Design principles to preserve

Before proposing larger changes, please read through these. They came out of real project experience and protect against common drift.

**1. Institution-agnostic via style-resolver.** Never hardcode citation rules (APA 7, Chicago, institutional house styles, etc.) into agent prompts. The `style-resolver` extracts rules from institutional guidelines into `styleguide.md`; agents read that file. Exceptions undermine the entire architecture.

**2. Self-contained agents.** Claude Code sub-agents cannot read `CLAUDE.md`. Every agent definition declares its own file paths and mandatory reads. Do not rely on external documentation being visible to the agent at runtime.

**3. Phase separation.** Content work (Phase A, capable models) and formatting work (Phase B, fast models) must stay separated. Mixing them eliminates the cost saving that phase separation provides.

**4. Structural isolation of guidelines.** Institutional guideline documents live in an underscore-prefixed directory (`_guidelines/` in flat, `guidelines/` at the top level in long-form) so the research-agent does not mistake them for citable sources.

**5. Templates over hardcoding.** If a setup script writes a file, the file's contents should come from `templates/`. Inline content in scripts drifts.

## Release checklist

Before tagging a new version, run the full checklist below. The static checks catch most issues; the runtime checks catch everything else.

### Static checks (from the repository root)

```bash
# YAML parse: all 8 workflows must load
for f in workflows/*.yaml; do
    python3 -c "import yaml; yaml.safe_load(open('$f'))" || echo "FAILED: $f"
done

# Reference integrity: every agent invoked in a workflow must be declared
# (manual check: each agent name referenced in a workflow YAML must exist in .claude/agents/)

# Shell syntax
bash -n setup.sh scripts/docx_postprocess.sh scripts/extract_styleguide.sh

# Python syntax
python3 -m py_compile scripts/abbreviations_extract.py scripts/bibliography_check.py scripts/cross_session_audit.py
```

### Runtime checks — the part that catches real bugs

**This is the lesson from the v6.1 release review.** Static checks miss platform-specific issues. Setup scripts that use `ln`, `New-Item`, `curl`, or any shell primitive that behaves differently across OSes must be run on each target platform before release.

At minimum, before a release, execute `setup.sh` or `setup.ps1` in a clean directory on:

- **Linux** (any recent distro — Ubuntu, Fedora, Arch): `bash setup.sh`
- **macOS** (any recent version): `bash setup.sh`
- **Windows + Git Bash** (MinGW64, the default from Git for Windows): `bash setup.sh`
- **Windows + PowerShell 5.1 or 7**: `./setup.ps1`

For each platform, test at least:

1. Flat structure (simplest, least moving parts)
2. Long-form structure (validates phase directory creation)
3. Multi-project structure (validates symlinks — this is where platform differences hurt most)

After each run, verify:

- All expected directories exist
- `.gitignore` and `.gitattributes` are present
- Symlinks, where expected, are real symlinks (not copies)
- Templates were copied from `templates/`, not echo-stubbed
- The reported workflow name matches what the configuration says

### Interrupt-handling tests (5 minutes, prevents silent-crash UX)

On each Windows shell:

1. **Git Bash, double-click start.** Double-click `setup.sh` in Explorer (or `bash setup.sh` without an already-open terminal). Press Ctrl+C before answering the first prompt. Expected: yellow cancellation message appears, window stays open with "Press Enter to close..."
2. **PowerShell, "Run with PowerShell" from context menu.** Same test: Ctrl+C early. Expected: same yellow message and pause.

If the window disappears silently, it's a regression of v6.1.3. Most users first learn about a tool by accidentally triggering Ctrl+C — a silent-close here is a confidence-killer.

On Linux and macOS, running from an already-open shell: Ctrl+C should print the message and return to the prompt (no pause needed, since the terminal stays open anyway).

### Target-directory tests (5 minutes, covers the v6.2 feature)

On each platform, run all four target scenarios:

1. **Flag-based, clean target:**
   ```bash
   ./setup.sh "Seminar paper" "Flat" full --target /tmp/ceph_test_1
   ```
   Expected: template copied, project created inside target, original kept (non-interactive).

2. **Interactive "choose a different directory":** run `./setup.sh`, answer `2` at the location prompt, enter a fresh path. Expected: same result as above, plus final prompt "Delete it now?".

3. **Non-empty target, non-interactive:**
   ```bash
   mkdir /tmp/ceph_nonempty && touch /tmp/ceph_nonempty/existing.txt
   ./setup.sh "Seminar paper" "Flat" full --target /tmp/ceph_nonempty
   ```
   Expected: exits 2, yellow warning printed, target folder untouched.

4. **Target = source:** run `./setup.sh "X" "Y" full --target $(pwd)`. Expected: falls back to "proceeding here" mode without copy.

If any of these fail on any platform, the release is blocked.

### Utility scripts

On at least one platform, run each utility script end-to-end against a real DOCX:

```bash
# Build a small test DOCX first (Python required)
python3 -c "
from docx import Document
d = Document()
d.add_heading('Test', 1)
d.add_paragraph('Schmidt 2020, S. 15 führt aus. Müller (2021) stimmt zu.')
d.add_heading('Literaturverzeichnis', 1)
d.add_paragraph('Schmidt, K. (2020). Test A.')
d.add_paragraph('Müller, J. (2021). Test B.')
d.save('test.docx')
"

python3 scripts/abbreviations_extract.py test.docx
python3 scripts/bibliography_check.py test.docx
bash scripts/docx_postprocess.sh test.docx
```

The `bibliography_check.py` output should not contain false positives for German prose constructs like `"Im Jahr 2020..."`, `"Die EU (2020)..."`, or `"Das Kapitel (2020)..."`. These are regression-test cases.

## Pull requests

- One logical change per PR. Small, focused changes merge faster.
- Update `CHANGELOG.md` in the same PR (add an `[Unreleased]` section at the top if none exists yet).
- If the change touches the setup scripts, confirm in the PR description which platforms you tested on.
- If the change touches `scripts/bibliography_check.py`, include a test case showing the new behavior.

## Versioning

cephalo follows [Semantic Versioning](https://semver.org/):

- **Major** — structural changes that existing projects cannot adopt without migration (e.g., directory layout, workflow schema)
- **Minor** — new functionality, new agents, new workflows
- **Patch** — bug fixes, documentation improvements, polish

## License

cephalo is licensed under the Apache License 2.0. See `LICENSE` for the full text.

By submitting a contribution, you agree that your contribution is licensed under the same terms. You retain your copyright; the license grant is what allows the project to redistribute your work.

Apache 2.0 was chosen over MIT for the explicit patent grant — contributors cannot later assert patent claims against downstream users of their own contributions. This matters more in academic-tooling contexts than in a casual MIT setting.
