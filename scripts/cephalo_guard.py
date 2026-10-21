#!/usr/bin/env python3
"""cephalo guard: a Claude Code hook that stops a few slips that the agent
definitions forbid but models repeat although they have just read the rule.
The definitions stay the rule: the guard checks a few of them, and a project
without it works the same.

templates/claude_settings.json runs it, through scripts/cephalo_guard.sh,
for PreToolUse (Bash, PowerShell, Write, Edit, MultiEdit, NotebookEdit,
Agent, Task, SendMessage) and PostToolUse (Write).

Rules (on, except P1)
  S1  A shell command writes a file's text: an inline Python program
      (py -c / python3 -c, or a program from a here-document) that writes a
      file, a here-document, echo or printf into a file, a stream editor's
      output into a project file, sed -i / perl -i / awk -i inplace, a
      PowerShell content cmdlet, or a script that is not cephalo's and does
      one of these.  Denied: Write or Edit is the tool for it.  Running one
      of cephalo's scripts in scripts/ or an analysis script under
      data/scripts/ and redirecting its output, git, pip and pandoc pass.
  S2  A write outside the project folder: a Write/Edit path, or a shell
      redirect, tee, cp/mv/mkdir/touch destination, -o of pandoc/curl/sort,
      into /tmp, the system's temporary folder, the home folder, Claude
      Code's scratchpad or any other folder outside the project.  Denied.
  S3  'python3 x.py || py x.py' (exit code 1 is a finished report, the ||
      runs it again): denied everywhere.  python3 on Windows where py exists:
      denied.
  S4  A file redirect in the PowerShell tool (Windows PowerShell 5.1 writes
      UTF-16): denied; the Bash tool (Git Bash) is the one for it.
  S5  A change to the hook settings (.claude/settings.json and
      .claude/settings.local.json, the project's or the user's) or to
      cephalo's scripts/ folder: a Write or Edit, or a shell command that
      writes, moves or deletes them.  Denied: only the user changes them.
  R5  The coordinator (main chat or an orchestrator) and a saved
      source-verifier report (verification/*_round_<n>.md,
      consistency_final.md): after a Write, asks for the read-back the
      definitions require and gives the saved file's counts to compare with
      the verifier's answer; an Edit is denied (the copy is written again).
  R6  The coordinator writes or edits a report the format-verifier writes:
      denied, except a Write of a file that does not exist yet (the
      definitions' fallback).
  P1  Off unless switched on.  Agent / SendMessage: a task prompt with a
      phrase that narrows the check, tells the agent to leave out a finding,
      rates in advance or states the project's state is denied once; the
      same prompt sent again unchanged passes.

Switches, read from the environment (the "env" of
.claude/settings.local.json, which the user edits):
  CEPHALO_GUARD_OFF=all       every rule off
  CEPHALO_GUARD_OFF=S1,S2     the rules named off
  CEPHALO_GUARD_ON=P1         P1 on

Contract: reads the hook's JSON from stdin, prints at most one JSON object
(ASCII-escaped), and always exits 0.  It blocks only by
permissionDecision "deny" (PreToolUse) or decision "block" (PostToolUse) and
never answers "allow", which would skip the user's permission prompts.  Input
it does not understand, and any error of its own, let the call pass with a
one-line note to the user (systemMessage), once per session.  It writes
nothing but a small file per session in a folder of its own in the system's
temporary folder (cephalo-guard-<user id>/, on Windows cephalo-guard/), for
P1 when it is on and for that note, and uses no network.  Python 3.9 or later, standard library only.
"""

import bisect
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import stat
import sys
import time
import unicodedata

# Overrides for tests only: CEPHALO_GUARD_OS=windows|macos|posix,
# CEPHALO_GUARD_HAS_PY=1|0, CEPHALO_GUARD_STATE_DIR=<dir>.

# Rules that are off unless CEPHALO_GUARD_ON names them.
DEFAULT_OFF = ('P1',)

# cephalo's own scripts (CI checks the list against scripts/): the guard
# trusts these, and an analysis script under data/scripts/, to write files.
SHIPPED_SCRIPTS = ('abbreviations_extract.py', 'bibliography_check.py', 'build_reference_docx.py',
                   'cephalo_guard.py', 'cephalo_guard.sh', 'cross_session_audit.py', 'docx_pagination.py',
                   'docx_postprocess.sh', 'extract_styleguide.sh', 'verbatim_check.py')


# Work limits for one call: past one of them the guard stops and lets the call
# pass with its note (it never blocks a call it did not finish checking).
DEADLINE_S = 5.0                # the hook's timeout is 10 s
MAX_COMMAND = 1 << 19           # characters of one Bash/PowerShell command
MAX_READ = 1 << 21              # bytes of all scripts and patches read for one call
MAX_SCAN = 1 << 23              # characters of shell text and programs scanned for one call
MAX_EXPAND = 1 << 20            # characters a $var substitution adds to one inline program


class OverBudget(Exception):
    """The call is too large to check within the limits above."""


class Budget:
    def __init__(self):
        self.deadline = time.monotonic() + DEADLINE_S
        self.read = self.scanned = 0
        self.files = {}             # normalized path -> text read (each file is read once)
        self.scripts = set()        # scripts already checked for this call

    def tick(self):
        if time.monotonic() > self.deadline:
            raise OverBudget('it took longer than %g s' % DEADLINE_S)

    def scan(self, text):
        self.scanned += len(text)
        if self.scanned > MAX_SCAN:
            raise OverBudget('more than %d characters to scan' % MAX_SCAN)
        self.tick()


def _rule_set(value):
    return {x.upper() for x in re.split(r'[\s,;]+', value or '') if x}


# --------------------------------------------------------------- context


class Ctx:
    """What the rules need to know about the call and the machine."""

    def __init__(self, data, env):
        forced = env.get('CEPHALO_GUARD_OS', '')
        self.windows = forced == 'windows' if forced else os.name == 'nt'
        self.macos = forced == 'macos' if forced else sys.platform == 'darwin'
        self.env = env
        self.session = str(data.get('session_id') or 'nosession')
        self.agent_type = str(data.get('agent_type') or '')
        self.agent_id = str(data.get('agent_id') or '')
        # The main chat has no agent_type; `claude --agent orchestrator`
        # has one without an agent_id.
        self.coordinator = (not self.agent_type) or self.agent_type.startswith('orchestrator')
        home = env.get('USERPROFILE') if self.windows else None
        self.home_raw = home or env.get('HOME') or os.path.expanduser('~')
        project = env.get('CLAUDE_PROJECT_DIR') or str(data.get('cwd') or '') or os.getcwd()
        self.project_raw = project
        self.home = self._abs(self.home_raw)
        self.project = self._abs(project)
        self.root = self.project
        # Multi-project: a sub-project writes to ../00_Shared_Materials/.
        parent = posixpath.dirname(self.project)
        if parent and parent != self.project and os.path.isdir(
                os.path.join(os.path.dirname(os.path.normpath(project)), '00_Shared_Materials')):
            self.root = parent
        cwd = str(data.get('cwd') or '')
        self.cwd = self._abs(cwd) if cwd else self.project
        sp = str(data.get('scratchpad_dir') or '')
        self.scratchpad = self._abs(sp) if sp else ''
        self.claude_home = self.home + '/.claude' if self.home else ''
        self.off = _rule_set(env.get('CEPHALO_GUARD_OFF', ''))
        self.on = _rule_set(env.get('CEPHALO_GUARD_ON', ''))
        self.budget = Budget()
        self._sub_projects = None

    def enabled(self, rule):
        if 'ALL' in self.off or rule in self.off:
            return False
        return rule in self.on if rule in DEFAULT_OFF else True

    def _abs(self, p):
        n = norm_path(p, self, None)
        return n if n and n not in (DEVICE, TEMPVAR) else ''

    def has_py(self):
        forced = self.env.get('CEPHALO_GUARD_HAS_PY', '')
        if forced:
            return forced == '1'
        import shutil  # only needed on Windows, for S3
        return shutil.which('py') is not None

    def definition(self, rule):
        """The agent definition to name in a message: the agent's own for the
        shell rules S1/S2 where it has them under "Principles", otherwise the
        coordinator's."""
        own = ('research-agent', 'style-resolver', 'format-verifier', 'data-agent', 'methods-agent')
        if self.agent_type.startswith('orchestrator') or (rule in ('S1', 'S2') and self.agent_type in own):
            return '.claude/agents/%s.md' % self.agent_type
        longform = self.root != self.project or os.path.exists(os.path.join(self.project_raw, '00_Status.md'))
        return '.claude/agents/orchestrator-longform.md' if longform else '.claude/agents/orchestrator.md'


DEVICE = '<device>'
TEMPVAR = '<temp>'
_DEVICES = {'/dev/null', '/dev/stdout', '/dev/stderr', '/dev/tty', '/dev/fd/1', '/dev/fd/2',
            'nul', 'nul:', '$null', 'con', 'con:'}
_VAR = re.compile(r'^(?:\$\{(\w+)\}|\$(\w+)|%(\w+)%|\$env:(\w+))(?=[\\/]|$)', re.I)


def _fold(p, ctx):
    """A name as the rules compare it.  Windows (NTFS) ignores letter case.
    macOS (APFS, HFS+) ignores the Unicode form: a folder named in Finder
    (decomposed 'U' + U+0308, NFD) is the folder a typed path names with a
    precomposed 'Ü' (NFC), so both become NFC; the form stays valid for
    opening the file.  Letter case stays on macOS, where a volume can be
    case-sensitive.  Linux and NTFS keep the two forms apart: there they are
    two folders."""
    if ctx.windows:
        return p.lower()
    if ctx.macos:
        return unicodedata.normalize('NFC', p)
    return p


