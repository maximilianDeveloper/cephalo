#!/usr/bin/env python3
"""Cross-session audit for multi-worktree repositories.

Identifies potentially lost information from old worktrees or sessions that was
never integrated into the current main worktree.

Three layers (numbering matches the report sections):
1. Main diff: which `_*.md` files exist in worktrees but NOT in the main worktree?
2. Reference validation: scans main-branch files for backticked cross-refs to
   other `.md` files (paths with a two-digit `NN_`, `scripts/`, or `workspace/`
   prefix) and checks that the targets exist.
3. Uncommitted changes per worktree.

The report also includes a worktree overview: all worktrees, their HEADs,
uncommitted changes, and closing/briefing/TODO notes (the `_*.md` pattern).

Run:
    python scripts/cross_session_audit.py [--report-file PATH] [--repo-root PATH]

Default output: stdout. With --report-file a Markdown report is also written.

Exit codes: 0 = no findings, 1 = findings (for CI / hooks),
2 = error (the audit could not run, e.g. not a git repository).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Reconfigure stdout/stderr to UTF-8 for Windows CP1252 consoles (common on
# non-UTF-8 Windows). Same pattern as other scripts in the project.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Underscore pattern for closing/briefing/TODO/pause notes
UNDERSCORE_GLOB = "**/_*.md"

# Directories that are not relevant
EXCLUDE_DIRS = {".git", ".claude", "node_modules", "__pycache__", "_Backups"}

# Framework documentation files that are not project-specific
# (refs inside them are examples from the cephalo template, not real project refs)
FRAMEWORK_DOC_FILES = {
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "CLAUDE.md",
}
FRAMEWORK_DOC_DIRS = {"docs", "templates", "checklists", "workflows"}

# Repository-local variables (`git rev-parse --local-env-vars`) that git exports
# to hooks. Inherited, they would make `git status` in the other worktrees read
# the calling worktree's index or repository, so they are not passed on. The
# `git -c` overrides GIT_CONFIG_PARAMETERS / GIT_CONFIG_COUNT are kept, as git
# itself does for submodules (e.g. a safe.directory set that way still applies).
GIT_LOCAL_ENV_VARS = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_OBJECT_DIRECTORY",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE",
    "GIT_PREFIX",
    "GIT_SHALLOW_FILE",
    "GIT_COMMON_DIR",
}


@dataclass
class WorktreeInfo:
    path: Path
    branch: str
    head: str
    is_main: bool = False
    is_bare: bool = False
    uncommitted: list[str] = field(default_factory=list)
    underscore_files: list[Path] = field(default_factory=list)


def run_git(args: list[str], cwd: Path) -> str:
    """Run git command and return stdout, raising on error."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env={k: v for k, v in os.environ.items() if k not in GIT_LOCAL_ENV_VARS},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        # One line: git's stderr can span several lines (e.g. dubious ownership).
        stderr = " ".join(result.stderr.split())
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {stderr}")
    return result.stdout


def find_repo_root(start: Path) -> Path:
    """Find the repository root by walking up until a .git is found."""
    out = run_git(["rev-parse", "--show-toplevel"], start)
    return Path(out.strip())


def list_worktrees(repo_root: Path) -> list[WorktreeInfo]:
    """Parse `git worktree list --porcelain` output."""
    out = run_git(["worktree", "list", "--porcelain"], repo_root)
    worktrees: list[WorktreeInfo] = []
    current: dict = {}
    for line in out.splitlines():
        if not line:
            if current:
                worktrees.append(_dict_to_worktree(current))
                current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line.removeprefix("worktree ").strip()
        elif line.startswith("HEAD "):
            current["head"] = line.removeprefix("HEAD ").strip()[:7]
        elif line.startswith("branch "):
            current["branch"] = line.removeprefix("branch ").strip().removeprefix("refs/heads/")
        elif line == "bare":
            current["bare"] = True
    if current:
        worktrees.append(_dict_to_worktree(current))

    # Mark the main worktree: the first entry in `git worktree list
    # --porcelain` is always the main worktree per git docs. (An earlier
    # path-based heuristic was removed: it misidentified the main worktree
    # whenever the main repo itself lived under a directory named
    # `worktrees`.)
    if worktrees:
        worktrees[0].is_main = True
    return worktrees


