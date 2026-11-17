#!/usr/bin/env python3
"""Prime guardrails and managed developer workflows. Python 3.9+, standard library only."""

import argparse
from dataclasses import asdict, dataclass
from typing import Optional
from datetime import datetime, timezone
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import time
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_ORIGIN = 'https://api.primesec.ai'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 1000
RELEASE_VERSION = '1.5.0-alpha.3'
MAX_PLAN_BYTES = 256 * 1024
PLATFORMS = ('github', 'gitlab', 'bitbucket', 'upload')
REFERENCE_FIELDS = ('organization', 'repository', 'platform', 'branch', 'commit', 'pull_request', 'filename', 'line_number', 'end_line_number')


class PrimeError(Exception):
    """Only static, credential-free messages cross the CLI boundary."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.result_ids = {}


def validate_origin(value, allowed_origin=None, approved_origins=()):
    try:
        url = urlsplit(value)
        valid = (url.scheme == 'https' and url.hostname and not url.username
                 and not url.password and not url.query and not url.fragment
                 and url.path in ('', '/') and not re.search(r'[\s\\]', value))
        port = url.port
    except ValueError:
        valid = False
    if not valid:
        raise PrimeError('invalid_origin', 'PRIME_API_URL must be an HTTPS origin without credentials, path, query, or fragment.')
    host = url.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    origin = 'https://' + host + (f':{port}' if port and port != 443 else '')
    if origin != DEFAULT_ORIGIN and allowed_origin != origin and origin not in approved_origins:
        raise PrimeError('origin_not_approved', 'Custom API origin requires user approval and --allow-origin with that exact origin.')
    return origin


def approval_file():
    root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return root / 'prime-security/approved-origins.json'


def load_approved_origins():
    try:
        fd = os.open(approval_file(), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
                raise ValueError('Unsafe approval file')
            origins = json.loads(stream.read(65537))
        if not isinstance(origins, list) or not all(isinstance(item, str) for item in origins):
            raise ValueError('Invalid approval list')
        return [validate_origin(origin, origin) for origin in origins]
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        raise PrimeError('invalid_approval_file', 'Cannot read the private approved-origins.json file; check ownership, permissions, and JSON format.') from None


def approve_origin(value):
    origin = validate_origin(value, value.rstrip('/'))
    origins = load_approved_origins()
    path = approval_file()
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise OSError('Unsafe configuration directory')
    except OSError:
        raise PrimeError('invalid_approval_file', 'The Prime configuration directory must be private and owned by the current user.') from None
    durable_write(path, json_bytes(sorted(set(origins + [origin]))), replace=True)
    return {'status': 'approved', 'api_origin': origin}


def resolve_token():
    token = os.environ.get('PRIME_PAT_TOKEN', '')
    if not token:
        root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
        path = root / 'prime-security/token'
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'r', encoding='utf-8') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise PrimeError('unsafe_token_file', 'The Prime token file must be a regular file.')
                if os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                    raise PrimeError('unsafe_token_file', 'Restrict the Prime token file to its owner (chmod 600).')
                token = stream.read(16385).removesuffix('\n').removesuffix('\r')
        except FileNotFoundError:
            raise PrimeError('missing_credentials', 'Configure PRIME_PAT_TOKEN or the private Prime token file in your terminal; never paste a PAT into chat.') from None
        except (OSError, UnicodeError):
            raise PrimeError('unreadable_token_file', 'Cannot securely read the Prime token file.') from None
    if not token or len(token) > 16384 or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise PrimeError('invalid_credentials', 'The configured PAT is empty or contains invalid characters.')
    return token


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, origin, token, opener=None):
        self.origin = origin
        self.token = token
        self.opener = opener or build_opener(NoRedirect())
        self.deadline = time.monotonic() + 120

    def request(self, method, path, payload=None):
        baseline_read = method == 'GET' and re.fullmatch(
            r'/(?:guardrails|code-management/repositories)\?limit=100&offset=[0-9]+|'
            r'/code-management/repositories/[0-9]+\?detailed_summary_required=true', path)
        if (not path.startswith('/dev/') and not baseline_read) or re.search(r'[\\\s#]', path):
            raise PrimeError('invalid_path', 'Prime requests require a reviewed developer route or baseline read route.')
        uncertain_write = ' Inspect history before explicitly repeating a write.' if method != 'GET' and path not in ('/dev/guardrails', '/dev/context') else ''
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise PrimeError('timeout', 'Prime request budget exceeded.' + uncertain_write)
        body = payload if isinstance(payload, bytes) else (json_bytes(payload) if payload is not None else None)
        request = Request(self.origin + path, data=body, method=method, headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json',
            'Content-Type': 'application/json', 'User-Agent': 'prime-security-dev/' + RELEASE_VERSION,
        })
        try:
            with self.opener.open(request, timeout=min(30, remaining)) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if method == 'DELETE' and response.getcode() != 204:
                    raise PrimeError('invalid_response', 'Deletion was not confirmed with HTTP 204; inspect history before repeating it.')
        except HTTPError as error:
            status = error.code
            error.close()
            messages = {
                401: ('authentication_failed', 'Renew the credential in your terminal; an environment PAT overrides the private token file.' + uncertain_write),
                403: ('permission_denied', 'The credential lacks permission; request the required access before explicit recovery.'),
                404: ('not_found', 'The requested developer record is absent or inaccessible to this caller.'),
                409: ('conflict', 'Developer request paused; check fresh settings before explicitly attempting new security work.'),
                422: ('invalid_input', 'Prime rejected the input; check the reviewed developer contract.'),
                429: ('rate_limited', 'Prime rate limit reached; retry explicitly later.'),
                503: ('unavailable', 'Developer settings or context unavailable; ordinary coding can continue. Retry security work explicitly later.'),
            }
            code, message = messages.get(status, ('http_error', 'Prime request failed; check connectivity and the reviewed contract.'))
            if 300 <= status < 400:
                code, message = 'redirect_refused', 'Prime returned a redirect; credentials were not forwarded.'
            raise PrimeError(code, message) from None
        except (OSError, URLError, HTTPException, ValueError):
            raise PrimeError('network_error', 'Prime request failed; check connectivity, TLS, and the configured API origin.' + uncertain_write) from None
        if len(data) > MAX_RESPONSE_BYTES:
            raise PrimeError('response_too_large', 'Prime response exceeded the supported size; no partial context was accepted.')
        if method == 'DELETE' and not data:
            return None
        try:
            result = json.loads(data)
        except (ValueError, UnicodeError):
            raise PrimeError('invalid_response', 'Prime returned invalid JSON; no partial context was accepted.') from None
        if not isinstance(result, dict):
            raise PrimeError('invalid_response', 'Prime returned an unexpected response shape; check the reviewed contract.')
        return result

    def get(self, path):
        return self.request('GET', path)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


@dataclass(frozen=True)
class Settings:
    guardrails: bool
    plans: bool
    response: dict

    @classmethod
    def read(cls, client):
        data = client.request('GET', '/dev/settings')
        caller = data.get('caller')
        if (not isinstance(caller, dict) or any(not isinstance(caller.get(key), str) or not caller[key] for key in ('account_id', 'user_id'))
                or any(type(data.get(key)) is not bool for key in ('dev_guardrails_enabled', 'security_plan_enabled'))):
            raise PrimeError('invalid_settings', 'Current controls and trusted caller could not be read; continue ordinary coding and retry security work explicitly.')
        return cls(data['dev_guardrails_enabled'], data['security_plan_enabled'], data)

    def require(self, operation):
        enabled = self.plans if operation == 'plan' else self.guardrails if operation == 'guidance' else self.guardrails or self.plans
        if not enabled:
            raise PrimeError('feature_disabled', 'This security feature is disabled. Discard reusable guidance when guardrails are off; ordinary coding and history/deletion remain available.')


def private_directory(path, repo):
    try:
        root = Path(repo).resolve()
        root = next((parent for parent in (root, *root.parents) if (parent / '.git').exists()), root)
        if path.resolve().is_relative_to(root):
            raise OSError('Repository artifact')
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise OSError('Unsafe directory')
    except OSError:
        raise PrimeError('unsafe_artifact_directory', 'Developer artifacts require a private owner-only directory outside the repository.') from None
    return path


def read_bytes(path, limit, private=False):
    if os.name != 'posix':
        raise PrimeError('unsupported_platform', 'Private developer artifacts currently require macOS or Linux.')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (private and os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
                raise OSError('Unsafe file')
            value = stream.read(limit + 1)
        if len(value) > limit:
            raise OSError('Oversize file')
        return value
    except OSError:
        raise PrimeError('invalid_artifact', 'Cannot securely read the complete regular artifact; check size, ownership and private artifact permissions.') from None


def durable_write(path, value, replace=False):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        if os.name == 'posix':
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except OSError:
        raise PrimeError('file_write_failed', 'Cannot durably publish the private artifact.') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def reference_key(reference):
    return tuple(reference.get(key) for key in REFERENCE_FIELDS)


def aware_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, TypeError, AttributeError):
        return False


class DeveloperWorkflow:
    def __init__(self, client):
        self.client = client

    def settings(self):
        return Settings.read(self.client)

    def request(self, method, path, payload=None):
        try:
            return self.client.request(method, path, payload)
        except PrimeError as error:
            if error.code == 'conflict':
                try:
                    controls = self.settings()
                    error.args = (str(error) + ' Current guidance: ' + str(controls.guardrails).lower()
                                  + '; plans: ' + str(controls.plans).lower() + '.',)
                except PrimeError:
                    pass
            raise

    def guardrails(self, code_references):
        self.settings().require('guidance')
        return self.validate_context(self.request('POST', '/dev/guardrails', {'code_references': code_references}), code_references, True)

    def context(self, code_references, intent=''):
        if not isinstance(intent, str) or len(intent) > 500:
            raise PrimeError('invalid_input', 'Context intent is limited to 500 characters.')
        self.settings().require('guidance')
        return self.validate_context(self.request('POST', '/dev/context', {'code_references': code_references, 'intent': intent}), code_references, True)

    def validate_context(self, context, code_references, guards=None):
        try:
            UUID(context['context_id'])
            references = context['code_references']
            included = context['guardrails_included']
            policies, evidence = context['policies'], context['evidence']
            valid = (type(included) is bool and (guards is None or included is guards)
                     and len(json_bytes(context)) <= 1024 * 1024
                     and isinstance(references, list) and all(isinstance(ref, dict) for ref in references)
                     and [reference_key(ref) for ref in references] == [reference_key(ref) for ref in code_references]
                     and isinstance(policies, list) and isinstance(evidence, list)
                     and (included or not policies) and aware_timestamp(context['fetched_at'])
                     and all(isinstance(context.get(key, []), list) for key in
                             ('packages', 'references', 'unavailable_sources', 'truncated_sources', 'limitations'))
                     and all(isinstance(policy, dict) and all(isinstance(policy.get(key), str) and policy[key].strip()
                             for key in ('guardrail_title', 'guardrail')) for policy in policies)
                     and all(isinstance(item, dict) and isinstance(item.get('id'), str) and item['id']
                             and isinstance(item.get('code_references', []), list)
                             and all(isinstance(ref, dict) for ref in item.get('code_references', [])) for item in evidence))
            if not valid:
                raise ValueError('Invalid context')
        except (KeyError, ValueError, TypeError, AttributeError):
            raise PrimeError('invalid_context', 'Context scope, coverage or complete policy text is invalid; no partial context was accepted.') from None
        return context

    def bounded_payload(self, payload):
        body = json_bytes(payload)
        if len(body) > MAX_PLAN_BYTES or json.dumps(self.client.token, ensure_ascii=False)[1:-1].encode() in body:
            raise PrimeError('invalid_payload', 'Plan/review requests must fit 256 KiB and contain no configured credential.')
        return body

    def register(self, plan_file, payload):
        self.settings().require('plan')
        try:
            markdown = read_bytes(plan_file, MAX_PLAN_BYTES).decode('utf-8')
        except UnicodeError:
            raise PrimeError('invalid_plan', 'The plan must be complete UTF-8 Markdown.') from None
        if not markdown.strip():
            raise PrimeError('invalid_plan', 'The plan must be nonempty UTF-8 Markdown.')
        body = self.bounded_payload(dict(payload, markdown=markdown))
        result = self.request('POST', '/dev/plans', body)
        if type(result.get('id')) is not int or result['id'] <= 0:
            raise PrimeError('invalid_plan_response', 'Registration was not confirmed; inspect plan history before explicitly registering again.')
        try:
            self.validate_context(result.get('context_snapshot'), payload['code_references'])
        except PrimeError:
            error = PrimeError('invalid_plan_snapshot', f"Plan {result['id']} was created, but its snapshot is invalid. Use plan-get --plan-id {result['id']} and inspect plan history before any new registration.")
            error.result_ids = {'id': result['id']}
            raise error from None
        return result

    def get(self, plan_id):
        result = self.request('GET', '/dev/plans/' + str(positive_id(plan_id)))
        if (result.get('id') != plan_id or not isinstance(result.get('markdown'), str)
                or not isinstance(result.get('code_references'), list) or not result['code_references']
                or not isinstance(result.get('context_snapshot'), dict)):
            raise PrimeError('invalid_plan_response', 'The stored plan response is invalid; no reviewer should use it.')
        self.validate_context(result['context_snapshot'], result['code_references'])
        if result.get('review_result') is not None:
            self.validate_review(result['review_result'], result['context_snapshot'], saved=True)
        return result

    def validate_review(self, result, snapshot, saved=False):
        try:
            allowed_fields = {'outcome', 'reviewer_client', 'reviewer_model', 'summary', 'findings', 'limitations', 'failure_code'}
            if saved:
                allowed_fields.add('saved_at')
            valid = (isinstance(result, dict) and not set(result) - allowed_fields
                     and result.get('outcome') in ('recorded', 'failed')
                     and all(isinstance(result.get(key), str) and result[key].strip()
                             for key in ('reviewer_client', 'reviewer_model', 'summary'))
                     and isinstance(result.get('findings', []), list) and isinstance(result.get('limitations', []), list)
                     and all(isinstance(item, str) for item in result.get('limitations', [])))
            if not valid or saved and not aware_timestamp(result.get('saved_at')):
                raise ValueError('Invalid review')
            normalized = dict(result, findings=result.get('findings', []), limitations=result.get('limitations', []), failure_code=result.get('failure_code'))
            if (result['outcome'] == 'failed' and result.get('failure_code') not in ('reviewer_unavailable', 'reviewer_failed', 'review_cancelled')
                    or result['outcome'] == 'recorded' and result.get('failure_code') is not None):
                raise ValueError('Invalid outcome')
            evidence = {item['id']: item for item in snapshot.get('evidence', [])}
            policy_ids = {str(item['external_id']) for item in snapshot.get('policies', []) if item.get('external_id') is not None}
            normalized['findings'] = []
            for finding in result.get('findings', []):
                if (not isinstance(finding, dict) or set(finding) - {'severity', 'explanation', 'suggested_action', 'evidence_ids', 'code_references'}
                        or finding.get('severity') not in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')
                        or any(not isinstance(finding.get(key), str) or not finding[key].strip() for key in ('explanation', 'suggested_action'))
                        or not isinstance(finding.get('evidence_ids', []), list)
                        or any(not isinstance(key, str) or key not in evidence and key not in policy_ids for key in finding.get('evidence_ids', []))):
                    raise ValueError('Invalid finding')
                references = finding.get('code_references', [])
                allowed = [reference_key(ref) for key in finding.get('evidence_ids', []) if key in evidence
                           for ref in evidence[key].get('code_references', [])]
                if not isinstance(references, list) or any(not isinstance(ref, dict) or set(ref) - set(REFERENCE_FIELDS) or reference_key(ref) not in allowed for ref in references):
                    raise ValueError('Invalid reference')
                normalized['findings'].append(dict(finding, evidence_ids=finding.get('evidence_ids', []),
                                                   code_references=[dict(zip(REFERENCE_FIELDS, reference_key(ref))) for ref in references]))
            self.bounded_payload({key: value for key, value in normalized.items() if key != 'saved_at'})
            return normalized
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise PrimeError('invalid_review', 'Review requires truthful reviewer identifiers, typed findings, snapshot evidence IDs and exact cited code references; saved results require an aware server timestamp.') from None

    def save_review(self, plan_id, result_file):
        self.settings().require('plan')
        record = self.get(plan_id)
        try:
            result = json.loads(read_bytes(result_file, MAX_PLAN_BYTES, private=True))
        except (ValueError, UnicodeError):
            raise PrimeError('invalid_review', 'The separate reviewer result must be complete private UTF-8 JSON.') from None
        expected = self.validate_review(result, record['context_snapshot'])
        saved = self.request('PUT', '/dev/plans/' + str(plan_id) + '/review', self.bounded_payload(result))
        confirmed = self.validate_review(saved, record['context_snapshot'], saved=True)
        if {key: value for key, value in confirmed.items() if key != 'saved_at'} != expected:
            raise PrimeError('invalid_review', 'The saved review differs from the submitted advisory; inspect the stored plan before repeating a save.')
        return saved

    def history(self, limit=100, offset=0, **filters):
        return self.list_records('/dev/plans', limit, offset, filters)

    def list_records(self, route, limit, offset, filters):
        if type(limit) is not int or not 0 <= limit < 10000 or type(offset) is not int or offset < 0:
            raise PrimeError('invalid_input', 'Pagination requires limit 0–9999 and offset zero or greater.')
        return self.request('GET', route + '?' + urlencode(dict(limit=limit, offset=offset, **{key: value for key, value in filters.items() if value is not None})))

    def delete(self, plan_id):
        self.request('DELETE', '/dev/plans/' + str(positive_id(plan_id)))
        return {'status': 'deleted', 'id': plan_id}

    def pr_review(self, repository, pull_request):
        self.settings()
        result = self.request('POST', '/dev/pr-reviews', {'pr_ref': dict(repository, pull_request=positive_id(pull_request))})
        if type(result.get('job_id')) is not int or result['job_id'] <= 0 or not isinstance(result.get('status'), str) or not result['status']:
            raise PrimeError('invalid_response', 'PR request acceptance was not confirmed; inspect PR request history before repeating it.')
        return result

    def pr_history(self, limit=100, offset=0, **filters):
        return self.list_records('/dev/pr-reviews', limit, offset, filters)

    def context_outcome(self, context_id, issue_ids):
        try:
            identifier = str(UUID(context_id))
        except (ValueError, TypeError, AttributeError):
            raise PrimeError('invalid_input', 'Outcome reporting requires a context UUID.') from None
        if not 1 <= len(issue_ids) <= 20 or len(set(issue_ids)) != len(issue_ids) or any(type(value) is not int or value <= 0 for value in issue_ids):
            raise PrimeError('invalid_input', 'Report 1–20 distinct positive issue IDs from the original context.')
        self.settings().require('outcome')
        return self.request('POST', '/dev/contexts/' + identifier + '/outcomes', {'issue_ids': issue_ids})


def paginate(get, path):
    results, seen = [], set()
    offset, expected_total = 0, None
    for _ in range(MAX_PAGES):
        data = get(path + '?' + urlencode({'limit': 100, 'offset': offset}))
        items = data.get('results')
        size, limit = data.get('size'), data.get('limit')
        total, more = data.get('total'), data.get('has_next')
        valid = (isinstance(items, list) and all(isinstance(item, dict) for item in items)
                 and type(size) is int and size == len(items)
                 and type(limit) is int and 0 < limit and size <= limit
                 and type(data.get('offset')) is int and data['offset'] == offset
                 and (total is None or type(total) is int and total >= 0)
                 and (more is None or type(more) is bool))
        if not valid:
            raise PrimeError('invalid_pagination', 'Prime returned invalid pagination; no partial results were accepted.')
        if total is not None:
            if expected_total is not None and total != expected_total:
                raise PrimeError('changed_pagination', 'Prime results changed during loading; retry for a complete snapshot.')
            expected_total = total
        for item in items:
            identity = json.dumps(item, sort_keys=True, separators=(',', ':'))
            if identity in seen:
                raise PrimeError('repeated_page', 'Prime repeated a result during pagination; retry for a complete snapshot.')
            seen.add(identity)
        results.extend(items)
        offset += size
        if expected_total is not None and (offset > expected_total or more is False and offset != expected_total):
            raise PrimeError('incomplete_pagination', 'Prime pagination is inconsistent; no partial results were accepted.')
        if more is True and (not size or expected_total is not None and offset >= expected_total):
            raise PrimeError('incomplete_pagination', 'Prime pagination cannot advance; no partial results were accepted.')
        if more is False or more is None and (offset == expected_total or expected_total is None and size == 0):
            return results
        if not size:
            raise PrimeError('incomplete_pagination', 'Prime pagination ended before all results were received.')
    raise PrimeError('pagination_limit', 'Prime exceeded the page limit; no partial results were accepted.')


@dataclass(frozen=True)
class ParsedRemote:
    host: str
    port: Optional[int]
    path: str


@dataclass(frozen=True)
class RepositoryScope:
    organization: str
    repository: str
    platform: str


@dataclass(frozen=True)
class CodeReference(RepositoryScope):
    branch: Optional[str] = None
    commit: Optional[str] = None
    pull_request: Optional[int] = None
    filename: Optional[str] = None


def parse_remote(remote: Optional[str]) -> Optional[ParsedRemote]:
    if not isinstance(remote, str) or re.search(r'[\s\\]', remote):
        return None
    if '://' not in remote:
        match = re.fullmatch(r'(?:[^/@:]+@)?([^/:]+):(.+)', remote)
        if not match:
            return None
        remote = 'ssh://' + match[1] + '/' + match[2]
    try:
        url = urlsplit(remote)
        if url.scheme not in ('ssh', 'https', 'http', 'git') or not url.hostname or url.query or url.fragment:
            return None
        host, port = url.hostname.lower(), url.port
    except ValueError:
        return None
    path = url.path.strip('/').removesuffix('.git')
    if '/' not in path or any(part in ('', '.', '..') for part in path.split('/')):
        return None
    default_port = {'ssh': 22, 'https': 443, 'http': 80, 'git': 9418}[url.scheme]
    return ParsedRemote(host, port if port != default_port else None, path)


def baseline_repo_identity(remote: Optional[str]) -> Optional[ParsedRemote]:
    parsed = parse_remote(remote)
    if parsed and parsed.host == 'github.com':
        return ParsedRemote(parsed.host, parsed.port, parsed.path.lower())
    return parsed


def match_repo(repositories, remote):
    identity = baseline_repo_identity(remote)
    if identity is None:
        return None
    matches = [repo for repo in repositories if baseline_repo_identity(repo.get('repo_url')) == identity]
    if len(matches) > 1:
        raise PrimeError('ambiguous_repository', 'Multiple Prime registrations match this remote; repository context was skipped.')
    return matches[0] if matches else None


def repository_context(client, remote):
    if baseline_repo_identity(remote) is None:
        return {'status': 'no_supported_remote'}
    try:
        repo = match_repo(paginate(client.get, '/code-management/repositories'), remote)
        if repo is None:
            return {'status': 'not_registered'}
        if type(repo.get('id')) is not int or repo['id'] < 0:
            raise PrimeError('invalid_repository', 'Prime returned an invalid repository identifier.')
        detail = client.get(f"/code-management/repositories/{repo['id']}?detailed_summary_required=true")
        analysis = detail.get('analysis')
        if not isinstance(analysis, dict) or not isinstance(analysis.get('concise_summary'), str):
            raise PrimeError('invalid_summary', 'Prime repository summary is unavailable or malformed.')
        detailed = analysis.get('detailed_summary')
        if detailed is not None and not isinstance(detailed, str):
            raise PrimeError('invalid_summary', 'Prime repository summary is malformed.')
        return {'status': 'loaded', 'id': repo['id'], 'concise_summary': analysis['concise_summary'],
                'detailed_summary': detailed}
    except PrimeError as error:
        return {'status': 'unavailable', 'reason': error.code}


def load_context(client, remote):
    policies = paginate(client.get, '/guardrails')
    for policy in policies:
        if any(not isinstance(policy.get(key), str) or not policy[key].strip()
               for key in ('guardrail_title', 'guardrail')):
            raise PrimeError('invalid_guardrail', 'Prime returned a guardrail without a title or policy text; loading failed.')
    return {'status': 'loaded', 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'guardrails': [{key: policy[key] for key in ('guardrail_title', 'guardrail', 'category',
                                                      'framework', 'policy_name', 'policy_id') if key in policy}
                          for policy in policies],
            'repository': repository_context(client, remote)}


def positive_id(value):
    if type(value) is not int or value <= 0:
        raise PrimeError('invalid_input', 'A positive plan or pull-request ID is required.')
    return value


def repo_identity(remote: Optional[str]) -> Optional[RepositoryScope]:
    parsed = parse_remote(remote)
    if parsed is None or parsed.port is not None:
        return None
    platform = {'github.com': 'github', 'gitlab.com': 'gitlab', 'bitbucket.org': 'bitbucket'}.get(parsed.host)
    parts = parsed.path.split('/')
    if platform is None or platform != 'gitlab' and len(parts) != 2 or '%' in parsed.path:
        return None
    return RepositoryScope('/'.join(parts[:-1]), parts[-1], platform)


def git_remote(directory):
    try:
        result = subprocess.run(['git', '-C', str(directory), 'remote', 'get-url', 'origin'],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def repository_scope(args, auto=True) -> Optional[RepositoryScope]:
    values = (args.organization, args.repository, args.platform)
    if any(value is not None for value in values):
        if not all(isinstance(value, str) and value.strip() and not re.search(r'[\x00-\x1f]', value) for value in values):
            raise PrimeError('invalid_scope', 'Supply canonical --organization, --repository and --platform together.')
        return RepositoryScope(*values)
    if not auto:
        return None
    identity = repo_identity(args.remote or git_remote(args.repo))
    if identity is None:
        raise PrimeError('unsupported_remote', 'Supply canonical --organization, --repository and --platform for uploaded, self-hosted or unsupported repositories.')
    return identity


def code_scope(args) -> list[CodeReference]:
    revisions = {key: value for key, value in (('branch', args.branch), ('commit', args.commit), ('pull_request', args.pull_request)) if value is not None}
    if any(isinstance(value, str) and not value.strip() for value in revisions.values()):
        raise PrimeError('invalid_scope', 'A revision selector must be nonempty.')
    if args.pull_request is not None:
        positive_id(args.pull_request)
    if len(args.path) > 100:
        raise PrimeError('invalid_scope', 'Scope accepts at most 100 relative repository paths.')
    paths = []
    for value in args.path:
        if (not value or len(value) > 4096 or '\\' in value or '\x00' in value or value.startswith('/')
                or re.match(r'^[A-Za-z]:', value) or '..' in value.split('/')):
            raise PrimeError('invalid_scope', 'Use relative POSIX file or directory paths without traversal, at most 4096 characters each.')
        path = str(PurePosixPath(value))
        if path == '.':
            raise PrimeError('invalid_scope', 'Each path must identify a file or directory.')
        paths.append(path)
    scope = repository_scope(args)
    return [CodeReference(scope.organization, scope.repository, scope.platform, **revisions, filename=path) for path in (paths or [None])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='guidance', choices=('capabilities', 'guidance', 'settings', 'guardrails', 'context', 'plan-register', 'plan-save-review', 'plan-list', 'plan-get', 'plan-delete', 'pr-review', 'pr-review-list', 'context-outcome'))
    parser.add_argument('--repo', default='.')
    parser.add_argument('--allow-origin')
    parser.add_argument('--approve-origin')
    parser.add_argument('--output', type=Path, help='New complete private JSON artifact outside the repository')
    parser.add_argument('--plan-file', type=Path)
    parser.add_argument('--result-file', type=Path)
    parser.add_argument('--plan-id', type=int)
    parser.add_argument('--path', action='append', default=[])
    parser.add_argument('--intent', default='')
    parser.add_argument('--remote')
    parser.add_argument('--organization')
    parser.add_argument('--repository')
    parser.add_argument('--platform', choices=PLATFORMS)
    revision = parser.add_mutually_exclusive_group()
    revision.add_argument('--branch')
    revision.add_argument('--commit')
    revision.add_argument('--pull-request', type=int)
    for name in ('title', 'client', 'client-version', 'base-commit', 'owner-id', 'context-id'):
        parser.add_argument('--' + name)
    parser.add_argument('--status', choices=('registered', 'review_recorded', 'review_failed'))
    parser.add_argument('--issue-id', action='append', type=int, default=[])
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    args = parser.parse_args()
    token = None
    result = {}
    try:
        if args.approve_origin:
            print(json.dumps(approve_origin(args.approve_origin)))
            return 0
        if args.output:
            output_path = args.output.absolute()
            private_directory(output_path.parent, args.repo)
            if os.path.lexists(output_path):
                raise PrimeError('file_write_failed', 'The output target already exists; choose a new private artifact path before sending a request.')
        value = os.environ.get('PRIME_API_URL') or DEFAULT_ORIGIN
        try:
            origin = validate_origin(value, args.allow_origin)
        except PrimeError as error:
            if error.code != 'origin_not_approved':
                raise
            origin = validate_origin(value, args.allow_origin, load_approved_origins())
        token = resolve_token()
        client = Client(origin, token)
        capabilities = client.get('/dev/capabilities')
        if type(capabilities.get('developer_security_enabled')) is not bool:
            raise PrimeError('invalid_capabilities', 'Current developer capabilities could not be read; retry security work explicitly.')
        workflow = DeveloperWorkflow(client)
        command = args.command
        if command == 'capabilities':
            result = capabilities
        elif not capabilities['developer_security_enabled']:
            if command not in ('guidance', 'guardrails'):
                raise PrimeError('feature_disabled', 'Managed developer security is unavailable for this account; use account-wide guidance or continue ordinary coding.')
            result = load_context(client, args.remote or git_remote(args.repo))
            result['api_origin'] = origin
            result['repository_directory'] = str(Path(args.repo).resolve())
        elif command == 'settings':
            result = workflow.settings().response
        elif command in ('guidance', 'guardrails', 'context', 'plan-register'):
            try:
                scopes = code_scope(args)
            except PrimeError as error:
                if error.code != 'unsupported_remote' or command not in ('guidance', 'guardrails'):
                    raise
                workflow.settings().require('guidance')
                result = load_context(client, args.remote or git_remote(args.repo))
                result['limitations'] = ['Account-wide guidance only; no code-area or revision coverage.']
                scopes = []
            references = [{key: value for key, value in asdict(scope).items() if value is not None} for scope in scopes]
            if command in ('guidance', 'guardrails'):
                if scopes:
                    result = workflow.guardrails(references)
            elif command == 'context':
                result = workflow.context(references, args.intent)
            else:
                names = ('title', 'client', 'client_version')
                values = vars(args)
                if args.plan_file is None or any(not values[name] or not values[name].strip() for name in names):
                    raise PrimeError('missing_input', 'Registration requires a plan file, title and actual host client/version.')
                payload = {name: values[name] for name in names}
                payload['code_references'] = references
                if args.base_commit is not None:
                    if not args.base_commit.strip():
                        raise PrimeError('invalid_scope', 'The base commit must be nonempty.')
                    payload['base_commit_ref'] = dict(organization=scopes[0].organization, repository=scopes[0].repository, platform=scopes[0].platform, commit=args.base_commit)
                result = workflow.register(args.plan_file, payload)
        elif command == 'plan-save-review':
            if args.result_file is None:
                raise PrimeError('missing_input', 'Saving requires --result-file from the separate reviewer.')
            result = workflow.save_review(positive_id(args.plan_id), args.result_file)
        elif command in ('plan-list', 'pr-review-list'):
            scope = repository_scope(args, auto=False)
            filters = dict(asdict(scope) if scope else {}, owner_id=args.owner_id)
            if command == 'plan-list':
                filters.update(status=args.status, title=args.title)
                result = workflow.history(args.limit, args.offset, **filters)
            else:
                result = workflow.pr_history(args.limit, args.offset, **filters)
        elif command in ('plan-get', 'plan-delete'):
            plan_id = positive_id(args.plan_id)
            result = workflow.get(plan_id) if command == 'plan-get' else workflow.delete(plan_id)
        elif command == 'pr-review':
            result = workflow.pr_review(asdict(repository_scope(args)), positive_id(args.pull_request))
        else:
            result = workflow.context_outcome(args.context_id, args.issue_id)
        if args.output:
            data = json.dumps(result, ensure_ascii=True, indent=2).replace(json.dumps(token)[1:-1], '[REDACTED]')
            try:
                durable_write(output_path, data.encode())
            except PrimeError as error:
                error.result_ids = {key: result[key] for key in ('id', 'context_id', 'saved_at', 'job_id') if key in result}
                error.args = (str(error) + ' Inspect the confirmed record or history before repeating a write.',)
                raise
            snapshot = result.get('context_snapshot') or result
            policies = snapshot.get('policies', snapshot.get('guardrails'))
            receipt = {'guardrail_count': len(policies)} if isinstance(policies, list) else {}
            if isinstance(result.get('repository'), dict):
                receipt['repository_status'] = result['repository'].get('status')
            result = {**receipt, 'status': result.get('status', 'saved'), 'output_path': str(output_path),
                      **{key: result[key] for key in ('id', 'context_id', 'saved_at', 'job_id') if key in result}}
        exit_code = 0
    except PrimeError as error:
        result = {'status': 'error', 'code': error.code, 'message': str(error), 'ordinary_coding': 'available', **error.result_ids}
        exit_code = 1
    output = json.dumps(result, ensure_ascii=True)
    if token:
        output = output.replace(json.dumps(token)[1:-1], '[REDACTED]')
    print(output)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
