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
        self.assertNotEqual(normalize('https://one.example/org/repo'), normalize('https://two.example/org/repo'))
        self.assertIsNone(normalize('/local/repo'))

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
        result = {'status': 'loaded', 'context': {'policies': [{'guardrail': 'x' * 50000}]}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'policies.json'
            with patch.object(self.api, 'resolve_token', return_value='synthetic-secret'), \
                 patch.object(self.api, 'load_context', return_value=result), \
                 patch.dict(os.environ, {'PRIME_API_URL': '', 'XDG_CONFIG_HOME': directory}), \
                 patch.object(sys, 'argv', [str(SCRIPT), '--output', str(output)]), \
                 patch('sys.stdout', new_callable=io.StringIO) as stdout:
                self.assertEqual(self.api.main(), 0)
            status = json.loads(stdout.getvalue())
            self.assertEqual(status['output_path'], str(output))
            self.assertLess(len(stdout.getvalue()), 1000)
            self.assertEqual(json.loads(output.read_text())['context']['policies'][0]['guardrail'], 'x' * 50000)
            if os.name == 'posix':
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_output_never_overwrites_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.json'
            output.write_text('keep this')
            with patch.object(self.api, 'resolve_token', return_value='synthetic-secret'), \
                 patch.object(self.api, 'load_context', return_value={'status': 'loaded', 'guardrails': [], 'repository': {}}), \
                 patch.dict(os.environ, {'PRIME_API_URL': '', 'XDG_CONFIG_HOME': directory}), \
                 patch.object(sys, 'argv', [str(SCRIPT), '--output', str(output)]), \
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
                 patch.object(self.api, 'load_context', side_effect=self.api.PrimeError('network_error', 'Unavailable')), \
                 patch.dict(os.environ, {'PRIME_API_URL': '', 'XDG_CONFIG_HOME': directory}), \
                 patch.object(sys, 'argv', [str(SCRIPT), '--output', str(output)]), \
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
                     patch.object(self.api, 'load_context', return_value={'status': 'loaded', 'guardrails': [], 'repository': {}}), \
                     patch.object(sys, 'argv', [str(SCRIPT)] + flags), \
                     patch('sys.stdout', new_callable=io.StringIO) as stdout:
                    self.assertEqual(self.api.main(), expected)
                    if expected:
                        self.assertEqual(json.loads(stdout.getvalue())['code'], 'invalid_approval_file')

if __name__ == '__main__':
    unittest.main()
