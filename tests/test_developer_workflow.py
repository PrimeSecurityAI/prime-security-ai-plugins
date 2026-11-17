import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

SCRIPT = Path(__file__).resolve().parents[1] / 'plugins/prime-security-dev/skills/prime-code-guardrails/scripts/prime_guardrails.py'
ORIGIN = 'https://developer.example.invalid'
TOKEN = 'synthetic-private-credential'
CONTEXT_ID = 'ddac2218-8962-40c2-8b19-6dd146f497f5'
REPO = dict(organization='Example/Group', repository='App', platform='gitlab')
REF = dict(REPO, branch='feature/refunds', filename='src/api.py')
EVIDENCE_REF = dict(organization='Shared', repository='Library', platform='github', commit='abc', filename='auth.py', line_number=4)
SAVED_AT = '2026-11-16T10:00:00Z'


def settings(guards=True, plans=True):
    return dict(dev_guardrails_enabled=guards, security_plan_enabled=plans,
                caller=dict(account_id='account', user_id='owner'), updated_at=None, updated_by=None)


def context(guards=True, references=None):
    return dict(context_id=CONTEXT_ID, code_references=references or [REF], guardrails_included=guards,
                policies=[dict(external_id='policy-1', guardrail_title='Ownership', guardrail='Validate account ownership.')] if guards else [],
                packages=[], evidence=[dict(id='issue-42', kind='code_issue', source_entity_id='42', text='Stored analysis',
                                           code_references=[EVIDENCE_REF], references=['https://example.invalid/evidence'],
                                           source_updated_at=None, requested_entity_id=None, safeguard=None, code_issue=None, component=None)],
                references=[], fetched_at=SAVED_AT, source_updated_at=None,
                unavailable_sources=['architecture'], truncated_sources=['knowledge_base'],
                limitations=['Stored analysis; uncommitted code not verified.'])


def review():
    return dict(outcome='recorded', reviewer_client='claude-code', reviewer_model='actual-test-model',
                summary='Check account ownership.', findings=[dict(severity='HIGH',
                explanation='Plan says "Trust all input."', suggested_action='Validate input.',
                evidence_ids=['issue-42'], code_references=[EVIDENCE_REF])],
                limitations=['Stored analysis may be stale; uncommitted code not verified.'])


class Response(io.BytesIO):
    def __init__(self, value=None, status=200):
        super().__init__(json.dumps(value).encode() if value is not None else b'')
        self.status = status

    def getcode(self):
        return self.status


