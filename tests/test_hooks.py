from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev'
SCRIPT = ROOT / 'skills/prime-developer-security/scripts/prime_hooks.py'
CONTEXT_ID = '2b0d7a4e-3f43-4c2b-9d55-0c6f8f3f9f11'
TOKEN = 'dummy-hook-token'
# The approval file lives in the account's real home directory, so tests fake the passwd entry
RUN = ("import pwd, runpy, sys, types; home = sys.argv.pop(1); "
       "pwd.getpwuid = lambda uid: types.SimpleNamespace(pw_dir=home); runpy.run_path(%r, run_name='__main__')" % str(SCRIPT))


def security_map(size=1):
    return {'context_id': CONTEXT_ID, 'connected': True, 'modules': [{'id': 1, 'name': 'payments'}],
            'threat_counts': [{'severity': 'HIGH', 'count': 2}], 'hotspots': [{'path': 'src/api', 'findings_count': 4}],
            'guardrails': [{'category': 'AUTHENTICATION', 'total': size, 'titles': ['Require MFA for admin routes ' * size] * size}],
            'unavailable_sources': [], 'truncated_sources': [], 'limitations': []}


def card(path, size=1):
    return {'path': path, 'threats_total': size + 1, 'safeguards_total': 0, 'components_total': 1, 'design_attack_vectors_total': 1,
            'threats': [{'id': 7, 'related_issue_ids': [8], 'title': 'SQL injection ' * size, 'type': 'CODE_THREAT', 'severity': 'HIGH',
                         'locations': [path + ':12'], 'suggested_fix': 'Use bound parameters'}] * size,
            'safeguards': [], 'components': [{'external_id': 'c1', 'name': 'Checkout API', 'role': 'api', 'security_controls': ['session auth']}],
            'design_attack_vectors': [{'id': 'v1', 'name': 'Order tampering', 'component_id': 'c1'}]}


