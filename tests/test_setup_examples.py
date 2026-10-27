"""Execute the published shell examples with dummy tokens and isolated config."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ['README.md', 'plugins/prime-security-operator/README.md',
        'plugins/prime-security-operator/skills/prime/SKILL.md',
        'plugins/prime-security-dev/skills/prime-code-guardrails/references/setup.md']


def example(doc, marker):
    return next(block for block in re.findall(r'```bash\n(.*?)```', (ROOT / doc).read_text(), re.S)
                if marker in block)


class SetupExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for shell in ('bash', 'zsh'):
            if not shutil.which(shell):
                raise RuntimeError(f'{shell} is required to validate the published setup commands')

    def shells(self):
        return ('bash', 'zsh')

    def run_example(self, shell, script, directory, value=''):
        env = {**os.environ, 'XDG_CONFIG_HOME': directory, 'PRIME_PAT_TOKEN': 'stale-dummy-token',
               'PATH': directory + os.pathsep + os.environ['PATH']}
        return subprocess.run([shell, '-c', script], input=value, text=True,
                              capture_output=True, env=env, timeout=10)

    def test_invalid_pat_preserves_existing_token(self):
        for shell in self.shells():
            for doc in DOCS:
                for value in ('', '\n', ' \t \n', '\r\n', 'bad token\n', 'bad\ttoken\n',
                              'bad\rtoken\n', 'bad\x1btoken\n', 'tökén\n'):
                    with self.subTest(shell=shell, doc=doc, value=repr(value)), tempfile.TemporaryDirectory() as directory:
                        token = Path(directory) / 'prime-security/token'
                        token.parent.mkdir(); token.write_text('existing-dummy-token\n')
                        result = self.run_example(shell, example(doc, 'read -r'), directory, value)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(token.read_text(), 'existing-dummy-token\n')
                        self.assertEqual(list(token.parent.iterdir()), [token])

    def test_pat_save_is_private_and_does_not_change_parent_shell(self):
        for shell in self.shells():
            for doc in DOCS:
                for value in ('new-dummy-token\n', ' \tnew-dummy-token \t\n',
                              'new-dummy-token\r\n', ' \tnew-dummy-token \t\r\n',
                              'new-dummy-token'):
                    with self.subTest(shell=shell, doc=doc, value=repr(value)), tempfile.TemporaryDirectory() as directory:
                        script = 'umask 022\nconfig_dir=parent-value\n' + example(doc, 'read -r') + '\nprintf "PARENT:%s:%s:%s" "$(umask)" "$config_dir" "$PRIME_PAT_TOKEN"'
                        result = self.run_example(shell, script, directory, value)
                        token = Path(directory) / 'prime-security/token'
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(token.read_text(), 'new-dummy-token\n')
                        self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)
                        self.assertEqual(stat.S_IMODE(token.parent.stat().st_mode), 0o700)
                        self.assertEqual(list(token.parent.iterdir()), [token])
                        self.assertRegex(result.stdout, r'PARENT:0?022:parent-value:stale-dummy-token')
                        self.assertNotIn('new-dummy-token', result.stdout + result.stderr)

    def test_pat_examples_match(self):
        for doc in DOCS[1:]:
            self.assertEqual(example(DOCS[0], 'read -r'), example(doc, 'read -r'))

    def test_failed_pat_replace_preserves_existing_token(self):
        for shell in self.shells():
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                token = Path(directory) / 'prime-security/token'
                token.parent.mkdir(); token.write_text('existing-dummy-token\n')
                failing_mv = Path(directory) / 'mv'
                failing_mv.write_text('#!/bin/sh\nexit 1\n'); failing_mv.chmod(0o700)
                result = self.run_example(shell, example(DOCS[0], 'read -r'), directory, 'new-dummy-token\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(token.read_text(), 'existing-dummy-token\n')
                self.assertEqual(list(token.parent.iterdir()), [token])

    def test_environment_mcp_launch_preserves_arguments_and_parent(self):
        for shell in self.shells():
            for client in ('codex', 'opencode', 'cursor'):
                with self.subTest(shell=shell, client=client), tempfile.TemporaryDirectory() as directory:
                    token = Path(directory) / 'prime-security/token'; token.parent.mkdir()
                    script = (f'{client}() {{ printf "%s\\n" "$PRIME_PAT_TOKEN" "$@" > "$XDG_CONFIG_HOME/received"; }}\n'
                              + example('README.md', 'prime_mcp()')
                              + f'\nprime_mcp {client} --flag "project with spaces"\nprintf "PARENT:%s" "$PRIME_PAT_TOKEN"')
                    for value in ('first-dummy-token', 'refreshed-dummy-token'):
                        token.write_text(value + '\n')
                        result = self.run_example(shell, script, directory)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual((Path(directory) / 'received').read_text(), value + '\n--flag\nproject with spaces\n')
                        self.assertIn('PARENT:stale-dummy-token', result.stdout)
                        self.assertNotIn(value, result.stdout + result.stderr)

    def test_environment_mcp_invalid_token_blocks_launch(self):
        for shell in self.shells():
            for content in (None, '', '\n', ' \t\n', 'bad token\n'):
                with self.subTest(shell=shell, content=repr(content)), tempfile.TemporaryDirectory() as directory:
                    token = Path(directory) / 'prime-security/token'; token.parent.mkdir()
                    if content is not None: token.write_text(content)
                    script = ('codex() { touch "$XDG_CONFIG_HOME/launched"; }\n'
                              + example('README.md', 'prime_mcp()') + '\nprime_mcp codex')
                    result = self.run_example(shell, script, directory)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((Path(directory) / 'launched').exists())
                    self.assertIn('Sign in or save a PAT', result.stderr)

    def test_claude_docs_describe_file_headers_and_reconnect(self):
        for doc in ('README.md', 'plugins/prime-security-operator/README.md', 'plugins/prime-security-dev/README.md'):
            with self.subTest(doc=doc):
                text = (ROOT / doc).read_text()
                self.assertIn('headersHelper', text)
                self.assertIn('2.1.312', text)
                self.assertIn('/mcp', text)
                self.assertNotIn('PRIME_PAT_TOKEN="$prime_pat" claude', text)

    def test_claude_manual_config_requires_real_helper_and_quotes_path(self):
        for shell in self.shells():
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                helper = Path(directory) / 'installed skill/prime_mcp_headers.py'
                received = Path(directory) / 'received'
                claude = Path(directory) / 'claude'
                claude.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                                  'from pathlib import Path\n'
                                  'Path(os.environ["XDG_CONFIG_HOME"], "received").write_text(json.dumps(sys.argv[1:]))\n')
                claude.chmod(0o700)
                script = example('README.md', 'subprocess.run').replace(
                    '/absolute/path/to/prime/scripts/prime_mcp_headers.py', str(helper))
                result = self.run_example(shell, script, directory)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(received.exists())
                helper.parent.mkdir(); helper.touch()
                result = self.run_example(shell, script, directory)
                self.assertEqual(result.returncode, 0, result.stderr)
                arguments = json.loads(received.read_text())
                self.assertEqual(arguments[:5], ['mcp', 'add-json', '--scope', 'user', 'prime'])
                config = json.loads(arguments[5])
                self.assertEqual(set(config), {'type', 'url', 'headersHelper'})
                self.assertEqual(shlex.split(config['headersHelper']), ['python3', str(helper)])
