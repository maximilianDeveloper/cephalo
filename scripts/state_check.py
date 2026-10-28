#!/usr/bin/env python3
"""
state_check.py

Lists what the closing check of a chat compares in the state file of a flat
project, workspace/state.md, in full: a Grep leaves out every line over
about 500 characters, and a Read in parts leaves out what lies between them.
It only reads; it changes nothing.

The report starts with a summary line (open and ticked items, chapter files
counted, the lines over 500 characters), then gives, each with its line
number:
  - every line of "Current state";
  - every line of "Chapter status" (its table and anything else in it);
  - every open item ("- [ ] ...", in any section), with its section, and the
    number of ticked ones ("- [x]");
  - the word count of each chapter file named, counted as
    `verbatim_check.py --words` counts it, for the page budget; a chapter it
    cannot count is listed as not counted, with the reason;
  - the lines of "Current state" and "Chapter status" over 500 characters,
    which "State file format" in .claude/agents/orchestrator.md keeps short.
A section runs from its heading (any level, "## Chapter status" or
"### Chapter status (2026-10-28)", for example) to the next heading. Whether
an open item is resolved, and whether the sections agree, is for whoever
reads the report to judge: the script compares no wording.

Usage:
    python scripts/state_check.py workspace/state.md
    python scripts/state_check.py workspace/state.md workspace/output/chapters/
    python scripts/state_check.py workspace/state.md ch_1_intro.md ch_2_body.md
    python scripts/state_check.py --help

A chapter argument is a .md, .txt or .docx file, or a folder whose .md and
.docx files are counted (not those in its subfolders, and no hidden file).
A Word chapter needs python-docx (requirements.txt).

Exit codes: 0 = no line of "Current state" or "Chapter status" over 500
characters, 1 = at least one, 2 = bad arguments, a state file that cannot be
read, or one without a "Current state" or "Chapter status" section. A
chapter that cannot be counted does not change the exit code.
"""

import contextlib
import io
import re
import sys
from pathlib import Path

# Encoding guard for Windows consoles (CP1252 by default); a file name that is
# not valid UTF-8 is printed with escapes instead of ending in a traceback.
for stream in (sys.stdout, sys.stderr):
    try:
        if stream.encoding and stream.encoding.lower() != "utf-8":
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        else:
            stream.reconfigure(errors="backslashreplace")
    except Exception:
        pass

USAGE = "Usage: python scripts/state_check.py <state file> [<chapter file or folder> ...]"
LONG = 500                     # characters; a Grep result leaves out longer lines
CHAPTER_SUFFIXES = {".md", ".markdown", ".txt", ".docx"}
FOLDER_SUFFIXES = {".md", ".markdown", ".docx"}
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
OPEN = re.compile(r"^\s*[-*+]\s+\[ \]")
TICKED = re.compile(r"^\s*[-*+]\s+\[[xX]\]")
SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
CHECKED = ("current state", "chapter status")


def fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(2)


