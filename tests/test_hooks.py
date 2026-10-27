import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev'


class HookTests(unittest.TestCase):
    def run_hook(self, script, payload, directory):
        return subprocess.run(['bash', str(ROOT / 'scripts' / script)],
                              input=json.dumps(payload), text=True, capture_output=True,
                              env=dict(os.environ, XDG_STATE_HOME=directory,
                                       CLAUDE_PLUGIN_DATA=directory, CLAUDE_PROJECT_DIR=directory))

    def test_reminder_does_not_claim_success_or_disappear_on_next_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {'session_id': 'example', 'hook_event_name': 'UserPromptSubmit'}
            for _ in range(2):
                result = self.run_hook('guardrails_reminder.sh', payload, directory)
                self.assertEqual(result.returncode, 0)
                self.assertIn('prime-code-guardrails', json.loads(result.stdout)['hookSpecificOutput']['additionalContext'])
            self.assertFalse(list(Path(directory).rglob('guardrails-loaded-*')))

    def test_tracking_handles_notebooks_and_session_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {'session_id': '../escape', 'cwd': directory,
                       'tool_name': 'NotebookEdit', 'tool_input': {'notebook_path': 'example.ipynb'}}
            result = self.run_hook('track_touched_files.sh', payload, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            logs = list(Path(directory).rglob('*.jsonl'))
            self.assertEqual(len(logs), 1)
            record = json.loads(logs[0].read_text())
            self.assertEqual(record['paths'], [str(Path(directory) / 'example.ipynb')])
            self.assertNotIn('escape', logs[0].name)
            if os.name == 'posix':
                self.assertEqual(logs[0].stat().st_mode & 0o777, 0o600)

    def test_tracking_codex_patch_records_moves_and_deletes(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = {'session_id': 'codex', 'cwd': directory, 'tool_name': 'apply_patch',
                       'tool_input': {'command': '*** Begin Patch\n*** Update File: old.py\n*** Move to: new.py\n@@\n-x\n+y\n*** Delete File: gone.py\n*** End Patch'}}
            result = self.run_hook('track_touched_files.sh', payload, directory)
            self.assertEqual(result.returncode, 0)
            logs = list(Path(directory).rglob('*.jsonl'))
            self.assertEqual(len(logs), 1)
            self.assertEqual(len(json.loads(logs[0].read_text())['paths']), 3)

    def test_malformed_payload_is_advisory_and_does_not_echo_data(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_hook('guardrails_reminder.sh', ['private-payload'], directory)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), {})
            self.assertNotIn('private-payload', result.stdout + result.stderr)

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlink protection')
    def test_tracking_refuses_symlinked_state_directory(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            (Path(directory) / 'prime-security').symlink_to(outside, target_is_directory=True)
            result = self.run_hook('track_touched_files.sh', {
                'session_id': 'test', 'cwd': directory, 'tool_input': {'file_path': 'a.py'}}, directory)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(list(Path(outside).iterdir()))


if __name__ == '__main__':
    unittest.main()