def _dict_to_worktree(d: dict) -> WorktreeInfo:
    return WorktreeInfo(
        path=Path(d["path"]),
        branch=d.get("branch", "(detached)"),
        head=d.get("head", "?"),
        is_bare=d.get("bare", False),
    )


def get_uncommitted(worktree_path: Path) -> list[str]:
    """Return porcelain status lines for the worktree, raising on error.

    --no-optional-locks: do not refresh the worktree's index under index.lock,
    which could make a parallel session's git command in that worktree fail.
    """
    # core.quotepath=false: show non-ASCII file names (umlauts) as they are,
    # not as octal escapes like "\303\274".
    out = run_git(
        ["-c", "core.quotepath=false", "--no-optional-locks", "status", "--porcelain"],
        worktree_path,
    )
    return [line for line in out.splitlines() if line]


def find_underscore_files(worktree_path: Path) -> list[Path]:
    """Find all `_*.md` files in the worktree, excluding irrelevant directories.

    Important: We only check EXCLUDE_DIRS against the relative-path parts
    (relative to worktree_path), not the absolute path. Otherwise, all
    worktrees under `.claude/worktrees/` would be filtered out because
    `.claude` appears in their absolute path.
    """
    matches: list[Path] = []
    for path in worktree_path.glob(UNDERSCORE_GLOB):
        if not path.is_file():
            continue
        try:
            relpath = path.relative_to(worktree_path)
        except ValueError:
            continue
        if any(part in EXCLUDE_DIRS for part in relpath.parts):
            continue
        matches.append(relpath)
    return sorted(matches)


def file_size_human(path: Path) -> str:
    """Return file size in human-readable form (KB / MB)."""
    try:
        size = path.stat().st_size
    except OSError:
        return "?"
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def file_mtime(path: Path) -> str:
    """Return file mtime as YYYY-MM-DD HH:MM."""
    try:
        ts = path.stat().st_mtime
    except OSError:
        return "?"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def collect_worktree_data(worktrees: list[WorktreeInfo]) -> None:
    """Populate uncommitted + underscore_files for each worktree (in place)."""
    for wt in worktrees:
        # A bare main repository has no working tree to inspect.
        if wt.is_bare or not wt.path.exists():
            continue
        wt.uncommitted = get_uncommitted(wt.path)
        wt.underscore_files = find_underscore_files(wt.path)


def find_master_only_diff(
    worktrees: list[WorktreeInfo],
) -> dict[Path, list[tuple[str, Path]]]:
    """Find `_*.md` files that exist in some worktree but NOT in the main worktree.

    Returns a dict {relative_path: [(worktree_branch, full_path)]}.
    """
    main = next((wt for wt in worktrees if wt.is_main), None)
    if not main:
        return {}
    main_files = set(main.underscore_files)

    missing: dict[Path, list[tuple[str, Path]]] = {}
    for wt in worktrees:
        if wt.is_main:
            continue
        for relpath in wt.underscore_files:
            if relpath in main_files:
                continue
            full = wt.path / relpath
            missing.setdefault(relpath, []).append((wt.branch, full))
    return missing


