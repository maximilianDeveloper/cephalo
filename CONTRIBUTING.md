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

**2. Self-contained agents.** Every agent definition declares its own file paths and mandatory reads. Do not rely on `CLAUDE.md` (which Claude Code may pass to sub-agents as well) or other documentation to instruct an agent at runtime: what an agent needs belongs in its own definition.

**3. Phase separation.** Content work (Phase A, capable models) and formatting work (Phase B, fast models) must stay separated. Mixing them eliminates the cost saving that phase separation provides.

**4. Structural isolation of guidelines.** Institutional guideline documents live in a dedicated directory, separate from the citable sources (`workspace/sources/_guidelines/` in flat, where the leading underscore marks it as non-citable; top-level `guidelines/` in long-form; `00_Shared_Materials/guidelines/` in multi-project), so the research-agent does not mistake them for citable sources.

**5. Templates over hardcoding.** If a setup script writes a file, the file's contents should come from `templates/`. Inline content in scripts drifts.

## Release checklist

Before tagging a new version, run the full checklist below. The static checks catch most issues; the runtime checks catch everything else.

### Static checks (from the repository root)

```bash
# Dependencies (as in CI)
python3 -m pip install -r requirements.txt pyyaml

# YAML parse: all 8 workflows must load (explicit UTF-8, as in CI)
python3 - <<'EOF'
import glob, yaml
files = sorted(glob.glob("workflows/*.yaml"))
assert len(files) == 8, f"expected 8 workflow files, found {len(files)}"
for f in files:
    yaml.safe_load(open(f, encoding="utf-8"))
    print("OK", f)
EOF

# Reference integrity (agents declared and present, frontmatter names, archive
# routing): run the Python block of the "Agent and workflow references" step
# in .github/workflows/ci.yml; CI runs the same check

# Shell syntax (one file per call: bash -n treats further names as arguments)
for f in setup.sh scripts/docx_postprocess.sh scripts/extract_styleguide.sh; do
    bash -n "$f" || echo "FAILED: $f"
done

# Shell lint (as in CI)
shellcheck setup.sh scripts/docx_postprocess.sh scripts/extract_styleguide.sh

# Python syntax
python3 -m py_compile scripts/abbreviations_extract.py scripts/bibliography_check.py scripts/cross_session_audit.py scripts/verbatim_check.py
```

### Runtime checks — the part that catches real bugs

**This is the lesson from the v6.1 release review.** Static checks miss platform-specific issues. Setup scripts that use `ln`, `New-Item`, `curl`, or any shell primitive that behaves differently across OSes must be run on each target platform before release.

At minimum, before a release, execute `setup.sh` or `setup.ps1` in a fresh copy of the template (extracted archive or clone) on:

- **Linux** (any recent distro — Ubuntu, Fedora, Arch): `bash setup.sh`
- **macOS** (any recent version): `bash setup.sh`
- **Windows + Git Bash** (MinGW64, the default from Git for Windows): `bash setup.sh`
- **Windows + PowerShell 5.1 or 7**: `./setup.ps1`

For each platform, test at least:

1. Flat structure (simplest, least moving parts)
2. Long-form structure (validates phase directory creation)
3. Multi-project structure (validates the three sub-projects and `00_Shared_Materials/`)

After each run, verify:

- All expected directories exist
- `.gitignore` and `.gitattributes` are present
- Multi-project: the sub-projects contain no `shared/` link or copy (the agents read `../00_Shared_Materials/`)
- Templates were copied from `templates/`, not echo-stubbed
- The reported workflow name matches what the configuration says

### Interrupt-handling tests (5 minutes, prevents silent-crash UX)

On each Windows shell:

1. **Git Bash, double-click start.** Double-click `setup.sh` in Explorer (or `bash setup.sh` without an already-open terminal). Press Ctrl+C before answering the first prompt. Expected: yellow cancellation message appears, window stays open with "Press Enter to close..."
2. **PowerShell, "Run with PowerShell" from context menu.** Same test: Ctrl+C early. Expected: the script stops without creating anything, and the window closes at once. PowerShell runs no trap on Ctrl+C (see the comment in `setup.ps1`), so there is no message or pause here; the yellow message and pause belong to terminating errors. On Windows 11 the entry is under "Show more options" (or select the file and press Shift+F10). Where it is missing, open PowerShell in the template folder (type `powershell` in Explorer's address bar) and run `Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File .\setup.ps1'`: it opens a window that closes when the script ends, as the entry does.

If the Git Bash window disappears silently, it's a regression of v6.1.3. Most users first learn about a tool by accidentally triggering Ctrl+C — a silent-close here is a confidence-killer.

On Linux and macOS, running from an already-open shell: Ctrl+C should print the message, wait at "Press Enter to close...", and return to the prompt after Enter.

### Target-directory tests (5 minutes, covers the v6.2 feature)

On each platform, run all five target scenarios:

1. **Flag-based, clean target:**
   ```bash
   ./setup.sh "Seminar paper" "Flat" full --target /tmp/ceph_test_1
   ```
   Expected: template copied, project created inside target, original kept. In a terminal the script still asks "Delete it now?" at the end (answer N); with `</dev/null` appended it runs fully non-interactive.

2. **Interactive "choose a different directory":** run `./setup.sh`, answer `2` at the location prompt, enter a fresh path. Expected: same result as above, plus final prompt "Delete it now?".

3. **Non-empty target, non-interactive:**
   ```bash
   mkdir /tmp/ceph_nonempty && touch /tmp/ceph_nonempty/existing.txt
   ./setup.sh "Seminar paper" "Flat" full --target /tmp/ceph_nonempty
   ```
   Expected: exits 2, yellow warning printed, target folder untouched.

4. **Target = source:** in a throwaway copy of the template, run `./setup.sh "Seminar paper" "Flat" full --target "$(pwd)"`. Expected: prints "Target path equals current location — proceeding here." and sets up in place without copy.

5. **Folder inside the template at the prompt:** run `./setup.sh` (or `.\setup.ps1`), answer `2`, and enter a bare folder name such as `Thesis`. Expected: "That folder lies inside the cephalo template folder:" with the full path, then "Target path:" again, and nothing is created. A full path outside the template entered next is used.

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
d.add_paragraph('Im Jahr 2020 stieg die Zahl. Die EU (2020) reagierte. Das Kapitel (2020) fasst zusammen.')
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
- If the change touches `README.md` or `docs/QUICKSTART.md`, re-render the embedded copy in `docs/setup-wizard.html` (between the `DOC_README_*` / `DOC_QUICKSTART_*` markers). CI fails while their wording differs; it compares words only, so check changed punctuation, options and paths (such as `--target` or `.\setup.ps1`) by eye.

## Versioning

cephalo follows [Semantic Versioning](https://semver.org/):

- **Major** — structural changes that existing projects cannot adopt without migration (e.g., directory layout, workflow schema)
- **Minor** — new functionality, new agents, new workflows
- **Patch** — bug fixes, documentation improvements, polish

## License

cephalo is licensed under the Apache License 2.0. See `LICENSE` for the full text.

By submitting a contribution, you agree that your contribution is licensed under the same terms. You retain your copyright; the license grant is what allows the project to redistribute your work.

Apache 2.0 was chosen over MIT for the explicit patent grant — contributors cannot later assert patent claims against downstream users of their own contributions. This matters more in academic-tooling contexts than in a casual MIT setting.
