#!/usr/bin/env bash
#
# setup.sh
#
# cephalo setup script (macOS/Linux/Git Bash).
# Creates project structure based on user choices.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh                                              # interactive
#   ./setup.sh "<work-type>" "<structure>" <full|minimal>   # non-interactive
#
# Run it from inside the cephalo template directory (it scaffolds into
# the current directory, or copies the template to --target PATH).

# -E (errtrace): the ERR trap below also fires for a command that fails
# inside a function (create_dir, copy_template_or_fallback, ...).
set -Eeuo pipefail
# An exported CDPATH would redirect the relative cd calls below (e.g. when
# resolving a relative --target) to same-named directories elsewhere.
unset CDPATH

# ==========================================================
# Graceful interrupt handling (Ctrl+C, SIGTERM)
# ==========================================================
#
# On Git Bash (Windows), the MinTTY terminal closes the window as soon as
# the shell process terminates, so Ctrl+C can leave the user with a blank
# screen and no idea what happened. We catch the signal, print a clear
# message, and pause briefly so the user sees what went on.

SETUP_INTERRUPTED=0
# Where the run was stopped, for the advice below: set when the template
# copy into a new --target begins, and when the setup has completed.
COPY_STARTED=0
TARGET_HAD_FILES=false
SETUP_DONE=0

on_interrupt() {
    SETUP_INTERRUPTED=1
    echo ""
    echo ""
    if [ "$SETUP_DONE" = "1" ]; then
        # Ctrl+C after the summary (e.g. at "Delete it now?"): the project
        # is complete, so this is no failure for a calling launcher.
        echo -e "\033[0;90m  Stopped (Ctrl+C) after the setup had completed.\033[0m"
        pause_before_close "done"
        exit 0
    fi
    echo -e "\033[1;33m! Setup cancelled by user (Ctrl+C).\033[0m"
    if [ "$COPY_STARTED" = "1" ] && [ "$TARGET_HAD_FILES" = "false" ]; then
        # The same command would now refuse the non-empty target.
        echo -e "\033[0;90m  The new project folder is only partly set up. Delete it, then re-run setup:\033[0m"
        echo -e "\033[0;90m  $TARGET_DIR\033[0m"
    else
        echo -e "\033[0;90m  Any directories created up to this point remain in place.\033[0m"
        echo -e "\033[0;90m  Re-run the script to resume; existing items will be skipped.\033[0m"
    fi
    pause_before_close "cancelled"
    exit 130
}

on_error() {
    local exit_code=$?
    # Skip if already handling interrupt (avoid double-pause)
    [ "$SETUP_INTERRUPTED" = "1" ] && exit $exit_code
    # In a subshell ( ... ) or $( ... ), carry on as without the trap: the
    # output of a $( ... ) must not take in the message, and a failed ( ... )
    # fails its caller, which reports it (not under bash 3.2, which runs no
    # ERR trap for a failed ( ... ): so no setup step runs in one).
    if [ "${BASH_SUBSHELL:-0}" -gt 0 ]; then
        return 0
    fi
    echo ""
    echo -e "\033[0;31m! Setup exited unexpectedly (exit code $exit_code).\033[0m"
    pause_before_close "error" "$exit_code"
    exit $exit_code
}

pause_before_close() {
    local reason="${1:-done}"
    # The exit code the caller ends with after the pause.
    local code="${2:-}"
    if [ -z "$code" ]; then
        case "$reason" in cancelled) code=130 ;; error) code=1 ;; *) code=0 ;; esac
    fi
    # Only pause if we're attached to a real interactive terminal.
    # In CI, piped, or non-interactive runs, exit immediately.
    if [ -t 0 ] && [ -t 1 ]; then
        echo ""
        case "$reason" in
            cancelled) echo "Press Enter to close..." ;;
            error)     echo "Press Enter to close (check the messages above)..." ;;
            *)         echo "Press Enter to close..." ;;
        esac
        # Ctrl+C here closes like Enter, with that exit code: the run has
        # already ended (and in Git Bash, Ctrl+C is how many users try to copy
        # the messages above), so there is no cancellation left to report.
        # At the pauses of on_interrupt, which runs as the Ctrl+C trap, bash
        # before 5.1 holds a second Ctrl+C back, so only Enter closes those.
        PAUSE_EXIT="$code"
        trap 'echo ""; exit "$PAUSE_EXIT"' INT
        # Use read with a short timeout fallback, in case even Enter is blocked
        read -r _ 2>/dev/null || sleep 3
    fi
}

trap on_interrupt INT TERM
trap on_error ERR

# ==========================================================
# Colors
# ==========================================================

CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
GRAY='\033[0;90m'
RED='\033[0;31m'
NC='\033[0m'

# ==========================================================
# Helpers
# ==========================================================

header() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}============================================================${NC}"
}

step() {
    echo ""
    echo -e "${YELLOW}-> $1${NC}"
}

ask_choice() {
    local prompt="$1"
    shift
    local options=("$@")
    echo ""
    echo -e "${CYAN}$prompt${NC}"
    for i in "${!options[@]}"; do
        echo "  $((i+1)). ${options[$i]}"
    done
    local attempts=0
    while true; do
        if ! read -r -p "Choice (1-${#options[@]}): " choice; then
            # EOF (e.g., non-interactive execution without piped input)
            echo "" >&2
            echo "Error: input closed before a choice was made." >&2
            echo "For non-interactive runs, supply all three positional arguments:" >&2
            echo "  $0 \"<work-type>\" \"<structure>\" <full|minimal>" >&2
            echo "  $0 --help" >&2
            exit 2
        fi
        # Bound the digit match to a sane length before handing it to a bash
        # arithmetic comparison: an oversized all-digit string (e.g. 50+
        # digits) overflows bash's integer expression and raises a raw
        # "integer expression expected" error instead of being rejected
        # cleanly like any other invalid input.
        if [[ "$choice" =~ ^[0-9]{1,9}$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
            SELECTED="${options[$((choice-1))]}"
            return
        fi
        attempts=$((attempts + 1))
        echo "Please enter a number between 1 and ${#options[@]}." >&2
        if [ "$attempts" -ge 10 ]; then
            echo "Error: too many invalid attempts. Aborting." >&2
            # A menu shows only in runs without all three arguments, such as a
            # double-clicked one, whose window would close at once.
            pause_before_close "error" 2
            exit 2
        fi
    done
}

create_dir() {
    if [ ! -d "$1" ]; then
        mkdir -p "$1"
        echo -e "  ${GREEN}+ $1${NC}"
    else
        echo -e "  ${GRAY}. $1 (exists)${NC}"
    fi
}

create_gitkeep() {
    local gk="$1/.gitkeep"
    # if-form (not `[ ] &&`): the function must return 0 when the file
    # already exists, or set -e aborts every re-run of the setup.
    if [ ! -f "$gk" ]; then
        touch "$gk"
    fi
}

copy_template_or_fallback() {
    local tmpl="$1"
    local dest="$2"
    local fallback="$3"
    # Never overwrite an existing file: state files (00_Status.md,
    # 00_Decisions.md, 00_Feedback_log.md) contain user data, and re-runs
    # are a documented resume flow ("existing items will be skipped").
    if [ -f "$dest" ]; then
        echo -e "  ${GRAY}. $dest (exists)${NC}"
        return
    fi
    if [ -f "$tmpl" ]; then
        cp "$tmpl" "$dest"
        echo -e "  ${GREEN}+ $dest${NC}"
    else
        echo -e "$fallback" > "$dest"
        echo -e "  ${GREEN}+ $dest (minimal fallback)${NC}"
    fi
}

normalize_structure() {
    # Map both the CLI value ("Flat") and the full interactive option text
    # ("Flat (single directory, simple)") to the canonical short form the
    # structure branches test against.
    case "$STRUCTURE" in
        "Flat"|"Flat ("*)                   STRUCTURE="Flat" ;;
        "Long-form"|"Long-form ("*)         STRUCTURE="Long-form" ;;
        "Multi-project"|"Multi-project ("*) STRUCTURE="Multi-project" ;;
    esac
}

