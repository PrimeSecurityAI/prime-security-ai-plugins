import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev/skills/prime-code-guardrails/scripts/prime_guardrails.py'
ORIGIN = 'https://developer.example.invalid'
TOKEN = 'synthetic-private-credential'


def settings(guards=True, plans=True, account='account', owner='owner'):
    return dict(dev_guardrails_enabled=guards, security_plan_enabled=plans,
                effective_dev_guardrails_enabled=guards, effective_security_plan_enabled=plans,
                revision=1, caller=dict(account_id=account, user_id=owner))


def context(guards=True):
    return dict(repository_id=7, module_id=9, guardrails_included=guards, policies=[], packages=[],
                evidence=[dict(id='stored-1', kind='safeguard', source_entity_id='42', text='Stored analysis',
                               locations=[dict(path='src/api.py', start_line=4, end_line=8, commit='abc')])],
                fetched_at='2026-11-13T00:00:00Z', limitations=['Stored analysis; uncommitted code not verified.'])


def review(record):
    return dict(plan_hash=record['plan_hash'], context_hash=record['context_hash'], outcome='recorded',
                reviewer_client='codex', reviewer_model='actual-test-model', summary='Check trust boundaries.',
                findings=[dict(severity='high', explanation='Plan says to trust all input.',
                               suggested_action='Validate input.', evidence_ids=[], locations=[])],
                limitations=['Plan-only finding; stored analysis may be stale.'])


class Boundary:
    def __init__(self):
        self.calls = []
        self.controls = settings()
        self.rows = {}
        self.lose_post = False
        self.lose_put = False
        self.fail_settings = False
        self.conflict = None
        self.before_send = None
        self.empty_evidence = False

    def open(self, request, timeout):
        method, path, body = request.get_method(), urlsplit(request.full_url).path + ('?' + urlsplit(request.full_url).query if urlsplit(request.full_url).query else ''), request.data
        self.calls.append((method, path, body, request.headers))
        if path == '/dev/settings':
            if self.fail_settings:
                raise HTTPError(request.full_url, 503, TOKEN, {}, io.BytesIO(TOKEN.encode()))
            return io.BytesIO(json.dumps(self.controls).encode())
        if self.before_send:
            self.before_send(method, path, body)
        if self.conflict:
            detail, self.conflict = self.conflict, None
            raise HTTPError(request.full_url, 409, TOKEN, {}, io.BytesIO(json.dumps({'detail': detail}).encode()))
        if path == '/dev/repositories/resolve':
            return io.BytesIO(json.dumps(dict(status='resolved', repository_id=7, module_id=9)).encode())
        if path.startswith('/dev/guardrails?') or path == '/dev/context':
            return io.BytesIO(json.dumps(context()).encode())
        if path == '/dev/plans' and method == 'POST':
            payload = json.loads(body)
            key = payload['submission_id']
            self.rows.setdefault(key, dict(payload, id=11, account_id='account', owner_id='owner',
                                         status='registered', guardrails_included=self.controls['effective_dev_guardrails_enabled'],
                                         request_hash='server-request-hash', plan_hash='server-plan-hash', context_hash='server-context-hash',
                                         context_snapshot=context(self.controls['effective_dev_guardrails_enabled']), review_result=None))
            if self.empty_evidence:
                self.rows[key]['context_snapshot']['evidence'] = []
            if self.lose_post:
                self.lose_post = False
                raise OSError('Lost response ' + TOKEN)
            return io.BytesIO(json.dumps(self.rows[key]).encode())
        if path == '/dev/plans/11/review':
            row = next(iter(self.rows.values()))
            row.update(status='review_recorded', review_result=json.loads(body))
            if self.lose_put:
                self.lose_put = False
                raise OSError('Lost response ' + TOKEN)
            return io.BytesIO(json.dumps(row).encode())
        if path == '/dev/plans/11' and method == 'DELETE':
            self.rows.clear()
            return io.BytesIO(b'')
        if path == '/dev/plans/11':
            return io.BytesIO(json.dumps(next(iter(self.rows.values()))).encode())
        if path.startswith('/dev/plans?'):
            return io.BytesIO(json.dumps(dict(results=[], size=0, offset=0, limit=100, total=0, has_next=False)).encode())
        raise AssertionError('Unexpected feature route: ' + path)


class DeveloperWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('developer_helper', SCRIPT)
        cls.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.api)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.plan = self.repo / 'plan.md'
        self.plan.write_bytes(b'# Plan\r\nTrust all input.\r\n')
        self.result = self.root / 'result.json'
        self.env = patch.dict(os.environ, {'XDG_STATE_HOME': str(self.root / 'state')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.boundary = Boundary()
        self.workflow = self.api.DeveloperWorkflow(self.api.Client(ORIGIN, TOKEN, self.boundary), self.repo)
        self.payload = dict(title='Boundary plan', repository_id=7, module_id=9, client='codex', client_version='0.test',
                            session_id='session', plan_key='plan', submission_id='submission', paths=['src/api.py'], branch=None, base_sha=None)

    def register(self):
        return self.workflow.register(self.plan, self.payload)

    def receipt(self):
        return next((self.root / 'state/prime-security/developer-receipts').glob('*.json'))

    def test_every_feature_operation_uses_managed_routes_and_fresh_controls(self):
        self.workflow.resolve('https://user:password@github.com/Org/repo.git')
        resolved_body = json.loads(self.boundary.calls[-1][2])
        self.assertEqual(resolved_body, {'remote_url': 'https://github.com/org/repo'})
        self.workflow.guardrails(7, 9)
        self.workflow.context(7, 9, ['src/api.py'], 'Implement API')
        self.register()
        receipt = self.receipt()
        record = self.workflow.get(11)
        self.result.write_text(json.dumps(review(record)))
        self.workflow.complete(receipt, self.result)
        self.workflow.history()
        self.workflow.delete(11)
        self.assertTrue(all(path.startswith('/dev/') for _, path, _, _ in self.boundary.calls))
        feature_calls = [(method, path) for method, path, _, _ in self.boundary.calls if path != '/dev/settings']
        self.assertEqual(len(feature_calls), 9)
        self.assertEqual(sum(path == '/dev/settings' for _, path, _, _ in self.boundary.calls), 5)
        self.assertTrue(all(headers['User-agent'] == 'prime-security-dev/1.5.0-alpha.1' for _, _, _, headers in self.boundary.calls))

    def test_settings_failure_and_independent_controls_stop_only_security_work(self):
        for guards, plans in ((False, False), (False, True)):
            self.boundary.controls = settings(guards, plans)
            with self.assertRaises(self.api.PrimeError):
                self.workflow.guardrails(7, 9)
            self.assertEqual(self.boundary.calls[-1][1], '/dev/settings')
        self.boundary.controls = settings(False, True)
        response = self.register()
        self.assertEqual(response['plan']['guardrails_included'], False)
        self.boundary.controls = settings(True, False)
        with self.assertRaises(self.api.PrimeError):
            self.register()
        self.boundary.fail_settings = True
        with self.assertRaises(self.api.PrimeError) as error:
            self.workflow.context(7, 9, [], 'Implement')
        self.assertNotIn(TOKEN, str(error.exception))
        self.assertEqual(self.boundary.calls[-1][1], '/dev/settings')

    def test_lost_registration_restart_replays_exact_saved_bytes_with_original_identity(self):
        self.boundary.lose_post = True
        def persisted(method, path, body):
            if method == 'POST' and path == '/dev/plans':
                stored = self.api.Receipt.load(self.receipt(), self.repo)
                self.assertEqual(stored.plan_bytes, b'# Plan\r\nTrust all input.\r\n')
                self.assertEqual(stored.request_bytes, body)
                self.assertEqual(self.receipt().stat().st_mode & 0o777, 0o600)
                self.assertNotIn(TOKEN, self.receipt().read_text())
        self.boundary.before_send = persisted
        with self.assertRaises(self.api.PrimeError):
            self.register()
        receipt = self.receipt()
        self.plan.write_text('Changed after lost response')
        renewed = self.api.DeveloperWorkflow(self.api.Client(ORIGIN, 'renewed-synthetic-token', self.boundary), self.repo)
        recovered = renewed.resume(receipt)
        self.assertEqual(recovered['plan']['id'], 11)
        self.assertEqual(len(self.boundary.rows), 1)
        posts = [body for method, path, body, _ in self.boundary.calls if method == 'POST' and path == '/dev/plans']
        self.assertEqual(posts[0], posts[1])
        self.assertEqual(json.loads(posts[1])['client_version'], '0.test')
        self.assertEqual(json.loads(posts[1])['markdown'], '# Plan\r\nTrust all input.\r\n')

    def test_resume_binds_trusted_account_owner_origin_and_guidance_setting(self):
        self.register()
        receipt = self.receipt()
        for controls, origin in ((settings(account='other'), ORIGIN), (settings(owner='other'), ORIGIN),
                                 (settings(), 'https://other.example.invalid'), (settings(False, True), ORIGIN)):
            self.boundary.controls = controls
            workflow = self.api.DeveloperWorkflow(self.api.Client(origin, TOKEN, self.boundary), self.repo)
            before = len(self.boundary.calls)
            with self.subTest(controls=controls, origin=origin), self.assertRaises(self.api.PrimeError):
                workflow.resume(receipt)
            self.assertTrue(all(path == '/dev/settings' for _, path, _, _ in self.boundary.calls[before:]))

    def test_disable_during_reviewer_keeps_pending_receipt_until_explicit_resume(self):
        record = self.register()['plan']
        receipt = self.receipt()
        self.result.write_text(json.dumps(review(record)))
        self.boundary.controls = settings(True, False)
        with self.assertRaises(self.api.PrimeError):
            self.workflow.complete(receipt, self.result)
        self.assertTrue(receipt.exists())
        self.boundary.controls = settings()
        self.assertEqual(self.workflow.complete(receipt, self.result)['plan']['status'], 'review_recorded')
        self.assertEqual(list(receipt.parent.iterdir()), [])

    def test_completion_accepts_server_optional_defaults_and_policy_evidence_ids(self):
        original = self.boundary.open
        def opened(request, timeout):
            response = original(request, timeout)
            if request.get_method() == 'POST' and request.full_url.endswith('/dev/plans'):
                record = json.loads(response.getvalue())
                record['context_snapshot']['policies'] = [{'external_id': 'policy-id', 'guardrail_title': 'Input', 'guardrail': 'Validate input.'}]
                return io.BytesIO(json.dumps(record).encode())
            if request.get_method() == 'PUT':
                record = json.loads(response.getvalue())
                record['review_result']['failure_code'] = None
                for finding in record['review_result']['findings']:
                    finding.setdefault('locations', [])
                return io.BytesIO(json.dumps(record).encode())
            return response
        self.boundary.open = opened
        record = self.register()['plan']
        result = review(record)
        result['findings'][0]['evidence_ids'] = ['policy-id']
        result['findings'][0].pop('locations')
        self.result.write_text(json.dumps(result))
        self.assertEqual(self.workflow.complete(self.receipt(), self.result)['plan']['status'], 'review_recorded')

    def test_pending_completion_recovers_from_receipt_instead_of_changed_result(self):
        record = self.register()['plan']
        receipt = self.receipt()
        self.result.write_text(json.dumps(review(record)))
        self.boundary.lose_put = True
        with self.assertRaises(self.api.PrimeError):
            self.workflow.complete(receipt, self.result)
        self.result.write_text('{changed}')
        self.workflow.resume(receipt)
        puts = [body for method, _, body, _ in self.boundary.calls if method == 'PUT']
        self.assertEqual(puts[0], puts[1])
        self.assertEqual(list(receipt.parent.iterdir()), [])

    def test_three_explicit_retries_preserve_receipt_and_never_replay_automatically(self):
        self.boundary.lose_post = True
        with self.assertRaises(self.api.PrimeError):
            self.register()
        receipt = self.receipt()
        for _ in range(3):
            self.boundary.lose_post = True
            with self.assertRaises(self.api.PrimeError):
                self.workflow.resume(receipt)
        with self.assertRaises(self.api.PrimeError) as error:
            self.workflow.resume(receipt)
        self.assertEqual(error.exception.code, 'retry_limit')
        self.assertEqual(sum(path == '/dev/plans' for _, path, _, _ in self.boundary.calls), 4)
        self.workflow.abandon(receipt)
        self.assertEqual(list(receipt.parent.iterdir()), [])

    def test_conflict_refreshes_controls_and_preserves_safe_specific_reason(self):
        self.boundary.conflict = 'submission_conflict'
        with self.assertRaises(self.api.PrimeError) as error:
            self.register()
        self.assertEqual(error.exception.code, 'submission_conflict')
        self.assertEqual(self.boundary.calls[-1][1], '/dev/settings')
        self.assertTrue(self.receipt().exists())

    def test_review_validation_binds_hashes_evidence_and_stored_locations(self):
        record = self.register()['plan']
        receipt = self.receipt()
        bad_results = []
        wrong_hash = review(record)
        wrong_hash['plan_hash'] = 'wrong'
        bad_results.append(wrong_hash)
        wrong_evidence = review(record)
        wrong_evidence['findings'][0]['evidence_ids'] = ['invented']
        bad_results.append(wrong_evidence)
        wrong_location = review(record)
        wrong_location['findings'][0].update(evidence_ids=['stored-1'], locations=[{'path': 'future/file.py'}])
        bad_results.append(wrong_location)
        for result in bad_results:
            self.result.write_text(json.dumps(result))
            with self.subTest(result=result), self.assertRaises(self.api.PrimeError):
                self.workflow.complete(receipt, self.result)
        valid = review(record)
        valid['findings'][0].update(evidence_ids=['stored-1'], locations=[dict(path='src/api.py', start_line=4, end_line=8, commit='abc')])
        self.result.write_text(json.dumps(valid))
        self.assertEqual(self.workflow.complete(receipt, self.result)['plan']['id'], 11)

    def test_history_and_deletion_remain_available_when_both_controls_off(self):
        self.register()
        receipt = self.receipt()
        self.boundary.controls = settings(False, False)
        self.workflow.history()
        self.assertEqual(self.workflow.get(11)['id'], 11)
        self.workflow.delete(11)
        self.assertEqual(list(receipt.parent.iterdir()), [])

    def test_settings_failure_still_allows_authorized_deletion_of_lost_submission(self):
        self.boundary.lose_post = True
        with self.assertRaises(self.api.PrimeError):
            self.register()
        receipt = self.receipt()
        self.boundary.fail_settings = True
        self.workflow.delete(11)
        self.assertEqual(list(receipt.parent.iterdir()), [])

    def test_plan_only_review_can_record_findings_without_stored_evidence(self):
        self.boundary.controls = settings(False, True)
        self.boundary.empty_evidence = True
        record = self.register()['plan']
        receipt = self.receipt()
        self.result.write_text(json.dumps(review(record)))
        self.assertEqual(self.workflow.complete(receipt, self.result)['plan']['status'], 'review_recorded')

    def test_guardrails_off_rejects_unexpected_policies_in_registered_snapshot(self):
        self.boundary.controls = settings(False, True)
        original = self.boundary.open
        def opened(request, timeout):
            response = original(request, timeout)
            if request.full_url.endswith('/dev/plans'):
                record = json.loads(response.getvalue())
                record['context_snapshot']['policies'] = [{'guardrail_title': 'Stale', 'guardrail': 'Old policy'}]
                return io.BytesIO(json.dumps(record).encode())
            return response
        self.boundary.open = opened
        with self.assertRaises(self.api.PrimeError):
            self.register()

    def test_receipts_reject_repository_storage_public_files_symlinks_and_tampering(self):
        with patch.dict(os.environ, {'XDG_STATE_HOME': str(self.repo)}), self.assertRaises(self.api.PrimeError):
            self.register()
        self.register()
        receipt = self.receipt()
        stored = json.loads(receipt.read_text())
        stored['request_digest'] = 'modified'
        receipt.write_text(json.dumps(stored))
        with self.assertRaises(self.api.PrimeError):
            self.workflow.resume(receipt)
        receipt.chmod(0o644)
        with self.assertRaises(self.api.PrimeError):
            self.workflow.resume(receipt)
        receipt.chmod(0o600)
        linked = receipt.parent / 'linked.json'
        linked.symlink_to(receipt)
        with self.assertRaises(self.api.PrimeError):
            self.workflow.resume(linked)
        linked.unlink()
        self.workflow.abandon(receipt)
        self.assertEqual(list(receipt.parent.iterdir()), [])

    def test_credential_in_plan_is_rejected_before_receipt_or_upload_even_if_json_escaped(self):
        credential = 'synthetic"private-credential'
        self.plan.write_text('# Plan\n' + credential)
        workflow = self.api.DeveloperWorkflow(self.api.Client(ORIGIN, credential, self.boundary), self.repo)
        with self.assertRaises(self.api.PrimeError):
            workflow.register(self.plan, self.payload)
        self.assertEqual([path for _, path, _, _ in self.boundary.calls], ['/dev/settings'])

    def test_ambiguous_or_unregistered_scope_is_returned_without_guessing(self):
        original = self.boundary.open
        for state in ('ambiguous', 'unregistered'):
            def opened(request, timeout):
                if request.full_url.endswith('/dev/repositories/resolve'):
                    return io.BytesIO(json.dumps(dict(status=state, candidates=[], retry_required=True)).encode())
                return original(request, timeout)
            self.workflow.client.opener.open = opened
            self.assertEqual(self.workflow.resolve('git@github.com:Org/repo.git')['status'], state)
