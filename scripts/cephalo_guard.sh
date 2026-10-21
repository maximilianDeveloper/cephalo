#!/bin/sh
# Runs the cephalo guard (scripts/cephalo_guard.py, beside this file) for the
# hook command of .claude/settings.json, which templates/claude_settings.json
# holds: with py on Windows, otherwise with python3, and not at all without
# Python, so that a missing Python never stops a tool call. The guard reads
# the hook's JSON from stdin and prints its answer; this script always exits 0.
g="${0%/*}/cephalo_guard.py"
[ -f "$g" ] || exit 0
# Every rule off (CEPHALO_GUARD_OFF=all): no Python start. Any other value,
# such as a list of rules, is read by the guard.
case "${CEPHALO_GUARD_OFF:-}" in [Aa][Ll][Ll]) exit 0 ;; esac
if [ "$OS" = Windows_NT ] && command -v py >/dev/null 2>&1; then
    py -3 -I -S "$g"
elif command -v python3 >/dev/null 2>&1; then
    # macOS without the Command Line Tools: /usr/bin/python3 only offers to
    # install them, in a dialog, on every call.
    if [ "$(command -v python3)" = /usr/bin/python3 ] && [ "$(uname -s)" = Darwin ] &&
        ! xcode-select -p >/dev/null 2>&1; then
        exit 0
    fi
    python3 -I -S "$g"
fi
exit 0