class FakePrime(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append((self.path, self.headers['Authorization'], body))
        size = self.server.size
        if self.path == '/dev/security-context':
            response = security_map(size)
        else:
            response = {'cards': [card(path, size) for path in body['paths']], 'unavailable_sources': [],
                        'truncated_sources': [], 'limitations': ['Stored analysis only']}
        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class HookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certs = tempfile.TemporaryDirectory()
        cert, key = (os.path.join(cls.certs.name, name) for name in ('cert.pem', 'key.pem'))
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key, '-out', cert, '-days', '1',
                        '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'], check=True, capture_output=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), FakePrime)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.cert = cert
        cls.origin = 'https://127.0.0.1:%d' % cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.certs.cleanup()

    def setUp(self):
        self.server.requests = []
        self.server.size = 1
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.repo = self.home / 'repo'
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'remote', 'add', 'origin', 'git@gitlab.com:group/sub/repo.git'], check=True)
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / 'config'),
                    'XDG_CACHE_HOME': str(self.home / 'cache'), 'SSL_CERT_FILE': self.cert, 'PRIME_API_URL': self.origin,
                    'PRIME_PAT_TOKEN': TOKEN}

    def approve(self):
        result = subprocess.run([sys.executable, '-c', RUN, str(self.home), '--approve-origin', self.origin], env=self.env, text=True, capture_output=True)
        self.assertEqual(json.loads(result.stdout), {'status': 'approved', 'api_origin': self.origin})

    def invoke(self, payload, *args):
        result = subprocess.run([sys.executable, '-c', RUN, str(self.home), *args], input=json.dumps(payload), text=True,
                                capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_session_map_for_each_client(self):
        self.approve()
        cases = (
            (('session',), {'hook_event_name': 'SessionStart', 'session_id': 'c', 'cwd': str(self.repo), 'source': 'compact'},
             lambda output: output['hookSpecificOutput']['additionalContext']),
            (('session',), {'hook_event_name': 'sessionStart', 'conversation_id': 'u', 'session_id': 'u', 'workspace_roots': [str(self.repo)]},
             lambda output: output['additional_context']),
            (('session', '--format', 'copilot'), {'sessionId': 'p', 'cwd': str(self.repo), 'source': 'startup'},
             lambda output: output['additionalContext']),
        )
        for args, payload, context in cases:
            with self.subTest(args=args, payload=payload):
                text = context(self.invoke(payload, *args))
                for expected in (CONTEXT_ID, 'untrusted', 'HIGH 2', 'src/api (4 findings)', 'Require MFA', 'payments',
                                 'get_developer_security_files', 'get_developer_security_details'):
                    self.assertIn(expected, text)
        self.assertEqual(self.server.requests[-1], ('/dev/security-context', 'Bearer ' + TOKEN,
                                                    {'organization': 'group/sub', 'repository': 'repo', 'platform': 'gitlab'}))

    def test_file_cards_for_each_client_payload(self):
        self.approve()
        nested = self.repo / 'src/app.py'
        cases = (
            ('claude-read', ('file',), {'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'tool_input': {'file_path': str(nested)}},
             ['src/app.py']),
            ('codex', ('file',), {'hook_event_name': 'PostToolUse', 'tool_name': 'apply_patch', 'tool_input': {'command':
             '*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n*** Add File: b.py\n+z\n*** Update File: c.py\n*** Move to: d/c.py\n*** End Patch'}},
             ['src/a.py', 'b.py', 'c.py', 'd/c.py']),
            ('cursor', ('file',), {'hook_event_name': 'postToolUse', 'tool_name': 'Write', 'tool_input': {'path': 'src/app.py'}},
             ['src/app.py']),
            ('copilot', ('file', '--format', 'copilot'), {'toolName': 'view', 'toolArgs': json.dumps({'path': str(nested)})},
             ['src/app.py']),
        )
        for name, args, payload, paths in cases:
            with self.subTest(client=name):
                key = 'conversation_id' if name == 'cursor' else 'sessionId' if name == 'copilot' else 'session_id'
                output = self.invoke({**payload, key: name, 'cwd': str(self.repo)}, *args)
                text = json.dumps(output)
                self.assertIn('threat 7 HIGH CODE_THREAT', text)
                self.assertIn('Use bound parameters', text)
                self.assertEqual(self.server.requests[-1][2], {'paths': paths})
                self.assertEqual(self.server.requests[-2][0], '/dev/security-context')  # no session state yet: map first

    def test_each_file_gets_one_card_per_session(self):
        self.approve()
        session = {'hook_event_name': 'SessionStart', 'session_id': 's', 'cwd': str(self.repo)}
        self.invoke(session, 'session')
        read = {**session, 'hook_event_name': 'PostToolUse', 'tool_name': 'Read', 'tool_input': {'file_path': str(self.repo / 'a.py')}}
        self.assertIn('component c1 Checkout API', self.invoke(read, 'file')['hookSpecificOutput']['additionalContext'])
        self.assertEqual(self.invoke(read, 'file'), {})
        other = {**read, 'tool_input': {'file_path': str(self.repo / 'b.py')}}
        self.assertIn('Part of (shown earlier): Checkout API', self.invoke(other, 'file')['hookSpecificOutput']['additionalContext'])
        outside = {**read, 'tool_input': {'file_path': str(self.home / 'other.py')}}
        self.assertEqual(self.invoke(outside, 'file'), {})
        self.assertEqual([request[0] for request in self.server.requests],
                         ['/dev/security-context'] + ['/dev/security-context/%s/files' % CONTEXT_ID] * 2)

    def test_unapproved_origin_or_missing_token_falls_back_without_requests(self):
        session = {'hook_event_name': 'SessionStart', 'session_id': 's', 'cwd': str(self.repo)}
        read = {**session, 'hook_event_name': 'PostToolUse', 'tool_input': {'file_path': str(self.repo / 'a.py')}}
        project_approval = self.home / 'config/prime-security/approved-origins.json'  # XDG_CONFIG_HOME is project-controllable
        project_approval.parent.mkdir(mode=0o700, parents=True)
        project_approval.write_text(json.dumps([self.origin]))
        project_approval.chmod(0o600)
        for approve, token in ((False, TOKEN), (True, None)):
            with self.subTest(approve=approve, token=token):
                if approve:
                    self.approve()
                    del self.env['PRIME_PAT_TOKEN']
                context = self.invoke(session, 'session')['hookSpecificOutput']['additionalContext']
                self.assertIn('get_developer_security_map', context)
                self.assertEqual(self.invoke(read, 'file'), {})
        self.assertEqual(self.server.requests, [])

    def test_outputs_stay_within_client_caps(self):
        self.approve()
        self.server.size = 60
        session = {'hook_event_name': 'SessionStart', 'session_id': 's', 'cwd': str(self.repo)}
        text = self.invoke(session, 'session')['hookSpecificOutput']['additionalContext']
        self.assertLessEqual(len(text), 6000)
        self.assertIn('more lines omitted', text)
        self.assertIn('get_developer_security_details', text)
        patch = '\n'.join('*** Add File: f%d.py' % index for index in range(12))
        read = {**session, 'hook_event_name': 'PostToolUse', 'tool_input': {'command': patch}}
        text = self.invoke(read, 'file')['hookSpecificOutput']['additionalContext']
        self.assertLessEqual(len(text), 4000)
        self.assertIn('Threats (60 of 61)', text)
        self.assertIn('more lines omitted', text)
        self.assertEqual(len(self.server.requests[-1][2]['paths']), 10)

    def test_malformed_payload_is_advisory_and_does_not_echo_data(self):
        self.assertEqual(self.invoke(['private-payload'], 'session'), {})

    def test_unknown_arguments_are_advisory(self):
        self.assertEqual(self.invoke({'hook_event_name': 'SessionStart'}, 'session', '--format', 'other'), {})

    def test_manifests_register_session_and_file_hooks(self):
        for name, events, matcher in (('hooks.json', ('SessionStart', 'PostToolUse'), 'Read|Edit|Write|NotebookEdit'),
                                      ('codex.json', ('SessionStart', 'PostToolUse'), 'apply_patch'),
                                      ('cursor.json', ('sessionStart', 'postToolUse'), 'Read|Write'),
                                      ('copilot.json', ('sessionStart', 'postToolUse'), 'view|edit|create')):
            with self.subTest(manifest=name):
                hooks = json.loads((ROOT / 'hooks' / name).read_text())['hooks']
                self.assertEqual(list(hooks), list(events))
                self.assertEqual(hooks[events[1]][0]['matcher'], matcher)
                self.assertEqual((ROOT / 'hooks' / name).read_text().count('python3 -I '), 2)

    def test_codex_manifest_registers_hooks(self):
        manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        self.assertEqual(manifest['hooks'], './hooks/codex.json')
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
            'prime-security-dev/.codex-plugin/plugin.json': 'prime-codex',
            'prime-security-dev/.github/plugin/plugin.json': 'prime-copilot',
            'prime-security-dev/.cursor-plugin/plugin.json': 'prime-cursor',
        }
        for path, client_id in configs.items():
            with self.subTest(path=path):
                server = json.loads((repo / 'plugins' / path).read_text())['mcpServers']['prime']
                self.assertEqual(server.get('oauth', {}).get('clientId') or server['auth']['CLIENT_ID'], client_id)
                self.assertNotIn('headers', server)  # a static Authorization header blocks the OAuth login
        # Copilot CLI also loads a root .mcp.json, which overrides its own manifest's client ID
        self.assertEqual(list((repo / 'plugins').glob('*/.mcp.json')), [])

    def test_copilot_manifest_registers_hooks(self):
        manifest = json.loads((ROOT / '.github/plugin/plugin.json').read_text())
        self.assertEqual((manifest['skills'], manifest['hooks']), ('./skills/', './hooks/copilot.json'))
        self.assertEqual(json.loads((ROOT / 'hooks/copilot.json').read_text())['version'], 1)

    def test_copilot_hook_command_finds_the_script(self):
        command = json.loads((ROOT / 'hooks/copilot.json').read_text())['hooks']['sessionStart'][0]['bash']
        payload = json.dumps({'sessionId': 's', 'cwd': '/', 'source': 'startup'})
        for variable in ('PLUGIN_ROOT', 'COPILOT_PLUGIN_ROOT', 'CLAUDE_PLUGIN_ROOT'):
            with self.subTest(variable=variable):
                result = subprocess.run(['bash', '-c', command], input=payload, cwd='/', text=True, capture_output=True,
                                        env={'PATH': os.environ['PATH'], 'HOME': str(self.home), variable: str(ROOT)})
                self.assertIn('prime-developer-security', json.loads(result.stdout)['additionalContext'])
