#!/bin/sh
# Runs the cephalo guard (scripts/cephalo_guard.py, beside this file) for the
# hook command of .claude/settings.json, which templates/claude_settings.json
# holds: with py on Windows, otherwise with python3, and not at all without
# Python, so that a missing Python never stops a tool call. The guard reads
# the hook's JSON from stdin and prints its answer; this script always exits 0.
# An Edit, MultiEdit or Write of a file inside the project that no rule of the
# guard concerns passes here, without a Python start (the fast path below);
# every other call goes to the guard with its input unchanged. A rule that
# comes to concern such a file needs its exclusion in harmless() too.
g="${0%/*}/cephalo_guard.py"
[ -f "$g" ] || exit 0
# Every rule off (CEPHALO_GUARD_OFF=all): no Python start. Any other value,
# such as a list of rules, is read by the guard.
case "${CEPHALO_GUARD_OFF:-}" in [Aa][Ll][Ll]) exit 0 ;; esac

# The interpreter, in py and pv: py -3 on Windows, otherwise python3; false
# without one.
interpreter() {
    if [ "$OS" = Windows_NT ] && command -v py >/dev/null 2>&1; then
        py=py pv=-3
    elif command -v python3 >/dev/null 2>&1; then
        # macOS without the Command Line Tools: /usr/bin/python3 only offers to
        # install them, in a dialog, on every call.
        if [ "$(command -v python3)" = /usr/bin/python3 ] && [ "$(uname -s)" = Darwin ] &&
            ! xcode-select -p >/dev/null 2>&1; then
            return 1
        fi
        py=python3 pv=''
    else
        return 1
    fi
}

# r with each // as /
squash() {
    while :; do
        case $r in
            *//*) r=${r%%//*}/${r#*//} ;;
            *) return 0 ;;
        esac
    done
}

