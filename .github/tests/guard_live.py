#!/usr/bin/env python3
"""Live check of the cephalo guard: a real Claude Code session calls the hook
that setup.sh installs, and the guard must deny, or let pass, what it should.

Usage, from the repository root (CI: .github/workflows/guard-live.yml, on
GitHub's macOS runner):

    python3 -I .github/tests/guard_live.py [--work DIR] [--keep] [--skip-without-key]

It sets up a seminar paper with setup.sh in a folder whose name has an umlaut,
on macOS stored decomposed (NFD, as Finder writes it), checks that the guard got
installed and that its hook command denies a shell write when run directly
(H0) and, on macOS, takes the folder's NFC spelling for the project (H1).
Then it runs short `claude -p` calls in that folder (model haiku, a cost cap
per call; well under a cent a call in the runs on Linux).  Each asks Claude
for one tool call:

  K1  Bash 'echo probe >> workspace/state.md'                   S1, no file
  K2  Write scripts/probe_s5.py                                 S5, no file
  K3  Write into the chapter folder by its NFC spelling         passes, file written (macOS)
  K4  Write into scripts/ by the NFC spelling                   S5, not S2, no file  (macOS)
  K6  Write /tmp/cephalo-guard-live-<random>.txt                S2, no file
  K7  Write <temp folder>/cephalo-guard-live-<random>.txt       S2, no file  (not when it is /tmp)

K3 and K4 name the NFC spelling with --add-dir, so that only the guard
decides.  Informational, never failing: K0, a start by the NFC spelling
(macOS; with a model name that does not exist, so that it costs nothing),
K5, what Claude Code itself does with the NFC path without --add-dir
(macOS), and the forms (NFD/NFC) of the folder as Claude Code reports it
(init cwd) and passes it to hooks (CLAUDE_PROJECT_DIR and the hook input's
cwd, recorded by a SessionStart hook in the --settings file; a PreToolUse
hook there records the path and CLAUDE_PROJECT_DIR each call reaches the
hooks with).  An NFC case in which both names had one form already is
reported as not meaningful (info), not as ok.  Linux keeps the two forms
apart (two folders), so the NFC cases run on macOS only, and outside macOS
the folder's name is NFC: Claude writes an absolute path precomposed (NFC)
even when its working folder's name is NFD, and on Linux that names another
folder.

A case in which Claude called no matching tool, or whose call failed to run,
runs once more; inconclusive twice counts as failed, and so does a call that
the cost cap or the time limit stopped (not run again).  No call starts after
--deadline seconds, so that the check ends, with its summary, within the
job's time limit.  Exit 1 if a required case failed.  --skip-without-key:
exit 0 with a notice when ANTHROPIC_API_KEY is empty (the secret is not set,
or the run gets no secrets, as a pull request from a fork).  The output names
the home folder as ~ and the temp folder as $TMPDIR, shows no API key and
never prints the environment; Claude's answers appear shortened.

Python 3.9 or later, standard library only; macOS or Linux.
"""
import argparse
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MACOS = sys.platform == 'darwin'
NAME_NFD = unicodedata.normalize('NFD', 'Prüfung Übung')
NAME_NFC = unicodedata.normalize('NFC', NAME_NFD)
RULE = re.compile(r'cephalo guard ([SRP][0-9]+): not (?:run|done)\.')
WRITERS = ('Bash', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit')
NEEDED = ('--print', '--model', '--permission-mode', '--output-format', '--verbose', '--no-session-persistence',
          '--setting-sources', '--settings', '--mcp-config', '--strict-mcp-config', '--add-dir', '--max-budget-usd')
# What a surrounding Claude Code session leaves in the environment (a run from inside one).
UNSET = ('CLAUDECODE', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_CODE_REMOTE_SESSION_ID', 'CLAUDE_CODE_CHILD_SESSION',
         'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SSE_PORT', 'CLAUDE_ADDITIONAL_DIRECTORIES',
         'CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD', 'CLAUDE_CODE_HOLD_UNANSWERED_PARKED_PERMISSION',
         'CLAUDE_CODE_SESSION_ATTENDED', 'CLAUDE_CODE_TEE_SDK_STDOUT', 'CLAUDE_CODE_DIAGNOSTICS_FILE',
         'CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN', 'CLAUDE_PID', 'CLAUDE_EFFORT',
         'CLAUDE_CODE_DEBUG', 'CLAUDE_PROJECT_DIR')
NO_MODEL = 'cephalo-guard-live-no-such-model'
PROBE_MARK = 'cephalo-guard-live-probe'       # what the PreToolUse probe hook prints, to tell its answer apart
MIN_LEFT = 30                                 # seconds a call needs at least before the deadline
TAIL = 'Use this absolute path exactly as written. Do nothing else. Then reply with one word: done or blocked.'
GHA = os.environ.get('GITHUB_ACTIONS') == 'true'
HOME = os.path.expanduser('~')
KEY = re.compile(r'sk-ant-[A-Za-z0-9_-]+')


def tmp_forms():
    """The temp folder as Claude or the guard may write it (on macOS also under /private); not when it
    is /tmp, too short, or holds the home folder."""
    t, h = tempfile.gettempdir().rstrip('/'), HOME.rstrip('/')

    def ok(f):
        return len(f) >= 5 and f not in ('/tmp', '/private/tmp') and not (h and (h == f or h.startswith(f + '/')))

    if not ok(t):
        return []
    forms = {t, os.path.realpath(t)}
    if t.startswith(('/var/', '/tmp/', '/etc/')):
        forms.add('/private' + t)
    return sorted((f for f in forms if ok(f)), key=len, reverse=True)


TMP_FORMS = tmp_forms()


# ------------------------------------------------------------------ output

def san(text):
    """No API key, the temp folder as $TMPDIR (others under /var/folders as <temp folder>), the home
    folder as ~ (in either Unicode form), no e-mail address.  Before any shortening: GitHub masks only
    the whole key."""
    text = str(text)
    key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if len(key) >= 8:
        text = text.replace(key, '<key>')
    text = KEY.sub('<key>', text)
    for t in TMP_FORMS:
        text = text.replace(t, '$TMPDIR')
    text = re.sub(r'(?:/private)?/var/folders/[^/\s]+/[^/\s]+', '<temp folder>', text)
    if HOME and HOME != '/':
        for h in sorted({HOME, unicodedata.normalize('NFC', HOME), unicodedata.normalize('NFD', HOME)},
                        key=len, reverse=True):
            text = text.replace(h, '~')
    return re.sub(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', '<e-mail>', text)


def short(text, n=200):
    t = ' '.join(str(text).split())
    return t if len(t) <= n else t[:n - 1] + '…'


def form(text):
    nfc, nfd = unicodedata.normalize('NFC', text), unicodedata.normalize('NFD', text)
    if nfc == nfd:
        return 'no umlaut'
    return 'NFD' if text == nfd else 'NFC' if text == nfc else 'mixed'


def out(text):
    sys.stdout.buffer.write((text + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


def gha_escape(text):
    return text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


class Report:
    def __init__(self):
        self.rows = []
        self.cost = 0.0
        self.calls = 0

    def add(self, status, case, text, details=()):
        text, details = san(text), [san(d) for d in details]
        self.rows.append((status, case, text, details))
        out('%-8s %-6s %s' % (status, case, text))
        for d in details:
            out('                - ' + d)
        if status == 'FAILED' and GHA:
            out('::error title=guard live %s::%s' % (case, gha_escape(text)))

    def failed(self):
        return [r for r in self.rows if r[0] == 'FAILED']

    def summary(self, title):
        path = os.environ.get('GITHUB_STEP_SUMMARY')
        if not path:
            return
        cell = lambda s: s.replace('|', '\\|').replace('\n', ' ')  # noqa: E731
        lines = ['## %s' % title, '', '| Result | Case | What happened |', '|---|---|---|']
        for status, case, text, details in self.rows:
            more = ''.join('<br>– ' + cell(d) for d in details)
            lines.append('| %s | %s | %s%s |' % (status, case, cell(text), more))
        lines += ['', 'Claude Code calls: %d, cost together: %.4f USD (sum of total_cost_usd).' % (self.calls, self.cost), '']
        try:
            with open(path, 'a', encoding='utf-8') as fh:
                fh.write('\n'.join(lines) + '\n')
        except OSError as e:
            out('(could not write the step summary: %s)' % e)


# ------------------------------------------------------------------ files

def read(path):
    try:
        with open(path, 'rb') as fh:
            return fh.read().decode('utf-8', 'surrogateescape')
    except OSError:
        return ''


def snap(path):
    """The file's bytes, None when it does not exist."""
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except OSError as e:
        return ('unreadable: %s' % e).encode()


def remove(path):
    try:
        if os.path.lexists(path):
            os.remove(path)
            return True
    except OSError:
        pass
    return False


# ------------------------------------------------------------------ claude -p

def classify(text):
    t = text.lower()
    if any(k in t for k in ('rate limit', 'usage limit', 'limit reached', 'hit your', 'reached your', 'spend limit',
                            'credit balance', 'overloaded', '429', '529')):
        return 'limit'
    if any(k in t for k in ('api key', '/login', 'log in', 'logged in', 'login', 'authenticat', 'oauth',
                            'unauthorized', '401', 'x-api-key')):
        return 'auth'
    if 'model' in t:
        return 'model'
    return 'other'


def analyze(path, errpath, rc, timeout):
    """Read one stream-json run: the init event, the top-level tool calls, their
    results, Claude Code's own permission denials, hook events and the result."""
    a = {'init': None, 'result': None, 'calls': [], 'results': {}, 'perm': {}, 'hooks': [], 'stray': []}
    for line in read(path).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line) if line.startswith('{') else None
        except ValueError:
            e = None
        if not isinstance(e, dict):
            a['stray'].append(line)
            continue
        t, st = e.get('type'), e.get('subtype')
        if t == 'system' and st == 'init':
            a['init'] = e
        elif t == 'system' and st == 'permission_denied':
            a['perm'][e.get('tool_use_id')] = (str(e.get('decision_reason_type') or ''),
                                               str(e.get('decision_reason') or e.get('message') or ''))
        elif t == 'system' and st == 'hook_response':
            a['hooks'].append((str(e.get('hook_name') or ''), str(e.get('output') or e.get('stdout') or '')))
        elif t == 'assistant' and not e.get('parent_tool_use_id'):
            for c in (e.get('message') or {}).get('content') or []:
                if isinstance(c, dict) and c.get('type') == 'tool_use':
                    a['calls'].append({'id': c.get('id'), 'name': str(c.get('name')), 'input': c.get('input') or {}})
        elif t == 'user':
            meta = {m.get('id'): m for m in e.get('tool_result_meta') or [] if isinstance(m, dict)}
            content = (e.get('message') or {}).get('content')
            for c in content if isinstance(content, list) else []:
                if isinstance(c, dict) and c.get('type') == 'tool_result':
                    txt = c.get('content')
                    if isinstance(txt, list):
                        txt = ' '.join(str(x.get('text', '')) for x in txt if isinstance(x, dict))
                    pd = (meta.get(c.get('tool_use_id')) or {}).get('permission_decision') or {}
                    a['results'][c.get('tool_use_id')] = {
                        'err': bool(c.get('is_error')), 'text': str(txt or ''),
                        'source': str(pd.get('source') or ''), 'decision': str(pd.get('decision') or '')}
        elif t == 'result':
            a['result'] = e
    err = [x.strip() for x in read(errpath).splitlines() if x.strip()]
    res = a['result'] or {}
    errs = [str(x) for x in res.get('errors') or [] if x] if isinstance(res.get('errors'), list) else []
    if rc is None:
        a['run'], a['error'] = 'timeout', 'stopped after %d s (time limit)' % timeout
    elif a['init'] is None or not a['result']:
        msg = a['stray'] + err + [str(res.get('result') or ''), 'no output (exit code %d)' % rc]
        a['run'], a['error'] = 'failed', next(x for x in msg if x)
    elif res.get('is_error') and not a['calls']:
        a['run'], a['error'] = 'failed', str(res.get('result') or (errs[0] if errs else '') or
                                             (err[0] if err else 'an error without text'))
    else:
        a['run'], a['error'] = 'ok', ''
    a['error'] = short(san(a['error']), 200)
    # how the run ended, for a tool call that never ran (the cost cap, for example)
    a['end'] = short(san(errs[0] if errs else str(res.get('subtype') or 'without a result') if res else 'without a result'), 120)
    a['subtype'] = str(res.get('subtype') or '')
    cost = res.get('total_cost_usd')
    a['cost'] = float(cost) if isinstance(cost, (int, float)) else 0.0
    a['answer'] = short(san(res.get('result') or ''), 80)
    init = a['init'] or {}
    a['cwd'] = str(init.get('cwd') or '')
    a['model'] = short(str(init.get('model') or ''), 60)
    a['version'] = short(str(init.get('claude_code_version') or ''), 30)
    a['key_source'] = short(str(init.get('apiKeySource') or ''), 40)
    sid = str(init.get('session_id') or '')
    a['sid'] = sid if re.match(r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$', sid) else ''
    return a


def rules_of(a, call):
    r = a['results'].get(call['id']) if call else None
    return sorted(set(RULE.findall(r['text']))) if r and r['err'] else []


def path_of(call):
    inp = call['input'] if call and isinstance(call['input'], dict) else {}
    return str(inp.get('file_path') or inp.get('notebook_path') or inp.get('command') or '')


def same_folder(p, target, cwd):
    """P names a file in TARGET's folder: relative to CWD, in either Unicode form, /tmp as /private/tmp."""
    def folder(x):
        return unicodedata.normalize('NFC', os.path.realpath(os.path.dirname(x)))
    return folder(p if os.path.isabs(p) else os.path.join(cwd or '', p)) == folder(target)


def stop(p):
    """End a claude call and what it started (its own process group)."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(p.pid, sig)
        except OSError:
            pass
        try:
            p.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


class Claude:
    def __init__(self, exe, work, model, budget, timeout, deadline):
        self.exe, self.work, self.model, self.budget, self.timeout = exe, work, model, budget, timeout
        self.end = time.monotonic() + deadline
        self.runs = os.path.join(work, 'runs')
        self.probe = os.path.join(work, 'probe')
        self.state = os.path.join(work, 'state')
        for d in (self.runs, self.probe, self.state):
            os.makedirs(d, exist_ok=True)
        self.hookev = False
        self.sids = set()
        self.probe_json = os.path.join(self.probe, 'start.json')
        self.probe_pd = os.path.join(self.probe, 'start-pd.txt')
        # A SessionStart hook records how Claude Code passes the project folder to hooks, and a
        # PreToolUse hook what each call reaches the hooks with (one file per call, named by mktemp).
        cmd = 'cat > %s; printf %%s "$CLAUDE_PROJECT_DIR" > %s' % (shlex.quote(self.probe_json),
                                                                   shlex.quote(self.probe_pd))
        pre = ('f=$(mktemp %s) || exit 0; cat > "$f"; printf %%s "$CLAUDE_PROJECT_DIR" > "$f.pd"; printf %%s %s'
               % (shlex.quote(os.path.join(self.probe, 'pre.XXXXXX')), PROBE_MARK))
        self.settings = os.path.join(work, 'iso-settings.json')
        self.mcp = os.path.join(work, 'iso-mcp.json')
        with open(self.settings, 'w', encoding='utf-8') as fh:
            json.dump({'disableClaudeAiConnectors': True,
                       'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': cmd, 'timeout': 10}]}],
                                 'PreToolUse': [{'matcher': 'Bash|Write',
                                                 'hooks': [{'type': 'command', 'command': pre, 'timeout': 10}]}]}},
                      fh, indent=2)
        with open(self.mcp, 'w', encoding='utf-8') as fh:
            fh.write('{"mcpServers": {}}\n')

    def env(self, cwd):
        e = {k: v for k, v in os.environ.items() if k not in UNSET and not k.startswith('CEPHALO_GUARD_')}
        e.update(ENABLE_CLAUDEAI_MCP_SERVERS='false', DISABLE_AUTOUPDATER='1', CLAUDE_CODE_DISABLE_AUTO_MEMORY='1',
                 CEPHALO_GUARD_STATE_DIR=self.state, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        if cwd:
            e['PWD'] = cwd                       # as a shell sets it after cd
        return e

    def plain(self, *args):
        """claude with ARGS (no model call): exit code and output, or None, text."""
        try:
            p = subprocess.run([self.exe] + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, env=self.env(None), cwd=self.work, timeout=60)
            return p.returncode, p.stdout.decode('utf-8', 'replace')
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, str(e)

    def left(self):
        """Seconds until the deadline of the whole check."""
        return self.end - time.monotonic()

    def pre_records(self, drop_only=False):
        """What the PreToolUse probe recorded, by tool_use_id: the path and CLAUDE_PROJECT_DIR."""
        got = {}
        for n in os.listdir(self.probe):
            if not n.startswith('pre.') or n.endswith('.pd'):
                continue
            f = os.path.join(self.probe, n)
            try:
                d = json.loads(read(f))
            except ValueError:
                d = None
            if not drop_only and isinstance(d, dict) and isinstance(d.get('tool_input'), dict):
                ti = d['tool_input']
                got[str(d.get('tool_use_id'))] = {'path': str(ti.get('file_path') or ti.get('command') or ''),
                                                  'pd': read(f + '.pd')}
            remove(f)
            remove(f + '.pd')
        return got

    def run(self, rid, cwd, prompt, model=None, extra=()):
        args = [self.exe, '-p', prompt, '--model', model or self.model, '--permission-mode', 'acceptEdits',
                '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
                '--setting-sources', 'project,local', '--settings', self.settings,
                '--mcp-config', self.mcp, '--strict-mcp-config', '--max-budget-usd', '%.2f' % self.budget]
        if self.hookev:
            args.append('--include-hook-events')
        args += list(extra)                    # last: --add-dir takes several values
        remove(self.probe_json)
        remove(self.probe_pd)
        self.pre_records(drop_only=True)
        limit = max(1, min(self.timeout, int(self.left())))
        outp, errp = os.path.join(self.runs, rid + '.jsonl'), os.path.join(self.runs, rid + '.err')
        rc = None
        with open(outp, 'wb') as fo, open(errp, 'wb') as fe:
            p = subprocess.Popen(args, cwd=cwd, env=self.env(cwd), stdin=subprocess.DEVNULL, stdout=fo, stderr=fe,
                                 start_new_session=True)
            try:
                rc = p.wait(timeout=limit)
            except subprocess.TimeoutExpired:
                stop(p)
            except BaseException:              # Ctrl+C: claude has a session of its own and gets no SIGINT
                stop(p)
                raise
        a = analyze(outp, errp, rc, limit)
        a['hookev'] = self.hookev
        a['pre'] = self.pre_records()
        a['pd'] = read(self.probe_pd) if os.path.isfile(self.probe_pd) else None
        try:
            a['hookcwd'] = str(json.loads(read(self.probe_json)).get('cwd') or '') if os.path.isfile(self.probe_json) else None
        except (ValueError, AttributeError):
            a['hookcwd'] = None
        if a['sid']:
            self.sids.add(a['sid'])
        return a


# ------------------------------------------------------------------ cases

class Case:
    def __init__(self, cid, expect, target, prompt, label, nfc=False, extra=(), required=True, tool='Write'):
        self.id, self.expect, self.target, self.prompt, self.label = cid, expect, target, prompt, label
        self.nfc, self.extra, self.required, self.tool = nfc, extra, required, tool
        self.before = None
        self.cwd = ''


def matches(case, call):
    """The call the case asks for: its tool, on the target file (for a Write, in the target's folder)."""
    p = path_of(call)
    if call['name'] != case.tool or os.path.basename(case.target) not in p:
        return False
    return case.tool == 'Bash' or same_folder(p, case.target, case.cwd)


def evaluate(case, a):
    """(status, text, details): status ok, FAILED, info or inconclusive."""
    label = case.label
    if a['run'] != 'ok':
        return 'inconclusive', '%s: the run failed: %s' % (label, a['error']), []
    cand = [c for c in a['calls'] if matches(case, c)]
    main = next((c for c in cand if rules_of(a, c)), None) or (cand[0] if cand else None)
    if not main:
        calls = ['%s %s' % (c['name'], short(san(path_of(c)), 100)) for c in a['calls'] if c['name'] in WRITERS]
        return 'inconclusive', '%s: Claude made no %s call on the target file (its answer: "%s")' % (
            label, case.tool, a['answer']), ['Claude called ' + '; '.join(calls[:3])] if calls else []
    rules, p = rules_of(a, main), path_of(main)
    pform = form(p) if p else ''
    details = ['Claude called %s %s' % (main['name'], short(san(p), 140)) + (
        ' (written as %s)' % pform if pform in ('NFC', 'NFD', 'mixed') else '')]
    others = [c['name'] for c in a['calls'] if c is not main]
    if others:
        details.append('other calls: ' + ', '.join(others[:6]))
    r = a['results'].get(main['id'])
    perm = a['perm'].get(main['id'])
    if not perm and r and r['err'] and r['source'] == 'config' and r['decision'] == 'reject':
        perm = ('', r['text'])
    why = ''
    if perm:
        why = 'a path outside its working folders' if perm[0] == 'workingDir' else short(san(perm[1] or perm[0]), 120)
    notes = [h for h in a['hooks'] if 'systemMessage' in h[1]]
    if notes:
        details.append('note of the guard: ' + short(san(notes[0][1]), 160))
    touched = snap(case.target) != case.before
    if r is None and not perm:
        if not touched:
            return 'inconclusive', '%s: the tool did not run (the run ended: %s)' % (label, a['end']), details
        details.append("the run ended before Claude Code reported the tool's result (%s)" % a['end'])
    # what the hooks got for this call (the PreToolUse probe): the path and CLAUDE_PROJECT_DIR
    hp = (a.get('pre') or {}).get(main['id'])
    moot = ''
    if case.nfc:
        if pform != 'NFC':
            return 'inconclusive', '%s: Claude wrote the path as %s, not NFC' % (label, pform), details
        if hp:
            details.append('the hooks got the path as %s, CLAUDE_PROJECT_DIR as %s' % (
                form(hp['path']) if hp['path'] else 'nothing', form(hp['pd']) if hp['pd'] else 'empty'))
        # The NFC path tests the fold only when the folder it is compared with is NFD: for the
        # guard CLAUDE_PROJECT_DIR (else the hook input's cwd), for Claude Code itself (K5) its cwd.
        basis, who = (a['cwd'], "Claude Code's cwd") if case.expect == 'info' else (
            (hp or {}).get('pd') or a['pd'] or a['hookcwd'] or '', 'CLAUDE_PROJECT_DIR in the hook')
        if hp and hp['path'] and form(hp['path']) != 'NFC':
            moot = 'Claude Code passed the path to the hooks as %s, not as NFC' % form(hp['path'])
        elif not basis:
            details.append('the form of %s was not recorded' % who)
        elif form(basis) != 'NFD':
            moot = '%s was %s already, so both names had one form' % (who, form(basis))

    def result(status, text):
        if status == 'ok' and moot:
            return 'info', '%s; not meaningful: %s' % (text, moot), details
        if moot:
            details.append('not meaningful as a test of the NFC spelling: ' + moot)
        return status, text, details

    want = case.expect
    if want in ('S1', 'S2', 'S5'):
        if rules == [want] and not touched:
            return result('ok', '%s: denied by the guard (%s), no file written' % (label, want))
        if rules == [want] and want == 'S1':
            # The S1 message points to Write or Edit; a file written that way afterwards is no leak.
            later = next((c for c in a['calls'][a['calls'].index(main) + 1:]
                          if c['name'] in ('Write', 'Edit', 'MultiEdit') and os.path.basename(case.target) in path_of(c)
                          and (a['results'].get(c['id']) or {}).get('err') is False), None)
            if later:
                return result('ok', '%s: denied by the guard (S1); Claude then wrote the file with %s, as the message '
                                    'says' % (label, later['name']))
        if rules == [want]:
            return result('FAILED', '%s: denied by the guard (%s), but the file was written' % (label, want))
        if rules:
            details.append('the guard said: ' + short(san(r['text']), 240))
            return result('FAILED', '%s: denied by the guard, but with %s instead of %s' % (label, '+'.join(rules), want))
        if perm:
            return result('FAILED', '%s: the guard did not act; Claude Code itself refused (%s)' % (label, why))
        if touched:
            return result('FAILED', '%s: the guard did not act, and the file was written' % label)
        if r and r['err']:
            return result('FAILED', '%s: the guard did not act; the tool reported: %s' % (label, short(san(r['text']), 120)))
        return result('FAILED', '%s: the guard did not act (no file written)' % label)
    # the guard's own answers to this tool (not the probe's)
    seen = [h for h in a['hooks'] if h[0] == 'PreToolUse:' + main['name'] and h[1].strip() != PROBE_MARK]
    if seen:
        details.append('the PreToolUse hook ran%s' % (' and answered nothing' if not any(h[1].strip() for h in seen) else ''))
    if want == 'pass':
        if rules:
            details.append('the guard said: ' + short(san(r['text']), 240))
            return result('FAILED', '%s: denied by the guard (%s): it does not take the NFC path for the project' % (
                label, '+'.join(rules)))
        if any(h[0] == 'PreToolUse:' + main['name'] for h in notes):
            return result('FAILED', '%s: the guard did not check the call (its note above)%s' % (
                label, ', the file was written' if touched else ''))
        if a.get('hookev') and not seen:
            return result('FAILED', "%s: no answer of the guard's PreToolUse hook was seen%s" % (
                label, ', the file was written' if touched else ''))
        if touched:
            return result('ok', '%s: let pass by the guard, file written' % label)
        if perm:
            return result('FAILED', '%s: let pass by the guard, but Claude Code itself refused (%s), no file' % (label, why))
        return result('FAILED', '%s: no objection of the guard, but no file%s' % (
            label, ' (the tool reported: %s)' % short(san(r['text']), 120) if r and r['err'] else ''))
    # info (K5)
    if rules:
        return 'info', '%s: denied by the guard (%s)' % (label, '+'.join(rules)), details
    if touched:
        return 'info', '%s: Claude Code took the NFC path for its working folder (file written)' % label, details
    if perm:
        return 'info', '%s: Claude Code itself took the NFC path for one outside its working folder and refused (%s); the guard had no objection' % (label, why), details
    return 'info', '%s: no file, and no refusal%s' % (
        label, ' (the tool reported: %s)' % short(san(r['text']), 120) if r and r['err'] else ''), details


def restore(case):
    """The target as it was before the case."""
    if case.before is None:
        remove(case.target)
    elif snap(case.target) != case.before:
        try:
            with open(case.target, 'wb') as fh:
                fh.write(case.before)
        except OSError:
            pass


def run_case(rep, claude, case, cwd):
    """Run one case, once more if inconclusive. Returns the last analysis."""
    case.cwd = cwd
    case.before = snap(case.target)
    a, status, text, details, runs = None, 'inconclusive', '', [], 0
    for attempt in (1, 2):
        if attempt == 2 and claude.left() < MIN_LEFT:
            details.append('not run again: the time limit of the whole check was near')
            break
        a = claude.run(case.id if attempt == 1 else case.id + '-again', cwd, case.prompt, extra=case.extra)
        runs += 1
        rep.calls += 1
        rep.cost += a['cost']
        status, text, details = evaluate(case, a)
        # not again: a call the time limit or the cost cap stopped, a login or limit error
        if status != 'inconclusive' or a['run'] == 'timeout' or a['subtype'] == 'error_max_budget_usd' or (
                a['run'] != 'ok' and classify(a['error']) in ('auth', 'limit')):
            break
        if attempt == 1:
            out('         %-6s inconclusive (%s), once more' % (case.id, short(san(text), 140)))
            restore(case)
    if status == 'inconclusive':
        status = 'FAILED' if case.required else 'info'
        if a['subtype'] == 'error_max_budget_usd':
            text = 'stopped by the cost cap (%.2f USD a call): %s' % (claude.budget, text)
        else:
            text = 'inconclusive%s: %s' % (' twice' if runs == 2 else '', text)
        if a['stray']:
            details.append('output outside JSON: ' + short(san(a['stray'][0]), 140))
    elif status == 'FAILED' and a['answer']:
        details.append('answer of Claude: "%s"' % a['answer'])
    rep.add(status, case.id, text, details)
    return a


# ------------------------------------------------------------------ steps

def find_claude(given):
    """--claude as given, else the one on PATH, else ~/.local/bin/claude (where the installer puts it)."""
    for c in (given,) if given else (shutil.which('claude'), os.path.join(HOME, '.local', 'bin', 'claude')):
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return ''


def hook_command(settings_path):
    try:
        with open(settings_path, encoding='utf-8') as fh:
            data = json.load(fh)
        cmds = {ev: [h.get('command', '') for m in data['hooks'][ev] for h in m['hooks']]
                for ev in ('PreToolUse', 'PostToolUse')}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ''
    if all(any('cephalo_guard.sh' in c for c in cmds[ev]) for ev in cmds):
        return next(c for c in cmds['PreToolUse'] if 'cephalo_guard.sh' in c)
    return ''


def hook_env(proj, state):
    env = {k: v for k, v in os.environ.items() if k not in UNSET and not k.startswith('CEPHALO_GUARD_')}
    env.update(CLAUDE_PROJECT_DIR=proj, CEPHALO_GUARD_STATE_DIR=state)
    return env


def hook_direct(cmd, proj, state, tool, tool_input, want):
    """The hook command as Claude Code starts it (/bin/sh -c), with a crafted PreToolUse input:
    (True when the guard answered as WANT, a list of rules or [] for letting the call pass, what it did)."""
    data = {'session_id': 'cephalo-guard-live', 'cwd': proj, 'permission_mode': 'acceptEdits',
            'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_use_id': 'toolu_guard_live',
            'tool_input': tool_input}
    try:
        p = subprocess.run(['/bin/sh', '-c', cmd], input=json.dumps(data).encode('utf-8'), cwd=proj,
                           env=hook_env(proj, state), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, 'did not run: %s' % e
    text = p.stdout.decode('utf-8', 'replace')
    try:
        h = json.loads(text) if text.strip() else {}
    except ValueError:
        h = None
    hs = h.get('hookSpecificOutput') if isinstance(h, dict) else None
    if isinstance(hs, dict) and hs.get('permissionDecision') == 'deny':
        rules = sorted(set(RULE.findall(str(hs.get('permissionDecisionReason')))))
        return rules == want, 'denied with %s' % ('+'.join(rules) or 'no rule named')
    if h == {} and p.returncode == 0:
        return want == [], 'let pass'
    return False, 'answered %s (exit code %d%s)' % (short(san(text), 120) or 'nothing', p.returncode,
                                                   ', stderr: ' + short(san(p.stderr.decode('utf-8', 'replace')), 120)
                                                   if p.stderr.strip() else '')


def python3_line():
    py = shutil.which('python3')
    if not py:
        return 'no python3 on PATH: the hook passes every call unchecked'
    try:
        v = subprocess.run([py, '-I', '-c', 'import sys; print("%d.%d.%d" % sys.version_info[:3])'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=60).stdout.decode().strip()
    except (OSError, subprocess.TimeoutExpired):
        v = '?'
    return 'python3 for the hook: %s, version %s' % (py, v or '?')


def cleanup_claude_leftovers(sids):
    """Claude Code's small per-session leftovers of these runs (with --no-session-persistence)."""
    home = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(HOME, '.claude')
    ctmp = os.path.join(tempfile.gettempdir(), 'claude-%d' % os.getuid())
    for s in sids:
        try:
            os.rmdir(os.path.join(home, 'session-env', s))      # only when empty
        except OSError:
            pass
        remove(os.path.join(ctmp, 'cache-break-state-%s.json' % s))


def main():
    ap = argparse.ArgumentParser(description='Live check of the cephalo guard with a real Claude Code session.')
    ap.add_argument('--work', help='folder for the test project and the run files '
                                   '(default: $RUNNER_TEMP, else the home folder)')
    ap.add_argument('--keep', action='store_true', help='keep the test project and the run files')
    ap.add_argument('--skip-without-key', action='store_true',
                    help='exit 0 with a notice when ANTHROPIC_API_KEY is empty')
    ap.add_argument('--claude', help='the claude executable (default: on PATH, else ~/.local/bin/claude)')
    ap.add_argument('--model', default='haiku')
    ap.add_argument('--budget', type=float, default=0.10, help='cost cap per call in USD (default 0.10)')
    ap.add_argument('--timeout', type=int, default=120, help='time limit per call in seconds (default 120)')
    ap.add_argument('--deadline', type=int, default=720,
                    help='seconds after which no call starts any more (default 720; the job allows 15 minutes)')
    args = ap.parse_args()
    title = 'cephalo guard in a live Claude Code session (%s)' % ('macOS' if MACOS else sys.platform)

    if args.skip_without_key and not os.environ.get('ANTHROPIC_API_KEY', '').strip():
        msg = ('ANTHROPIC_API_KEY is empty (the repository secret is not set, or this run gets no secrets, '
               'as a pull request from a fork does). No Claude Code session ran.')
        out(('::notice title=Guard live check skipped::' + msg) if GHA else 'Guard live check skipped: ' + msg)
        path = os.environ.get('GITHUB_STEP_SUMMARY')
        if path:
            with open(path, 'a', encoding='utf-8') as fh:
                fh.write('## %s\n\nSkipped: %s\n\n' % (title, msg))
        return 0

    rep = Report()
    base = args.work or os.environ.get('RUNNER_TEMP') or HOME
    os.makedirs(base, exist_ok=True)
    work = tempfile.mkdtemp(prefix='cephalo-guard-live-', dir=base)
    tag = secrets.token_hex(4)
    probes = []                                # files outside the project a case asks for
    claude = None
    try:
        system = ('macOS %s' % platform.mac_ver()[0]).strip() if MACOS else platform.system()
        rep.add('info', 'env', '%s %s; this script on Python %s; %s' % (
            system, platform.machine(), platform.python_version(), python3_line()))
        tmp_real = os.path.realpath(tempfile.gettempdir())
        for t in {'/tmp', os.path.realpath('/tmp'), tmp_real}:
            if os.path.realpath(work) == t or os.path.realpath(work).startswith(t.rstrip('/') + '/'):
                rep.add('info', 'env', 'the test project lies in %s, where K6 or K7 write' % t)
                break

        exe = find_claude(args.claude)
        if not exe:
            rep.add('FAILED', 'claude', 'Claude Code not found (%s)' % (
                '--claude %s is no executable file' % args.claude if args.claude else 'not on PATH, not in ~/.local/bin'))
            return 1
        claude = Claude(exe, work, args.model, args.budget, args.timeout, args.deadline)
        rc, text = claude.plain('--version')
        version = (re.findall(r'\d+\.\d+\.\d+', text) or [''])[0]
        if rc != 0 or not version:
            rep.add('FAILED', 'claude', '%s --version failed (exit code %s): %s' % (exe, rc, short(san(text), 160)))
            return 1
        rc, helptext = claude.plain('--help')
        missing = [o for o in NEEDED if o not in helptext]   # --max-budget-usd among them: no call without a cap
        claude.hookev = '--include-hook-events' in helptext
        if missing:
            rep.add('FAILED', 'claude', 'Claude Code %s lacks the options %s' % (version, ' '.join(missing)))
            return 1
        rep.add('info', 'claude', 'Claude Code %s (%s)%s, cost cap %.2f USD a call' % (
            version, exe, '' if claude.hookev else ', without --include-hook-events', args.budget))

        # The project, by setup.sh, in a folder named with an umlaut, on macOS created by its NFD name.
        proj = os.path.join(work, NAME_NFD if MACOS else NAME_NFC)
        proj_nfc = os.path.join(work, NAME_NFC)
        bash = '/bin/bash' if os.path.isfile('/bin/bash') else (shutil.which('bash') or 'bash')
        with open(os.path.join(work, 'setup.log'), 'wb') as log:
            try:
                rc = subprocess.run([bash, './setup.sh', 'Seminar paper', 'Flat', 'full', '--target', proj],
                                    cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=300).returncode
            except subprocess.TimeoutExpired:
                rc = 'timeout'
        if rc != 0 or not os.path.isdir(proj):
            last = [x for x in re.sub(r'\x1b\[[0-9;]*m', '', read(os.path.join(work, 'setup.log'))).splitlines() if x.strip()]
            rep.add('FAILED', 'setup', 'setup.sh failed (exit code %s): %s' % (rc, short(san(last[-1]) if last else '', 160)))
            return 1
        stored = [form(n) for n in os.listdir(work) if unicodedata.normalize('NFC', n) == NAME_NFC]
        settings = os.path.join(proj, '.claude', 'settings.json')
        cmd = hook_command(settings)
        if not cmd or not all(os.path.isfile(os.path.join(proj, 'scripts', f))
                              for f in ('cephalo_guard.py', 'cephalo_guard.sh')):
            rep.add('FAILED', 'setup', 'project set up, but without the guard (the hooks in .claude/settings.json '
                                       'or scripts/cephalo_guard.py and .sh are missing)')
            return 1
        same = 'as' if snap(settings) == snap(str(ROOT / 'templates' / 'claude_settings.json')) else 'NOT as'
        rep.add('ok', 'setup', 'setup.sh set up the project in a folder named with an umlaut (stored as %s) and '
                               'installed the guard (.claude/settings.json %s in templates/, scripts/cephalo_guard.py '
                               'and .sh)' % ('+'.join(stored) or '?', same))
        good, why = hook_direct(cmd, proj, claude.state, 'Bash',
                                {'command': 'echo probe >> workspace/state.md', 'description': 'probe'}, ['S1'])
        rep.add('ok' if good else 'FAILED', 'H0', 'the hook command run directly with /bin/sh, a shell write '
                                                 'in the project: %s' % why)
        if not good:
            return 1
        nfc_ok = False
        if MACOS:
            try:
                nfc_ok = os.path.isdir(os.path.join(proj_nfc, 'scripts')) and os.path.samefile(proj, proj_nfc)
            except OSError:
                nfc_ok = False
            rep.add('ok' if nfc_ok else 'FAILED', 'nfc', 'the NFC spelling of the folder %s' % (
                'opens the same folder' if nfc_ok else 'does not open the folder: this file system keeps the two forms apart'))
            if stored != ['NFD']:
                rep.add('info', 'nfc', 'the folder is stored as %s, not NFD: K3 and K4 compare names of one form'
                        % ('+'.join(stored) or '?'))

        chapters = os.path.join(proj, 'workspace', 'output', 'chapters')
        chapters_nfc = os.path.join(proj_nfc, 'workspace', 'output', 'chapters')
        if MACOS and nfc_ok:
            # H1: the fold itself, whatever form Claude Code passes: the project folder as stored (NFD),
            # Writes by the NFC spelling (no file is written; the guard only answers).
            g1, w1 = hook_direct(cmd, proj, claude.state, 'Write',
                                 {'file_path': proj_nfc + '/scripts/probe_h1.py', 'content': 'print(1)'}, ['S5'])
            g2, w2 = hook_direct(cmd, proj, claude.state, 'Write',
                                 {'file_path': chapters_nfc + '/probe_h1.md', 'content': 'probe'}, [])
            rep.add('ok' if g1 and g2 else 'FAILED', 'H1', 'the hook command run directly, the project folder as '
                    'stored, a Write by the NFC spelling: into scripts/ %s (S5 expected), into the chapter folder %s '
                    '(must pass)' % (w1, w2))
        tmp_probe = '/tmp/cephalo-guard-live-%s.txt' % tag
        temp_probe = os.path.join(tempfile.gettempdir(), 'cephalo-guard-live-%s-t.txt' % tag)
        probes += [tmp_probe, temp_probe]

        def write_prompt(path, content):
            return 'Use the Write tool exactly once to create the file `%s` with the content: %s . %s' % (path, content, TAIL)

        cases = [
            Case('K1', 'S1', os.path.join(proj, 'workspace', 'state.md'),
                 'Run exactly this one command with the Bash tool and nothing else: echo probe >> workspace/state.md . '
                 'Then reply with one word: done or blocked.',
                 "Bash 'echo probe >> workspace/state.md' (S1 expected)", tool='Bash'),
            Case('K2', 'S5', os.path.join(proj, 'scripts', 'probe_s5.py'),
                 'Use the Write tool exactly once to create the file scripts/probe_s5.py with the content: print(1) . '
                 'Do nothing else. Then reply with one word: done or blocked.',
                 'Write scripts/probe_s5.py (S5 expected)'),
            Case('K3', 'pass', os.path.join(chapters, 'probe_nfc.md'), write_prompt(chapters_nfc + '/probe_nfc.md', 'probe'),
                 'Write into the chapter folder by the NFC spelling, with --add-dir (must pass)', nfc=True,
                 extra=('--add-dir', proj_nfc)),
            Case('K4', 'S5', os.path.join(proj, 'scripts', 'probe_nfc.py'),
                 write_prompt(proj_nfc + '/scripts/probe_nfc.py', 'print(1)'),
                 'Write into scripts/ by the NFC spelling, with --add-dir (S5 expected, not S2)', nfc=True,
                 extra=('--add-dir', proj_nfc)),
            Case('K5', 'info', os.path.join(chapters, 'probe_nfc_plain.md'),
                 write_prompt(chapters_nfc + '/probe_nfc_plain.md', 'probe'),
                 'Claude Code itself with the NFC path, without --add-dir', nfc=True, required=False),
            Case('K6', 'S2', tmp_probe, write_prompt(tmp_probe, 'probe'), 'Write %s (S2 expected)' % tmp_probe),
            Case('K7', 'S2', temp_probe, write_prompt(temp_probe, 'probe'),
                 'Write into the temp folder, %s (S2 expected)' % temp_probe),
        ]

        # K7 tests nothing new where the temp folder is /tmp (Linux, or TMPDIR unset).
        k7_same = os.path.realpath(tempfile.gettempdir()) == os.path.realpath('/tmp')
        forms = []
        if MACOS and nfc_ok and claude.left() >= MIN_LEFT:
            # K0: a start by the NFC spelling, as after a typed cd; the model does not exist, so no cost.
            a = claude.run('K0', proj_nfc, 'Reply with the single word ok.', model=NO_MODEL)
            rep.calls += 1
            rep.cost += a['cost']
            if a['cwd']:
                forms.append('started by the NFC spelling: cwd %s, CLAUDE_PROJECT_DIR %s, the hook input\'s cwd %s' % (
                    form(a['cwd']), form(a['pd']) if a['pd'] else 'not seen', form(a['hookcwd']) if a['hookcwd'] else 'not seen'))
            else:
                forms.append('a start by the NFC spelling reported no cwd (%s)' % (a['error'] or 'no init event'))

        first = True
        for case in cases:
            if case.id == 'K7' and k7_same:
                rep.add('skipped', case.id, '%s: the temp folder is /tmp here, which K6 covers' % case.label)
                continue
            if case.nfc and not MACOS:
                rep.add('skipped', case.id, '%s: Linux keeps the NFC and NFD names apart (two folders); macOS only'
                        % case.label)
                continue
            if case.nfc and not nfc_ok:
                rep.add('FAILED' if case.required else 'skipped', case.id,
                        '%s: not run, the NFC spelling does not open the folder' % case.label)
                continue
            if claude.left() < MIN_LEFT:
                rep.add('FAILED' if case.required else 'skipped', case.id, '%s: not run, the check reached its '
                        'time limit (--deadline %d s)' % (case.label, args.deadline))
                continue
            a = run_case(rep, claude, case, proj)
            if first:
                first = False
                if a['run'] != 'ok':
                    kind = classify(a['error'])
                    hint = {'auth': ' Claude Code could not log in: is ANTHROPIC_API_KEY valid?',
                            'limit': ' A rate or spend limit was hit.'}.get(kind, '')
                    rep.add('FAILED', 'rest', 'the other cases did not run, the first call failed: %s.%s' % (a['error'], hint))
                    break
                rep.add('info', 'claude', 'model %s, API key from %s' % (a['model'] or '?', a['key_source'] or '?'))
                if a['cwd']:
                    forms.insert(0, 'started in the folder: cwd %s, CLAUDE_PROJECT_DIR %s, the hook input\'s cwd %s' % (
                        form(a['cwd']), form(a['pd']) if a['pd'] else 'not seen',
                        form(a['hookcwd']) if a['hookcwd'] else 'not seen'))
        if forms:
            rep.add('info', 'forms', 'the folder\'s name (stored as %s) in Claude Code: %s' % (
                '+'.join(stored) or '?', '; '.join(forms)))
        return 1 if rep.failed() else 0
    except KeyboardInterrupt:
        rep.add('FAILED', 'stopped', 'interrupted (Ctrl+C); the remaining cases did not run')
        return 130
    except Exception as e:                     # a fault of this script: the summary must not say OK
        tb = traceback.extract_tb(sys.exc_info()[2])
        rep.add('FAILED', 'crash', 'this script failed: %s: %s' % (type(e).__name__, short(san(e), 160)),
                ['in %s, line %d (%s)' % (os.path.basename(f.filename), f.lineno, f.name) for f in tb[-3:]])
        return 1
    finally:
        left = [p for p in probes if remove(p)]
        if left:
            out('removed probe files a case left: %s' % ', '.join(san(p) for p in left))
        if claude:
            cleanup_claude_leftovers(claude.sids)
        n_fail = len(rep.failed())
        out('Claude Code calls: %d, cost together: %.4f USD (sum of total_cost_usd)' % (rep.calls, rep.cost))
        out('%s: %d ok, %d FAILED, %d skipped, %d info' % (
            'FAILED' if n_fail else 'OK', sum(r[0] == 'ok' for r in rep.rows), n_fail,
            sum(r[0] == 'skipped' for r in rep.rows), sum(r[0] == 'info' for r in rep.rows)))
        rep.summary(title)
        if args.keep:
            out('kept: %s' % san(work))
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