def find_dangling_refs(main_path: Path) -> list[tuple[Path, str, str]]:
    """Scan all .md files in the main worktree for cross-refs that point to non-existent files.

    Returns list of (source_file, line_text, missing_target).

    The regex requires a directory separator (slash or backslash) in the
    candidate path — otherwise generic mentions like `00_Status.md` in
    framework docs would create false positives. Framework docs themselves
    are also excluded from the source-side scan.

    Recognized refs are backticked `.md` paths starting with `NN_...`
    (two ASCII digits; long-form / multi-project layouts), `scripts/`, or
    `workspace/` (flat layout).
    """
    import re

    # Path must contain at least one '/' or '\' to be considered a real ref.
    # Otherwise we match every generic mention like `00_Status.md` and produce
    # noise from CHANGELOG.md / README.md. Recognized prefixes: `NN_...`
    # (two ASCII digits, as in the sub-project root check below; long-form /
    # multi-project), `scripts/`, and `workspace/` (flat).
    REF_PATTERN = re.compile(
        r"`((?:[0-9]{2}_[^`]*[/\\][^`]*?|(?:scripts|workspace)[/\\][^`]*?)\.md)`"
    )
    findings: list[tuple[Path, str, str]] = []

    for md_path in main_path.glob("**/*.md"):
        relpath = md_path.relative_to(main_path)
        # Skip excluded directories
        if any(part in EXCLUDE_DIRS for part in relpath.parts):
            continue
        # Skip framework documentation files
        if relpath.name in FRAMEWORK_DOC_FILES:
            continue
        if any(part in FRAMEWORK_DOC_DIRS for part in relpath.parts):
            continue
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_num, line in enumerate(text.splitlines(), start=1):
            for match in REF_PATTERN.finditer(line):
                target = match.group(1).replace("\\", "/")
                # Try three resolutions:
                # 1. Absolute against repo-root (e.g. `01_Proposal/foo.md`)
                # 2. Relative to the containing file's parent directory
                # 3. Relative to the sub-project root (e.g. `02_Outline/foo.md`
                #    from `01_Proposal/01_Research/handover.md` resolves to
                #    `01_Proposal/02_Outline/foo.md`)
                candidates = [
                    main_path / target,
                    main_path / relpath.parent / target,
                ]
                first_part = relpath.parts[0] if relpath.parts else ""
                if re.match(r"^[0-9]{2}_", first_part):
                    candidates.append(main_path / first_part / target)
                if not any(p.exists() for p in candidates):
                    findings.append(
                        (relpath, f"L{line_num}: {line.strip()[:100]}", target)
                    )
    return findings


