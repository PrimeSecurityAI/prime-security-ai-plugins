import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [ROOT / 'plugins' / plugin / 'scripts/prime_mcp_headers.py' for plugin in ('prime-security-dev', 'prime-security-operator')]


class McpHeaderTests(unittest.TestCase):
    def run_helper(self, script, directory):
        return subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                              env={**os.environ, 'XDG_CONFIG_HOME': directory, 'PRIME_PAT_TOKEN': 'stale-secret'})

    def test_refresh_reads_file_even_with_stale_environment(self):
        for script in SCRIPTS:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as directory:
                token = Path(directory) / 'prime-security/token'
                token.parent.mkdir()
                for value in ['first-token', 'renewed-token']:
                    token.write_text(value + '\n'); token.chmod(0o600)
                    result = self.run_helper(script, directory)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout), {'Authorization': 'Bearer ' + value})
                    self.assertEqual(result.stderr, '')

    def test_missing_file_keeps_environment_header(self):
        for script in SCRIPTS:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as directory:
                result = self.run_helper(script, directory)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {})

    def test_unsafe_or_invalid_file_blocks_environment_fallback(self):
        for script in SCRIPTS:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as directory:
                token = Path(directory) / 'prime-security/token'; token.parent.mkdir()
                target = Path(directory) / 'other'; target.write_text('private-token'); target.chmod(0o600)
                for value in ['', '   ', 'bad secret', '\xff', 'valid-secret', 'symlink']:
                    token.unlink(missing_ok=True)
                    if value == 'symlink':
                        token.symlink_to(target)
                    else:
                        token.write_bytes(value.encode('latin-1')); token.chmod(0o644 if value == 'valid-secret' else 0o600)
                    result = self.run_helper(script, directory)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(json.loads(result.stdout), {'Authorization': ''})
                    self.assertNotIn('secret', result.stderr)
                    self.assertIn('Prime token', result.stderr)

    def test_both_plugins_include_identical_helpers_and_environment_fallback(self):
        self.assertEqual(SCRIPTS[0].read_bytes(), SCRIPTS[1].read_bytes())
        for script in SCRIPTS:
            plugin = script.parents[1]
            config = json.loads((plugin / '.mcp.json').read_text())['mcpServers']['prime']
            self.assertEqual(config['headers'], {'Authorization': 'Bearer ${PRIME_PAT_TOKEN:-}'})
            self.assertIn('${CLAUDE_PLUGIN_ROOT}/' + str(script.relative_to(plugin)), config['headersHelper'])
