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

    def test_cursor_session_start_provides_context(self):
        result = self.invoke({'hook_event_name': 'sessionStart', 'composer_mode': 'agent'})
        self.assertIn('prime-code-guardrails', json.loads(result.stdout)['additional_context'])

    def test_ordinary_prompts_do_not_add_reminders(self):
        result = self.invoke({'hook_event_name': 'UserPromptSubmit'})
        self.assertEqual(json.loads(result.stdout), {})

    def test_malformed_payload_is_advisory_and_does_not_echo_data(self):
        result = self.invoke(['private-payload'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertNotIn('private-payload', result.stdout + result.stderr)

    def test_manifests_only_register_session_reminders(self):
        for name, event in (('hooks.json', 'SessionStart'), ('codex.json', 'SessionStart'), ('cursor.json', 'sessionStart')):
            hooks = json.loads((ROOT / 'hooks' / name).read_text())['hooks']
            self.assertEqual(set(hooks), {event})

    def test_codex_manifest_registers_hooks_without_mcp(self):
        manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        self.assertEqual((manifest['hooks'], manifest['mcpServers']), ('./hooks/codex.json', {}))
        self.assertFalse((ROOT / 'plugin.json').exists())  # Codex drops all hooks for agent-plugins root manifests

    def test_marketplace_entries_match_plugin_manifests(self):
        repo = ROOT.parents[1]
        for marketplace, folder in (('.claude-plugin/marketplace.json', '.claude-plugin'), ('.agents/plugins/marketplace.json', '.codex-plugin'), ('.cursor-plugin/marketplace.json', '.cursor-plugin')):
            for entry in json.loads((repo / marketplace).read_text())['plugins']:
                with self.subTest(marketplace=marketplace, plugin=entry['name']):
                    plugin = repo / entry['source']
                    manifest = json.loads((plugin / folder / 'plugin.json').read_text())
                    version = json.loads((plugin / '.claude-plugin/plugin.json').read_text())['version']
                    self.assertEqual((manifest['name'], manifest['version'], entry.get('version', version)), (entry['name'], version, version))
                    if folder == '.cursor-plugin':
                        self.assertTrue((plugin / manifest['logo']).is_file())