canon_path() {
    # Print the canonical absolute form of path $1, which need not exist
    # yet: the deepest existing ancestor is resolved physically (cd +
    # pwd -P, so symlinks and a symlinked cwd are seen through), the
    # remaining components are appended with "." and ".." resolved
    # lexically. A relative path ends at "." (the cwd); a path that is
    # already a directory is resolved as given (e.g. C:/... on Git Bash).
    # Plain bash 3.2 (macOS): no arrays, no mapfile.
    local p="$1" rest="" out comp
    while [ ! -d "$p" ]; do
        case "$p" in .|/) return 1 ;; esac
        rest="$(basename -- "$p")${rest:+/$rest}"
        p="$(dirname -- "$p")"
    done
    out="$(cd -- "$p" 2>/dev/null && pwd -P)" || return 1
    while [ -n "$rest" ]; do
        comp="${rest%%/*}"
        case "$rest" in
            */*) rest="${rest#*/}" ;;
            *)   rest="" ;;
        esac
        case "$comp" in
            ""|.) ;;
            ..)   out="${out%/*}"; [ -n "$out" ] || out="/" ;;
            *)    out="${out%/}/$comp" ;;
        esac
    done
    printf '%s\n' "$out"
}

path_inside() {
    # Whether the canonical path $1 lies inside the canonical folder $2 (a
    # path equal to $2 counts as inside: callers check that case first).
    # Besides the text, -ef compares each existing ancestor with $2, as the
    # letter case of a path may differ (APFS on macOS and NTFS under Git
    # Bash usually ignore case).
    local ancestor
    if [[ "${1%/}/" == "${2%/}/"* ]]; then
        return 0
    fi
    ancestor="${1%/*}"
    while [ -n "$ancestor" ]; do
        if [ "$ancestor" -ef "$2" ]; then
            return 0
        fi
        ancestor="${ancestor%/*}"
    done
    return 1
}