def generate_report(
    repo_root: Path,
    worktrees: list[WorktreeInfo],
    master_only_diff: dict[Path, list[tuple[str, Path]]],
    dangling_refs: list[tuple[Path, str, str]],
) -> str:
    """Generate Markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    lines.append("# Cross-Session Audit Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Repository:** `{repo_root}`")
    main = next((wt for wt in worktrees if wt.is_main), None)
    if main:
        lines.append(f"**Main worktree:** `{main.path}` (HEAD: `{main.head}`, branch: `{main.branch}`)")
    lines.append("")

    # Summary
    n_worktrees = len(worktrees)
    n_uncommitted = sum(1 for wt in worktrees if wt.uncommitted)
    n_master_only_diff = len(master_only_diff)
    n_dangling = len(dangling_refs)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Worktrees in total:** {n_worktrees}")
    lines.append(f"- **Worktrees with uncommitted changes:** {n_uncommitted}")
    lines.append(f"- **`_*.md` files in a worktree but NOT in the main worktree:** {n_master_only_diff}")
    lines.append(f"- **Dangling refs in the main worktree (links to non-existent files):** {n_dangling}")
    lines.append("")

    # Worktree overview
    lines.append("## Worktree overview")
    lines.append("")
    lines.append("| Worktree | Branch | HEAD | Uncommitted | `_*.md` files |")
    lines.append("|---|---|---|---:|---:|")
    for wt in worktrees:
        marker = " [main]" if wt.is_main else ""
        name = wt.path.name + marker
        n_uncomm = len(wt.uncommitted)
        n_us = len(wt.underscore_files)
        lines.append(f"| `{name}` | `{wt.branch}` | `{wt.head}` | {n_uncomm} | {n_us} |")
    lines.append("")

    # Layer 1: files only in a worktree
    lines.append("## Layer 1 — `_*.md` files in a worktree but NOT in the main worktree")
    lines.append("")
    if not master_only_diff:
        lines.append("**No** findings: every `_*.md` file from the worktrees is present in the main worktree or already merged.")
        lines.append("")
    else:
        lines.append(
            "These files exist in one or more worktrees but not in the main worktree. "
            "**Potentially lost information** that should be reviewed."
        )
        lines.append("")
        for relpath, locations in sorted(master_only_diff.items()):
            lines.append(f"### `{relpath}`")
            lines.append("")
            for branch, full_path in locations:
                size = file_size_human(full_path)
                mtime = file_mtime(full_path)
                lines.append(f"- Worktree `{branch}`: {size}, mtime {mtime}")
            lines.append("")

    # Layer 2: dangling refs
    lines.append("## Layer 2 — dangling refs in the main worktree")
    lines.append("")
    if not dangling_refs:
        lines.append("**No** findings: every `.md` file reference in the main worktree points to an existing file.")
        lines.append("")
    else:
        lines.append(
            "Cross-refs in main-branch files point to non-existent paths. "
            "Either refactor drift or a typo."
        )
        lines.append("")
        lines.append("| Source file | Line | Missing target |")
        lines.append("|---|---|---|")
        for src, line_text, target in dangling_refs[:50]:  # Cap at 50
            lines.append(f"| `{src}` | {line_text} | `{target}` |")
        if len(dangling_refs) > 50:
            lines.append(f"| ... | ... | (+{len(dangling_refs) - 50} more, truncated) |")
        lines.append("")

    # Layer 3: uncommitted changes
    lines.append("## Layer 3 — uncommitted changes per worktree")
    lines.append("")
    any_uncomm = False
    for wt in worktrees:
        if not wt.uncommitted:
            continue
        any_uncomm = True
        lines.append(f"### `{wt.path.name}` (branch `{wt.branch}`)")
        lines.append("")
        lines.append("```")
        for line in wt.uncommitted[:30]:  # Cap at 30 per worktree
            lines.append(line)
        if len(wt.uncommitted) > 30:
            lines.append(f"... (+{len(wt.uncommitted) - 30} more)")
        lines.append("```")
        lines.append("")
    if not any_uncomm:
        lines.append("**No** uncommitted changes in any worktree.")
        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if master_only_diff:
        lines.append(
            f"- Review {len(master_only_diff)} file(s) from old worktrees to check "
            "whether their content is missing from the main worktree or already integrated elsewhere."
        )
    if dangling_refs:
        lines.append(
            f"- Review {len(dangling_refs)} dangling ref(s); fix refactor drift or typos."
        )
    if n_uncommitted:
        lines.append(
            f"- {n_uncommitted} worktree(s) have uncommitted changes; decide whether to stash / commit / discard."
        )
    if not master_only_diff and not dangling_refs and not n_uncommitted:
        lines.append("- No findings; repository hygiene is clean.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    # `__doc__` is None under `python -OO`.
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().split("\n\n")[0])
    parser.add_argument(
        "--report-file",
        type=Path,
        default=None,
        help="Optional path for the Markdown report (in addition to stdout).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root; defaults to the current directory.",
    )
    args = parser.parse_args()

    if not args.repo_root.is_dir():
        print(
            f"Error: --repo-root does not exist or is not a directory: {args.repo_root}",
            file=sys.stderr,
        )
        return 2

    try:
        repo_root = find_repo_root(args.repo_root)
        worktrees = list_worktrees(repo_root)
        collect_worktree_data(worktrees)
        master_only_diff = find_master_only_diff(worktrees)

        main_wt = next((wt for wt in worktrees if wt.is_main), None)
        dangling = find_dangling_refs(main_wt.path) if main_wt else []

        report = generate_report(repo_root, worktrees, master_only_diff, dangling)
        print(report)

        if args.report_file:
            args.report_file.parent.mkdir(parents=True, exist_ok=True)
            args.report_file.write_text(report, encoding="utf-8")
            print(f"\n[Report written: {args.report_file}]", file=sys.stderr)
    except (RuntimeError, OSError) as e:
        # RuntimeError: git returned nonzero (e.g. not a git repo, or the
        # status of a worktree could not be read).
        # OSError: subprocess-level failure (git binary not on PATH, cwd
        # invalid), an unreadable worktree, or an unwritable --report-file.
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Exit code: 0 if there are no findings, 1 if findings exist (for CI / hooks).
    # Operational errors (the audit could not run) return 2, see above,
    # mirroring the 0/1/2 convention of bibliography_check.py.
    has_findings = bool(master_only_diff or dangling or any(wt.uncommitted for wt in worktrees))
    return 1 if has_findings else 0


if __name__ == "__main__":
    sys.exit(main())