def norm_path(p, ctx, base):
    """Normalize a path to an absolute, '/'-separated string (compared as the
    file system does, see _fold).  Returns DEVICE for /dev/null and the like,
    TEMPVAR for a path in a temporary-folder variable, None when it cannot be
    resolved."""
    p = (p or '').strip()
    if len(p) >= 2 and p[0] == p[-1] and p[0] in '"\'':
        p = p[1:-1]
    if not p:
        return None
    if p.lower() in _DEVICES:
        return DEVICE
    m = _VAR.match(p)
    if m:
        var = next(g for g in m.groups() if g).upper()
        rest = p[m.end():]
        if var in ('TMP', 'TEMP', 'TMPDIR'):
            return TEMPVAR
        if var in ('HOME', 'USERPROFILE'):
            p = ctx.home_raw + rest
        elif var == 'CLAUDE_PROJECT_DIR':
            p = ctx.project_raw + rest
        else:
            return None
    elif p == '~' or p.startswith('~/') or p.startswith('~\\'):
        p = ctx.home_raw + p[1:]
    elif p.startswith('~') or '$' in p.split('/')[0] or '`' in p:
        return None
    p = p.replace('\\', '/')
    if ctx.windows:
        m = re.match(r'^/([a-zA-Z])(?=/|$)', p)       # Git Bash: /c/...
        if m:
            p = m.group(1) + ':' + p[2:]
        m = re.match(r'^/cygdrive/([a-zA-Z])(?=/|$)', p)
        if m:
            p = m.group(1) + ':' + p[11:]
    drive = re.match(r'^[a-zA-Z]:(?=/|$)', p)
    if not drive and not p.startswith('/'):
        if not base:
            return None
        if base == TEMPVAR:
            return TEMPVAR
        p = base + '/' + p
    if drive or re.match(r'^[a-zA-Z]:', p):
        head, tail = p[:2], p[2:] or '/'
        p = head.lower() + posixpath.normpath(tail)
    else:
        lead = '//' if p.startswith('//') and not p.startswith('///') else ''
        p = lead + posixpath.normpath(p).lstrip('/') if lead else posixpath.normpath(p)
    return _fold(p, ctx)


def inside(p, folder):
    if not p or not folder:
        return False
    folder = folder.rstrip('/')
    return p == folder or p.startswith(folder + '/')


def outside_reason(path, ctx, base):
    """Why a write target lies outside the project, or None."""
    n = norm_path(path, ctx, base)
    if n is None or n == DEVICE:
        return None
    if n == TEMPVAR:
        return 'a temporary folder'
    if ctx.scratchpad and inside(n, ctx.scratchpad):
        return "Claude Code's scratchpad"
    if inside(n, ctx.root):
        return None
    if ctx.claude_home and inside(n, ctx.claude_home):
        return None                 # plan files, memory: Claude Code's own
    return 'outside the project folder'


def under_scratch(path, ctx, base):
    n = norm_path(path, ctx, base)
    return bool(n) and (inside(n, ctx.project + '/_scratch') or inside(n, ctx.root + '/_scratch'))


# --------------------------------------------------------------- shell parsing

_HEREDOC = re.compile(r"(?<!<)<<(?!<)(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([A-Za-z_][\w.-]*))")


def strip_heredocs(cmd):
    """Replace each here-document by a placeholder word __HD<k>__ and return
    (command, bodies).  A '<<' whose closing line is missing is left alone
    (it is more likely text inside quotes)."""
    lines = cmd.split('\n')
    out, bodies = [], []
    plain, tabbed = {}, {}                       # closing-line text -> its line numbers, ascending
    for k, x in enumerate(lines):
        plain.setdefault(x.rstrip('\r'), []).append(k)
        tabbed.setdefault(x.lstrip('\t').rstrip('\r'), []).append(k)
    i, first_rest = 0, None
    while i < len(lines):
        line = lines[i]
        pending = []

        def repl(m):
            delim = next(g for g in (m.group(2), m.group(3), m.group(4)) if g is not None)
            pending.append((delim, m.group(1) == '-'))
            return '<<__HD%d__ ' % (len(bodies) + len(pending) - 1)

        new = _HEREDOC.sub(repl, line)
        if not pending:
            out.append(line)
            i += 1
            continue
        j, found, ok = i + 1, [], True
        for delim, dash in pending:
            at = (tabbed if dash else plain).get(delim, ())
            k = bisect.bisect_left(at, j)
            if k == len(at):
                ok = False                       # no closing line after it
                break
            found.append('\n'.join(lines[j:at[k]]))
            j = at[k] + 1
        if not ok:
            # bash reads an unterminated here-document up to the end (a closing
            # line with spaces around it does not end it).  Register the rest as
            # its body but keep the lines, so nothing is hidden from the checks;
            # a '<<' inside quotes stays text for the tokenizer and has no effect.
            if first_rest is None:                # later ones: the same text holds theirs
                first_rest = '\n'.join(lines[i + 1:])
            bodies.extend([first_rest] * len(pending))
            out.append(new)
            i += 1
            continue
        bodies.extend(found)
        out.append(new)
        i = j
    return '\n'.join(out), bodies


def _skip_paren(s, j):
    """s[j] == '(': index after the matching ')'."""
    depth, i, n = 0, j, len(s)
    while i < n:
        c = s[i]
        if c == '\\':
            i += 2
            continue
        if c in '\'"':
            k = s.find(c, i + 1)
            i = n if k < 0 else k + 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def tokenize(s, ps=False):
    """Split a command line into ('w', word), ('op', operator) and
    ('r', redirect-operator, fd) tokens.  Bash rules, or PowerShell's with
    ps=True (backtick escapes, backslash literal).  Approximate, never raises."""
    toks = []
    buf = []
    st = {'have': False, 'quoted': False}
    esc = '`' if ps else '\\'
    i, n = 0, len(s)

    def flush():
        if st['have']:
            toks.append(('w', ''.join(buf)))
        del buf[:]
        st['have'] = st['quoted'] = False

    while i < n:
        c = s[i]
        if c in ' \t\r':
            flush()
            i += 1
        elif c == '\n':
            flush()
            toks.append(('op', '\n'))
            i += 1
        elif c == '#' and not st['have']:
            k = s.find('\n', i)
            i = n if k < 0 else k
        elif c == esc:
            if i + 1 < n and s[i + 1] == '\n':
                i += 2
                continue
            if i + 1 < n:
                buf.append(s[i + 1])
                st['have'] = st['quoted'] = True
            i += 2
        elif c == "'":
            k = s.find("'", i + 1)
            k = n if k < 0 else k
            buf.append(s[i + 1:k])
            st['have'] = st['quoted'] = True
            i = k + 1
        elif c == '"':
            k, part = i + 1, []
            while k < n and s[k] != '"':
                if s[k] == esc and k + 1 < n and (ps or s[k + 1] in '"\\$`\n'):
                    part.append(s[k + 1])
                    k += 2
                elif s.startswith('$(', k):
                    e = _skip_paren(s, k + 1)
                    part.append(s[k:e])
                    k = e
                else:
                    part.append(s[k])
                    k += 1
            buf.append(''.join(part))
            st['have'] = st['quoted'] = True
            i = k + 1
        elif c == '$' and s.startswith('$(', i):
            e = _skip_paren(s, i + 1)
            buf.append(s[i:e])
            st['have'] = True
            i = e
        elif c == '`' and not ps:
            k = s.find('`', i + 1)
            k = n if k < 0 else k
            buf.append(s[i:k + 1])
            st['have'] = True
            i = k + 1
        elif c in '<>':
            fd = None
            word = ''.join(buf)
            if st['have'] and not st['quoted'] and (word.isdigit() or (ps and word == '*')):
                fd = word
                del buf[:]
                st['have'] = False
            else:
                flush()
            if c == '>':
                op = next(o for o in ('>>', '>&', '>|', '>') if s.startswith(o, i))
            else:
                op = next(o for o in ('<<<', '<<-', '<<', '<&', '<>', '<') if s.startswith(o, i))
            toks.append(('r', op, fd))
            i += len(op)
        elif ps and c in '{}':
            flush()                                  # a script block starts or ends a statement
            toks.append(('op', ';'))
            i += 1
        elif c in '|&;()':
            flush()
            if s.startswith('&>', i):
                op = '&>>' if s.startswith('&>>', i) else '&>'
                toks.append(('r', op, '&'))
                i += len(op)
                continue
            two = s[i:i + 2]
            if two in ('&&', '||', ';;', '|&'):
                toks.append(('op', two))
                i += 2
            else:
                toks.append(('op', c))
                i += 1
        else:
            buf.append(c)
            st['have'] = True
            i += 1
    flush()
    return toks


class Seg:
    """One simple command: its words, redirects (fd, op, target), here-document
    numbers, here-strings, the operator after it, and the segments it groups
    when it is the redirect part after '( ... )' or '{ ... }'."""
    __slots__ = ('words', 'redirs', 'heredocs', 'herestrings', 'sep', 'group', 'subshell_end')

    def __init__(self):
        self.words, self.redirs, self.heredocs, self.herestrings = [], [], [], []
        self.sep = ''
        self.group = None
        self.subshell_end = None    # on the first segment of a '( ... )': the index after it

    def empty(self):
        return not (self.words or self.redirs or self.heredocs or self.herestrings)


def parse(cmd, ps=False, pre=None):
    """Return (segments, pipelines, heredoc bodies).  pre: bodies already
    taken out of the text by an enclosing command."""
    if pre is not None:
        text, bodies = cmd, pre
    else:
        text, bodies = strip_heredocs(cmd) if not ps else (cmd, [])
    toks = tokenize(text, ps)
    segs, stack = [], []
    cur = Seg()
    pending_group = None

    def finish(sep):
        nonlocal cur, pending_group
        if pending_group is not None and not cur.words:
            cur.group = pending_group
        pending_group = None
        if not cur.empty() or cur.group:
            cur.sep = sep
            segs.append(cur)
        elif segs and sep:
            segs[-1].sep = sep
        cur = Seg()

    i = 0
    while i < len(toks):
        t = toks[i]
        if t[0] == 'w':
            w = t[1]
            if not cur.words and not ps and w == '{':
                finish('')
                stack.append(('{', len(segs)))
            elif not cur.words and not ps and w == '}' and stack:
                finish(';')
                pending_group = (stack.pop()[1], len(segs))
            else:
                cur.words.append(w)
        elif t[0] == 'r':
            op, fd = t[1], t[2]
            target = ''
            if i + 1 < len(toks) and toks[i + 1][0] == 'w':
                target = toks[i + 1][1]
                i += 1
            if op in ('<<', '<<-'):
                m = re.match(r'^__HD(\d+)__$', target)
                if m:
                    cur.heredocs.append(int(m.group(1)))
            elif op == '<<<':
                cur.herestrings.append(target)
            else:
                cur.redirs.append((fd, op, target))
        else:
            op = t[1]
            if op == '(':
                finish('')
                stack.append(('(', len(segs)))
            elif op == ')':
                finish(';')
                if stack:
                    kind, start = stack.pop()
                    pending_group = (start, len(segs))
                    if kind == '(' and start < len(segs):
                        segs[start].subshell_end = len(segs)
            else:
                finish(op)
        i += 1
    finish('')
    pipelines, run = [], []
    for k, seg in enumerate(segs):
        run.append(k)
        if seg.sep not in ('|', '|&'):
            pipelines.append(run)
            run = []
    if run:
        pipelines.append(run)
    return segs, pipelines, bodies


