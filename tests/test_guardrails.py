import importlib.util
import io
from http.client import BadStatusLine, IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from test_developer_workflow import Boundary, context, CONTEXT_ID

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev/skills/prime-code-guardrails/scripts/prime_guardrails.py'

class GuardrailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SCRIPT.exists():
            spec = importlib.util.spec_from_file_location('prime_guardrails', SCRIPT)
            cls.api = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.api)

    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'Portable guardrails helper must exist')

    def test_credentials_precedence_and_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / 'prime-security/token'
            token.parent.mkdir()
            token.write_text('file-token\n')
            token.chmod(0o600)
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory, 'PRIME_PAT_TOKEN': ''}):
                self.assertEqual(self.api.resolve_token(), 'file-token')
                with patch.dict(os.environ, {'PRIME_PAT_TOKEN': 'env-token'}):
                    self.assertEqual(self.api.resolve_token(), 'env-token')
                if os.name == 'posix':
                    token.chmod(0o644)
                    with self.assertRaises(self.api.PrimeError):
                        self.api.resolve_token()
                    token.chmod(0o600)
                    real_token = token.with_name('real-token')
                    token.rename(real_token)
                    token.symlink_to(real_token)
                    with self.assertRaises(self.api.PrimeError):
                        self.api.resolve_token()

    def test_origin_requires_https_and_exact_custom_opt_in(self):
        for url in ['http://api.primesec.ai', 'https://user:secret@api.primesec.ai',
                    'https://api.primesec.ai?token=x', 'https://api.primesec.ai/#x',
                    'https://api.primesec.ai/path', 'https://api.primesec.ai\n']:
            with self.subTest(url=url), self.assertRaises(self.api.PrimeError):
                self.api.validate_origin(url)
        with self.assertRaises(self.api.PrimeError):
            self.api.validate_origin('https://private.example')
        self.assertEqual(self.api.validate_origin('https://private.example', 'https://private.example'),
                         'https://private.example')

    def test_repository_identity(self):
        normalize = self.api.repo_identity
        self.assertEqual(normalize('git@github.com:Acme/project.git'), normalize('https://github.com/Acme/project/'))
        self.assertEqual(normalize('https://user:password@gitlab.com/Example/Group/App.git'),
                         {'organization': 'Example/Group', 'repository': 'App', 'platform': 'gitlab'})
        self.assertEqual(normalize('ssh://git@bitbucket.org/Team/App.git'),
                         {'organization': 'Team', 'repository': 'App', 'platform': 'bitbucket'})
        self.assertEqual(normalize('https://github.com/Acme/Project')['repository'], 'Project')
        self.assertIsNone(normalize('https://user:password@private.example/org/repo'))
        self.assertIsNone(normalize('/local/repo'))

    def test_canonical_cli_paths_revisions_filters_and_default_branch(self):
        def invoke(*flags):
            boundary = Boundary()
            with patch.object(self.api, 'build_opener', return_value=boundary), \
                 patch.dict(os.environ, {'PRIME_PAT_TOKEN': 'synthetic-secret', 'PRIME_API_URL': ''}), \
                 patch.object(sys, 'argv', [str(SCRIPT)] + list(flags)), \
                 patch('sys.stdout', new_callable=io.StringIO) as stdout:
                status = self.api.main()
            return status, json.loads(stdout.getvalue()), boundary.calls
        status, result, calls = invoke('--remote', 'git@github.com:Acme/App.git', '--path', './src//api.py')
        self.assertEqual(status, 0)
        self.assertEqual(calls[-1][3], {'code_references': [{'organization': 'Acme', 'repository': 'App', 'platform': 'github', 'filename': 'src/api.py'}]})
        for path in ('/absolute', '../escape', 'src/../escape', 'C:/file', '.', 'src\\file'):
            with self.subTest(path=path):
                self.assertEqual(invoke('--remote', 'https://github.com/Acme/App', '--path', path)[1]['code'], 'invalid_scope')
        self.assertEqual(invoke('--organization', 'Acme')[1]['code'], 'invalid_scope')
        status, result, calls = invoke('context', '--organization', 'Uploaded', '--repository', 'App', '--platform', 'upload', '--commit', 'abc')
        self.assertEqual(status, 0)
        self.assertEqual(calls[-1][3]['code_references'][0], {'organization': 'Uploaded', 'repository': 'App', 'platform': 'upload', 'commit': 'abc'})
        status, result, calls = invoke('plan-list')
        self.assertEqual(status, 0)
        self.assertEqual(calls[-1][2], {'limit': ['100'], 'offset': ['0']})
        status, result, calls = invoke('pr-review-list', '--organization', 'Example/Group', '--repository', 'App', '--platform', 'gitlab', '--owner-id', 'user & name')
        self.assertEqual(status, 0)
        self.assertEqual(calls[-1][2]['owner_id'], ['user & name'])
        self.assertEqual(invoke('--remote', 'https://user:password@private.example/repo')[1]['code'], 'unsupported_remote')
        with patch('sys.stderr', new_callable=io.StringIO), patch.object(sys, 'argv', [str(SCRIPT), '--branch', 'main', '--commit', 'abc']), self.assertRaises(SystemExit):
            self.api.main()

    def test_transport_never_follows_redirects(self):
        handler = self.api.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'https://other.example'))

    def test_transport_sanitizes_http_errors(self):
        opener = type('FailingOpener', (), {'open': lambda *args, **kwargs: (_ for _ in ()).throw(
            HTTPError('https://api.primesec.ai', 401, 'secret-token', {}, io.BytesIO(b'secret-token')))})()
        client = self.api.Client('https://api.primesec.ai', 'secret-token', opener=opener)
        with self.assertRaises(self.api.PrimeError) as caught:
            client.get('/dev/guardrails')
        self.assertNotIn('secret-token', str(caught.exception))
        self.assertEqual(caught.exception.code, 'authentication_failed')

    def test_malformed_http_and_truncated_body_are_safe_errors(self):
        for error in [BadStatusLine('Bearer secret-token'), IncompleteRead(b'secret-token', 100)]:
            opener = type('FailingOpener', (), {'open': lambda *a, **kw: (_ for _ in ()).throw(error)})()
            client = self.api.Client('https://api.primesec.ai', 'secret-token', opener=opener)
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(self.api.PrimeError) as caught:
                    client.get('/dev/guardrails')
                self.assertNotIn('secret-token', str(caught.exception))

    def test_transport_response_bounds_and_invocation_deadline(self):
        for data, code in [(b'x' * (self.api.MAX_RESPONSE_BYTES + 1), 'response_too_large'),
                           (b'not JSON', 'invalid_response'), (b'[]', 'invalid_response')]:
            opener = type('Opener', (), {'open': lambda *args, **kwargs: io.BytesIO(data)})()
            client = self.api.Client('https://developer.example.invalid', 'synthetic-secret', opener=opener)
            with self.subTest(code=code), self.assertRaises(self.api.PrimeError) as caught:
                client.get('/dev/settings')
            self.assertEqual(caught.exception.code, code)
        client.deadline = 0
        with self.assertRaises(self.api.PrimeError) as caught:
            client.get('/dev/settings')
        self.assertEqual(caught.exception.code, 'timeout')

    def test_real_transport_refuses_redirect_before_sending_second_request(self):
        paths = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(inner):
                paths.append(inner.path)
                inner.send_response(302)
                inner.send_header('Location', '/redirect-target')
                inner.end_headers()
            def log_message(*args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = self.api.Client(f'http://127.0.0.1:{server.server_port}', 'synthetic-test-token')
            with self.assertRaises(self.api.PrimeError) as caught:
                client.get('/dev/guardrails')
            self.assertEqual(caught.exception.code, 'redirect_refused')
            self.assertEqual(paths, ['/dev/guardrails'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_missing_credentials_cli_does_not_print_traceback_or_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PRIME_PAT_TOKEN='', XDG_CONFIG_HOME=directory)
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'error')
        self.assertNotIn('Traceback', result.stderr)

    def test_large_output_is_recoverable_private_and_compact(self):
        result = context()
        result['policies'][0]['guardrail'] = 'x' * 50000
        result['limitations'].append('synthetic-secret')
        boundary = Boundary()
        boundary.snapshot = result
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'policies.json'
            with patch.object(self.api, 'resolve_token', return_value='synthetic-secret'), \
                 patch.object(self.api, 'build_opener', return_value=boundary), \
                 patch.dict(os.environ, {'PRIME_API_URL': '', 'XDG_CONFIG_HOME': directory}), \
                 patch.object(sys, 'argv', [str(SCRIPT), '--remote', 'https://gitlab.com/Example/Group/App', '--branch', 'feature/refunds', '--path', 'src/api.py', '--output', str(output)]), \
                 patch('sys.stdout', new_callable=io.StringIO) as stdout:
                self.assertEqual(self.api.main(), 0)
            status = json.loads(stdout.getvalue())
            self.assertEqual(status['output_path'], str(output))
            self.assertEqual(status['context_id'], CONTEXT_ID)
            self.assertLess(len(stdout.getvalue()), 1000)
            artifact = json.loads(output.read_text())
            self.assertEqual(artifact['policies'][0]['guardrail'], 'x' * 50000)
            self.assertEqual(artifact['limitations'][-1], '[REDACTED]')
            if os.name == 'posix':
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_output_never_overwrites_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.json'
            output.write_text('keep this')
            with patch.object(self.api, 'resolve_token', return_value='synthetic-secret'), \
                 patch.object(self.api, 'build_opener', return_value=Boundary()), \
                 patch.dict(os.environ, {'PRIME_API_URL': '', 'XDG_CONFIG_HOME': directory}), \
                 patch.object(sys, 'argv', [str(SCRIPT), '--remote', 'https://gitlab.com/Example/Group/App', '--branch', 'feature/refunds', '--path', 'src/api.py', '--output', str(output)]), \
                 patch('sys.stdout', new_callable=io.StringIO) as stdout:
                self.assertEqual(self.api.main(), 1)
            self.assertEqual(json.loads(stdout.getvalue())['status'], 'error')
            self.assertEqual(output.read_text(), 'keep this')

    def test_origin_approval_persists_only_the_exact_origin_without_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), \
             patch.object(self.api.Client, 'get', side_effect=AssertionError('No network allowed')), \
             patch.object(sys, 'argv', [str(SCRIPT), '--approve-origin', 'https://api.primesec.dev']), \
             patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(self.api.main(), 0)
            approved = self.api.load_approved_origins()
            self.assertEqual(self.api.validate_origin('https://api.primesec.dev', approved_origins=approved), 'https://api.primesec.dev')
            with self.assertRaises(self.api.PrimeError):
                self.api.validate_origin('https://other.primesec.dev', approved_origins=approved)

    def test_failed_load_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'failed.json'
            with patch.object(self.api, 'resolve_token', return_value='synthetic-secret'), \
                 patch.object(self.api, 'build_opener', return_value=type('FailingOpener', (), {'open': lambda *a, **kw: (_ for _ in ()).throw(OSError('Unavailable'))})()), \
                 patch.dict(os.environ, {'PRIME_API_URL': '', 'XDG_CONFIG_HOME': directory}), \
                 patch.object(sys, 'argv', [str(SCRIPT), '--remote', 'https://gitlab.com/Example/Group/App', '--branch', 'feature/refunds', '--path', 'src/api.py', '--output', str(output)]), \
                 patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(self.api.main(), 1)
            self.assertFalse(output.exists())

    def test_broken_saved_approvals_only_block_requests_that_depend_on_them(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'prime-security/approved-origins.json'
            config.parent.mkdir(mode=0o700)
            config.write_text('broken JSON')
            config.chmod(0o600)
            for origin, flags, expected in [
                ('https://api.primesec.ai', [], 0),
                ('https://api.primesec.dev', ['--allow-origin', 'https://api.primesec.dev'], 0),
                ('https://api.primesec.dev', [], 1),
            ]:
                with self.subTest(origin=origin, flags=flags), \
                     patch.dict(os.environ, {'PRIME_API_URL': origin, 'XDG_CONFIG_HOME': directory}), \
                     patch.object(self.api, 'resolve_token', return_value='synthetic-secret'), \
                     patch.object(self.api, 'build_opener', return_value=Boundary()), \
                     patch.object(sys, 'argv', [str(SCRIPT), '--remote', 'https://gitlab.com/Example/Group/App', '--branch', 'feature/refunds', '--path', 'src/api.py'] + flags), \
                     patch('sys.stdout', new_callable=io.StringIO) as stdout:
                    self.assertEqual(self.api.main(), expected)
                    if expected:
                        self.assertEqual(json.loads(stdout.getvalue())['code'], 'invalid_approval_file')

if __name__ == '__main__':
    unittest.main()
