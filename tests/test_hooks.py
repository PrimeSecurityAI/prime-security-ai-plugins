import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev'
SCRIPT = ROOT / 'skills/prime-code-guardrails/scripts/prime_hooks.py'


class HookTests(unittest.TestCase):
    def invoke(self, payload, *args):
        return subprocess.run([sys.executable, str(SCRIPT), 'reminder', *args],
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
        for name, event in (('hooks.json', 'SessionStart'), ('codex.json', 'SessionStart'), ('cursor.json', 'sessionStart'),
                            ('copilot.json', 'sessionStart')):
            hooks = json.loads((ROOT / 'hooks' / name).read_text())['hooks']
            self.assertEqual(set(hooks), {event})

    def test_codex_manifest_registers_hooks_without_mcp(self):
        manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        self.assertEqual((manifest['hooks'], manifest['mcpServers']), ('./hooks/codex.json', {}))
        self.assertFalse((ROOT / 'plugin.json').exists())  # Codex drops all hooks for agent-plugins root manifests

    def test_marketplace_entries_match_plugin_manifests(self):
        repo = ROOT.parents[1]
        for marketplace, folder in (('.claude-plugin/marketplace.json', '.claude-plugin'), ('.claude-plugin/marketplace.json', '.github/plugin'), ('.agents/plugins/marketplace.json', '.codex-plugin'), ('.cursor-plugin/marketplace.json', '.cursor-plugin')):
            for entry in json.loads((repo / marketplace).read_text())['plugins']:
                with self.subTest(marketplace=marketplace, plugin=entry['name']):
                    plugin = repo / entry['source']
                    manifest = json.loads((plugin / folder / 'plugin.json').read_text())
                    version = json.loads((plugin / '.claude-plugin/plugin.json').read_text())['version']
                    self.assertEqual((manifest['name'], manifest['version'], entry.get('version', version)), (entry['name'], version, version))
                    if folder == '.cursor-plugin':
                        self.assertTrue((plugin / manifest['logo']).is_file())

    def test_plugin_mcp_servers_log_in_with_their_client_id(self):
        repo = ROOT.parents[1]
        configs = {
            'prime-security-operator/.claude-plugin/plugin.json': 'prime-claude-code',
            'prime-security-operator/.codex-plugin/plugin.json': 'prime-codex',
            'prime-security-operator/.github/plugin/plugin.json': 'prime-copilot',
            'prime-security-operator/.cursor-plugin/plugin.json': 'prime-cursor',
            'prime-security-dev/.claude-plugin/plugin.json': 'prime-claude-code',
            'prime-security-dev/.cursor-plugin/plugin.json': 'prime-cursor',
        }
        for path, client_id in configs.items():
            with self.subTest(path=path):
                server = json.loads((repo / 'plugins' / path).read_text())['mcpServers']['prime']
                self.assertEqual(server.get('oauth', {}).get('clientId') or server['auth']['CLIENT_ID'], client_id)
                self.assertNotIn('headers', server)  # a static Authorization header blocks the OAuth login
        # Copilot CLI also loads a root .mcp.json, which overrides its own manifest's client ID
        self.assertEqual(list((repo / 'plugins').glob('*/.mcp.json')), [])

    def test_copilot_session_start_gets_top_level_context(self):
        for source in ('startup', 'resume', 'new'):
            with self.subTest(source=source):
                result = self.invoke({'sessionId': 's', 'timestamp': 1, 'cwd': '/tmp', 'source': source},
                                     '--format', 'copilot')
                output = json.loads(result.stdout)
                self.assertEqual(set(output), {'additionalContext'})
                self.assertIn('prime-code-guardrails', output['additionalContext'])

    def test_unknown_arguments_are_advisory(self):
        result = self.invoke({'hook_event_name': 'SessionStart'}, '--format', 'other')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {})

    def test_copilot_manifest_registers_hooks_without_mcp(self):
        manifest = json.loads((ROOT / '.github/plugin/plugin.json').read_text())
        self.assertEqual((manifest['skills'], manifest['hooks'], manifest['mcpServers']),
                         ('./skills/', './hooks/copilot.json', {}))
        self.assertEqual(json.loads((ROOT / 'hooks/copilot.json').read_text())['version'], 1)

    def test_copilot_hook_command_finds_the_script(self):
        command = json.loads((ROOT / 'hooks/copilot.json').read_text())['hooks']['sessionStart'][0]['bash']
        payload = json.dumps({'sessionId': 's', 'source': 'startup'})
        cases = [({variable: str(ROOT)}, '/') for variable in ('PLUGIN_ROOT', 'COPILOT_PLUGIN_ROOT', 'CLAUDE_PLUGIN_ROOT')]
        for extra_env, cwd in cases + [({}, str(ROOT))]:
            with self.subTest(env=extra_env, cwd=cwd):
                result = subprocess.run(['bash', '-c', command], input=payload, cwd=cwd, text=True,
                                        capture_output=True, env={'PATH': os.environ['PATH'], **extra_env})
                self.assertIn('prime-code-guardrails', json.loads(result.stdout)['additionalContext'])
