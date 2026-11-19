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
from test_developer_workflow import Boundary, Response, context, settings, CONTEXT_ID

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
                         self.api.RepositoryScope('Example/Group', 'App', 'gitlab'))
        self.assertEqual(normalize('ssh://git@bitbucket.org/Team/App.git'),
                         self.api.RepositoryScope('Team', 'App', 'bitbucket'))
        self.assertEqual(normalize('https://github.com/Acme/Project').repository, 'Project')
        self.assertIsNone(normalize('https://user:password@private.example/org/repo'))
        self.assertIsNone(normalize('/local/repo'))
        baseline = self.api.baseline_repo_identity
        self.assertEqual(baseline('git@github.com:Acme/App.git'), baseline('https://github.com/acme/app'))
        self.assertNotEqual(baseline('https://private.example/Org/App'), baseline('https://private.example/org/app'))
        self.assertNotEqual(baseline('ssh://private.example:2222/Org/App'), baseline('ssh://private.example/Org/App'))
        self.assertIsNone(normalize('ssh://github.com:2222/Org/App'))
        self.assertIsNone(normalize('https://github.com/Org/A%70p'))
        repos = [dict(id=1, repo_url='git@github.com:Acme/App.git'), dict(id=2, repo_url='https://github.com/acme/app')]
        with self.assertRaises(self.api.PrimeError) as caught:
            self.api.match_repo(repos, 'https://github.com/Acme/App')
        self.assertEqual(caught.exception.code, 'ambiguous_repository')

    def invoke(self, *flags, boundary=None):
        boundary = boundary or Boundary()
        with patch.object(self.api, 'build_opener', return_value=boundary), \
             patch.dict(os.environ, {'PRIME_PAT_TOKEN': 'synthetic-secret', 'PRIME_API_URL': ''}), \
             patch.object(sys, 'argv', [str(SCRIPT)] + list(flags)), \
             patch('sys.stdout', new_callable=io.StringIO) as stdout:
            status = self.api.main()
        return status, json.loads(stdout.getvalue()), boundary.calls

    def test_canonical_cli_paths_revisions_filters_and_default_branch(self):
        invoke = self.invoke
        status, result, calls = invoke('--remote', 'git@github.com:Acme/App.git', '--path', './src//api.py')
        self.assertEqual(status, 0)
        self.assertEqual([call[1] for call in calls], ['/dev/capabilities', '/dev/settings', '/dev/guardrails'])
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
        self.assertEqual(invoke('context', '--remote', 'https://user:password@private.example/repo')[1]['code'], 'unsupported_remote')
        with patch('sys.stderr', new_callable=io.StringIO), patch.object(sys, 'argv', [str(SCRIPT), '--branch', 'main', '--commit', 'abc']), self.assertRaises(SystemExit):
            self.api.main()

    def test_capability_selection_loads_complete_stable_policies_without_canonical_scope(self):
        for remote, expected in [(None, 'no_supported_remote'), ('https://private.example/org/repo', 'not_registered'),
                                 ('git@gitlab.com:Example/Group/App.git', 'loaded')]:
            boundary = Boundary()
            boundary.capabilities = {'developer_security_enabled': False}
            flags = ['guidance', '--repo', '/nonexistent/unversioned-directory']
            if remote:
                flags += ['--remote', remote]
            status, result, calls = self.invoke(*flags, boundary=boundary)
            self.assertEqual(status, 0)
            self.assertEqual([policy['guardrail'] for policy in result['guardrails']],
                             ['Validate account ownership.', 'Validate incoming data.'])
            self.assertEqual(result['repository']['status'], expected)
            self.assertEqual(calls[0][1], '/dev/capabilities')
            self.assertEqual([call[2]['offset'] for call in calls if call[1] == '/guardrails'], [['0'], ['1']])
            self.assertTrue(all(method == 'GET' for method, _, _, _, _ in calls))
            if expected == 'loaded':
                self.assertEqual(result['repository']['concise_summary'], 'Example application')
        boundary.summary_error = True
        self.assertEqual(self.invoke('guardrails', '--remote', 'https://gitlab.com/Example/Group/App', boundary=boundary)[1]['repository'],
                         {'status': 'unavailable', 'reason': 'unavailable'})

    def test_baseline_pagination_completeness_and_policy_provenance(self):
        class Pages(Boundary):
            def open(inner, request, timeout):
                if '/guardrails?' not in request.full_url:
                    return super().open(request, timeout)
                response = inner.pages.pop(0)
                if isinstance(response, Exception):
                    raise response
                return Response(response)
        policy = dict(guardrail_title='Same title', guardrail='Full policy', policy_id='policy-a',
                      policy_name='Source A', category='security', framework='Framework', secret='filtered')
        def page(rows, offset=0, total=None, more=None):
            return dict(results=rows, size=len(rows), limit=100, offset=offset, total=total, has_next=more)
        for pages, expected in [([page([], more=False)], []),
                                ([page([policy]), page([], offset=1)], [policy]),
                                ([page([policy, dict(policy, policy_id='policy-b', policy_name='Source B')], more=False)],
                                 [policy, dict(policy, policy_id='policy-b', policy_name='Source B')])]:
            boundary = Pages()
            boundary.capabilities = dict(developer_security_enabled=False)
            boundary.pages = pages
            status, result, _ = self.invoke('--repo', '/no/git', boundary=boundary)
            self.assertEqual(status, 0)
            self.assertEqual(result['guardrails'], [{key: value for key, value in item.items() if key != 'secret'} for item in expected])
        for pages, code in [
            ([page([policy], total=2, more=True), HTTPError('https://example.invalid', 503, '', {}, io.BytesIO())], 'unavailable'),
            ([page([policy], total=2, more=True), page([policy], offset=1, total=2, more=False)], 'repeated_page'),
            ([page([policy], total=2, more=False)], 'incomplete_pagination'),
            ([page([policy], total=2, more=True), page([], offset=1, total=3, more=False)], 'changed_pagination'),
            ([page([dict(policy, guardrail='')], more=False)], 'invalid_guardrail'),
        ]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                boundary = Pages()
                boundary.capabilities = dict(developer_security_enabled=False)
                boundary.pages = pages
                status, result, _ = self.invoke('--repo', '/no/git', '--output', str(Path(directory) / 'policies.json'), boundary=boundary)
                self.assertEqual((status, result['code']), (1, code))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_disabled_advanced_commands_stop_before_scope_or_plan_inputs(self):
        for command in ('settings', 'context', 'plan-register', 'plan-save-review', 'plan-list', 'plan-get',
                        'plan-delete', 'pr-review', 'pr-review-list', 'context-outcome'):
            boundary = Boundary()
            boundary.capabilities = {'developer_security_enabled': False}
            with self.subTest(command=command):
                status, result, calls = self.invoke(command, '--repo', '/no/git', boundary=boundary)
                self.assertEqual((status, result['code']), (1, 'feature_disabled'))
                self.assertEqual([call[1] for call in calls], ['/dev/capabilities'])

    def test_capabilities_are_exact_booleans_and_errors_never_select_stable(self):
        for capabilities in ({}, {'developer_security_enabled': None}, {'developer_security_enabled': 0},
                             {'developer_security_enabled': 'false'}):
            boundary = Boundary()
            boundary.capabilities = capabilities
            with self.subTest(capabilities=capabilities):
                status, result, calls = self.invoke('plan-register', boundary=boundary)
                self.assertEqual((status, result['code']), (1, 'invalid_capabilities'))
                self.assertEqual([call[1] for call in calls], ['/dev/capabilities'])
        for code in (401, 403, 503):
            boundary = Boundary()
            boundary.capability_error = code
            with self.subTest(code=code):
                status, result, calls = self.invoke(boundary=boundary)
                self.assertEqual(status, 1)
                self.assertEqual(result['status'], 'error')
                self.assertEqual([call[1] for call in calls], ['/dev/capabilities'])
        for enabled in (False, True):
            boundary = Boundary()
            boundary.capabilities = {'developer_security_enabled': enabled}
            self.assertEqual(self.invoke('capabilities', boundary=boundary)[:2], (0, boundary.capabilities))
        boundary.capabilities = {'developer_security_enabled': False}
        boundary.stable_error = 503
        boundary.calls.clear()
        self.assertEqual(self.invoke(boundary=boundary)[1]['code'], 'unavailable')
        self.assertEqual([call[1] for call in boundary.calls], ['/dev/capabilities', '/guardrails'])
        boundary = Boundary()
        boundary.fail_settings = True
        status, result, calls = self.invoke('--remote', 'https://github.com/Acme/App', boundary=boundary)
        self.assertEqual((status, result['code']), (1, 'unavailable'))
        self.assertEqual([call[1] for call in calls], ['/dev/capabilities', '/dev/settings'])

    def test_transport_allows_only_reviewed_baseline_read_routes(self):
        client = self.api.Client('https://developer.example.invalid', 'synthetic-secret', Boundary())
        for method, route in [('POST', '/guardrails'), ('GET', '/guardrails/1'), ('GET', '/code-management/repositories/42/other'),
                              ('GET', '/unreviewed'), ('GET', '//other.example/guardrails')]:
            with self.subTest(method=method, route=route), self.assertRaises(self.api.PrimeError) as caught:
                client.request(method, route)
            self.assertEqual(caught.exception.code, 'invalid_path')

    def test_transport_never_follows_redirects(self):
        handler = self.api.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'https://other.example'))

    def test_transport_sanitizes_http_errors(self):
        for status, code in ((401, 'authentication_failed'), (502, 'http_error'), (503, 'unavailable'), (504, 'http_error')):
            for method, path, idempotent, warning in (('GET', '/dev/settings', False, False),
                                                     ('POST', '/dev/plans', False, True),
                                                     ('POST', '/dev/guardrails', True, False)):
                with self.subTest(status=status, method=method, path=path):
                    opener = type('FailingOpener', (), {'open': lambda *args, **kwargs: (_ for _ in ()).throw(
                        HTTPError('https://api.primesec.ai', status, 'secret-token', {}, io.BytesIO(b'secret-token')))})()
                    client = self.api.Client('https://api.primesec.ai', 'secret-token', opener=opener)
                    with self.assertRaises(self.api.PrimeError) as caught:
                        client.request(method, path, idempotent=idempotent)
                    self.assertNotIn('secret-token', str(caught.exception))
                    self.assertEqual(caught.exception.code, code)
                    self.assertEqual('Inspect history before explicitly repeating a write.' in str(caught.exception), warning)

    def test_malformed_http_and_truncated_body_are_safe_errors(self):
        for error in [BadStatusLine('Bearer secret-token'), IncompleteRead(b'secret-token', 100)]:
            opener = type('FailingOpener', (), {'open': lambda *a, **kw: (_ for _ in ()).throw(error)})()
            client = self.api.Client('https://api.primesec.ai', 'secret-token', opener=opener)
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(self.api.PrimeError) as caught:
                    client.get('/dev/guardrails')
                self.assertNotIn('secret-token', str(caught.exception))
                self.assertNotIn('history', str(caught.exception))

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
        self.assertNotIn('history', str(caught.exception))

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
            self.assertEqual(status['guardrail_count'], 1)
            self.assertLess(len(stdout.getvalue()), 1000)
            artifact = json.loads(output.read_text())
            self.assertEqual(artifact['policies'][0]['guardrail'], 'x' * 50000)
            self.assertEqual(artifact['limitations'][-1], '[REDACTED]')
            if os.name == 'posix':
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_output_rejected_before_any_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'repo'
            repo.mkdir()
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subdir = repo / 'src'
            subdir.mkdir()
            existing = root / 'existing.json'
            existing.write_text('keep this')
            dangling = root / 'dangling.json'
            dangling.symlink_to(root / 'missing')
            unsafe = root / 'public'
            unsafe.mkdir(mode=0o755)
            for output, code in [(existing, 'file_write_failed'), (dangling, 'file_write_failed'),
                                 (unsafe / 'out.json', 'unsafe_artifact_directory'),
                                 (repo / '.private/out.json', 'unsafe_artifact_directory')]:
                for command in ('plan-register', 'plan-save-review', 'plan-delete', 'pr-review'):
                    with self.subTest(output=output, command=command):
                        boundary = Boundary()
                        status, result, calls = self.invoke(command, '--repo', str(subdir), '--output', str(output), boundary=boundary)
                        self.assertEqual((status, result['code'], calls), (1, code, []))
            self.assertEqual(existing.read_text(), 'keep this')
            marker = repo / '.git'
            marker.rename(repo / '.git-storage')
            marker.write_text('gitdir: .git-storage')
            self.assertEqual(self.invoke('pr-review', '--repo', str(subdir), '--output', str(repo / '.private/out.json'))[1]['code'],
                             'unsafe_artifact_directory')

    def test_late_output_failure_keeps_confirmed_write_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / 'plan.md'
            plan.write_text('# Original plan')
            for command, flags, key, identifier in [
                ('plan-register', ['--plan-file', str(plan), '--title', 'Plan', '--client', 'test', '--client-version', '1'], 'id', 11),
                ('pr-review', ['--pull-request', '42'], 'job_id', 91),
            ]:
                with self.subTest(command=command), patch.object(self.api.os, 'link', side_effect=OSError('Full disk')):
                    boundary = Boundary()
                    status, result, calls = self.invoke(command, '--remote', 'https://github.com/Acme/App',
                                                       '--output', str(root / 'output.json'), *flags, boundary=boundary)
                    self.assertEqual((status, result['code'], result[key]), (1, 'file_write_failed', identifier))
                    self.assertIn('history', result['message'])
                    self.assertNotIn('no request was sent', result['message'])
                    self.assertEqual(sum(method == 'POST' for method, _, _, _, _ in calls), 1)
            boundary = Boundary()
            status, result, calls = self.invoke('plan-register', '--remote', 'https://github.com/Acme/App',
                '--branch', 'feature', '--path', 'src', '--base-commit', 'abc', '--plan-file', str(plan),
                '--title', 'Plan', '--client', 'test', '--client-version', '1', '--output', str(root / 'plan.json'), boundary=boundary)
            self.assertEqual((status, result['id'], result['guardrail_count']), (0, 11, 1))
            self.assertEqual(calls[-1][3]['base_commit_ref'], dict(organization='Acme', repository='App', platform='github', commit='abc'))
            boundary.capabilities = dict(developer_security_enabled=False)
            status, result, _ = self.invoke('--repo', '/no/git', '--output', str(root / 'account.json'), boundary=boundary)
            self.assertEqual((status, result['guardrail_count'], result['repository_status']), (0, 2, 'no_supported_remote'))

    def test_unconnected_repository_receipt_reports_not_connected(self):
        boundary = Boundary()
        boundary.snapshot = dict(context(), evidence=[], unavailable_sources=['repository'])
        with tempfile.TemporaryDirectory() as directory:
            status, result, _ = self.invoke('--remote', 'https://gitlab.com/Example/Group/App', '--branch', 'feature/refunds',
                                            '--path', 'src/api.py', '--output', str(Path(directory) / 'policies.json'),
                                            boundary=boundary)
        self.assertEqual((status, result['repository_status']), (0, 'not_connected'))

    def test_created_plan_snapshot_failure_reports_known_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / 'plan.md'
            plan.write_text('# Plan')
            class MissingSnapshot(Boundary):
                def open(inner, request, timeout):
                    response = super().open(request, timeout)
                    if request.get_method() == 'POST' and request.full_url.endswith('/dev/plans'):
                        return Response(dict(id=11))
                    return response
            status, result, _ = self.invoke('plan-register', '--remote', 'https://github.com/Acme/App',
                '--plan-file', str(plan), '--title', 'Plan', '--client', 'test', '--client-version', '1', boundary=MissingSnapshot())
            self.assertEqual((status, result['code'], result['id']), (1, 'invalid_plan_snapshot', 11))
            for snapshot in (dict(context(), code_references=[dict(organization='Other')]),
                             dict(context(), policies=[dict(guardrail_title='', guardrail='text')])):
                boundary = Boundary()
                boundary.snapshot = snapshot
                status, result, calls = self.invoke('plan-register', '--remote', 'https://github.com/Acme/App',
                    '--plan-file', str(plan), '--title', 'Plan', '--client', 'test', '--client-version', '1', boundary=boundary)
                self.assertEqual((status, result['code'], result['id']), (1, 'invalid_plan_snapshot', 11))
                self.assertIn('plan-get --plan-id 11', result['message'])
                self.assertIn('history', result['message'])
                self.assertEqual(list(boundary.rows), [11])

    def test_enabled_account_guidance_requires_fresh_controls_and_valid_selectors(self):
        for remote in ('https://private.example/org/repo', ''):
            boundary = Boundary()
            status, result, calls = self.invoke('guidance', '--repo', '/no/git', '--remote', remote, boundary=boundary)
            self.assertEqual(status, 0)
            self.assertEqual(len(result['guardrails']), 2)
            self.assertIn('account-wide', result['limitations'][0].lower())
            self.assertEqual([call[1] for call in calls][:3], ['/dev/capabilities', '/dev/settings', '/guardrails'])
            for flags, expected in [(['--path', '../bad'], 'invalid_scope'), (['--branch', ' '], 'invalid_scope'),
                                    (['--organization', 'Acme'], 'invalid_scope')]:
                self.assertEqual(self.invoke('--repo', '/no/git', '--remote', remote, *flags)[1]['code'], expected)
            for command in ('context', 'plan-register'):
                self.assertEqual(self.invoke(command, '--repo', '/no/git', '--remote', remote)[1]['code'], 'unsupported_remote')
            boundary = Boundary()
            boundary.controls = settings(False, True)
            self.assertEqual(self.invoke('--repo', '/no/git', '--remote', remote, boundary=boundary)[1]['code'], 'feature_disabled')
            boundary.fail_settings = True
            self.assertEqual(self.invoke('--repo', '/no/git', '--remote', remote, boundary=boundary)[1]['code'], 'unavailable')
            boundary.fail_settings = False
            boundary.controls = dict(settings(), caller={})
            self.assertEqual(self.invoke('--repo', '/no/git', '--remote', remote, boundary=boundary)[1]['code'], 'invalid_settings')
        for code in (401, 404, 503):
            class ManagedError(Boundary):
                def open(inner, request, timeout):
                    if request.full_url.endswith('/dev/guardrails'):
                        inner.calls.append((request.get_method(), '/dev/guardrails', {}, None, {}))
                        raise HTTPError(request.full_url, code, '', {}, io.BytesIO())
                    return super().open(request, timeout)
            boundary = ManagedError()
            status, result, calls = self.invoke('--remote', 'https://github.com/Acme/App', boundary=boundary)
            self.assertEqual(status, 1)
            self.assertEqual([call[1] for call in calls], ['/dev/capabilities', '/dev/settings', '/dev/guardrails'])

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
