import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev'
SCRIPT = ROOT / 'skills/prime-code-guardrails/scripts/prime_hooks.py'


class HookTests(unittest.TestCase):
    def invoke(self, payload):
        return subprocess.run([sys.executable, str(SCRIPT), 'reminder'],
                              input=json.dumps(payload), text=True, capture_output=True)

    def test_start_resume_and_compaction_provide_context(self):
        for source in ('startup', 'resume', 'compact'):
            with self.subTest(source=source):
                result = self.invoke({'hook_event_name': 'SessionStart', 'source': source})
                context = json.loads(result.stdout)['hookSpecificOutput']
                self.assertEqual(context['hookEventName'], 'SessionStart')
                self.assertIn('prime-code-guardrails', context['additionalContext'])

    def test_ordinary_prompts_do_not_add_reminders(self):
        result = self.invoke({'hook_event_name': 'UserPromptSubmit'})
        self.assertEqual(json.loads(result.stdout), {})

    def test_malformed_payload_is_advisory_and_does_not_echo_data(self):
        result = self.invoke(['private-payload'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertNotIn('private-payload', result.stdout + result.stderr)

    def test_manifests_only_register_session_reminders(self):
        for name in ('hooks.json', 'codex.json'):
            hooks = json.loads((ROOT / 'hooks' / name).read_text())['hooks']
            self.assertEqual(set(hooks), {'SessionStart'})