def read_state(path: Path) -> list:
    """The lines of the state file: UTF-8 (with or without BOM), UTF-16 with
    BOM, otherwise Windows-1252."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        reason = "is a directory" if path.is_dir() else exc.strerror or exc
        fail(f"cannot read {path}: {reason}")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()            # the newline at the end of the file
    return lines


def section_of(title: str) -> str:
    """'current state' or 'chapter status' for those sections, else ''."""
    key = re.sub(r"\s+", " ", title.strip().casefold())
    return next((name for name in CHECKED if key.startswith(name)), "")


def chapter_files(args: list) -> tuple:
    """(files to count, notes on arguments that hold none)."""
    files, notes = [], []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            try:
                found = sorted(x for x in p.iterdir() if x.is_file() and not x.name.startswith((".", "~$"))
                               and x.suffix.lower() in FOLDER_SUFFIXES)
            except OSError as exc:
                notes.append(f"{p}: folder not read ({exc.strerror or exc})")
                continue
            files.extend(found)
            if not found:
                notes.append(f"{p}: no chapter files in this folder")
        elif p.is_file():
            if p.suffix.lower() in CHAPTER_SUFFIXES:
                files.append(p)
            else:
                notes.append(f"{p}: not counted (not a .md, .txt or .docx chapter)")
        else:
            notes.append(f"{p}: not found")
    return files, notes


def counts(files: list) -> list:
    """(file, line, counted) with verbatim_check.py's word count, or the reason
    it could not count the file."""
    if not files:
        return []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import verbatim_check as vc
    except Exception as exc:
        return [(f, f"not counted: verbatim_check.py could not be loaded beside this script ({exc})", False)
                for f in files]
    out = []
    for f in files:
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                out.append((f, vc.word_count(vc.read_chapter(f)), True))
        except SystemExit:
            why = " ".join(err.getvalue().split()).removeprefix("Error: ")
            out.append((f, f"not counted: {why or 'verbatim_check.py could not read it'}", False))
        except Exception as exc:
            out.append((f, f"not counted: {type(exc).__name__}: {' '.join(str(exc).split())}", False))
    return out


def report(args: list) -> int:
    state = Path(args[0])
    lines = read_state(state)
    files, notes = chapter_files(args[1:])

    section, title, seen = "", "", {}
    current, status, open_items, ticked, long_lines = [], [], [], 0, []
    for no, line in enumerate(lines, 1):
        m = HEADING.match(line)
        if m:
            title = m.group(1)
            section = section_of(title)
            if section:
                seen.setdefault(section, no)
            continue
        if OPEN.match(line):
            open_items.append((no, title, line.strip()))
        elif TICKED.match(line):
            ticked += 1
        text = line.rstrip()
        if section and text.strip():
            (current if section == "current state" else status).append((no, text))
            if len(text) > LONG:
                long_lines.append((no, title, len(text)))

    missing = [name for name in CHECKED if name not in seen]
    if missing:
        fail(f"{state} has no " + " and no ".join(f'"{x.capitalize()}" heading' for x in missing)
             + ': is it the state file of a flat project (orchestrator.md, "State file format")?')

    counted = counts(files)
    rows = [t for _, t in status if t.lstrip().startswith("|") and not SEPARATOR.match(t)]
    print(f"State check for: {state} ({len(lines)} lines)")
    where = ", ".join(f"l. {no} ({n} characters)" for no, _, n in long_lines)
    print(f"Summary: open items {len(open_items)}, ticked {ticked}; chapter files counted "
          f"{sum(1 for c in counted if c[2])} of {len(counted)}; lines over {LONG} characters in "
          f"Current state and Chapter status: {len(long_lines)}" + (f" ({where})" if where else ""))
    print()
    print(f"Current state (l. {seen['current state']}):")
    for no, text in current:
        print(f"  l. {no}: {text}")
    if not current:
        print("  (empty)")
    print()
    print(f"Chapter status (l. {seen['chapter status']}): {max(len(rows) - 1, 0)} row(s) below the table's header")
    for no, text in status:
        print(f"  l. {no}: {text}")
    if not status:
        print("  (empty)")
    print()
    print(f"Open items (- [ ]): {len(open_items)}; ticked (- [x]): {ticked}")
    for no, sec, item in open_items:
        print(f"  l. {no} [{sec or 'no heading'}]: {item}")
    if files or notes:
        print()
        print("Word counts (as verbatim_check.py --words counts them):")
        for f, line, _ in counted:
            print(f"  {f}: {line}")
        for note in notes:
            print(f"  {note}")
    print()
    print(f"Lines over {LONG} characters in Current state and Chapter status: {len(long_lines)}")
    for no, sec, n in long_lines:
        print(f"  l. {no} [{sec}], {n} characters (in full above)")
    if long_lines:
        print('  Shorten each as "State file format" in .claude/agents/orchestrator.md says, then run this again.')
    return 1 if long_lines else 0


def main() -> None:
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print((__doc__ or USAGE).strip())
        sys.exit(0)
    if not args or any(a.startswith("-") for a in args):
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    try:
        code = report(args)
    except SystemExit:
        raise
    except Exception as exc:  # an unexpected error is no finding: exit 2, not 1
        fail(f"{type(exc).__name__}: {' '.join(str(exc).split())}")
    sys.exit(code)


if __name__ == "__main__":
    main()