prompt_target_inside() {
    # For the target prompt: print the canonical form of path $1 if it lies
    # inside the template folder (the current directory), as a bare folder
    # name does, so the prompt can ask again. Resolved as below for a target.
    local t="$1" canon here
    case "$t" in
        \~|\~/*) t="$HOME${t#\~}" ;;
    esac
    canon="$(canon_path "$t")" || return 1
    here="$(pwd -P)"
    if [ "$canon" = "$here" ] || [ "$canon" -ef "$here" ]; then
        return 1
    fi
    path_inside "$canon" "$here" || return 1
    printf '%s\n' "$canon"
}

shell_quote() {
    # Print $1 in single quotes (' as '\''), for commands the user may paste:
    # nothing in it expands, in bash and zsh alike. The substitution runs in
    # an assignment, where bash 3.2 and 5 treat the quote characters the same.
    local q="'\\''" s
    s=${1//\'/$q}
    printf "'%s'" "$s"
}

merge_missing_lines() {
    # Append to the project's file $2 the rules of the template's file $1
    # that it lacks (blank and comment lines aside), under one comment line.
    # Prints how many rules were added. CR and a UTF-8 BOM are ignored when
    # comparing, so a file edited on Windows is not filled with duplicates.
    local missing count
    missing="$(LC_ALL=C awk '
        { sub(/\r$/, "") }
        FNR == 1 && substr($0, 1, 3) == "\357\273\277" { $0 = substr($0, 4) }
        FILENAME == ARGV[1] { have[$0] = 1; next }
        $0 != "" && $0 !~ /^#/ && !($0 in have) && !seen[$0]++ { print }
    ' "$2" "$1")" || return 1
    count=0
    [ -n "$missing" ] && count="$(printf '%s\n' "$missing" | wc -l | tr -d ' ')"
    if [ "$count" -gt 0 ]; then
        # Keep the file's last line intact if it has no line break.
        if [ -s "$2" ] && [ -n "$(tail -c 1 "$2")" ]; then printf '\n' >> "$2"; fi
        printf '\n# Added by cephalo setup: template rules this file lacked\n%s\n' "$missing" >> "$2"
    fi
    printf '%s\n' "$count"
}

# ==========================================================
# Start
# ==========================================================

header "cephalo setup"
echo ""
echo "This script prepares a project directory for academic work."
echo "Current location: $(pwd)"
echo ""
echo -e "${GRAY}NOTE: The agent files (in .claude/, workflows/, etc.) and the"
echo -e "project content will coexist in this directory. Claude Code needs"
echo -e "both. This is expected and correct.${NC}"
echo ""
echo -e "${GRAY}You can cancel at any time with Ctrl+C — already-created directories${NC}"
echo -e "${GRAY}will stay in place and the next run will skip them.${NC}"
echo ""

# ==========================================================
# Argument handling
# ==========================================================

# --help (accepted anywhere in the argument list). ${1+"$@"} instead of a
# bare "$@": older bash versions treat "$@" without arguments as unbound
# under set -u.
for arg in ${1+"$@"}; do
    [ "$arg" = "-h" ] || [ "$arg" = "--help" ] || continue
    cat << 'USAGE'
Usage: ./setup.sh [WORK_TYPE] [STRUCTURE] [SCAFFOLDING] [--target PATH]

Positional arguments (all optional; missing values trigger interactive prompts):

  WORK_TYPE    One of:
                 "Seminar paper", "Presentation", "Bachelor thesis",
                 "Master thesis", "Dissertation"

  STRUCTURE    One of:
                 "Flat", "Long-form", "Multi-project"
               ("Seminar paper" and "Presentation": "Flat" only)

  SCAFFOLDING  "full" or "minimal"

When all three positional arguments are supplied, the configuration and
confirmation prompts are skipped and the run is safe with closed stdin (CI).
On a terminal, the script still waits for Enter before closing and, after
a --target copy, offers to delete the original template folder. Redirect
stdin (</dev/null) for fully unattended runs.

Optional flags:

  --target PATH
               Copy the cephalo template to PATH and create the project
               there. The current directory is preserved. If omitted and
               the run is interactive, the script will ask.

Examples:
  ./setup.sh                                         # fully interactive
  ./setup.sh "Bachelor thesis" "Long-form" full      # non-interactive, here
  ./setup.sh --target ~/Documents/Thesis_OSS         # interactive, target given
  ./setup.sh "Master thesis" --target ~/MA           # partial + target

USAGE
    exit 0
done

# ==========================================================
# Template location sanity check
# ==========================================================
# The script scaffolds into the CURRENT directory (and, with --target,
# copies the template FROM it). If the current directory is not a cephalo
# template — e.g. the script was invoked by path from somewhere else —
# the result would be a project without agents, workflows, or templates.

if [ ! -f "setup.sh" ] || [ ! -d ".claude" ] || [ ! -d "templates" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || SCRIPT_DIR=""
    echo -e "${RED}Error: the current directory does not look like a cephalo template${NC}" >&2
    echo -e "${RED}(setup.sh, .claude/ and templates/ expected in: $(pwd)).${NC}" >&2
    if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/.claude" ]; then
        echo -e "${YELLOW}The template appears to be at: $SCRIPT_DIR${NC}" >&2
        printf '%bRun:  cd %s && ./setup.sh [args]%b\n' "$YELLOW" "$(shell_quote "$SCRIPT_DIR")" "$NC" >&2
        echo -e "${YELLOW}Use --target PATH to create the project elsewhere.${NC}" >&2
    fi
    pause_before_close "error" 2
    exit 2
fi

# Parse --target out of the arguments, keeping positionals in order
TARGET_DIR=""
POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --target)
            if [ -z "${2:-}" ]; then
                echo "Error: --target requires a path argument." >&2
                exit 2
            fi
            TARGET_DIR="$2"
            shift 2
            ;;
        --target=*)
            TARGET_DIR="${1#--target=}"
            if [ -z "$TARGET_DIR" ]; then
                echo "Error: --target requires a path argument." >&2
                exit 2
            fi
            shift
            ;;
        -*)
            # A misspelled flag (e.g. --taget) must not fall through to an
            # in-place setup of the template directory.
            echo "Error: unknown option '$1'." >&2
            echo "See: $0 --help" >&2
            exit 2
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done
if [ "${#POSITIONAL[@]}" -gt 3 ]; then
    echo "Error: too many arguments (at most 3 positional: WORK_TYPE STRUCTURE SCAFFOLDING)." >&2
    echo "See: $0 --help" >&2
    exit 2
fi
# Restore positional arguments
set -- "${POSITIONAL[@]:-}"

WORK_TYPE="${1:-}"
STRUCTURE="${2:-}"
SCAFFOLDING="${3:-}"

# Validate positional arguments if provided
VALID_WORK_TYPES=("Seminar paper" "Presentation" "Bachelor thesis" "Master thesis" "Dissertation")
if [ -n "$WORK_TYPE" ]; then
    valid=0
    for v in "${VALID_WORK_TYPES[@]}"; do
        [ "$WORK_TYPE" = "$v" ] && valid=1 && break
    done
    if [ "$valid" -eq 0 ]; then
        # Comma-join: the values contain spaces (same format as setup.ps1).
        printf -v valid_list '%s, ' "${VALID_WORK_TYPES[@]}"
        echo "Error: invalid WORK_TYPE '$WORK_TYPE'." >&2
        echo "Valid options: ${valid_list%, }" >&2
        echo "See: $0 --help" >&2
        exit 2
    fi
fi

if [ -n "$STRUCTURE" ]; then
    normalize_structure
    # Anchored at both ends: normalize_structure has already mapped the
    # accepted long forms, so anything else is a typo we reject cleanly.
    if ! [[ "$STRUCTURE" =~ ^(Flat|Long-form|Multi-project)$ ]]; then
        echo "Error: invalid STRUCTURE '$STRUCTURE'." >&2
        echo "Valid options: Flat, Long-form, Multi-project" >&2
        echo "See: $0 --help" >&2
        exit 2
    fi
fi

if [ -n "$SCAFFOLDING" ] && [ "$SCAFFOLDING" != "full" ] && [ "$SCAFFOLDING" != "minimal" ]; then
    echo "Error: invalid SCAFFOLDING '$SCAFFOLDING'." >&2
    echo "Valid options: full, minimal" >&2
    exit 2
fi

# Seminar papers and presentations have flat workflows only: with Long-form
# or Multi-project, setup would suggest a thesis workflow for them. The
# interactive menu and the setup assistant pick Flat for them anyway.
# Checked here and again after the work-type menu (STRUCTURE may come from
# the command line while WORK_TYPE is chosen interactively).
check_flat_only() {
    if [[ "$WORK_TYPE" =~ ^(Seminar\ paper|Presentation)$ ]] && [ -n "$STRUCTURE" ] && [ "$STRUCTURE" != "Flat" ]; then
        echo "Error: '$WORK_TYPE' uses the Flat structure; there is no $STRUCTURE workflow for it." >&2
        if [ -n "$TARGET_DIR" ]; then
            echo "Use: $0 \"$WORK_TYPE\" Flat ${SCAFFOLDING:-full} --target $(shell_quote "$TARGET_DIR")" >&2
        else
            echo "Use: $0 \"$WORK_TYPE\" Flat ${SCAFFOLDING:-full}" >&2
        fi
        exit 2
    fi
}
check_flat_only

# All three positional arguments supplied -> documented non-interactive
# mode (parity with setup.ps1 -NonInteractive): skip the location and
# confirmation prompts so the run works with closed stdin (CI, scripts).
NON_INTERACTIVE=false
if [ -n "$WORK_TYPE" ] && [ -n "$STRUCTURE" ] && [ -n "$SCAFFOLDING" ]; then
    NON_INTERACTIVE=true
fi

# For the error exits below, which a double-clicked run can reach: Git Bash
# closes its window on exit, so an interactive run waits for Enter first.
# Runs with all three arguments do not (the setup assistant's launchers,
# which pass them, pause themselves).
exit_with_pause() {
    $NON_INTERACTIVE || pause_before_close "error" "$1"
    exit "$1"
}

# ==========================================================
# Target directory handling
# ==========================================================
# If the user specified a target path (via --target or the interactive
# prompt), we copy all cephalo template files into the target and
# continue the setup there. The original directory is left intact; at
# the end the user is asked whether to delete it.

SOURCE_DIR_BEFORE_MOVE=""   # set if we copied into a target

# If no --target given and we're interactive, ask.
# (Skipped in non-interactive mode: all three positionals mean "here".)
if [ -z "$TARGET_DIR" ] && ! $NON_INTERACTIVE && [ -t 0 ] && [ -t 1 ]; then
    echo ""
    echo -e "${CYAN}Where should the project be created?${NC}"
    echo "  1. Here (current location: $(pwd))"
    echo "  2. Choose a different directory"
    echo ""
    while true; do
        # EOF (Ctrl+D) counts as an empty answer, i.e. the default.
        read -r -p "Your choice [1-2, default 1]: " loc_choice || loc_choice=""
        loc_choice="${loc_choice:-1}"
        case "$loc_choice" in
            1) break ;;
            2)
                echo ""
                echo "Enter a target path. The cephalo template will be copied there,"
                echo "and the project structure will be created inside it."
                echo "Example: ~/Documents/Bachelorarbeit_KMU_OSS"
                while true; do
                    read -r -p "Target path: " TARGET_DIR || TARGET_DIR=""
                    # A folder dragged into the terminal arrives quoted ('/a/My
                    # Thesis') or shell-escaped (/a/My\ Thesis, macOS Terminal).
                    # Undo that as the shell does for --target; backslashes in
                    # other paths stay (C:\... typed in Git Bash).
                    case "$TARGET_DIR" in
                        \'*\') TARGET_DIR="${TARGET_DIR#\'}"; TARGET_DIR="${TARGET_DIR%\'}"
                               # An apostrophe inside comes as '\'' (John'\''s Thesis).
                               TARGET_DIR="$(printf '%s\n' "$TARGET_DIR" | sed "s/'\\\\''/'/g")" ;;
                        \"*\") TARGET_DIR="${TARGET_DIR#\"}"; TARGET_DIR="${TARGET_DIR%\"}" ;;
                        /*|\~*) TARGET_DIR="$(printf '%s\n' "$TARGET_DIR" | sed 's/\\\(.\)/\1/g')" ;;
                    esac
                    if [ -z "$TARGET_DIR" ]; then
                        echo -e "${YELLOW}Empty path — using current location instead.${NC}"
                        TARGET_DIR=""
                        break
                    fi
                    # A folder inside the template, such as a bare folder name,
                    # cannot take a copy of it: ask again rather than end the
                    # run with the error below, which a --target gets.
                    if inside_path="$(prompt_target_inside "$TARGET_DIR")"; then
                        echo -e "${YELLOW}That folder lies inside the cephalo template folder:${NC}"
                        # printf %s: a backslash in the folder name is no escape.
                        printf '%b  %s%b\n' "$YELLOW" "$inside_path" "$NC"
                        echo "Enter a full path outside it, such as the example above,"
                        echo "or leave it empty to set up here."
                        continue
                    fi
                    break
                done
                break
                ;;
            *) echo "Please enter 1 or 2." ;;
        esac
    done
fi

# Validate and process TARGET_DIR if set
if [ -n "$TARGET_DIR" ]; then
    # Expand a bare ~ or a leading ~/ if not yet expanded (e.g. typed at
    # the prompt). ~user forms are left alone: replacing only the ~ would
    # turn ~Documents/X into "$HOME" + "Documents/X", a sibling of HOME.
    case "$TARGET_DIR" in
        \~|\~/*) TARGET_DIR="$HOME${TARGET_DIR#\~}" ;;
    esac
    
    # Reject obviously bad paths
    if [[ "$TARGET_DIR" == *$'\n'* ]] || [[ "$TARGET_DIR" == *$'\r'* ]]; then
        echo -e "${RED}Error: target path contains invalid characters.${NC}" >&2
        exit_with_pause 2
    fi
    
    # Resolve to absolute path (the source must stay resolvable too)
    SOURCE_DIR_BEFORE_MOVE="$(pwd)"

    # Compare canonical physical paths, so alternate spellings of the same
    # directory (trailing slash, relative path like "." or "..", symlinked
    # path or cwd) are recognized and we do not tar-copy a directory onto
    # itself. canon_path also resolves targets that do not exist yet.
    SOURCE_CANON="$(pwd -P)"
    if ! TARGET_CANON="$(canon_path "$TARGET_DIR")"; then
        echo -e "${RED}Error: cannot resolve target path '$TARGET_DIR'.${NC}" >&2
        exit_with_pause 2
    fi
    # canon_path keeps the letter case as typed, but APFS (macOS) and NTFS
    # (Git Bash) usually ignore case: -ef compares the directories themselves.
    if [ "$TARGET_CANON" = "$SOURCE_CANON" ] || [ "$TARGET_CANON" -ef "$SOURCE_CANON" ]; then
        echo -e "${GRAY}Target path equals current location — proceeding here.${NC}"
        TARGET_DIR=""
        SOURCE_DIR_BEFORE_MOVE=""
    else
        # Refuse a target INSIDE the template directory: the copy would try to
        # copy the source into one of its own subdirectories (self-copy), fail
        # mid-way, and leave a half-populated directory behind. Reject up front
        # with an actionable message (mirrors setup.ps1's equivalent guard).
        if path_inside "$TARGET_CANON" "$SOURCE_CANON"; then
            echo "" >&2
            echo -e "${RED}Error: the target directory must not be inside the cephalo template directory.${NC}" >&2
            echo -e "${RED}  Template: $SOURCE_CANON${NC}" >&2
            echo -e "${RED}  Target:   $TARGET_CANON${NC}" >&2
            echo -e "${RED}  Choose a target outside the template folder, or run without --target to set up here.${NC}" >&2
            exit_with_pause 2
        fi
        # Continue with the canonical path, so mkdir -p below never creates
        # stray directories for spellings like "a/zzz/../Thesis".
        TARGET_DIR="$TARGET_CANON"
    fi
fi

# NOTE: the actual template copy into TARGET_DIR happens AFTER the
# configuration is confirmed (see below), so a declined or aborted run
# leaves no half-configured leftover directory behind.

# ==========================================================
# Interactive prompts (only for missing arguments)
# ==========================================================

if [ -z "$WORK_TYPE" ]; then
    ask_choice "What kind of work is this?" \
        "Seminar paper" \
        "Presentation" \
        "Bachelor thesis" \
        "Master thesis" \
        "Dissertation"
    WORK_TYPE="$SELECTED"
    check_flat_only
fi

if [ -z "$STRUCTURE" ]; then
    if [[ "$WORK_TYPE" == "Seminar paper" || "$WORK_TYPE" == "Presentation" ]]; then
        STRUCTURE="Flat"
        echo ""
        echo -e "${GRAY}For '$WORK_TYPE', using flat structure automatically.${NC}"
    else
        ask_choice "What project structure?" \
            "Flat (single directory, simple)" \
            "Long-form (phase-based directories, centralized state)" \
            "Multi-project (proposal + main work + defense, separated)"
        STRUCTURE="$SELECTED"
        normalize_structure
    fi
fi

if [ -z "$SCAFFOLDING" ]; then
    ask_choice "How much scaffolding should the script pre-create?" \
        "Standard (full phase directories, ready to use)" \
        "Minimal (only base structure; let the style-resolver add more)"
    SCAFFOLDING="$SELECTED"
fi

echo ""
echo -e "${CYAN}Configuration:${NC}"
echo "  Work type:   $WORK_TYPE"
echo "  Structure:   $STRUCTURE"
echo "  Scaffolding: $SCAFFOLDING"
if [ -n "$TARGET_DIR" ]; then
    echo "  Target:      $TARGET_DIR"
fi
echo ""
if $NON_INTERACTIVE; then
    echo -e "${GRAY}All arguments supplied — proceeding without confirmation.${NC}"
else
    if ! read -r -p "Proceed? (y/j = yes, n = no): " confirm; then
        # EOF (e.g., closed stdin without all three positional arguments)
        echo "" >&2
        echo "Error: input closed before confirmation." >&2
        echo "For non-interactive runs, supply all three positional arguments:" >&2
        echo "  $0 \"<work-type>\" \"<structure>\" <full|minimal>" >&2
        exit 2
    fi
    case "$confirm" in
        [yYjJ]|[yY][eE][sS]|[jJ][aA]) : ;;
        *) echo "Cancelled."; exit 0 ;;
    esac
fi

# ==========================================================
# Copy template to target (only after confirmation)
# ==========================================================

if [ -n "$TARGET_DIR" ]; then
    # Create the parent directory chain if needed
    TARGET_PARENT="$(dirname "$TARGET_DIR")"
    if [ ! -d "$TARGET_PARENT" ]; then
        echo -e "${GRAY}Creating parent directory: $TARGET_PARENT${NC}"
        if ! mkdir -p "$TARGET_PARENT"; then
            echo -e "${RED}Error: cannot create parent directory '$TARGET_PARENT'.${NC}" >&2
            exit_with_pause 2
        fi
    fi

    # Handle non-empty existing target
    if [ -d "$TARGET_DIR" ]; then
        # Folder metadata alone (.DS_Store: Finder writes one into every
        # folder it shows) does not make the target non-empty.
        if [ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 ! -name .DS_Store ! -name Thumbs.db ! -name desktop.ini 2>/dev/null)" ]; then
            TARGET_HAD_FILES=true
            echo ""
            echo -e "${YELLOW}Warning: target directory already exists and is not empty:${NC}"
            echo -e "${YELLOW}  $TARGET_DIR${NC}"
            echo ""
            echo "Copying replaces files of the same name with the template's version:"
            echo "  .claude/agents/, workflows/, checklists/, templates/, scripts/, docs/,"
            echo "  CLAUDE.md, README.md and the template's other top-level files."
            echo "Files the template does not contain (00_Status.md, phase folders,"
            echo "guidelines/, styleguide.md, ...) are kept. The project's own .gitignore"
            echo "and .gitattributes are kept too; template rules they lack are appended."
            echo ""
            if ! $NON_INTERACTIVE && [ -t 0 ] && [ -t 1 ]; then
                read -r -p "Continue and copy into this directory? [y/N]: " overwrite_ans || overwrite_ans=""
                case "$overwrite_ans" in
                    [yYjJ]|[yY][eE][sS]|[jJ][aA]) : ;;
                    *) echo "Aborted."; exit 1 ;;
                esac
            else
                echo -e "${RED}Refusing to copy into non-empty directory in non-interactive mode.${NC}" >&2
                exit 2
            fi
        fi
    elif [ -e "$TARGET_DIR" ] || [ -L "$TARGET_DIR" ]; then
        # -L: a link to a folder that is gone (an unmounted drive) fails -e too.
        echo -e "${RED}Error: target path exists and is not a directory (or is a broken link).${NC}" >&2
        exit_with_pause 2
    else
        mkdir -p "$TARGET_DIR"
    fi

    # Copy the cephalo template into the target.
    # We copy visible and dot-files, but exclude .git (user will init fresh).
    # Virtual environments (.venv/, venv/) are skipped at any depth, as in
    # setup.ps1 and .gitignore: their scripts point back into the template.
    # The wizard launcher (cephalo-setup*, also a copy the browser renamed
    # to e.g. "cephalo-setup (1).sh", at the template root) is left out:
    # it embeds the user's absolute path and would end up in the commit.
    # So is .github/: cephalo's own CI and issue templates would otherwise
    # run and show up in every thesis repository pushed to GitHub.
    # The project's own .gitignore/.gitattributes may hold rules the user
    # added (docs/git_introduction.md suggests it): they are not replaced,
    # but completed with the template's rules after the copy.
    KEEP_FILES=()
    KEEP_EXCLUDES=()
    if $TARGET_HAD_FILES; then
        for f in .gitignore .gitattributes; do
            if [ -f "$TARGET_DIR/$f" ] && [ -f "$SOURCE_DIR_BEFORE_MOVE/$f" ]; then
                KEEP_FILES+=("$f")
                KEEP_EXCLUDES+=("--exclude=./$f")
            fi
        done
    fi
    echo ""
    echo -e "${CYAN}Copying cephalo template to target...${NC}"
    COPY_STARTED=1
    # Use a tar-pipe to reliably include dotfiles and respect excludes
    # across Linux / macOS / Git Bash, without needing rsync.
    # tar's own messages stay visible (disk full, permissions, path too
    # long). set -e is off inside an if-condition, hence the && chains: a
    # failed cd must never let tar run in the wrong directory.
    if ! (
        cd "$SOURCE_DIR_BEFORE_MOVE" &&
        tar --exclude='./.git' --exclude='./.git/*' \
            --exclude='./.claude/worktrees' --exclude='./.claude/worktrees/*' \
            --exclude='./.claude/settings.local.json' \
            --exclude='./cephalo-setup*' \
            --exclude='./.github' --exclude='./.github/*' \
            --exclude='.venv' --exclude='*/.venv' --exclude='*/.venv/*' \
            --exclude='venv' --exclude='*/venv' --exclude='*/venv/*' \
            --exclude='__pycache__' --exclude='*/__pycache__' --exclude='*/__pycache__/*' \
            --exclude='*.pyc' \
            ${KEEP_EXCLUDES[@]+"${KEEP_EXCLUDES[@]}"} \
            -cf - .
    ) | (
        cd "$TARGET_DIR" &&
        tar -xf -
    ); then
        echo -e "${RED}Error: copying the template failed (see the tar messages above).${NC}" >&2
        echo -e "${RED}  Source: $SOURCE_DIR_BEFORE_MOVE${NC}" >&2
        echo -e "${RED}  Target: $TARGET_DIR${NC}" >&2
        if $TARGET_HAD_FILES; then
            # Never advise deleting a directory that also holds the user's files.
            echo -e "${RED}  The target already contained your files: remove the copied template files, or re-run with an empty target.${NC}" >&2
        else
            echo -e "${RED}  Delete the partial target directory, then re-run setup.${NC}" >&2
        fi
        exit_with_pause 3
    fi

    # Basic sanity check after copy
    if [ ! -f "$TARGET_DIR/setup.sh" ] || [ ! -d "$TARGET_DIR/.claude" ]; then
        echo -e "${RED}Error: copy appears incomplete. Aborting.${NC}" >&2
        echo -e "${RED}  Source: $SOURCE_DIR_BEFORE_MOVE${NC}" >&2
        echo -e "${RED}  Target: $TARGET_DIR${NC}" >&2
        exit_with_pause 3
    fi

    echo -e "${GREEN}+ Template copied to: $TARGET_DIR${NC}"
    for f in ${KEEP_FILES[@]+"${KEEP_FILES[@]}"}; do
        if added="$(merge_missing_lines "$SOURCE_DIR_BEFORE_MOVE/$f" "$TARGET_DIR/$f")"; then
            echo -e "${GRAY}. $f kept (project's own); template rules added: $added${NC}"
        else
            echo -e "${YELLOW}! $f kept, but the template's rules could not be added: compare it with $SOURCE_DIR_BEFORE_MOVE/$f${NC}"
        fi
    done
    echo ""

    # Change into target and continue the rest of the setup there
    cd "$TARGET_DIR"
fi

IS_MINIMAL=false
# Case-insensitive prefix: matches both the CLI value "minimal" and the
# interactive option text "Minimal (only base structure; ...)".
[[ "$SCAFFOLDING" =~ ^[Mm]inimal ]] && IS_MINIMAL=true

# Set by exactly one of the structure branches below; guarded after them.
WORKFLOW=""
# Multi-project: shared/ entries left from an earlier cephalo version.
OLD_SHARED=""

# ==========================================================
# Flat structure
# ==========================================================

if [ "$STRUCTURE" = "Flat" ]; then
    step "Creating flat structure"
    
    create_dir "workspace"
    create_dir "workspace/sources"
    create_dir "workspace/sources/_guidelines"
    
    if ! $IS_MINIMAL; then
        create_dir "workspace/sources/extracts"
        create_dir "workspace/output"
        create_dir "workspace/output/chapters"
        create_gitkeep "workspace/sources/extracts"
        create_gitkeep "workspace/output/chapters"
        
        if [ "$WORK_TYPE" = "Presentation" ]; then
            create_dir "workspace/output/slides"
            create_dir "workspace/data"
        fi
        
        if [[ "$WORK_TYPE" == "Master thesis" || "$WORK_TYPE" == "Dissertation" ]]; then
            create_dir "workspace/methods"
            create_dir "workspace/data"
            create_dir "workspace/data/raw"
            create_dir "workspace/data/processed"
            create_dir "workspace/data/scripts"
            create_dir "workspace/data/outputs"
            create_gitkeep "workspace/data/raw"
            create_gitkeep "workspace/data/processed"
        fi
    fi
    
    case "$WORK_TYPE" in
        "Seminar paper")    WORKFLOW="seminar_2agent.yaml" ;;
        "Presentation")     WORKFLOW="presentation_3agent.yaml" ;;
        "Bachelor thesis")  WORKFLOW="bachelor_5agent.yaml" ;;
        "Master thesis")    WORKFLOW="master_7agent.yaml" ;;
        "Dissertation")     WORKFLOW="master_7agent.yaml (adapt as needed)" ;;
    esac

# ==========================================================
# Long-form
# ==========================================================

elif [[ "$STRUCTURE" =~ ^Long-form ]]; then
    step "Creating long-form structure"
    
    create_dir "guidelines"
    
    if ! $IS_MINIMAL; then
        create_dir "01_Proposal"
        create_dir "02_Literature"
        create_dir "02_Literature/extracts"
        create_dir "02_Literature/sources"
        create_dir "03_Theory_chapters"
        create_dir "06_Discussion_Conclusion"
        create_dir "07_Introduction"
        create_dir "08_Formal_Review"
        create_dir "08_Formal_Review/format_reports"
        create_dir "08_Formal_Review/submissions"
        
        if [[ "$WORK_TYPE" == "Master thesis" || "$WORK_TYPE" == "Dissertation" ]]; then
            create_dir "04_Methods"
            create_dir "05_Empirical"
            create_dir "05_Empirical/data"
            create_dir "05_Empirical/data/raw"
            create_dir "05_Empirical/data/processed"
            create_dir "05_Empirical/data/scripts"
            create_dir "05_Empirical/data/outputs"
            create_gitkeep "05_Empirical/data/raw"
            create_gitkeep "05_Empirical/data/processed"
        fi
    fi
    
    step "Creating central state files"
    copy_template_or_fallback "templates/status.md" "00_Status.md" "# Project Status\n"
    copy_template_or_fallback "templates/decisions.md" "00_Decisions.md" "# Architectural Decisions\n"
    copy_template_or_fallback "templates/feedback_log.md" "00_Feedback_log.md" "# Feedback Log\n"
    
    if [[ "$WORK_TYPE" == "Master thesis" || "$WORK_TYPE" == "Dissertation" ]]; then
        WORKFLOW="master_7agent_longform.yaml"
    else
        WORKFLOW="bachelor_5agent_longform.yaml"
    fi

# ==========================================================
# Multi-project
# ==========================================================

elif [[ "$STRUCTURE" =~ ^Multi-project ]]; then
    step "Creating multi-project structure"
    
    MAIN_NAME="02_Main_Work"
    
    # Shared materials
    create_dir "00_Shared_Materials"
    create_dir "00_Shared_Materials/guidelines"
    create_dir "00_Shared_Materials/course_materials"
    
    # Proposal
    create_dir "01_Proposal"
    if ! $IS_MINIMAL; then
        create_dir "01_Proposal/01_Research"
        create_dir "01_Proposal/02_Outline"
        create_dir "01_Proposal/03_Drafting"
        create_dir "01_Proposal/04_Submission"
    fi
    
    # Main work
    create_dir "$MAIN_NAME"
    if ! $IS_MINIMAL; then
        create_dir "$MAIN_NAME/01_Proposal_Reference"
        create_dir "$MAIN_NAME/02_Literature"
        create_dir "$MAIN_NAME/02_Literature/extracts"
        create_dir "$MAIN_NAME/02_Literature/sources"
        create_dir "$MAIN_NAME/03_Theory_chapters"
        create_dir "$MAIN_NAME/06_Discussion_Conclusion"
        create_dir "$MAIN_NAME/07_Introduction"
        create_dir "$MAIN_NAME/08_Formal_Review"
        create_dir "$MAIN_NAME/08_Formal_Review/format_reports"
        create_dir "$MAIN_NAME/08_Formal_Review/submissions"
        
        if [[ "$WORK_TYPE" == "Master thesis" || "$WORK_TYPE" == "Dissertation" ]]; then
            create_dir "$MAIN_NAME/04_Methods"
            create_dir "$MAIN_NAME/05_Empirical"
            create_dir "$MAIN_NAME/05_Empirical/data"
            create_dir "$MAIN_NAME/05_Empirical/data/raw"
            create_dir "$MAIN_NAME/05_Empirical/data/processed"
            create_dir "$MAIN_NAME/05_Empirical/data/scripts"
            create_dir "$MAIN_NAME/05_Empirical/data/outputs"
            create_gitkeep "$MAIN_NAME/05_Empirical/data/raw"
            create_gitkeep "$MAIN_NAME/05_Empirical/data/processed"
        fi
    fi
    
    # Defense
    create_dir "03_Defense"
    if ! $IS_MINIMAL; then
        create_dir "03_Defense/01_Slides"
        create_dir "03_Defense/02_Speaker_Notes"
        create_dir "03_Defense/03_Defense_Prep"
        create_dir "03_Defense/04_Handout"
        create_dir "03_Defense/05_Rehearsals"
        create_dir "03_Defense/06_Defense_Day"
        create_gitkeep "03_Defense/04_Handout"
        create_gitkeep "03_Defense/05_Rehearsals"
    fi
    
    # The agents read ../00_Shared_Materials/ directly. Earlier versions
    # linked or copied it into each sub-project as shared/: name such an
    # entry in "Next steps" (a copy may hold changes), never delete it.
    for p in "01_Proposal" "$MAIN_NAME" "03_Defense"; do
        if [ -e "$p/shared" ] || [ -L "$p/shared" ]; then
            OLD_SHARED="$OLD_SHARED $p/shared"
        fi
    done
    
    # Central files per sub-project
    step "Creating central state files per sub-project"
    for p in "01_Proposal" "$MAIN_NAME" "03_Defense"; do
        copy_template_or_fallback "templates/status.md" "$p/00_Status.md" "# Status: $p\n"
        copy_template_or_fallback "templates/decisions.md" "$p/00_Decisions.md" "# Decisions: $p\n"
        copy_template_or_fallback "templates/feedback_log.md" "$p/00_Feedback_log.md" "# Feedback Log: $p\n"
    done
    
    WORKFLOW="proposal_workflow.yaml, bachelor/master_*_longform.yaml, defense_workflow.yaml (per sub-project)"
fi

# ==========================================================
# Git setup
# ==========================================================

step "Git repository"

if [ ! -f ".gitignore" ]; then
    cat > .gitignore <<'EOF'
# System files
.DS_Store
Thumbs.db
desktop.ini

# Temporary Office files
~$*.docx
~$*.pptx
~$*.xlsx
~WRL*.tmp
.~lock.*#

# Editor directories
.vscode/
.idea/
*.swp

# Python
__pycache__/
*.pyc
.venv/
venv/

# Research data — never commit it: raw data may carry personal identifiers
**/data/raw/*
**/data/processed/*

# Keep placeholders
!**/data/raw/.gitkeep
!**/data/raw/README.md
!**/data/processed/.gitkeep

# Claude Code runtime artifacts (in every folder: in a multi-project
# setup, Claude Code is opened on a sub-project)
**/.claude/worktrees/
**/.claude/settings.local.json
EOF
    echo -e "  ${GREEN}+ .gitignore${NC}"
else
    echo -e "  ${GRAY}. .gitignore (exists)${NC}"
fi

# The LFS rules are written with a new .gitattributes, or appended to an
# existing one that has none yet (e.g. the template's own line-ending
# rules). Once present they are left alone, so re-runs never duplicate them.
if [ -f ".gitattributes" ] && grep -q 'filter=lfs' .gitattributes; then
    echo -e "  ${GRAY}. .gitattributes (exists)${NC}"
else
    GITATTRIBUTES_NOTE=""
    if [ -f ".gitattributes" ]; then
        GITATTRIBUTES_NOTE=" (LFS rules added)"
        # Start the appended block on a line of its own.
        if [ -n "$(tail -c 1 .gitattributes)" ]; then
            echo "" >> .gitattributes
        fi
    fi
    cat >> .gitattributes <<'EOF'
*.docx filter=lfs diff=lfs merge=lfs -text
*.pptx filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
*.xlsx filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
EOF
    echo -e "  ${GREEN}+ .gitattributes${GITATTRIBUTES_NOTE}${NC}"
fi

# -e, not -d: in a Git worktree or submodule, .git is a file.
if [ ! -e ".git" ]; then
    if command -v git &> /dev/null; then
        if git init > /dev/null 2>&1; then
            if command -v git-lfs &> /dev/null; then
                # Optional step: a failing `git lfs install` only warns
                # (parity with setup.ps1) instead of aborting under set -e.
                if git lfs install > /dev/null 2>&1; then
                    echo -e "  ${GREEN}+ Git repository initialized (with LFS)${NC}"
                else
                    echo -e "  ${GREEN}+ Git repository initialized${NC}"
                    echo -e "  ${YELLOW}! Git LFS present but 'git lfs install' failed. Large files will not use LFS.${NC}"
                fi
            else
                echo -e "  ${GREEN}+ Git repository initialized${NC}"
                echo -e "  ${YELLOW}! Git LFS not installed. Recommended: brew install git-lfs / apt install git-lfs (Windows: https://git-lfs.com)${NC}"
            fi
        else
            echo -e "  ${RED}! git init failed. Re-run manually to see the error: git init${NC}"
        fi
    else
        echo -e "  ${RED}! Git not installed. Install it from https://git-scm.com${NC}"
    fi
else
    echo -e "  ${GRAY}. Git repository exists${NC}"
fi

# ==========================================================
# Summary
# ==========================================================

SETUP_DONE=1
header "Setup complete"
echo ""
echo "Work type:    $WORK_TYPE"
echo "Structure:    $STRUCTURE"
echo "Scaffolding:  $SCAFFOLDING"
if [ -n "$SOURCE_DIR_BEFORE_MOVE" ]; then
    echo "Project:      $TARGET_DIR"
fi
echo ""
echo -e "${CYAN}Suggested workflow: $WORKFLOW${NC}"
echo ""
if [ -n "$SOURCE_DIR_BEFORE_MOVE" ]; then
    # The cd into the target happened in this script's process only: the
    # calling shell is still in the template folder, which the steps below
    # ("this directory", "git add .") do not mean.
    echo -e "${YELLOW}Next steps (in the project folder, not in this template folder):${NC}"
    # Single quotes (' as '\''): readable for umlauts in any locale, unlike
    # printf %q, and valid in bash and zsh alike. The substitution runs in an
    # assignment, where bash 3.2 and 5 treat the quote characters the same.
    squote="'\\''"
    target_quoted=${TARGET_DIR//\'/$squote}
    echo "   cd '$target_quoted'"
    echo ""
else
    echo -e "${YELLOW}Next steps:${NC}"
fi
# Keep the step numbers contiguous whether or not the minimal-only step
# prints (mirrors setup.ps1).
STEP_NO=1
echo "$STEP_NO. Place institutional guidelines into:"
if [ "$STRUCTURE" = "Flat" ]; then
    echo "   -> workspace/sources/_guidelines/"
elif [[ "$STRUCTURE" =~ ^Long-form ]]; then
    echo "   -> guidelines/"
else
    echo "   -> 00_Shared_Materials/guidelines/"
    if [ -n "$OLD_SHARED" ]; then
        echo -e "   ${YELLOW}No longer used (the agents read ../00_Shared_Materials/):${OLD_SHARED}"
        echo -e "   Delete them in Explorer or Finder: on the command line, deleting a link can"
        echo -e "   empty 00_Shared_Materials/. Move changes out of a copy first (docs/multiproject_structure.md).${NC}"
    fi
fi
echo ""
STEP_NO=$((STEP_NO + 1))
if [[ "$STRUCTURE" =~ ^Multi-project ]]; then
    echo "$STEP_NO. Open a sub-project (e.g. 01_Proposal/) in Claude Code — not this root —"
    echo "   and invoke the style-resolver"
else
    echo "$STEP_NO. Open this directory in Claude Code and invoke the style-resolver"
fi
echo ""

if $IS_MINIMAL; then
    STEP_NO=$((STEP_NO + 1))
    echo -e "${YELLOW}$STEP_NO. The style-resolver will propose additional subdirectories"
    echo -e "   based on your guidelines. Review and confirm before creation.${NC}"
    echo ""
fi

STEP_NO=$((STEP_NO + 1))
echo "$STEP_NO. Git commit:"
echo "   git add ."
echo "   git commit -m 'meta: initial setup ($WORK_TYPE, $STRUCTURE)'"
echo ""

# ==========================================================
# Offer to clean up the original source folder (if we copied)
# ==========================================================

if [ -n "$SOURCE_DIR_BEFORE_MOVE" ] && [ -d "$SOURCE_DIR_BEFORE_MOVE" ]; then
    # Started from a project (set up here earlier), not a bare template: the
    # copy left out its .git history and local Claude Code files, so it is
    # not offered for deletion.
    SOURCE_IS_PROJECT=false
    for marker in 00_Status.md 00_Shared_Materials workspace styleguide.md; do
        if [ -e "$SOURCE_DIR_BEFORE_MOVE/$marker" ]; then SOURCE_IS_PROJECT=true; fi
    done
    echo -e "${GRAY}The original cephalo template folder is still at:${NC}"
    echo -e "${GRAY}  $SOURCE_DIR_BEFORE_MOVE${NC}"
    echo ""
    if $SOURCE_IS_PROJECT; then
        echo -e "${YELLOW}! That folder is a project, not a bare template (it has 00_Status.md, workspace/ or the like).${NC}"
        echo -e "${YELLOW}  Kept: its Git history and local Claude Code files were not copied. Delete it only if you no longer need them.${NC}"
    elif [ -t 0 ] && [ -t 1 ]; then
        read -r -p "Delete it now? [y/N]: " del_ans || del_ans=""
        case "$del_ans" in
            [yYjJ]|[yY][eE][sS]|[jJ][aA])
                # Safety: only delete if it still looks like a cephalo template,
                # to avoid catastrophic rm -rf on an unrelated directory.
                if [ -f "$SOURCE_DIR_BEFORE_MOVE/setup.sh" ] \
                   && [ -d "$SOURCE_DIR_BEFORE_MOVE/.claude" ]; then
                    # "if": a failed deletion (a file without write access, or
                    # on Windows a folder still open in another window) is no
                    # failed setup for the ERR trap: the project is complete.
                    # The physical folder: entered through a symbolic link,
                    # rm -rf on the path would remove only the link.
                    if rm -rf "$SOURCE_CANON"; then
                        echo -e "${GREEN}+ Original folder deleted.${NC}"
                    else
                        echo -e "${YELLOW}! Could not delete the original folder completely (see above).${NC}"
                        echo -e "${YELLOW}  Parts of it may be gone already. Close other windows open in it, then delete the rest manually.${NC}"
                    fi
                else
                    echo -e "${YELLOW}! Source folder no longer looks like a cephalo template.${NC}"
                    echo -e "${YELLOW}  Skipped for safety. Please review and delete manually if needed.${NC}"
                fi
                ;;
            *)
                echo -e "${GRAY}Kept. You can delete it later manually.${NC}"
                ;;
        esac
    else
        echo -e "${GRAY}Non-interactive run: keeping the original in place.${NC}"
        echo -e "${GRAY}Delete manually if no longer needed:${NC}"
        printf '%b  rm -rf %s%b\n' "$GRAY" "$(shell_quote "$SOURCE_DIR_BEFORE_MOVE")" "$NC"
    fi
    echo ""
fi

# Disable error-trap for the clean-exit pause (we are done, not erroring)
trap - ERR
pause_before_close "done"