_PYNAME = re.compile(r'^(?:py|pyw|python|pythonw|python[23](?:\.\d+)?)$')
_WRAPPERS = ('env', 'command', 'exec', 'nohup', 'time', 'builtin', 'nice', 'xargs', 'timeout', 'gtimeout',
             'stdbuf', 'winpty', 'sudo', 'doas', 'unbuffer', 'chronic', 'caffeinate')
_RUNNERS = ('uv', 'poetry', 'pipenv', 'conda', 'pdm', 'hatch', 'rye')      # '<runner> run [opts] cmd'


def base_name(w):
    b = re.split(r'[\\/]', w)[-1].lower()
    return b[:-4] if b.endswith('.exe') else b


def cmd_args(words):
    """The command's base name and its arguments, past VAR=value and wrappers."""
    return cmd_split(words)[1:]


def cmd_split(words):
    """The command word as written, its base name and its arguments."""
    k = 0
    while k < len(words):
        w = words[k]
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', w):
            k += 1
            continue
        # PowerShell: '$x = Cmd', '[void]$x = Cmd'
        if re.match(r'^(?:\[[\w.\[\]]+\])?\$[\w:]+$', w) and k + 1 < len(words) and words[k + 1] in ('=', '+='):
            k += 2
            continue
        b = base_name(w)
        if b == 'command' and k + 1 < len(words) and words[k + 1] in ('-v', '-V'):
            return w, b, words[k + 1:]               # a lookup, not a run
        if b in _WRAPPERS:
            k += 1
            while k < len(words) and words[k].startswith('-'):
                k += 2 if (b == 'xargs' and words[k] in ('-I', '-n', '-d', '-L', '-P', '-s', '-E')) or \
                    (b in ('timeout', 'gtimeout') and words[k] in ('-s', '-k', '--signal', '--kill-after')) else 1
            if b in ('timeout', 'gtimeout') and k < len(words):
                k += 1                                   # the duration
            continue
        if b in _RUNNERS and k + 1 < len(words) and words[k + 1] == 'run':
            k += 2
            while k < len(words) and words[k].startswith('-'):
                k += 2 if words[k] in ('-n', '--name', '-p', '--prefix', '--with', '--python') else 1
            continue
        return w, b, words[k + 1:]
    return '', '', []