# The fast path: true for an Edit, MultiEdit or Write (PreToolUse, and
# PostToolUse for Write) of a file inside the project that none of the guard's
# rules can concern. For these tools the guard checks S2 (a path outside the
# project, Claude Code's scratchpad), S5 (.claude/settings.json and
# .claude/settings.local.json at any depth, scripts/ of the project or of a
# multi-project root), R5 and R6 (the reports in verification/ and
# format_reports/, also for the PostToolUse read-back), nothing else. Claude
# Code sends compact JSON ("tool_name":"Edit"); anything else, and anything
# read here without certainty, goes to the guard. A JSON string holds a quote
# only escaped, so '"key":' can only end a key. On the whole input only case
# patterns and one split at the quotes are used, which stay linear on a large
# Write (bash's ${x%%y*} or ${x#*y} on it would not); other expansions work on
# short strings.
harmless() {
    # a large input goes to the guard, which reads it faster than the patterns
    # below scan it (bash takes the path from the input's head, another shell
    # splits the whole input)
    if [ -n "${BASH_VERSINFO:-}" ]; then
        [ "${#json}" -le 2097152 ] || return 1
    else
        [ "${#json}" -le 262144 ] || return 1
    fi
    case $json in
        *'"tool_name":"Write"'[',}']* | *'"tool_name":"Edit"'[',}']* | \
        *'"tool_name":"MultiEdit"'[',}']*) ;;
        *) return 1 ;;
    esac
    case $json in
        *'"hook_event_name":"PreToolUse"'[',}']* | *'"hook_event_name":"PostToolUse"'[',}']*) ;;
        *) return 1 ;;
    esac
    case $json in
        *'"tool_input":{"file_path":"'* | *'"tool_input":{'*',"file_path":"'*) ;;
        *) return 1 ;;
    esac
    # one tool_name and one file_path key; a scratchpad_dir (S2) goes to the guard
    case $json in
        *'"tool_name":'*'"tool_name":'* | *'"file_path":'*'"file_path":'* | \
        *'"scratchpad_dir":'*) return 1 ;;
    esac
    # the path: the input split at its quotes, the token after file_path and ':'
    # (in bash only its head: bash splits a large Write's text slowly)
    h=$json
    [ -z "${BASH_VERSINFO:-}" ] || command eval 'h=${json:0:8192}' 2>/dev/null
    set -f
    IFS='"'
    # shellcheck disable=SC2086 # split on purpose
    set -- $h
    unset IFS
    set +f
    v='' a='' b='' c='' n=0
    for t do
        if [ "$b" = file_path ] && [ "$c" = : ]; then
            case $a in *['{,']) v=$t ;; esac
            break
        fi
        a=$b b=$c c=$t
        n=$((n + 1))
        [ "$n" -lt 256 ] || break
    done
    # a value that ends in a backslash may hold an escaped quote, and one the
    # head cut off has no closing quote in it
    case $v in '' | *\\) return 1 ;; esac
    case $h in *'"file_path":"'"$v"'"'*) ;; *) return 1 ;; esac
    [ "${#v}" -le 4096 ] || return 1
    # its escapes \\ and \/ become /; another one (\" \n \u...) goes to the guard
    r=''
    while :; do
        case $v in
            *\\*) r=$r${v%%\\*}/; v=${v#*\\} ;;
            *) r=$r$v; break ;;
        esac
        case $v in
            [\\/]*) v=${v#?} ;;
            *) return 1 ;;
        esac
    done
    case $r in //* | *..* | */./* | */. | *'~'*) return 1 ;; esac
    squash
    p=$r
    # an alternate data stream (x.md:s) goes to the guard
    case $p in [A-Za-z]:*) q=${p#??} ;; *) q=$p ;; esac
    case $q in *:*) return 1 ;; esac
    # the project folder, its \ as /
    v=${CLAUDE_PROJECT_DIR:-}
    case $v in '' | *'`'* | *[[:space:]]) return 1 ;; esac
    r=''
    while :; do
        case $v in
            *\\*) r=$r${v%%\\*}/; v=${v#*\\} ;;
            *) r=$r$v; break ;;
        esac
    done
    case $r in //*) return 1 ;; esac
    squash
    d=${r%/}
    # absolute, and not itself named scripts (a sub-project that is the
    # multi-project root's scripts/)
    case $d in
        /?* | [A-Za-z]:/?*) ;;
        *) return 1 ;;
    esac
    case $d in */[Ss][Cc][Rr][Ii][Pp][Tt][Ss]) return 1 ;; esac
    case $p in "$d"/?*) ;; *) return 1 ;; esac
    # what lies in the project: not scripts/, a .claude/ folder, the hook
    # settings or a report (in any letter case, as Windows ignores it)
    r=${p#"$d"/}
    case $r in
        [Ss][Cc][Rr][Ii][Pp][Tt][Ss]* | *.[Cc][Ll][Aa][Uu][Dd][Ee]/* | \
        *[Ss][Ee][Tt][Tt][Ii][Nn][Gg][Ss]* | *[Ff][Oo][Rr][Mm][Aa][Tt]* | \
        *[Vv][Ee][Rr][Ii][Ff][Ii][Cc][Aa][Tt][Ii][Oo][Nn]* | \
        *[Cc][Oo][Nn][Ss][Ii][Ss][Tt][Ee][Nn][Cc][Yy]_[Ff][Ii][Nn][Aa][Ll]*) return 1 ;;
    esac
    return 0
}

# No stdin (fd 0 closed, which a copy to fd 3 finds): the guard reads none and
# says so, as before; bash's $(cat) would wait on its own pipe there. (Not
# 'if ! ...': bash takes a failed redirection there for a success.)
if { :; } 2>/dev/null 3<&0; then :; else
    interpreter && "$py" ${pv:+"$pv"} -I -S "$g"
    exit 0
fi
# The input, read whole: bash reads $(< /dev/stdin) itself (5.2 without even a
# fork), another shell starts cat. Both read a pipe in blocks; the read builtin
# reads it byte by byte, one system call each, slow in Git Bash for a large
# Write. (bash: BASH_VERSINFO, an array, which no environment sets; 'command
# eval', which would not end another shell on an error.)
json=''
[ -z "${BASH_VERSINFO:-}" ] || command eval 'json=$(< /dev/stdin)' 2>/dev/null
[ -n "$json" ] || json=$(cat)
# The checks in bytes (bash matches a UTF-8 text 2 to 3 times slower), the
# locale restored for Python.
lc=${LC_ALL-} lcset=${LC_ALL+1}
LC_ALL=C
if harmless; then
    exit 0
fi
if [ -n "$lcset" ]; then LC_ALL=$lc; else unset LC_ALL; fi
# The input to the guard unchanged (but for trailing line ends, which the
# shell drops and JSON does not need), the interpreter at the pipe's end, where
# the shell starts it without a subshell of its own.
interpreter || exit 0
printf '%s' "$json" 2>/dev/null | "$py" ${pv:+"$pv"} -I -S "$g"
exit 0
