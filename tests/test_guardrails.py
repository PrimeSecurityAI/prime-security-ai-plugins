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


def page(items, offset=0, limit=100, total=None, has_next=False):
    return dict(results=items, size=len(items), offset=offset, limit=limit,
                total=total, has_next=has_next)


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

    def test_pagination_uses_actual_page_size(self):
        pages = [page([{'id': 1}, {'id': 2}], limit=2, total=3, has_next=True),
                 page([{'id': 3}], offset=2, limit=2, total=3)]
        calls = []
        def get(path):
            calls.append(path)
            return pages.pop(0)
        self.assertEqual(len(self.api.paginate(get, '/guardrails')), 3)
        self.assertIn('offset=2', calls[1])

    def test_pagination_rejects_partial_repeated_and_inconsistent_pages(self):
        cases = [
            [page([{'id': 1}], total=2)],
            [page([], total=1, has_next=True)],
            [page([{'id': 1}], limit=1, has_next=True), page([{'id': 1}], offset=1, limit=1)],
            [page([{'id': 1}], total=2, has_next=True), page([{'id': 2}], offset=1, total=3)],
        ]
        for pages in cases:
            with self.subTest(pages=pages), self.assertRaises(self.api.PrimeError):
                self.api.paginate(lambda _: pages.pop(0), '/guardrails')

    def test_pagination_nullable_metadata_and_empty_success(self):
        pages = [page([{'id': 1}], limit=100, has_next=None),
                 page([{'id': 2}], offset=1, limit=100, has_next=None),
                 page([], offset=2, limit=100, has_next=None)]
        self.assertEqual(self.api.paginate(lambda _: pages.pop(0), '/guardrails'), [{'id': 1}, {'id': 2}])
        self.assertEqual(self.api.paginate(lambda _: page([], total=0), '/guardrails'), [])

    def test_repository_identity_and_ambiguity(self):
        normalize = self.api.repo_identity
        self.assertEqual(normalize('git@github.com:Acme/project.git'), normalize('https://github.com/Acme/project/'))
        self.assertNotEqual(normalize('https://one.example/org/repo'), normalize('https://two.example/org/repo'))
        self.assertIsNone(normalize('/local/repo'))
        repo = {'id': 1, 'repo_url': 'https://github.com/Acme/project'}
        self.assertEqual(self.api.match_repo([repo], 'git@github.com:Acme/project.git'), repo)
        self.assertIsNone(self.api.match_repo([repo], 'git@github.com:Other/project.git'))
        with self.assertRaises(self.api.PrimeError):
            self.api.match_repo([repo, dict(repo, id=2)], repo['repo_url'])

    def test_transport_never_follows_redirects(self):
        handler = self.api.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'https://other.example'))

    def test_transport_sanitizes_http_errors(self):
        opener = type('FailingOpener', (), {'open': lambda *args, **kwargs: (_ for _ in ()).throw(
            HTTPError('https://api.primesec.ai', 401, 'secret-token', {}, io.BytesIO(b'secret-token')))})()
        client = self.api.Client('https://api.primesec.ai', 'secret-token', opener=opener)
        with self.assertRaises(self.api.PrimeError) as caught:
            client.get('/guardrails')
        self.assertNotIn('secret-token', str(caught.exception))
        self.assertEqual(caught.exception.code, 'authentication_failed')

    def test_malformed_http_and_truncated_body_are_safe_errors(self):
        for error in [BadStatusLine('Bearer secret-token'), IncompleteRead(b'secret-token', 100)]:
            opener = type('FailingOpener', (), {'open': lambda *a, **kw: (_ for _ in ()).throw(error)})()
            client = self.api.Client('https://api.primesec.ai', 'secret-token', opener=opener)
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(self.api.PrimeError) as caught:
                    client.get('/guardrails')
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
                client.get('/guardrails')
            self.assertEqual(caught.exception.code, 'redirect_refused')
            self.assertEqual(paths, ['/guardrails'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_load_distinguishes_empty_policies_from_failure_and_optional_context(self):
        class FakeClient:
            def get(inner, path):
                if path.startswith('/guardrails?'):
                    return page([], total=0)
                raise self.api.PrimeError('unavailable', 'Unavailable')
        result = self.api.load_context(FakeClient(), 'https://github.com/org/repo')
        self.assertEqual(result['status'], 'loaded')
        self.assertEqual(result['guardrails'], [])
        self.assertEqual(result['repository']['status'], 'unavailable')
        with self.assertRaises(self.api.PrimeError):
            self.api.load_context(type('BadClient', (), {'get': lambda _, path: {}})(), None)

    def test_invalid_guardrail_is_not_success(self):
        client = type('BadClient', (), {'get': lambda _, path: page([{'guardrail_title': 'missing body'}])})()
        with self.assertRaises(self.api.PrimeError):
            self.api.load_context(client, None)

    def test_complete_policy_load_and_unique_repository_summary(self):
        policy = {'guardrail_title': 'Validate input', 'guardrail': 'Validate input at the boundary.'}
        responses = {
            '/guardrails?limit=100&offset=0': page([policy], total=1),
            '/code-management/repositories?limit=100&offset=0': page([
                {'id': 7, 'repo_url': 'https://github.com/org/repo.git'}], total=1),
            '/code-management/repositories/7?detailed_summary_required=true': {
                'id': 7, 'analysis': {'concise_summary': 'An API', 'detailed_summary': None}},
        }
        client = type('FakeClient', (), {'get': lambda _, path: responses[path]})()
        result = self.api.load_context(client, 'git@github.com:org/repo.git')
        self.assertEqual(result['guardrails'], [policy])
        self.assertEqual(result['repository'], {
            'status': 'loaded', 'id': 7, 'concise_summary': 'An API', 'detailed_summary': None})

    def test_failure_on_second_page_does_not_return_partial_policies(self):
        def get(path):
            if 'offset=0' in path:
                return page([{'guardrail_title': 'First', 'guardrail': 'Policy'}], total=2, has_next=True)
            raise self.api.PrimeError('network_error', 'Unavailable')
        client = type('FakeClient', (), {'get': lambda _, path: get(path)})()
        with self.assertRaises(self.api.PrimeError):
            self.api.load_context(client, None)

    def test_missing_credentials_cli_does_not_print_traceback_or_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PRIME_PAT_TOKEN='', XDG_CONFIG_HOME=directory)
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'error')
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