def py_mode(args):
    """How a Python command runs: ('c', code), ('stdin', ''), ('m', module),
    ('script', path) or ('probe', '')."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == '-':
            return 'stdin', ''
        if a in ('--version', '-V', '-VV', '--help', '-h', '-0', '--list'):
            return 'probe', ''
        if re.match(r'^-\d+(\.\d+)?(-\d+)?$', a):       # py -3, py -3.12
            i += 1
            continue
        m = re.match(r'^-[bBdEhiIOPqRsSuvx]*([cm])(.*)$', a)
        if m:
            val = m.group(2) or (args[i + 1] if i + 1 < len(args) else '')
            return ('c' if m.group(1) == 'c' else 'm'), val
        if re.match(r'^-[bBdEhiIOPqRsSuvx]*[WX]$', a):
            i += 2
            continue
        if a.startswith('-'):
            i += 1
            continue
        return 'script', a
    return 'stdin', ''


# --------------------------------------------------------------- S1 helpers

_PY_WRITE = re.compile(
    r"""open\s*\([^()]{0,160}?(?:\([^()]*\)[^()]{0,80}?)?(?:,\s*|mode\s*=\s*)['"][rbt]*(?:[wax]|\+)[rbt+]*['"]"""
    r"""|\.open\s*\(\s*(?:mode\s*=\s*)?['"][rbt]*(?:[wax]|\+)"""
    r"""|\.write_(?:text|bytes)\s*\("""
    r"""|\.save\s*\("""
    r"""|ZipFile\s*\([^()]{0,160}?,\s*(?:mode\s*=\s*)?['"][wax]['"]"""
    r"""|\.to_(?:csv|excel|json|parquet|pickle|html|latex|markdown)\s*\(\s*(?!\))"""
    r"""|\bshutil\.(?:copy\w*|move)\s*\(|\bos\.(?:replace|rename)\s*\("""
    r"""|savefig\s*\("""
    r"""|fileinput\.input\s*\([^()]{0,120}inplace""")
_PATH_LIT = re.compile(r"""['"]([^'"\n]{1,300})['"]""")
_PY_TARGET = re.compile(r"""\.save\s*\(\s*r?['"]([^'"\n]+)['"]"""
                        r"""|\bopen\s*\(\s*r?['"]([^'"\n]+)['"]\s*,\s*(?:mode\s*=\s*)?['"][rbt]*(?:[wax]|\+)"""
                        r"""|Path\s*\(\s*r?['"]([^'"\n]+)['"]\s*\)\s*\.(?:write_(?:text|bytes)|open\s*\(\s*['"][rbt]*[wax+])"""
                        r"""|ZipFile\s*\(\s*r?['"]([^'"\n]+)['"]\s*,\s*(?:mode\s*=\s*)?['"][wax]""")


def py_write(code, ctx=None, base=None):
    """The first write operation in a Python program, or None."""
    m = _PY_WRITE.search(code or '')
    if not m:
        return None
    lits = [x for x in _PATH_LIT.findall(code)
            if ('/' in x or '\\' in x or re.search(r'\.\w{1,5}$', x)) and not re.match(r'^\.\w{1,5}$', x)]
    def in_scratch(x):
        if ctx is not None:
            return under_scratch(x, ctx, base)
        n = posixpath.normpath(x.replace('\\', '/'))
        return not n.startswith('../') and bool(re.search(r'(?:^|/)_scratch/', n))
    if lits and all(in_scratch(x) for x in lits):
        return None                                  # writes only in _scratch/
    # every write call names its target, and each is in _scratch/ (reading a project file is fine)
    calls = len(_PY_WRITE.findall(code))
    targets = _PY_TARGET.findall(code)
    if targets and len(targets) >= calls and all(in_scratch(next(g for g in t if g)) for t in targets):
        return None
    return re.sub(r'\s+', ' ', m.group(0))[:40]


_TEXT_EDITORS = ('sed', 'awk', 'gawk', 'perl', 'tr', 'node', 'ruby', 'iconv')


def producer(segs, pipe, pos, bodies, depth=0):
    """What writes the text that reaches a file at segment pipe[pos]:
    ('typed', label) for text Claude typed (echo, printf, here-document,
    inline program), ('editor', label) for a stream editor, or None."""
    if pos < 0 or depth > 6:
        return None
    seg = segs[pipe[pos]]
    if seg.group:
        for k in range(seg.group[0], seg.group[1]):
            c, a = cmd_args(segs[k].words)
            if c in ('echo', 'printf') or (c in ('cat', 'tee') and (segs[k].heredocs or segs[k].herestrings)):
                return 'typed', c + ' in a ( ) or { } group'
        return None
    c, args = cmd_args(seg.words)
    if c in ('echo', 'printf'):
        return 'typed', c
    if c in ('cat', 'tee', '') and (seg.heredocs or seg.herestrings):
        return 'typed', 'a here-document' if seg.heredocs else 'a here-string'
    if c in ('cat', 'tee') and all(a == '-' or (c == 'tee' and a.startswith('-')) for a in args) or c == 'tee':
        return producer(segs, pipe, pos - 1, bodies, depth + 1)
    if _PYNAME.match(c):
        mode, _ = py_mode(args)
        if mode in ('c', 'stdin'):
            return 'typed', 'an inline Python program'
        return None
    if c in ('node', 'ruby', 'perl') and any(a in ('-e', '-E', '-pe', '-ne', '-lne', '-lpe') for a in args):
        return 'editor', c + ' -e'
    if c in _TEXT_EDITORS:
        return 'editor', c
    if c in _FILTERS and pos > 0:
        return producer(segs, pipe, pos - 1, bodies, depth + 1)   # typed text through a filter
    return None


_FILTERS = ('cat', 'sort', 'uniq', 'head', 'tail', 'cut', 'fold', 'fmt', 'column', 'nl', 'rev', 'paste',
            'expand', 'unexpand', 'grep', 'egrep', 'fgrep', 'tac', 'pr')


_STDOUT_OPS = ('>', '>>', '>|', '&>', '&>>')


def _target_ok(t):
    return t and not t.startswith('&') and t.lower() not in _DEVICES


# --------------------------------------------------------------- shell rules

_PS_WRITERS = ('set-content', 'add-content', 'out-file', 'tee-object', 'sc', 'ac')
_PS_FILE_API = re.compile(r'\[(?:System\.)?IO\.(?:File\]::(?:Write|Append|Create)\w*|StreamWriter\]::new)'
                          r'|New-Object\s+(?:-TypeName\s+)?(?:System\.)?IO\.StreamWriter', re.I)


def _substitutions(s):
    """The commands inside $( ) and backticks of a (here-document-free) bash
    command, outside single quotes."""
    out, i, n, dq = [], 0, len(s), False
    while i < n:
        c = s[i]
        if c == '\\':
            i += 2
        elif c == "'" and not dq:
            k = s.find("'", i + 1)
            i = n if k < 0 else k + 1
        elif c == '"':
            dq = not dq
            i += 1
        elif s.startswith('$(', i) and not s.startswith('$((', i):
            e = _skip_paren(s, i + 1)
            out.append(s[i + 2:e - 1])
            i = e
        elif c == '`':
            k = s.find('`', i + 1)
            if k < 0:
                break
            out.append(s[i + 1:k])
            i = k + 1
        else:
            i += 1
    return out


_DEVNAME = re.compile(r'com[1-9]|lpt[1-9]|con|nul|prn|aux', re.I)


def _fs_ok(n, ctx):
    """False when a filesystem call on the normalized path n would reach the
    network (a UNC or WebDAV share, a macOS /net automount), a Windows device or
    pipe namespace or a reserved device name, or a kernel pseudo-file whose read
    can block (procfs, sysfs).  Callers then skip the stat/open and let the call
    pass unchecked (fail open), so no slip is turned into an allow.  A network
    path inside the project's own root is kept, so a thesis on a UNC home share
    is still checked.  Pure string test: it never touches the filesystem, so it
    runs before os.path.isfile/exists (which would themselves open the share or
    device) and before any read that could hang."""
    if not n or n in (DEVICE, TEMPVAR):
        return False
    s = n.replace('\\', '/').lower()
    if s.startswith('//') or s.startswith('/net/'):      # UNC, //?/ , //./ , WebDAV, automount
        return inside(n, ctx.root) or bool(ctx.claude_home and inside(n, ctx.claude_home))
    if s == '/proc' or s == '/sys' or s.startswith('/proc/') or s.startswith('/sys/'):
        return False                                     # pseudo-files: a read can block with no timeout
    if ctx.windows and _DEVNAME.fullmatch(s.rsplit('/', 1)[-1].split('.', 1)[0]):
        return False                                     # COM1.., AUX, PRN resolve to a device in any dir
    return True


def _read_regular(path, limit):
    """Up to limit bytes of a regular file, or None.  Opened without blocking
    and checked on the open file, so a FIFO or device never blocks the hook."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
    except (OSError, ValueError, TypeError):
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        with os.fdopen(fd, 'rb') as fh:
            fd = None
            return fh.read(limit)
    except (OSError, ValueError):
        return None
    finally:
        if fd is not None:
            os.close(fd)


def _read_small(path, ctx, limit=262144):
    """A script, patch or input the command names (a normalized path): read
    once per call, within the call's read budget, and never from the network,
    a device or a pseudo-file (_fs_ok)."""
    if not _fs_ok(path, ctx):
        return None
    files = ctx.budget.files
    if path not in files:
        data = _read_regular(path, limit)
        if data:
            ctx.budget.read += len(data)
            if ctx.budget.read > MAX_READ:
                raise OverBudget('more than %d bytes of scripts to read' % MAX_READ)
        files[path] = None if data is None else data.decode('utf-8', 'replace')
    return files[path]


def _trusted_script(n, ctx):
    """A saved script the definitions run: one of cephalo's in scripts/ of the
    project (or the multi-project root), its setup script, or an analysis
    script under */data/scripts/.  Another file saved in scripts/ is not
    trusted."""
    if not n:
        return False
    for d in (ctx.project, ctx.root):
        if n in (d + '/setup.sh', d + '/setup.ps1'):
            return True
        if n.startswith(d + '/scripts/'):
            return n[len(d) + 9:] in SHIPPED_SCRIPTS
    return '/data/scripts/' in n


_SETTINGS = ('/.claude/settings.json', '/.claude/settings.local.json')


def protected(n, ctx):
    """What a normalized path is, if only the user changes it: the hook
    settings (the project's, a sub-project's or the user's) or cephalo's
    scripts/ folder.  None otherwise."""
    if not n or n in (DEVICE, TEMPVAR):
        return None
    if any(n.endswith(x) for x in _SETTINGS):
        return 'the hook settings ' + n.rsplit('/', 2)[-2] + '/' + n.rsplit('/', 1)[-1]
    for d in (ctx.project + '/scripts', ctx.root + '/scripts'):
        if inside(n, d):
            return "cephalo's scripts/ folder"
    return None


def holds_protected(n, ctx):
    """A folder whose removal or move takes the hook settings or scripts/
    with it (the project folder, a .claude/ folder, scripts/ itself, in a
    multi-project setup also a sibling sub-project)."""
    if not n or n in (DEVICE, TEMPVAR):
        return None
    if n.rsplit('/', 1)[-1] == '.claude':
        return 'a folder that holds hook settings'
    anchors = [ctx.project + '/scripts', ctx.root + '/scripts']
    bases = {ctx.project, ctx.root, ctx.home}
    if ctx.root != ctx.project:
        if ctx._sub_projects is None:
            try:
                ctx._sub_projects = [ctx.root + '/' + _fold(d, ctx) for d in os.listdir(ctx.root)
                                     if os.path.isdir(os.path.join(ctx.root, d))]
            except OSError:
                ctx._sub_projects = []
        bases.update(ctx._sub_projects)
    for base in bases:
        if base:
            anchors += [base + x for x in _SETTINGS]
    for a in anchors:
        if inside(a, n):
            why = protected(a, ctx) or "cephalo's scripts/ folder"
            return why if a == n else 'a folder that holds ' + why
    return None


_PY_REMOVE = re.compile(r'\bos\.(?:remove|unlink|rmdir|removedirs|rename|replace)\s*\(|\bshutil\.(?:rmtree|move|copy\w*)\s*\('
                        r'|\.(?:unlink|rmdir|rename|write_text|write_bytes|touch)\s*\(')
_PY_MOVES = re.compile(r'\bshutil\.(?:rmtree|move)\s*\(|\bos\.(?:rename|replace|rmdir|removedirs)\s*\(|\.(?:rmdir|rename)\s*\(|\brmtree\s*\(')


def py_protected(code, ctx, base):
    """A Python program that writes, moves or deletes a protected path."""
    if not code or not (_PY_WRITE.search(code) or _PY_REMOVE.search(code)):
        return None
    moves = bool(_PY_MOVES.search(code))
    for k, lit in enumerate(dict.fromkeys(_PATH_LIT.findall(code))):
        if not k % 1024:
            ctx.budget.tick()
        n = norm_path(lit, ctx, base)
        why = protected(n, ctx) or (holds_protected(n, ctx) if moves else None)
        if why:
            return lit, why
    return None


def check_shell(cmd, tool, ctx, depth=0, pre=None):
    """Hits [(rule, detail)] for a Bash or PowerShell command.  pre: the
    here-document bodies of an enclosing command (for a $( ) inside it)."""
    ps = tool == 'PowerShell'
    hits = []
    ctx.budget.scan(cmd)
    segs, pipes, bodies = parse(cmd, ps, pre)
    pipe_of = {k: pp for pp in pipes for k in pp}
    pos_of = {k: i for pp in pipes for i, k in enumerate(pp)}
    base = ctx.cwd
    bases = []                 # the folder relative paths of each segment start from
    prev_script = False        # the previous segment ran a Python script and ended in '||'
    assigns = {}               # name=value words seen so far (for python3 -c "$code")
    scratch_made = set()       # _scratch files this command fills by an exempt producer
    restore = []               # (end, folder) of the ( ... ) subshells the loop is in
    for si, seg in enumerate(segs):
        if not si % 256:
            ctx.budget.tick()
        while restore and restore[-1][0] <= si:
            base = restore.pop()[1]               # a cd inside ( ... ) ends with it
        if seg.subshell_end is not None:
            restore.append((seg.subshell_end, base))
        for w in seg.words:
            m = re.match(r'^([A-Za-z_]\w*)=(.*)$', w, re.S)
            if not m:
                break
            assigns[m.group(1)] = m.group(2)
        raw, c, args = cmd_split(seg.words)
        lc = c.lower()
        bases.append(base)
        # follow cd / pushd / Set-Location for the segments after this one
        if lc in ('popd', 'pop-location') or (lc in ('cd', 'chdir') and args[:1] == ['-']):
            base = None                             # where it goes back to is not known here
        elif lc in ('cd', 'pushd', 'set-location', 'sl', 'chdir'):
            dest = [a for a in args if not a.startswith('-')]
            if not dest:
                base = ctx.home if not ps else base
            else:
                n = norm_path(dest[0], ctx, base)
                base = TEMPVAR if n == TEMPVAR else (n if n and n != DEVICE else None)
        is_script = False
        p = pipe_of.get(si, [si])
        pos = pos_of.get(si, 0)
        pseg = segs[p[pos - 1]] if pos > 0 else None
        # S1 (a)/(b): inline Python programs that write a file
        if _PYNAME.match(c):
            mode, val = py_mode(args)
            code = None
            if mode == 'script' and val in ('/dev/stdin', '-'):
                mode = 'stdin'
            if mode == 'c':
                code = val + ''.join('\n' + b for b in {id(bodies[int(k)]): bodies[int(k)] for k in
                                     re.findall(r'__HD(\d+)__', val) if int(k) < len(bodies)}.values())
                code = re.sub(r'\$\{?([A-Za-z_]\w*)\}?', _expander(assigns), code)
                added = set()
                for f in dict.fromkeys(re.findall(r"""exec\s*\(\s*open\s*\(\s*['"]([^'"]+)['"]""", code)):
                    n = norm_path(f, ctx, bases[si]) or ''
                    if n not in added:
                        added.add(n)
                        code += '\n' + (_read_small(n, ctx) or '')
                for f in dict.fromkeys(re.findall(r"""\brun_path\s*\(\s*r?['"]([^'"]+)['"]""", code)):
                    hits += _script_hits(f, 'py', ctx, bases[si], depth)
            elif mode == 'stdin':
                parts = [bodies[k] for k in seg.heredocs if k < len(bodies)] + seg.herestrings
                parts += [_read_small(norm_path(t, ctx, bases[si]) or '', ctx) or '' for fd, op, t in seg.redirs
                          if op == '<' and fd in (None, '0')]
                if pseg is not None:
                    parts += [bodies[k] for k in pseg.heredocs if k < len(bodies)] + pseg.herestrings
                    pc, pargs = cmd_args(pseg.words)
                    if pc in ('echo', 'printf'):
                        parts += pargs                       # echo "program" | python3
                    elif pc == 'cat':
                        parts += [_read_small(norm_path(a, ctx, bases[si]) or '', ctx) or ''
                                  for a in pargs if not a.startswith('-')]
                code = '\n'.join(parts)
            if code:
                ctx.budget.scan(code)
            what = py_write(code, ctx, bases[si]) if code else None
            if what:
                hits.append(('S1', 'an inline Python program that writes a file: %s' % what))
            prot = py_protected(code, ctx, bases[si]) if code else None
            if prot:
                hits.append(('S5', '%s (%s), by an inline Python program' % prot))
            elif code:
                scratch_made.update(norm_path(x, ctx, bases[si]) for x in _PATH_LIT.findall(code)
                                    if under_scratch(x, ctx, bases[si]))
            # S1b: a Python script that is not cephalo's or an analysis script and writes a file
            if mode == 'script':
                hits += _script_hits(val, 'py', ctx, bases[si], depth)
            if mode == 'm' and val == 'runpy':
                rest = args[args.index('runpy') + 1:] if 'runpy' in args else []
                if rest and not rest[0].startswith('-'):
                    hits += _script_hits(rest[0], 'py', ctx, bases[si], depth)
            # S3 (a): a Python script run, '||', and the same script again
            if prev_script and mode == 'script' and val == prev_script[1]:
                hits.append(('S3', "'%s ... || %s ...' runs the script a second time" % (prev_script[0], c)))
            is_script = mode == 'script'
            # S3 (b): python3 on Windows
            if ctx.windows and re.match(r'^python3(\.\d+)?$', c) and mode != 'probe' and ctx.has_py():
                hits.append(('S3', 'python3 on Windows'))
        prev_script = (c, py_mode(args)[1]) if is_script and seg.sep == '||' else False
        # S1 (g): a patch typed into git apply / patch
        if (c == 'patch' or (c == 'git' and args[:1] == ['apply'])) and '--check' not in args and \
                '--stat' not in args and (seg.heredocs or seg.herestrings or
                                          (pseg is not None and producer(segs, p, pos - 1, bodies))):
            hits.append(('S1', '%s with a patch typed into the command' % ('git apply' if c == 'git' else c)))
        # S1 (g2), S5: a saved patch file applied (git apply f, patch -i f, patch < f)
        if (c == 'patch' or (c == 'git' and args[:1] == ['apply'])) and '--check' not in args and \
                '--stat' not in args:
            if c == 'git':
                pfiles = [a for a in args[1:] if not a.startswith('-')]
            else:
                pfiles = [args[k + 1] for k, a in enumerate(args) if a in ('-i', '--input') and k + 1 < len(args)]
                pfiles += [t for fd, op, t in seg.redirs if op == '<' and fd in (None, '0')]
            for pf in pfiles:
                body = _read_small(norm_path(pf, ctx, bases[si]) or '', ctx)
                if body is None:
                    continue
                hits.append(('S1', '%s with the saved patch %s' % ('git apply' if c == 'git' else c, pf)))
                for t in re.findall(r'^(?:\+\+\+|---) (?:[ab]/)?([^\t\n]+)', body, re.M):
                    why = protected(norm_path(t.strip(), ctx, bases[si]), ctx)
                    if why:
                        hits.append(('S5', '%s (%s), by the patch %s' % (t.strip(), why, pf)))
        # S1 (h): a file filled in _scratch/ by this command copied or moved over a project file
        for fd, op, t in seg.redirs:
            if op in _STDOUT_OPS and fd in (None, '1', '&') and _target_ok(t) and \
                    under_scratch(t, ctx, bases[si]) and producer(segs, p, pos, bodies):
                scratch_made.add(norm_path(t, ctx, bases[si]))
        if c in ('cp', 'mv', 'install', 'rsync') and scratch_made:
            pos_args = [a for a in args if not a.startswith('-')]
            if len(pos_args) >= 2 and not under_scratch(pos_args[-1], ctx, bases[si]) and any(
                    norm_path(a, ctx, bases[si]) in scratch_made for a in pos_args[:-1]):
                hits.append(('S1', '%s of a file this command wrote in _scratch/ to %s' % (c, pos_args[-1])))
        # S1 (e): in-place stream editors, also run by find -exec
        what = _inplace(c, args)
        if not what and c == 'find':
            for k, a in enumerate(args):
                if a in ('-exec', '-execdir', '-ok', '-okdir'):
                    sub = args[k + 1:]
                    end = next((j for j, x in enumerate(sub) if x in (';', '+')), len(sub))
                    what = _inplace(*cmd_args(sub[:end])) or what
        if what:
            hits.append(('S1', what))
        # nested shells (also bash -ec, sh -xc, cmd /c), and shell scripts run by name
        if depth < 2 and c in ('bash', 'sh', 'zsh', 'dash'):
            k = next((j for j, a in enumerate(args) if re.match(r'^-[A-Za-z]*c[A-Za-z]*$', a)), None)
            if k is not None and k + 1 < len(args):
                hits += check_shell(args[k + 1], 'Bash', ctx, depth + 1)
            elif k is None:
                files = [a for a in args if not a.startswith('-') and not a.startswith('+')]
                if files:
                    hits += _script_hits(files[0], 'sh', ctx, bases[si], depth)
                else:                               # the script on stdin: 'bash < f', 'cat f | sh'
                    src = [t for fd, op, t in seg.redirs if op == '<' and fd in (None, '0')]
                    if pseg is not None and cmd_args(pseg.words)[0] == 'cat':
                        src += [a for a in cmd_args(pseg.words)[1] if not a.startswith('-')]
                    for f in src:
                        hits += _script_hits(f, 'sh', ctx, bases[si], depth)
        if depth < 2 and lc in ('source', '.') and args and not ps:
            hits += _script_hits(args[0], 'sh', ctx, bases[si], depth)
        # a script run by its path (./fix.py, _scratch/fix.sh, a .ps1 in the PowerShell tool)
        if ('/' in raw or '\\' in raw) and re.search(r'\.(?:py|sh|bash)$', raw, re.I):
            hits += _script_hits(raw, 'py' if raw.lower().endswith('.py') else 'sh', ctx, bases[si], depth)
        if ps and raw.lower().endswith('.ps1'):
            hits += _script_hits(raw, 'ps', ctx, bases[si], depth)
        if depth < 2 and c == 'cmd':
            k = next((j for j, a in enumerate(args) if a.lower() in ('/c', '//c', '/k', '//k')), None)
            if k is not None and k + 1 < len(args):
                hits += check_shell(' '.join(args[k + 1:]), 'Bash', ctx, depth + 1)
        if depth < 2 and c in ('powershell', 'pwsh'):
            for k, a in enumerate(args):
                if a.lower() in ('-command', '-c') and k + 1 < len(args):
                    hits += check_shell(' '.join(args[k + 1:]), 'PowerShell', ctx, depth + 1)
                    break
                if a.lower() in ('-file', '-f') and k + 1 < len(args):
                    hits += _script_hits(args[k + 1], 'ps', ctx, bases[si], depth)
                    break
        # S1 (f): PowerShell content cmdlets
        if ps and (lc in _PS_WRITERS or (lc == 'new-item' and any(a.lower() == '-value' for a in args))):
            hits.append(('S1', 'the PowerShell cmdlet %s writes a file' % c))
        # S2: write targets outside the project; S5: the hook settings and scripts/
        for t in _write_targets(c, args, seg, ps):
            why = outside_reason(t, ctx, bases[si])
            if why:
                hits.append(('S2', '%s (%s)' % (t, why)))
            why = protected(norm_path(t, ctx, bases[si]), ctx)
            if why:
                hits.append(('S5', '%s (%s)' % (t, why)))
        if c in ('cp', 'mv', 'install', 'ln', 'rsync') or (ps and lc in ('copy-item', 'copy', 'cpi', 'move-item', 'move', 'mi')):
            pa = [a for a in args if not a.startswith('-')]
            if '-t' in args and args.index('-t') + 1 < len(args):
                dst = args[args.index('-t') + 1]; srcs = [a for a in pa if a != dst]
            else:
                dst, srcs = (pa[-1], pa[:-1]) if len(pa) >= 2 else ('', [])
            for src in srcs:
                why = protected(norm_path(dst.rstrip('/\\') + '/' + base_name(src), ctx, bases[si]), ctx) if dst else None
                if why:
                    hits.append(('S5', '%s (%s)' % (dst, why)))
        for t, kind in _change_targets(c, args, ps):
            n = norm_path(t, ctx, bases[si])
            why = protected(n, ctx) or (holds_protected(n, ctx) if kind == 'remove' else None)
            if why:
                hits.append(('S5', '%s (%s)' % (t, why)))
        # S4: PowerShell redirects
        if ps:
            for fd, op, t in seg.redirs:
                if op in _STDOUT_OPS and _target_ok(t):
                    hits.append(('S4', "'%s %s' in PowerShell" % (op if fd is None else fd + op, t)))
    # S1 (c)/(d): typed text or a stream editor's output into a file
    for p in pipes:
        for pos, si in enumerate(p):
            seg = segs[si]
            c, args = cmd_args(seg.words)
            sinks = [t for fd, op, t in seg.redirs
                     if op in _STDOUT_OPS and fd in (None, '1', '&', '*') and _target_ok(t)]
            for t in sinks:
                kind = producer(segs, p, pos, bodies)
                _sink_hit(hits, kind, t, ctx, bases[si])
            if c == 'tee' or (ps and c.lower() == 'tee-object'):
                files = [a for a in args if not a.startswith('-') and _target_ok(a)]
                if files:
                    if seg.heredocs or seg.herestrings:
                        kind = ('typed', 'a here-document')
                    else:
                        kind = producer(segs, p, pos - 1, bodies)
                    for t in files:
                        _sink_hit(hits, kind, t, ctx, bases[si])
    if ps and _PS_FILE_API.search(cmd):
        hits.append(('S1', '%s writes a file' % _PS_FILE_API.search(cmd).group(0)))
    # commands inside $( ) and backticks
    if not ps and depth < 2:
        text = cmd if pre is not None else strip_heredocs(cmd)[0]
        for sub in _substitutions(text):
            hits += check_shell(sub, 'Bash', ctx, depth + 1, pre=bodies)
    return _dedupe(hits)


def _expander(assigns):
    """re.sub callback for $x / ${x} in an inline program: the value of an
    assignment seen before, within MAX_EXPAND characters in all."""
    left = [MAX_EXPAND]

    def sub(mm):
        v = assigns.get(mm.group(1))
        if v is None:
            return mm.group(0)
        left[0] -= len(v)
        if left[0] < 0:
            raise OverBudget('a $variable expands to more than %d characters' % MAX_EXPAND)
        return v
    return sub


def _sink_hit(hits, kind, target, ctx, base):
    if not kind:
        return
    typ, label = kind
    if typ == 'editor' or label == 'an inline Python program':
        if under_scratch(target, ctx, base):
            return
    hits.append(('S1', '%s into %s' % (label, target)))


def _inplace(c, args):
    """A detail when the command edits a file in place, else None."""
    if c in ('sed', 'gsed') and _sed_inplace(args):
        return 'sed -i edits a file in place'
    if c == 'perl' and any(re.match(r'^-[0-9alnpsSTtuUwWX]*i', a) for a in args):
        return 'perl -i edits a file in place'
    if c in ('awk', 'gawk') and _awk_inplace(args):
        return 'awk -i inplace edits a file in place'
    if c == 'ruby' and any(re.match(r'^-[a-zA-Z]*i', a) for a in args if not a.startswith('--')):
        return 'ruby -i edits a file in place'
    return None


def _sed_inplace(args):
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ('-e', '-f', '--expression', '--file'):
            skip = True
            continue
        if a.startswith('--in-place') or re.match(r'^-[A-Za-z]*i', a):
            return True
    return False


def _awk_inplace(args):
    for k, a in enumerate(args):
        if a in ('-iinplace', '--include=inplace'):
            return True
        if a in ('-i', '--include') and k + 1 < len(args) and args[k + 1] == 'inplace':
            return True
    return False


def _write_targets(c, args, seg, ps):
    """Paths a simple command writes to (for S2)."""
    out = [t for fd, op, t in seg.redirs if op in _STDOUT_OPS + ('<>',) and _target_ok(t)]
    pos = [a for a in args if not a.startswith('-')]
    if c == 'tee':
        out += [a for a in pos]
    elif c in ('cp', 'mv', 'install', 'ln', 'rsync', 'scp'):
        if '-t' in args and args.index('-t') + 1 < len(args):
            out.append(args[args.index('-t') + 1])
        elif len(pos) >= 2:
            out.append(pos[-1])
    elif c in ('mkdir', 'touch'):
        out += pos
    elif c in ('pandoc', 'curl', 'wget', 'sort', 'unzip', 'soffice', 'libreoffice'):
        names = {'pandoc': ('-o', '--output'), 'curl': ('-o', '--output'), 'sort': ('-o', '--output'),
                 'wget': ('-O', '--output-document'), 'unzip': ('-d',),
                 'soffice': ('--outdir',), 'libreoffice': ('--outdir',)}[c]
        for k, a in enumerate(args):
            if a in names and k + 1 < len(args):
                out.append(args[k + 1])
            for nm in names:
                if nm.startswith('--') and a.startswith(nm + '='):
                    out.append(a.split('=', 1)[1])
            if c == 'pandoc' and a.startswith('-o') and len(a) > 2 and a != '-o':
                out.append(a[2:])
    elif ps:
        lc = c.lower()
        params = ('-path', '-filepath', '-literalpath', '-destination', '-outfile', '-destinationpath')
        if lc in ('new-item', 'ni', 'mkdir', 'md', 'copy-item', 'copy', 'cpi', 'move-item', 'move', 'mi',
                  'set-content', 'add-content', 'out-file', 'tee-object', 'expand-archive',
                  'invoke-webrequest', 'iwr', 'export-csv', 'sc', 'ac'):
            for k, a in enumerate(args):
                if a.lower() in params and k + 1 < len(args):
                    out.append(args[k + 1])
            if lc in ('copy-item', 'copy', 'cpi', 'move-item', 'move', 'mi') and len(pos) >= 2:
                out.append(pos[-1])
            elif lc in ('new-item', 'ni', 'mkdir', 'md', 'set-content', 'add-content', 'out-file') and pos:
                out.append(pos[0])
    return out


_REMOVERS = ('rm', 'rmdir', 'unlink', 'shred', 'truncate')
_PS_REMOVERS = ('remove-item', 'ri', 'del', 'erase', 'rd', 'rmdir', 'rm', 'clear-content', 'clc')
_PS_MOVERS = ('rename-item', 'ren', 'rni', 'move-item', 'mi', 'move', 'mv')


def _change_targets(c, args, ps):
    """Paths a simple command deletes, moves away or edits in place, for S5:
    [(path, 'remove' | 'edit')]."""
    lc = c.lower()
    pos = [a for a in args if not a.startswith('-')]
    if ps and (lc in _PS_REMOVERS or lc in _PS_MOVERS):
        named = [args[k + 1] for k, a in enumerate(args)
                 if a.lower() in ('-path', '-literalpath') and k + 1 < len(args)]
        if lc in _PS_REMOVERS:
            return [(a, 'remove') for a in named + pos]
        free = [a for k, a in enumerate(args) if not a.startswith('-') and
                not (k > 0 and args[k - 1].startswith('-'))]
        return [(a, 'remove') for a in (named or free[:1])]
    if lc in _REMOVERS:
        return [(a, 'remove') for a in pos]
    if lc == 'mv':
        if '-t' in args:
            k = args.index('-t')
            return [(a, 'remove') for i, a in enumerate(args) if not a.startswith('-') and i != k + 1]
        return [(a, 'remove') for a in pos[:-1]]
    if lc == 'find' and pos and ('-delete' in args or any(
            a in ('-exec', '-execdir') and k + 1 < len(args) and base_name(args[k + 1]) in _REMOVERS + ('mv',)
            for k, a in enumerate(args))):
        # a -name filter that can match none of the protected names only touches other files
        names = [args[k + 1] for k, a in enumerate(args) if a in ('-name', '-iname') and k + 1 < len(args)]
        wide = any(a in ('-path', '-ipath', '-regex', '-iregex', '-wholename', '-iwholename') for a in args)
        keys = ('.claude', 'scripts') + tuple(x.rsplit('/', 1)[-1] for x in _SETTINGS) + SHIPPED_SCRIPTS
        # (a file name has at most 255 characters; a longer pattern counts as matching, unread)
        if names and not wide and not any(len(p) > 255 or fnmatch.fnmatchcase(k.lower(), p.lower())
                                          for p in names for k in keys):
            return [(pos[0], 'edit')]
        return [(pos[0], 'remove')]
    if lc == 'git' and args:
        sub, rest = args[0], args[1:]
        paths = [a for a in rest if not a.startswith('-')]
        if sub == 'rm' and '--cached' not in rest or sub == 'mv':
            return [(a, 'remove') for a in paths]
        if sub in ('checkout', 'restore'):
            if '--' in rest:
                paths = rest[rest.index('--') + 1:]
            elif sub == 'checkout':
                return []                           # a branch switch
            return [(a, 'edit') for a in paths]
    if _inplace(lc, args):
        return [(a, 'edit') for a in pos]
    return []


def _script_hits(path, kind, ctx, base, depth):
    """S1 and S5 for a script that is run by the command: cephalo's own and an
    analysis script pass; another one is read, and what it writes counts as
    the command's."""
    n = norm_path(path, ctx, base)
    if not n or n in (DEVICE, TEMPVAR) or _trusted_script(n, ctx):
        return []
    if base_name(path) in ('setup.sh', 'setup.ps1'):
        return [('S1', 'SETUP:%s' % path)]          # cephalo's setup, outside this project
    key = (n, kind, base, depth)
    if key in ctx.budget.scripts:
        return []                                   # checked already for this call: same hits
    ctx.budget.scripts.add(key)
    ctx.budget.tick()
    body = _read_small(n, ctx)
    if not body:
        return []
    hits = []
    if kind == 'py':
        what = py_write(body, ctx, base)
        if what:
            hits.append(('S1', "the script %s, which is not one of cephalo's, writes a file: %s" % (path, what)))
        prot = py_protected(body, ctx, base)
        if prot:
            hits.append(('S5', '%s (%s), by the script %s' % (prot[0], prot[1], path)))
    elif depth < 2:
        for rule, detail in check_shell(body, 'PowerShell' if kind == 'ps' else 'Bash', ctx, depth + 1):
            if rule in ('S1', 'S2', 'S5'):
                hits.append((rule, '%s, in the script %s' % (detail, path)))
    return hits


def _dedupe(hits):
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# --------------------------------------------------------------- reports (R5, R6)

_FORMAT_REPORT = re.compile(r'(?:/verification/[^/]+_format_round_\d+\.md|/format_reports/round_\d+\.md'
                            r'|/format_report_round_\d+\.md)$', re.I)
_VERIFIER_REPORT = re.compile(r'/verification/(?:[^/]+_round_\d+|consistency_final)\.md$', re.I)


def check_file_write(tool, tin, ctx):
    path = tin.get('file_path') or tin.get('notebook_path')
    if not isinstance(path, str) or not path:
        return []
    hits = []
    why = outside_reason(path, ctx, ctx.cwd)
    if why:
        hits.append(('S2', '%s (%s)' % (path, why)))
    n = norm_path(path, ctx, ctx.cwd) or ''
    why = protected(n, ctx)
    if why:
        hits.append(('S5', '%s (%s)' % (_rel(n, ctx), why)))
    if ctx.coordinator and _FORMAT_REPORT.search(n):
        if tool != 'Write':
            hits.append(('R6', 'an Edit of the format report %s' % _rel(n, ctx)))
        elif _fs_ok(n, ctx) and os.path.exists(n):
            hits.append(('R6', 'a Write over the existing format report %s' % _rel(n, ctx)))
    elif ctx.coordinator and tool in ('Edit', 'MultiEdit') and _VERIFIER_REPORT.search(n):
        hits.append(('R5', 'an Edit of the saved report %s' % _rel(n, ctx)))
    return hits


def _rel(n, ctx):
    return n[len(ctx.root) + 1:] if inside(n, ctx.root) and n != ctx.root else n


def report_definition(ctx):
    """The definition that holds the rules on saved reports (orchestrator-defense
    saves none)."""
    d = ctx.definition('R5')
    return '.claude/agents/orchestrator-longform.md' if d.endswith('orchestrator-defense.md') else d


def readback(tin, ctx):
    path = tin.get('file_path')
    if not isinstance(path, str) or not ctx.coordinator:
        return None
    n = norm_path(path, ctx, ctx.cwd) or ''
    fmt = bool(_FORMAT_REPORT.search(n))
    if not fmt and not _VERIFIER_REPORT.search(n):
        return None
    if not ctx.enabled('R6' if fmt else 'R5'):
        return None
    data = _read_regular(path, 1 << 22) if _fs_ok(n, ctx) else None   # a report is far smaller than 4 MiB
    if data is not None:
        text = data.decode('utf-8', 'replace')
    else:
        text = tin.get('content') if isinstance(tin.get('content'), str) else ''
    lines = text.replace('\r\n', '\n').split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    rows = sum(1 for ln in lines if ln.lstrip().startswith('|'))
    status = sum(1 for ln in lines if 'Status:' in ln)
    quotes = sum(1 for ln in lines if re.search('[\u201e\u201c\u201d\u201a\u2018\u2019\u00ab\u00bb]', ln))
    last = lines[-1].strip() if lines else ''
    if len(last) > 160:
        last = last[:157] + '...'
    rel = _rel(n, ctx)
    counts = ('Lines in the saved file: %d table rows (starting with "|"), %d with "Status:", %d with '
              'typographic quotation marks; its last line is: %s.' % (rows, status, quotes, last or '(empty)'))
    if fmt:
        return ('cephalo guard R6: %s is saved as the format-verifier\'s answer, the fallback when it writes no '
                'report (%s, "The format-verifier writes its report itself"). Read it back with the Read tool '
                'and compare it with the answer. %s If it differs, tell the user: the guard does not let a '
                'format report be written over.' % (rel, report_definition(ctx), counts))
    msg = ('cephalo guard R5: %s is saved. Now read it back with the Read tool and compare it with the '
           'agent\'s answer, as %s says ("Save every source-verifier report as a file"; the Write tool\'s note '
           'that you need not read it back does not apply here). %s If any of this differs from the answer, '
           'write the file again with the Write tool, the answer unchanged; only an absolute path becomes '
           'project-relative.') % (rel, report_definition(ctx), counts)
    nfc = unicodedata.normalize('NFC', text)
    absolute = [unicodedata.normalize('NFC', x) for x in {ctx.project_raw, ctx.project_raw.replace('\\', '/'),
                                                          ctx.home_raw} if len(x) > 3]
    if any(x in nfc for x in absolute):
        msg += (' It still contains an absolute path of this machine: write the file again with the Write tool, '
                'the path made project-relative (an Edit of the saved report is denied).')
    return msg


# --------------------------------------------------------------- task prompts (P1)

_P1 = [(k, re.compile(p, re.I)) for k, p in [
    ('skip', r'\b(?:muss|müssen|brauchst?|braucht|need(?:s)?)\b[^.\n]{0,40}?\b(?:nicht|not|no longer)\b'
             r'[^.\n]{0,30}?\b(?:erneut|nochmal|noch einmal|again|re-?(?:check|verif|prüf|review|rate|flag|report|'
             r'assess))\w*[^.\n]{0,30}?(?:prüf|geprüft|check|verif|flag|report|meld|bewert)'),
    ('skip', r'\b(?:nicht|not)\s+(?:erneut|again|nochmals?|noch einmal|mehr)\s+(?:\w+\s+){0,3}?'
             r'(?:prüf|geprüft|check|verif|flag|report|meld|bewert|beanstand)'),
    ('skip', r"\b(?:do not|don't|dont|nicht)\s+(?:re-?)?(?:flag|report|melden|beanstanden|bewerten)\b"
             r'(?!\s+(?:to|back|directly|an|dem|den)\b)'),
    ('skip', r'\bleave\s+(?:\w+\s+){0,3}?out\b|\blass\w*\s+(?:\w+\s+){0,4}?weg\b|\bweglassen\b'),
    ('only', r'\bbeschränke?\s+dich\s+auf\b|\b(?:restrict|limit)\s+(?:yourself|your\s+(?:check|review|'
             r'verification))\s+to\b|\bonly\s+(?:look\s+at|read|consider|review)\b'),
    ('skip', r'\b(?:prüfe|prüft|check|verify|re-?check|re-?verify|bewerte|rate|review)\w*\s+(?:\w+\s+){0,3}?'
             r'(?:nicht|not)\s+(?:\w+\s+)?(?:erneut|again|nochmals?|noch einmal|neu)\b'),
    ('skip', r"\b(?:no need to|you (?:do not|don't) need to|need not|brauchst du nicht|musst du nicht)\s+"
             r'(?:\w+\s+){0,2}?(?:re-?)?(?:check|verify|review|rate|flag|report|prüfen|bewerten|melden)'),
    ('skip', r'\b(?:überspringe?|skip)\s+(?:\w+\s+){0,3}?(?:prüfung|check|verification|sätze|sentences|'
             r'zeilen|rows|befund|finding)'),
    ('only', r'(?:^|[.!?:;]\s+|\n\s*|\b(?:please|bitte)\s+)(?:prüfe|prüft|check|verify|re-?verify|re-?check|'
             r'bewerte|rate)\s+(?:\w+\s+)?(?:nur|only|just|lediglich|ausschließlich)\b'),
    ('only', r'\b(?:nur|only|just|lediglich|ausschließlich)\s+(?:die|the|den|der)?\s*(?:\w+\s+){0,2}?'
             r'(?:geänderten|changed|neuen|new|revised|überarbeiteten)\s+(?:sätze|sentences|satz|sentence|'
             r'stellen|passages|teilsatz|zeilen)'),
    ('change-only', r'\b(?:ändere|change|edit|bearbeite|revise|überarbeite)\s+(?:\w+\s+)?'
                    r'(?:nur|only|just|ausschließlich|lediglich)\b'),
    ('keep-files', r'(?:ändere|bearbeite|aktualisiere|edit|change|update|touch)\w*\s+(?:\w+\s+){0,3}?'
                   r'(?:nicht|not|keine)\s+(?:\w+\s+){0,3}?(?:quellenregister|source registry|registry|'
                   r'register|used in)'),
    ('keep-files', r'(?:quellenregister|registry|register|used in)[^.\n]{0,30}\b(?:nicht|not)\s+'
                   r'(?:ändern|anfassen|bearbeiten|aktualisieren|edit|change|touch|update)'),
    ('pre-rate', r'\b(?:should|sollte[n]?|müsste[n]?|dürfte[n]?)\s+(?:\w+\s+){0,3}?(?:pass|bestehen|green|'
                 r'grün|ok|in ordnung|fine|passen)\b'),
    ('pre-rate', r'(?<!\bso )\b(?:this|that|dies|das)\s+(?:\w+\s+){0,2}?(?:fixes|behebt|löst|resolves)\b'),
    ('pre-rate', r'\b(?:known|bekannte[nrs]?|erwartete[nrs]?|expected)\s+(?:\w+\s+){0,2}?(?:issue|problem|'
                 r'punkt|befund|finding|state|zustand|placeholder|platzhalter)'),
    ('presuppose', r'\b(?:bereits|already|schon)\s+(?:\w+\s+){0,3}?(?:geprüft|checked|verified|verifiziert|'
                   r'bestätigt|confirmed|green|grün)\b'),
    ('presuppose', r'\b(?:laut|per|according to|wie)\s+(?:dem\s+|the\s+)?(?:decision log|'
                   r'entscheidungsprotokoll|entscheidungslog)'),
    ('presuppose', r'\b(?:der|die|das|the)\s+(?:nutzer(?:in)?|user|anwender)\s+(?:hat|has)\s+(?:\w+\s+){0,3}?'
                   r'(?:bestätigt|entschieden|confirmed|decided|accepted|zugestimmt|akzeptiert)'),
]]
_NAMES_FILES = re.compile(r'state\.md|registry|register|used[\s-]in|00_Status', re.I)
_NAMES_EXTRACTS = re.compile(r'extracts?\b|exzerpt', re.I)
_P1_WHAT = {
    'skip': 'tells the agent to leave out part of its check or a finding',
    'only': 'narrows the check that the agent\'s definition sets',
    'change-only': 'limits the change but does not name all the files the agent may change (for the writer '
                   "also its chapter's rows of the source registry, or the Used in lines of the extracts)",
    'keep-files': 'keeps the agent from files its definition gives it',
    'pre-rate': 'rates in advance what the agent will find',
    'presuppose': "states the project's state",
}


def prompt_text(tool, tin):
    if tool == 'SendMessage':
        for key in ('message', 'content'):
            v = tin.get(key)
            if isinstance(v, str) and v:
                return v
        return None
    v = tin.get('prompt')
    return v if isinstance(v, str) else None


def p1_findings(text, target=''):
    """target: the subagent_type the prompt goes to ('' when unknown)."""
    found = []
    names_files = bool(_NAMES_FILES.search(text)) or (
        target == 'research-agent' and bool(_NAMES_EXTRACTS.search(text)))   # its files are the extracts
    rates_ok = bool(target) and 'verifier' not in target     # a rating in advance misleads a verifier
    for kind, rx in _P1:
        m = rx.search(text)
        if not m or (kind == 'change-only' and names_files) or (kind == 'pre-rate' and rates_ok) or \
                kind in (k for k, _ in found):
            continue
        s, e = max(0, m.start() - 30), min(len(text), m.end() + 30)
        while s > 0 and not text[s - 1].isspace() and s > m.start() - 45:
            s -= 1
        while e < len(text) and not text[e].isspace() and e < m.end() + 45:
            e += 1
        found.append((kind, re.sub(r'\s+', ' ', text[s:e]).strip()))
    return found


_NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)


def _state_dir(env):
    """The folder of the guard's state files, or '' when there is none it can
    use safely.  In a shared temporary folder (Linux, and macOS where TMPDIR is
    unset) another local user could create the folder first and plant links in
    it: the folder carries the user id, is made with mode 0700 and is used only
    when it is a real folder of this user that no one else can write.  On
    Windows %TEMP% is the user's own."""
    d = env.get('CEPHALO_GUARD_STATE_DIR')
    if d:
        return d
    import tempfile
    base = tempfile.gettempdir()
    if os.name == 'nt' or not hasattr(os, 'getuid'):
        return os.path.join(base, 'cephalo-guard')
    d = os.path.join(base, 'cephalo-guard-%d' % os.getuid())
    try:
        os.mkdir(d, 0o700)
    except FileExistsError:
        pass
    except OSError:
        return ''
    try:
        st = os.lstat(d)
    except OSError:
        return ''
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
        return ''
    return d


def _state_file(ctx, prefix='p1'):
    d = _state_dir(ctx.env)
    if not d:
        return '', ''
    sid = hashlib.sha256(ctx.session.encode('utf-8', 'replace')).hexdigest()[:16]
    return d, os.path.join(d, '%s-%s.txt' % (prefix, sid))


def _seen(ctx, key):
    path = _state_file(ctx)[1]
    data = _read_regular(path, 1 << 20) if path else None   # 65 bytes a deny: 16000 denies
    return data is not None and key in data.decode('ascii', 'replace').split()


def _remember(ctx, key):
    d, path = _state_file(ctx)
    if not d:
        return False
    try:
        os.makedirs(d, exist_ok=True)
        if not os.path.exists(path):
            _prune(d)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NONBLOCK', 0) | _NOFOLLOW,
                     0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return False
            os.write(fd, (key + '\n').encode('ascii'))
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def _prune(d, days=14):
    import time
    limit = time.time() - days * 86400
    try:
        for name in os.listdir(d):
            if name.startswith(('p1-', 'note-')) and name.endswith('.txt'):
                full = os.path.join(d, name)
                if os.path.getmtime(full) < limit:
                    os.remove(full)
    except OSError:
        pass


def check_prompt(tool, tin, ctx):
    """('deny', reason) | ('context', text) | None."""
    text = prompt_text(tool, tin)
    if not text:
        return None                       # e.g. a SendMessage protocol message without text
    defn = ctx.definition('P1')
    found = p1_findings(re.sub(r'\n\s+', '\n', text), str(tin.get('subagent_type') or ''))
    if not found:
        return None
    key = hashlib.sha256((tool + '\0' + text).encode('utf-8', 'replace')).hexdigest()
    if _seen(ctx, key):
        return None                       # sent again unchanged after a deny: passes
    parts = ['%s: "...%s..."' % (_P1_WHAT[k], s) for k, s in found[:3]]
    reason = ('cephalo guard P1: not sent. This task prompt %s. See %s, "Task prompts", and rewrite the '
              'prompt. If the wording is right (the definition asks for it, the user asked for exactly this, or '
              'a file you read in this chat shows it), send the same prompt again unchanged: the guard lets an '
              'identical prompt pass.') % ('; and it '.join(parts), defn)
    if _remember(ctx, key):
        return 'deny', reason
    return 'context', reason.replace('not sent.', 'sent, but check it:', 1)


# --------------------------------------------------------------- messages


def shell_reason(hits, ctx, cmd=''):
    by = {}
    for rule, detail in hits:
        by.setdefault(rule, []).append(detail)
    out = []
    setup = [x[6:] for x in by.get('S1', []) if x.startswith('SETUP:')]
    if setup:
        out.append('cephalo guard S1: not run. %s is cephalo\'s setup script, outside this project: the user runs '
                   'it in a terminal (README.md, "Quick start"). Tell the user the command instead.' % setup[0])
        by['S1'] = [x for x in by['S1'] if not x.startswith('SETUP:')]
        if not by['S1']:
            del by['S1']
    if 'S1' in by:
        d = ctx.definition('S1')
        tool_words = 'Write tool' if ctx.agent_type == 'format-verifier' else 'Write or Edit tool'
        msg = ('cephalo guard S1: not run. This command writes a file\'s text through the shell (%s). %s, '
               '"Principles": "Write a file\'s text with the %s". Make the change with %s.'
               % ('; '.join(by['S1'][:3]), d, tool_words, 'Write' if ctx.agent_type == 'format-verifier'
                  else 'Edit or Write'))
        joined = ' '.join(by['S1'])
        if '.save' in joined and re.search(r'docx|reference', cmd + joined, re.I):
            msg += ' A layout change in the reference document goes through scripts/build_reference_docx.py.'
        if 'in place' in joined and ctx.agent_type != 'format-verifier':
            msg += (' For a string that repeats, use Edit with replace_all, one call per file; do not rewrite '
                    'a whole chapter with Write.')
        msg += (" Running one of cephalo's scripts and redirecting its output is fine. If the tool cannot make "
                'the change, ask the user; do not save the program as a script file to get around this check.')
        if re.search(r'\bS\.(?:\\?\s|\\u00a0|\\xa0|\\x\{a0\}|\xa0)', cmd) or \
                re.search(r'00a0|x\{a0\}|nbsp|\xa0', cmd, re.I):
            msg += (' A non-breaking space before a page number is written in a chapter file as a backslash '
                    'before the space, `S.\\ 12` (writer-agent.md).')
        out.append(msg)
    if 'S2' in by:
        out.append('cephalo guard S2: not run. This writes outside the project: %s. %s, "Principles": "Stay '
                   'inside the project": scratch files go to _scratch/<your role>/ at the project root, not to '
                   "/tmp, the system's temporary folder or a scratchpad Claude Code names, and are deleted "
                   'before the chat ends. If the user asked for this place, tell them the guard stops it.'
                   % ('; '.join(by['S2'][:3]), ctx.definition('S2')))
    if 'S3' in by:
        if any('second time' in x for x in by['S3']):
            out.append("cephalo guard S3: not run. %s: exit code 1 of a cephalo script is a finished report "
                       "(it found something), and the '||' then runs it again. Run it once, with this "
                       "machine's Python command: py on Windows, otherwise python3 (checklists/precheck.md)."
                       % [x for x in by['S3'] if 'second time' in x][0])
        if any('Windows' in x for x in by['S3']):
            out.append('cephalo guard S3: not run. On this Windows machine the Python command is py, not '
                       'python3 (checklists/precheck.md). Run the same command with py.')
    if 'S4' in by:
        out.append('cephalo guard S4: not run. %s: Windows PowerShell writes a redirected file in UTF-16 '
                   '(docs/scripts.md, "Commands on Windows"). Run the command with the Bash tool (Git Bash) and '
                   'redirect there.' % by['S4'][0])
    if 'S5' in by:
        out.append('cephalo guard S5: not run. This changes %s. The hook settings in .claude/ and cephalo\'s '
                   'scripts in scripts/ are changed only by the user, by hand (docs/scripts.md, "cephalo '
                   'guard"). If the change is needed, tell the user what to change and why; do not get around '
                   'this check.' % '; '.join(by['S5'][:3]))
    if 'R5' in by:
        out.append('cephalo guard R5: not done (%s). A saved source-verifier report stays as the agent\'s '
                   'answer (%s, "Save every source-verifier report as a file"): if your copy differs from the '
                   'answer, write the file again with the Write tool, the answer unchanged; only an absolute '
                   'path becomes project-relative.' % (by['R5'][0], report_definition(ctx)))
    if 'R6' in by:
        out.append('cephalo guard R6: not done (%s). The format-verifier writes its report itself; do not write '
                   'or change it (%s, "The format-verifier writes its report itself"). Read in the file the '
                   'findings you fix. Only if the file does not exist after the call, save the agent\'s answer '
                   'there unchanged.' % (by['R6'][0], report_definition(ctx)))
    return ' '.join(out)


# --------------------------------------------------------------- main

_FILE_TOOLS = ('Write', 'Edit', 'MultiEdit', 'NotebookEdit')
_SHELL_TOOLS = ('Bash', 'PowerShell')
_AGENT_TOOLS = ('Agent', 'Task', 'SendMessage')


def evaluate(data, env=None):
    """The hook's answer for one input: a dict to print, or None."""
    env = os.environ if env is None else env
    if 'ALL' in _rule_set(env.get('CEPHALO_GUARD_OFF', '')):
        return None
    if not isinstance(data, dict):
        return note('hook input not understood (not a JSON object)', None, env)
    event = data.get('hook_event_name')
    tool = data.get('tool_name')
    tin = data.get('tool_input')
    if event not in ('PreToolUse', 'PostToolUse'):
        return None if isinstance(event, str) else note('hook input not understood (no hook_event_name)', data, env)
    if not isinstance(tool, str):
        return note('hook input not understood (no tool_name)', data, env)
    if tool not in _FILE_TOOLS + _SHELL_TOOLS + _AGENT_TOOLS:
        return None
    if not isinstance(tin, dict):
        return note('hook input not understood (tool_input of %s)' % tool, data, env)
    ctx = Ctx(data, env)
    if event == 'PostToolUse':
        if tool != 'Write':
            return None
        msg = readback(tin, ctx)
        return {'decision': 'block', 'reason': msg} if msg else None
    if tool in _SHELL_TOOLS:
        cmd = tin.get('command')
        if not isinstance(cmd, str):
            return note('hook input not understood (no command in the %s call)' % tool, data, env)
        try:
            if len(cmd) > MAX_COMMAND:
                raise OverBudget('more than %d characters' % MAX_COMMAND)
            hits = [h for h in check_shell(cmd, tool, ctx) if ctx.enabled(h[0])]
        except OverBudget as exc:
            return note('the %s command is too large to check (%s)' % (tool, exc), data, env)
        return deny(shell_reason(hits, ctx, cmd)) if hits else None
    if tool in _FILE_TOOLS:
        hits = [h for h in check_file_write(tool, tin, ctx) if ctx.enabled(h[0])]
        return deny(shell_reason(hits, ctx).replace('not run.', 'not done.')) if hits else None
    if not ctx.enabled('P1'):
        return None
    res = check_prompt(tool, tin, ctx)
    if not res:
        return None
    kind, text = res
    if kind == 'deny':
        return deny(text)
    if kind == 'note':
        return note(text)
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': text}}


def deny(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': reason}}


def note(text, data=None, env=None):
    """A one-line note to the user that the call was not checked, once per
    session (a later Claude Code may send input the guard does not know)."""
    env = os.environ if env is None else env
    session = str(data.get('session_id') or 'nosession') if isinstance(data, dict) else 'nosession'
    d = _state_dir(env)
    if d:
        path = os.path.join(d, 'note-%s.txt' % hashlib.sha256(session.encode('utf-8', 'replace')).hexdigest()[:16])
        try:
            os.makedirs(d, exist_ok=True)
            if not os.path.lexists(path):
                _prune(d)
            os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600))
        except FileExistsError:
            return None                   # shown already in this session
        except OSError:
            pass
    return {'systemMessage': 'cephalo guard: %s; nothing was checked.' % text}


def main():
    data = None
    try:
        raw = sys.stdin.buffer.read()
        try:
            data = json.loads(raw.decode('utf-8-sig', 'replace')) if raw.strip() else None
        except ValueError:
            data = None
        out = evaluate(data) if data is not None else note('hook input not understood (no JSON on stdin)')
    except Exception as exc:                       # fail open, whatever happens
        try:
            out = note('internal error (%s: %s)' % (type(exc).__name__, str(exc)[:80]), data)
        except Exception:
            out = None
    if out:
        try:
            sys.stdout.write(json.dumps(out, ensure_ascii=True))
            sys.stdout.flush()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
