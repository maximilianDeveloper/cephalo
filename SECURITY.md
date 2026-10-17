# Security Policy

## Scope

cephalo ships code that runs locally on your machine:

- the setup scripts (`setup.sh`, `setup.ps1`),
- the utility scripts in `scripts/` — including `extract_styleguide.sh`, which parses untrusted third-party PDFs and ZIP archives, `verbatim_check.py`, which reads such PDFs as well, and `docx_postprocess.sh` and `docx_pagination.py`, which rewrite DOCX files in place,
- the cephalo guard (`scripts/cephalo_guard.py`, started by `scripts/cephalo_guard.sh`), a Claude Code hook that setup installs in `.claude/settings.json`: Claude Code runs it on each shell command, file write or edit and agent call. It reads that call's input from stdin and prints a verdict, can deny a call but never allows one that Claude Code would otherwise ask about, writes nothing but a small file per session in `cephalo-guard/` in the system's temporary folder, and uses no network,
- the setup wizard (`docs/setup-wizard.html`), which generates commands and launcher scripts but never executes anything itself.

Vulnerabilities in any of these are in scope: command or path injection, archive-extraction issues (e.g. path traversal), unsafe file handling, anything that makes a generated command do more than it displays, or a tool call that makes the guard run anything but its own check or block calls it should let pass. A slip the guard does not catch is a bug, not a vulnerability.

The agent definitions (`.claude/agents/`) process user-supplied documents. Reports about prompt-injection-style behavior (a source document steering an agent into unintended actions) are welcome as hardening suggestions — please report them the same way, but note they are mitigations-by-design territory, not CVE material.

## Supported versions

Only the latest tagged release is supported with fixes.

## Reporting a vulnerability

Please use **GitHub's private vulnerability reporting**: on the repository page, go to the **Security** tab and choose **Report a vulnerability**. This keeps the report private while it is being assessed.

Please do **not** open a public issue for security-relevant findings — a public issue would expose users before a fix exists.

Include what you would for any bug (platform, exact command, full output, expected vs. actual), plus your assessment of impact. You can expect an initial response within two weeks; fixes are published as a new tagged release with a `CHANGELOG.md` entry crediting the reporter (unless you prefer otherwise).
