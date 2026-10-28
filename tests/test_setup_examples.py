"""Execute the published shell examples with dummy tokens and isolated config."""
import os
from pathlib import Path
import re
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
