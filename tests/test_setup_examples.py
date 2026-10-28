"""Execute the published shell examples with dummy tokens and isolated config."""
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ['README.md', 'plugins/prime-security-operator/README.md',
        'plugins/prime-security-operator/skills/prime/SKILL.md',
        'plugins/prime-security-dev/skills/prime-code-guardrails/references/setup.md']
SHELLS = ('bash', 'zsh')


def example(doc):
    return next(block for block in re.findall(r'```bash\n(.*?)```', (ROOT / doc).read_text(), re.S)
                if 'read -r' in block)


EXAMPLE = example(DOCS[0])


class SetupExamplesTests(unittest.TestCase):
    def run_example(self, shell, script, directory, value=''):
        env = {**os.environ, 'XDG_CONFIG_HOME': directory, 'PRIME_PAT_TOKEN': 'stale-dummy-token',
               'PATH': directory + os.pathsep + os.environ['PATH']}
        return subprocess.run([shell, '-c', script], input=value, text=True,
                              capture_output=True, env=env, timeout=10)

    def existing_token(self, directory):
        token = Path(directory) / 'prime-security/token'
        token.parent.mkdir(); token.write_text('existing-dummy-token\n')
        return token

    def assert_only_token(self, token, content):
        self.assertEqual(token.read_text(), content)
        self.assertEqual(list(token.parent.iterdir()), [token])

    def test_pat_examples_match(self):
        for doc in DOCS[1:]:
            self.assertEqual(EXAMPLE, example(doc))

    def test_invalid_pat_preserves_existing_token(self):
        for shell in SHELLS:
            for value in ('', '\n', ' \t \n', '\r\n', 'bad token\n', 'bad\ttoken\n',
                          'bad\rtoken\n', 'bad\x1btoken\n', 'tökén\n'):
                with self.subTest(shell=shell, value=repr(value)), tempfile.TemporaryDirectory() as directory:
                    token = self.existing_token(directory)
                    result = self.run_example(shell, EXAMPLE, directory, value)
                    self.assertNotEqual(result.returncode, 0)
                    self.assert_only_token(token, 'existing-dummy-token\n')

    def test_pat_save_is_private_and_does_not_change_parent_shell(self):
        script = 'umask 022\nconfig_dir=parent-value\n' + EXAMPLE + '\nprintf "PARENT:%s:%s:%s" "$(umask)" "$config_dir" "$PRIME_PAT_TOKEN"'
        for shell in SHELLS:
            for value in ('new-dummy-token\n', ' \tnew-dummy-token \t\n',
                          'new-dummy-token\r\n', ' \tnew-dummy-token \t\r\n', 'new-dummy-token'):
                with self.subTest(shell=shell, value=repr(value)), tempfile.TemporaryDirectory() as directory:
                    result = self.run_example(shell, script, directory, value)
                    token = Path(directory) / 'prime-security/token'
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assert_only_token(token, 'new-dummy-token\n')
                    self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)
                    self.assertEqual(stat.S_IMODE(token.parent.stat().st_mode), 0o700)
                    self.assertRegex(result.stdout, r'PARENT:0?022:parent-value:stale-dummy-token')
                    self.assertNotIn('new-dummy-token', result.stdout + result.stderr)

    def test_failed_pat_replace_preserves_existing_token(self):
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                token = self.existing_token(directory)
                failing_mv = Path(directory) / 'mv'
                failing_mv.write_text('#!/bin/sh\nexit 1\n'); failing_mv.chmod(0o700)
                result = self.run_example(shell, EXAMPLE, directory, 'new-dummy-token\n')
                self.assertNotEqual(result.returncode, 0)
                self.assert_only_token(token, 'existing-dummy-token\n')