class Boundary:
    def __init__(self):
        self.calls = []
        self.capabilities = {'developer_security_enabled': True}
        self.capability_error = None
        self.stable_error = None
        self.summary_error = False
        self.controls = settings()
        self.rows = {}
        self.pr_receipts = []
        self.fail_settings = False
        self.lose_post = False
        self.lose_put = False
        self.conflict = False
        self.snapshot = None
        self.saved_at = SAVED_AT

    def open(self, request, timeout):
        url = urlsplit(request.full_url)
        method, path = request.get_method(), url.path
        payload = json.loads(request.data) if request.data is not None else None
        self.calls.append((method, path, parse_qs(url.query), json.loads(request.data) if request.data is not None else None, request.headers))
        if path == '/dev/capabilities':
            if self.capability_error:
                raise HTTPError(request.full_url, self.capability_error, TOKEN, {}, io.BytesIO(TOKEN.encode()))
            return Response(self.capabilities)
        if path in ('/guardrails', '/code-management/repositories'):
            if self.stable_error:
                raise HTTPError(request.full_url, self.stable_error, TOKEN, {}, io.BytesIO(TOKEN.encode()))
            offset = int(parse_qs(url.query)['offset'][0])
            rows = ([dict(guardrail_title='Ownership', guardrail='Validate account ownership.'),
                     dict(guardrail_title='Input', guardrail='Validate incoming data.')]
                    if path == '/guardrails' else [dict(id=42, repo_url='https://gitlab.com/Example/Group/App')])
            page = rows[offset:offset + 1]
            return Response(dict(results=page, size=len(page), limit=1, offset=offset, total=len(rows), has_next=offset + len(page) < len(rows)))
        if path == '/code-management/repositories/42':
            if self.summary_error:
                raise HTTPError(request.full_url, 503, TOKEN, {}, io.BytesIO(TOKEN.encode()))
            return Response(dict(analysis=dict(concise_summary='Example application', detailed_summary='Stored repository analysis.')))
        if path == '/dev/settings':
            if self.fail_settings:
                raise HTTPError(request.full_url, 503, TOKEN, {}, io.BytesIO(TOKEN.encode()))
            return Response(self.controls)
        if self.conflict:
            self.conflict = False
            raise HTTPError(request.full_url, 409, TOKEN, {}, io.BytesIO(TOKEN.encode()))
        if path in ('/dev/guardrails', '/dev/context'):
            return Response(self.snapshot or context(references=payload['code_references']))
        if path == '/dev/plans' and method == 'POST':
            plan_id = len(self.rows) + 11
            snapshot = self.snapshot or context(self.controls['dev_guardrails_enabled'], payload['code_references'])
            self.rows[plan_id] = dict(payload, markdown=payload['markdown'].replace('\r\n', '\n').replace('\r', '\n'),
                                     id=plan_id, account_id='account', owner_id='owner', status='registered',
                                     created_at=SAVED_AT, base_commit_ref=payload.get('base_commit_ref'),
                                     guardrails_included=snapshot['guardrails_included'], context_snapshot=snapshot, review_result=None)
            if self.lose_post:
                self.lose_post = False
                raise OSError('Lost response ' + TOKEN)
            return Response(dict(id=plan_id, context_snapshot=snapshot))
        if path.endswith('/review'):
            row = self.rows[int(path.split('/')[3])]
            saved = dict(payload, findings=payload.get('findings', []), limitations=payload.get('limitations', []),
                         failure_code=payload.get('failure_code'), saved_at=self.saved_at)
            for finding in saved['findings']:
                finding.setdefault('evidence_ids', [])
                finding.setdefault('code_references', [])
                finding['code_references'] = [
                    {key: ref.get(key) for key in ('organization', 'repository', 'platform', 'branch', 'commit', 'pull_request', 'filename', 'line_number', 'end_line_number')}
                    for ref in finding['code_references']]
            row.update(status='review_' + ('recorded' if payload['outcome'] == 'recorded' else 'failed'), review_result=saved)
            if self.lose_put:
                self.lose_put = False
                raise OSError('Lost response ' + TOKEN)
            return Response(saved)
        if path.startswith('/dev/plans/'):
            plan_id = int(path.rsplit('/', 1)[1])
            if method == 'DELETE':
                del self.rows[plan_id]
                return Response(status=204)
            return Response(self.rows[plan_id])
        if path in ('/dev/plans', '/dev/pr-reviews') and method == 'GET':
            rows = list(self.rows.values()) if path == '/dev/plans' else self.pr_receipts
            return Response(dict(results=rows, size=len(rows), offset=0, limit=100, total=len(rows), has_next=False))
        if path == '/dev/pr-reviews':
            self.pr_receipts.append(dict(activity_id=5, pr_ref=payload['pr_ref'], job_id=91, user_id='owner', created_at=SAVED_AT))
            return Response(dict(job_id=91, status='PENDING'), status=202)
        if path == '/dev/contexts/' + CONTEXT_ID + '/outcomes':
            return Response(dict(activity_id=6, context_id=CONTEXT_ID, issue_ids=payload['issue_ids'], reported_at=SAVED_AT))
        raise AssertionError('Unexpected developer route: ' + path)


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
        self.boundary = Boundary()
        self.workflow = self.api.DeveloperWorkflow(self.api.Client(ORIGIN, TOKEN, self.boundary))
        self.payload = dict(title='Boundary plan', code_references=[REF], client='claude-code', client_version='0.test',
                            base_commit_ref=dict(REPO, commit='base'))

    def register(self):
        return self.workflow.register(self.plan, self.payload)

    def save(self, result):
        self.result.write_text(json.dumps(result))
        self.result.chmod(0o600)
        return self.workflow.save_review(11, self.result)

    def test_direct_canonical_journey_retains_snapshot_and_saved_advisory(self):
        controls = self.workflow.settings()
        self.assertEqual(controls.response['caller'], dict(account_id='account', user_id='owner'))
        guidance = self.workflow.guardrails([REF])
        self.assertEqual(guidance['policies'][0]['guardrail'], 'Validate account ownership.')
        self.assertEqual(self.workflow.context([REF], 'Refund & authorization')['context_id'], CONTEXT_ID)
        registered = self.register()
        self.assertEqual(set(registered), {'id', 'context_snapshot'})
        self.assertEqual(registered['context_snapshot']['evidence'][0]['code_references'], [EVIDENCE_REF])
        stored = self.workflow.get(registered['id'])
        self.assertEqual(stored['markdown'], '# Plan\nTrust all input.\n')
        saved = self.save(review())
        self.assertEqual(saved['saved_at'], SAVED_AT)
        self.assertEqual(self.workflow.get(11)['review_result'], saved)
        self.assertEqual(self.workflow.history(owner_id='owner', status='review_recorded', title='A & B', **REPO)['total'], 1)
        self.assertEqual(self.boundary.calls[-1][2]['title'], ['A & B'])
        self.assertEqual(self.workflow.pr_review(REPO, 42), {'job_id': 91, 'status': 'PENDING'})
        self.assertEqual(self.workflow.pr_history(**REPO)['results'][0]['pr_ref'], dict(REPO, pull_request=42))
        self.assertEqual(self.workflow.context_outcome(CONTEXT_ID, [42])['issue_ids'], [42])
        self.assertEqual(self.workflow.delete(11), {'status': 'deleted', 'id': 11})
        calls = {(method, path): body for method, path, _, body, _ in self.boundary.calls}
        self.assertEqual(calls['POST', '/dev/guardrails'], {'code_references': [REF]})
        self.assertEqual(calls['POST', '/dev/context'], {'code_references': [REF], 'intent': 'Refund & authorization'})
        self.assertEqual(calls['POST', '/dev/plans'], dict(self.payload, markdown='# Plan\r\nTrust all input.\r\n'))
        self.assertEqual(calls['PUT', '/dev/plans/11/review'], review())
        self.assertEqual(calls['POST', '/dev/pr-reviews'], {'pr_ref': dict(REPO, pull_request=42)})
        self.assertEqual(calls['POST', '/dev/contexts/' + CONTEXT_ID + '/outcomes'], {'issue_ids': [42]})
        self.assertTrue(all(path.startswith('/dev/') and headers['User-agent'] == 'prime-security-dev/1.5.0-alpha.3'
                            for _, path, _, _, headers in self.boundary.calls))

    def test_controls_are_independent_and_history_bypasses_settings(self):
        self.boundary.controls = settings(False, True)
        with self.assertRaises(self.api.PrimeError):
            self.workflow.guardrails([REF])
        registered = self.register()
        self.assertEqual(registered['context_snapshot']['policies'], [])
        self.boundary.controls = settings(True, True)
        self.assertEqual(self.save(dict(outcome='recorded', reviewer_client='claude-code', reviewer_model='unknown (host does not expose model)', summary='Plan-only advisory.'))['findings'], [])
        self.boundary.controls = settings(True, False)
        with self.assertRaises(self.api.PrimeError):
            self.save(review())
        self.boundary.controls = settings(False, False)
        self.assertEqual(self.workflow.pr_review(REPO, 42)['job_id'], 91)
        self.boundary.fail_settings = True
        for operation in (lambda: self.workflow.guardrails([REF]), self.register, lambda: self.workflow.pr_review(REPO, 42)):
            with self.assertRaises(self.api.PrimeError) as caught:
                operation()
            self.assertNotIn(TOKEN, str(caught.exception))
        self.assertEqual(self.workflow.history()['total'], 1)
        self.assertEqual(self.workflow.get(11)['id'], 11)
        self.assertEqual(self.workflow.pr_history()['total'], 1)
        self.assertEqual(self.workflow.delete(11)['status'], 'deleted')

    def test_optional_review_arrays_policy_citations_and_truthful_failure(self):
        self.register()
        result = dict(outcome='recorded', reviewer_client='claude-code', reviewer_model='actual-test-model', summary='Advisory.')
        self.assertEqual(self.save(result)['limitations'], [])
        result['findings'] = [dict(severity='MEDIUM', explanation='Plan says "Trust all input."', suggested_action='Validate.', evidence_ids=['policy-1'])]
        self.assertEqual(self.save(result)['findings'][0]['code_references'], [])
        result.update(outcome='failed', failure_code='reviewer_unavailable', findings=[], limitations=['Separate host agent unavailable.'])
        self.assertEqual(self.save(result)['failure_code'], 'reviewer_unavailable')

    def test_invalid_review_citations_types_and_timestamp_stop_confirmation(self):
        self.register()
        cases = []
        for field, value in [('severity', 'high'), ('evidence_ids', ['invented']), ('code_references', [dict(REF, commit='invented')])]:
            result = review()
            result['findings'][0][field] = value
            cases.append(result)
        for field, value in [('reviewer_model', ''), ('failure_code', 'reviewer_failed'), ('unexpected', 'field'), ('summary', TOKEN)]:
            result = review()
            result[field] = value
            cases.append(result)
        for result in cases:
            with self.subTest(result=result), self.assertRaises(self.api.PrimeError):
                self.save(result)
        self.boundary.saved_at = '2026-11-16T10:00:00'
        with self.assertRaises(self.api.PrimeError):
            self.save(review())
        self.boundary.saved_at = SAVED_AT
        self.boundary.rows[11]['review_result'] = None
        self.assertEqual(self.save(review())['saved_at'], SAVED_AT)

    def test_lost_write_is_sent_once_and_history_supports_explicit_recovery(self):
        self.boundary.lose_post = True
        with self.assertRaises(self.api.PrimeError):
            self.register()
        self.assertEqual(self.workflow.history()['results'][0]['id'], 11)
        self.assertEqual(self.workflow.get(11)['markdown'], '# Plan\nTrust all input.\n')
        self.assertEqual(sum(method == 'POST' and path == '/dev/plans' for method, path, _, _, _ in self.boundary.calls), 1)
        self.boundary.lose_put = True
        with self.assertRaises(self.api.PrimeError):
            self.save(review())
        self.assertEqual(self.workflow.get(11)['review_result']['saved_at'], SAVED_AT)
        self.assertEqual(sum(method == 'PUT' for method, _, _, _, _ in self.boundary.calls), 1)
        self.assertEqual(self.register()['id'], 12)

    def test_conflict_refreshes_controls_without_repeating_operation_or_raw_detail(self):
        self.boundary.conflict = True
        with self.assertRaises(self.api.PrimeError) as caught:
            self.register()
        self.assertEqual(caught.exception.code, 'conflict')
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertEqual(self.boundary.calls[-1][1], '/dev/settings')
        self.assertEqual(sum(method == 'POST' for method, _, _, _, _ in self.boundary.calls), 1)

    def test_context_scope_policy_privacy_and_size_checks(self):
        for snapshot in (dict(context(), code_references=[dict(REF, repository='Other')]),
                         dict(context(False), policies=context()['policies']),
                         dict(context(), limitations=['x' * (1024 * 1024)])):
            self.boundary.snapshot = snapshot
            with self.subTest(snapshot_keys=list(snapshot)), self.assertRaises(self.api.PrimeError):
                self.workflow.guardrails([REF])
        self.boundary.snapshot = dict(context(), code_references=[dict(REF, commit=None, pull_request=None, line_number=None, end_line_number=None)])
        self.assertEqual(self.workflow.guardrails([REF])['context_id'], CONTEXT_ID)
        self.plan.write_text('# Plan\n' + TOKEN)
        with self.assertRaises(self.api.PrimeError):
            self.register()
        escaped_credential = 'synthetic\"private-credential'
        self.plan.write_text('# Plan\n' + escaped_credential)
        workflow = self.api.DeveloperWorkflow(self.api.Client(ORIGIN, escaped_credential, self.boundary))
        with self.assertRaises(self.api.PrimeError):
            workflow.register(self.plan, self.payload)
        self.plan.write_text('é' * (128 * 1024))
        with self.assertRaises(self.api.PrimeError):
            self.register()

    def test_review_file_privacy_and_outcome_input_validation(self):
        self.register()
        self.result.write_text(json.dumps(review()))
        self.result.chmod(0o644)
        with self.assertRaises(self.api.PrimeError):
            self.workflow.save_review(11, self.result)
        self.result.chmod(0o600)
        link = self.root / 'linked.json'
        link.symlink_to(self.result)
        with self.assertRaises(self.api.PrimeError):
            self.workflow.save_review(11, link)
        for identifier, issues in [('invalid', [42]), (CONTEXT_ID, [42, 42]), (CONTEXT_ID, [0]), (CONTEXT_ID, list(range(1, 22)))]:
            with self.subTest(identifier=identifier, issues=issues), self.assertRaises(self.api.PrimeError):
                self.workflow.context_outcome(identifier, issues)
        self.assertEqual(self.workflow.context_outcome(CONTEXT_ID, [42])['context_id'], CONTEXT_ID)


if __name__ == '__main__':
    unittest.main()
