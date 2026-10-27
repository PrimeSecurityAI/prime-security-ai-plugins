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
    def shells(self):
        return [shell for shell in ('bash', 'zsh') if shutil.which(shell)]

    def run_example(self, shell, script, directory, value=''):
        env = {**os.environ, 'XDG_CONFIG_HOME': directory, 'PRIME_PAT_TOKEN': 'stale-dummy-token'}
        return subprocess.run([shell, '-c', script], input=value, text=True,
                              capture_output=True, env=env, timeout=10)

    def test_pat_cancel_preserves_existing_token(self):
        for shell in self.shells():
            for doc in DOCS:
                for value in ('', '\n'):
                    with self.subTest(shell=shell, doc=doc, value=repr(value)), tempfile.TemporaryDirectory() as directory:
                        token = Path(directory) / 'prime-security/token'
                        token.parent.mkdir(); token.write_text('existing-dummy-token\n')
                        result = self.run_example(shell, example(doc, 'read -r'), directory, value)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(token.read_text(), 'existing-dummy-token\n')

    def test_pat_save_is_private_and_does_not_change_parent_shell(self):
        for shell in self.shells():
            for doc in DOCS:
                with self.subTest(shell=shell, doc=doc), tempfile.TemporaryDirectory() as directory:
                    script = 'umask 022\nconfig_dir=parent-value\n' + example(doc, 'read -r') + '\nprintf "PARENT:%s:%s" "$(umask)" "$config_dir"'
                    result = self.run_example(shell, script, directory, 'new-dummy-token\n')
                    token = Path(directory) / 'prime-security/token'
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(token.read_text(), 'new-dummy-token\n')
                    self.assertEqual(stat.S_IMODE(token.stat().st_mode), 0o600)
                    self.assertRegex(result.stdout, r'PARENT:0?022:parent-value')
                    self.assertNotIn('new-dummy-token', result.stdout + result.stderr)

    def test_mcp_launch_reads_current_token_without_changing_parent(self):
        for shell in self.shells():
            for doc in DOCS[:2]:
                with self.subTest(shell=shell, doc=doc), tempfile.TemporaryDirectory() as directory:
                    token = Path(directory) / 'prime-security/token'; token.parent.mkdir()
                    script = 'claude() { printf "%s" "$PRIME_PAT_TOKEN" > "$XDG_CONFIG_HOME/received"; }\n' + example(doc, 'PRIME_PAT_TOKEN=') + '\nprintf "PARENT:%s" "$PRIME_PAT_TOKEN"'
                    for value in ('first-dummy-token', 'refreshed-dummy-token'):
                        token.write_text(value + '\n')
                        result = self.run_example(shell, script, directory)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual((Path(directory) / 'received').read_text(), value)
                        self.assertIn('PARENT:stale-dummy-token', result.stdout)
                        self.assertNotIn(value, result.stdout + result.stderr)

    def test_mcp_missing_or_empty_token_blocks_launch(self):
        for shell in self.shells():
            for doc in DOCS[:2]:
                for content in (None, '', '\n'):
                    with self.subTest(shell=shell, doc=doc, content=repr(content)), tempfile.TemporaryDirectory() as directory:
                        token = Path(directory) / 'prime-security/token'; token.parent.mkdir()
                        if content is not None: token.write_text(content)
                        script = 'claude() { touch "$XDG_CONFIG_HOME/launched"; }\n' + example(doc, 'PRIME_PAT_TOKEN=')
                        result = self.run_example(shell, script, directory)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertFalse((Path(directory) / 'launched').exists())
                        self.assertIn('Sign in or save a PAT', result.stderr)
