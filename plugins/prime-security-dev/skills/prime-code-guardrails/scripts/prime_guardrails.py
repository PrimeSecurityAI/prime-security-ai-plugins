#!/usr/bin/env python3
"""Managed Prime developer workflows. Python 3.9+, standard library only."""

import argparse
from dataclasses import asdict, dataclass
import base64
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_ORIGIN = 'https://api.primesec.ai'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
RELEASE_VERSION = '1.5.0-alpha.1'
MAX_PLAN_BYTES = 256 * 1024
MAX_RECEIPT_BYTES = 3 * 1024 * 1024
CONFLICT_CODES = {'submission_conflict', 'context_settings_changed', 'review_hash_mismatch', 'review_conflict'}


class PrimeError(Exception):
    """Only static, credential-free messages cross the CLI boundary."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.receipt = None
        self.conflict = False


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
        if not path.startswith('/dev/') or re.search(r'[\\\s#]', path):
            raise PrimeError('invalid_path', 'Developer feature requests require a reviewed /dev route.')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise PrimeError('timeout', 'Prime request budget exceeded; resume explicitly if a receipt exists.')
        body = payload if isinstance(payload, bytes) else (json_bytes(payload) if payload is not None else None)
        request = Request(self.origin + path, data=body, method=method, headers={
            'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json',
            'Content-Type': 'application/json', 'User-Agent': 'prime-security-dev/' + RELEASE_VERSION,
        })
        try:
            with self.opener.open(request, timeout=min(30, remaining)) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            status, code = error.code, 'http_error'
            try:
                if status == 409:
                    try:
                        detail = json.loads(error.read(4097)).get('detail')
                        if isinstance(detail, str) and detail in CONFLICT_CODES:
                            code = detail
                    except (ValueError, OSError, HTTPException, AttributeError):
                        pass
            finally:
                error.close()
            messages = {
                401: ('authentication_failed', 'Renew the credential in your terminal; an environment PAT overrides the private token file. Then resume explicitly.'),
                403: ('permission_denied', 'The credential lacks permission; request the required access before explicit recovery.'),
                409: (code if code != 'http_error' else 'conflict', 'Developer request conflict; check fresh settings and use an explicit new revision for changed content or context.'),
                422: ('invalid_input', 'Prime rejected the input; check the reviewed developer contract.'),
                429: ('rate_limited', 'Prime rate limit reached; retry explicitly later.'),
                503: ('unavailable', 'Developer settings or context unavailable; ordinary coding can continue. Retry security work explicitly later.'),
            }
            code, message = messages.get(status, ('http_error', 'Prime request failed; check connectivity and the reviewed contract.'))
            if 300 <= status < 400:
                code, message = 'redirect_refused', 'Prime returned a redirect; credentials were not forwarded.'
            failure = PrimeError(code, message)
            failure.conflict = status == 409
            raise failure from None
        except (OSError, URLError, HTTPException, ValueError):
            raise PrimeError('network_error', 'Prime request failed; check connectivity, TLS, and the configured API origin. Resume explicitly if a receipt exists.') from None
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
    account_id: str
    owner_id: str
    guardrails: bool
    plans: bool
    response: dict

    @classmethod
    def read(cls, client):
        data = client.request('GET', '/dev/settings')
        caller = data.get('caller')
        if (not isinstance(caller, dict) or any(not isinstance(caller.get(key), str) or not caller[key] for key in ('account_id', 'user_id'))
                or any(type(data.get(key)) is not bool for key in ('effective_dev_guardrails_enabled', 'effective_security_plan_enabled'))):
            raise PrimeError('invalid_settings', 'Current controls and trusted caller could not be read; continue ordinary coding and retry security work explicitly.')
        return cls(caller['account_id'], caller['user_id'], data['effective_dev_guardrails_enabled'], data['effective_security_plan_enabled'], data)

    def require(self, operation):
        enabled = self.plans if operation == 'plan' else self.guardrails if operation == 'guidance' else self.guardrails or self.plans
        if not enabled:
            raise PrimeError('feature_disabled', 'This security feature is disabled. Discard reusable guidance when guardrails are off; ordinary coding and history/deletion remain available.')


def private_directory(path, repo):
    try:
        if path.resolve().is_relative_to(Path(repo).resolve()):
            raise OSError('Repository artifact')
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise OSError('Unsafe directory')
    except OSError:
        raise PrimeError('unsafe_artifact_directory', 'Developer artifacts require a private owner-only directory outside the repository.') from None
    return path


def receipt_directory(repo):
    root = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    return private_directory(root / 'prime-security/developer-receipts', repo)


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
        raise PrimeError('invalid_artifact', 'Cannot securely read the complete regular artifact; check size, ownership and private receipt permissions.') from None


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
        raise PrimeError('file_write_failed', 'Cannot durably publish the private artifact; no request was sent from an incomplete artifact.') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@dataclass
class Receipt:
    origin: str
    account_id: str
    owner_id: str
    guardrails_included: bool
    plan_b64: str
    request_b64: str
    plan_digest: str
    request_digest: str
    registered: Optional[dict] = None
    completion_b64: str = ''
    completion_digest: str = ''
    retries: int = 0

    @property
    def plan_bytes(self):
        return base64.b64decode(self.plan_b64, validate=True)

    @property
    def request_bytes(self):
        return base64.b64decode(self.request_b64, validate=True)

    @property
    def completion_bytes(self):
        return base64.b64decode(self.completion_b64, validate=True)

    def save(self, path, replace=True):
        durable_write(path, json_bytes(asdict(self)), replace)

    @classmethod
    def load(cls, path, repo):
        path = Path(path).absolute()
        if path.parent != receipt_directory(repo):
            raise PrimeError('invalid_receipt', 'Use a receipt in the private developer receipt directory.')
        try:
            receipt = cls(**json.loads(read_bytes(path, MAX_RECEIPT_BYTES, private=True)))
            if (hashlib.sha256(receipt.plan_bytes).hexdigest() != receipt.plan_digest
                    or hashlib.sha256(receipt.request_bytes).hexdigest() != receipt.request_digest
                    or receipt.completion_b64 and hashlib.sha256(receipt.completion_bytes).hexdigest() != receipt.completion_digest
                    or type(receipt.retries) is not int or receipt.retries < 0):
                raise ValueError('Invalid integrity')
            return receipt
        except (TypeError, ValueError, UnicodeError):
            raise PrimeError('invalid_receipt', 'Receipt integrity validation failed; preserve it for investigation or explicitly abandon it.') from None

    def bind(self, client, controls):
        if (self.origin, self.account_id, self.owner_id) != (client.origin, controls.account_id, controls.owner_id):
            raise PrimeError('receipt_identity_mismatch', 'Receipt origin or trusted caller changed; restore the original origin/account/owner before recovery.')
        controls.require('plan')
        if self.guardrails_included != controls.guardrails:
            raise PrimeError('context_settings_changed', 'Guidance settings changed; explicitly create a new submission with current context instead of reusing this snapshot.')


class DeveloperWorkflow:
    def __init__(self, client, repo):
        self.client, self.repo = client, Path(repo)

    def settings(self):
        return Settings.read(self.client)

    def request(self, method, path, payload=None):
        try:
            return self.client.request(method, path, payload)
        except PrimeError as error:
            if error.conflict:
                self.settings()
            raise

    def resolve(self, remote):
        self.settings().require('resolve')
        identity = repo_identity(remote)
        if identity is None:
            raise PrimeError('unsupported_remote', 'Select a registered repository/module explicitly; a supported remote is required for resolution.')
        host, port, path = identity
        remote = 'https://' + host + (':' + str(port) if port else '') + '/' + path
        return self.request('POST', '/dev/repositories/resolve', {'remote_url': remote})

    def guardrails(self, repository_id, module_id):
        self.settings().require('guidance')
        return self.validate_context(self.request('GET', '/dev/guardrails?' + urlencode({'repository_id': repository_id, 'module_id': module_id})), repository_id, module_id, True)

    def context(self, repository_id, module_id, paths, intent):
        self.settings().require('guidance')
        return self.validate_context(self.request('POST', '/dev/context', {'repository_id': repository_id, 'module_id': module_id, 'paths': paths, 'intent': intent}), repository_id, module_id, True)

    def validate_context(self, context, repository_id, module_id, guards):
        if (context.get('repository_id') != repository_id or context.get('module_id') != module_id
                or context.get('guardrails_included') is not guards or len(json_bytes(context)) > 1024 * 1024
                or not isinstance(context.get('policies') or [], list)
                or not guards and context.get('policies')
                or any(not isinstance(policy, dict) or any(not isinstance(policy.get(key), str) or not policy[key].strip()
                       for key in ('guardrail_title', 'guardrail')) for policy in context.get('policies') or [])):
            raise PrimeError('invalid_context', 'Context scope, coverage or complete policy text is invalid; no partial context was accepted.')
        return context

    def register(self, plan_file, payload):
        controls = self.settings()
        controls.require('plan')
        plan = read_bytes(plan_file, MAX_PLAN_BYTES)
        try:
            request = json_bytes(dict(payload, markdown=plan.decode('utf-8')))
        except UnicodeError:
            raise PrimeError('invalid_plan', 'The plan must be complete UTF-8 Markdown.') from None
        if not plan.strip() or json.dumps(self.client.token, ensure_ascii=False)[1:-1].encode() in request:
            raise PrimeError('invalid_plan', 'The plan must be nonempty and contain no configured credential.')
        receipt = Receipt(self.client.origin, controls.account_id, controls.owner_id, controls.guardrails,
                          base64.b64encode(plan).decode(), base64.b64encode(request).decode(),
                          hashlib.sha256(plan).hexdigest(), hashlib.sha256(request).hexdigest())
        key = [receipt.origin, receipt.account_id, receipt.owner_id] + [payload[key] for key in ('client', 'session_id', 'plan_key', 'submission_id')]
        path = receipt_directory(self.repo) / (hashlib.sha256(json_bytes(key)).hexdigest() + '.json')
        if path.exists():
            raise PrimeError('pending_submission', 'This submission already has a receipt; explicitly resume or abandon it before a new intent.')
        receipt.save(path, replace=False)
        return self.send_registration(receipt, path)

    def send_registration(self, receipt, path):
        try:
            record = self.request('POST', '/dev/plans', receipt.request_bytes)
            self.validate_record(receipt, record)
            receipt.registered = record
            receipt.save(path)
            return self.result(receipt, path)
        except PrimeError as error:
            error.receipt = str(path)
            raise

    def validate_record(self, receipt, record):
        request = json.loads(receipt.request_bytes)
        if (type(record.get('id')) is not int or record['id'] <= 0
                or record.get('account_id') != receipt.account_id or record.get('owner_id') != receipt.owner_id
                or any(record.get(key) != request[key] for key in ('client', 'client_version', 'session_id', 'plan_key', 'submission_id', 'repository_id', 'module_id'))
                or record.get('guardrails_included') != receipt.guardrails_included
                or any(not isinstance(record.get(key), str) or not record[key] for key in ('plan_hash', 'context_hash', 'request_hash'))
                or not isinstance(record.get('context_snapshot'), dict)):
            raise PrimeError('invalid_plan_response', 'Registered plan identity or immutable snapshot is invalid; retain the receipt and recover explicitly.')
        if receipt.registered is not None and any(record[key] != receipt.registered[key] for key in ('request_hash', 'plan_hash', 'context_hash')):
            raise PrimeError('invalid_plan_response', 'Immutable server hashes changed; retain the receipt for explicit recovery.')
        self.validate_context(record['context_snapshot'], request['repository_id'], request['module_id'], receipt.guardrails_included)
        if json.dumps(self.client.token, ensure_ascii=False)[1:-1].encode() in json_bytes(record):
            raise PrimeError('invalid_plan_response', 'Registered response contains a configured credential; it was not saved.')

    def result(self, receipt, path):
        return {'status': 'registered', 'receipt': str(path), 'plan': receipt.registered,
                'label': 'Developer-agent review · Client-reported advisory'}

    def complete(self, path, result_file):
        receipt = Receipt.load(path, self.repo)
        receipt.bind(self.client, self.settings())
        if receipt.registered is None or receipt.completion_b64:
            raise PrimeError('pending_operation', 'Explicitly resume the existing pending operation before supplying a result.')
        body = read_bytes(result_file, MAX_PLAN_BYTES)
        self.validate_review(receipt, body)
        receipt.completion_b64, receipt.completion_digest = base64.b64encode(body).decode(), hashlib.sha256(body).hexdigest()
        receipt.save(Path(path))
        return self.send_completion(receipt, Path(path))

    def validate_review(self, receipt, body):
        try:
            result = json.loads(body)
            record = receipt.registered
            required_strings = ('reviewer_client', 'reviewer_model', 'summary')
            valid = (isinstance(result, dict) and result.get('plan_hash') == record['plan_hash']
                     and result.get('context_hash') == record['context_hash'] and result.get('outcome') in ('recorded', 'failed')
                     and all(isinstance(result.get(key), str) and result[key].strip() for key in required_strings)
                     and isinstance(result.get('findings'), list) and isinstance(result.get('limitations'), list)
                     and all(isinstance(item, str) for item in result['limitations']) and json.dumps(self.client.token, ensure_ascii=False)[1:-1].encode() not in json_bytes(result))
            if not valid:
                raise ValueError('Invalid review')
            if result['outcome'] == 'failed' and (result.get('failure_code') not in ('reviewer_unavailable', 'reviewer_failed', 'review_cancelled') or result['findings']):
                raise ValueError('Invalid failure')
            if result['outcome'] == 'recorded' and result.get('failure_code') is not None:
                raise ValueError('Invalid outcome')
            evidence = {item['id']: item for item in record['context_snapshot'].get('evidence') or []}
            policy_ids = {str(item['external_id']) for item in record['context_snapshot'].get('policies') or [] if item.get('external_id') is not None}
            for finding in result['findings']:
                if (not isinstance(finding, dict) or any(not isinstance(finding.get(key), str) or not finding[key].strip() for key in ('severity', 'explanation', 'suggested_action'))
                        or not isinstance(finding.get('evidence_ids'), list) or any(not isinstance(key, str) or key not in evidence and key not in policy_ids for key in finding['evidence_ids'])):
                    raise ValueError('Invalid finding')
                locations = finding.get('locations', [])
                allowed = [location for key in finding['evidence_ids'] if key in evidence for location in evidence[key].get('locations') or []]
                if not isinstance(locations, list) or any(location not in allowed for location in locations):
                    raise ValueError('Invalid location')
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise PrimeError('invalid_review', 'Review must match registered hashes, typed findings and stored evidence IDs/locations; plan-only findings cite exact plan text with empty evidence IDs.') from None

    def send_completion(self, receipt, path):
        try:
            record = self.request('PUT', '/dev/plans/' + str(receipt.registered['id']) + '/review', receipt.completion_bytes)
            self.validate_record(receipt, record)
            expected_status = 'review_recorded' if json.loads(receipt.completion_bytes)['outcome'] == 'recorded' else 'review_failed'
            if record.get('status') != expected_status or not isinstance(record.get('review_result'), dict):
                raise PrimeError('invalid_completion', 'Completion was not confirmed; retain the receipt and resume explicitly.')
            self.validate_review(receipt, json_bytes(record['review_result']))
            path.unlink()
            return {'status': 'completed', 'plan': record, 'label': 'Developer-agent review · Client-reported advisory'}
        except PrimeError as error:
            error.receipt = str(path)
            raise

    def resume(self, path):
        receipt = Receipt.load(path, self.repo)
        receipt.bind(self.client, self.settings())
        if receipt.retries >= 3:
            raise PrimeError('retry_limit', 'Three explicit retries exhausted; preserve for investigation or explicitly abandon the receipt.')
        receipt.retries += 1
        receipt.save(Path(path))
        if receipt.completion_b64:
            self.validate_review(receipt, receipt.completion_bytes)
            return self.send_completion(receipt, Path(path))
        if receipt.registered is None:
            return self.send_registration(receipt, Path(path))
        return self.result(receipt, path)

    def history(self, limit=100, offset=0):
        return self.request('GET', '/dev/plans?' + urlencode({'limit': limit, 'offset': offset}))

    def get(self, plan_id):
        return self.request('GET', '/dev/plans/' + str(plan_id))

    def delete(self, plan_id):
        record = self.get(plan_id)
        self.request('DELETE', '/dev/plans/' + str(plan_id))
        keys = ('client', 'session_id', 'plan_key', 'submission_id', 'repository_id', 'module_id')
        for path in receipt_directory(self.repo).glob('*.json'):
            receipt = Receipt.load(path, self.repo)
            request = json.loads(receipt.request_bytes)
            if ((receipt.origin, receipt.account_id, receipt.owner_id) == (self.client.origin, record['account_id'], record['owner_id'])
                    and all(request[key] == record[key] for key in keys)):
                path.unlink()
        return {'status': 'deleted', 'plan_id': plan_id}

    def abandon(self, path):
        path = Path(path).absolute()
        if path.parent != receipt_directory(self.repo):
            raise PrimeError('invalid_receipt', 'Use a receipt in the private developer receipt directory.')
        read_bytes(path, MAX_RECEIPT_BYTES, private=True)
        path.unlink()
        return {'status': 'abandoned', 'message': 'Local payload removed; an already registered server row remains in history until explicitly deleted.'}


def repo_identity(remote):
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
    # Preserve case on arbitrary providers; false negatives are safer than incorrect context.
    if host == 'github.com':
        path = path.lower()
    default_port = {'ssh': 22, 'https': 443, 'http': 80, 'git': 9418}[url.scheme]
    return (host, port if port != default_port else None, path)


def load_context(client, remote, repo='.'):
    workflow = DeveloperWorkflow(client, repo)
    workflow.settings().require('guidance')
    scope = workflow.resolve(remote)
    if scope.get('status') != 'resolved':
        return {'status': scope.get('status'), 'scope': scope}
    return {'status': 'loaded', 'context': workflow.guardrails(scope['repository_id'], scope['module_id'])}


def git_remote(directory):
    try:
        result = subprocess.run(['git', '-C', directory, 'remote', 'get-url', 'origin'],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='guidance', choices=('guidance', 'settings', 'resolve', 'guardrails', 'context', 'plan-register', 'plan-complete', 'plan-list', 'plan-get', 'plan-delete', 'resume'))
    parser.add_argument('--repo', default='.')
    parser.add_argument('--allow-origin')
    parser.add_argument('--approve-origin')
    parser.add_argument('--output', type=Path, help='New complete private JSON artifact outside the repository')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--abandon', action='store_true', help='With resume, delete the local pending payload without an API request')
    parser.add_argument('--plan-file', type=Path)
    parser.add_argument('--result-file', type=Path)
    parser.add_argument('--plan-id', type=int)
    parser.add_argument('--repository-id', type=int)
    parser.add_argument('--module-id', type=int)
    parser.add_argument('--path', action='append', default=[])
    parser.add_argument('--intent', default='')
    parser.add_argument('--remote')
    for name in ('title', 'client', 'client-version', 'session-id', 'plan-key', 'submission-id', 'branch', 'base-sha'):
        parser.add_argument('--' + name)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    args = parser.parse_args()
    token = None
    try:
        if args.approve_origin:
            print(json.dumps(approve_origin(args.approve_origin)))
            return 0
        if args.command == 'resume' and args.abandon:
            if args.receipt is None:
                raise PrimeError('missing_input', 'Specify --receipt for explicit local abandonment.')
            result = DeveloperWorkflow(None, args.repo).abandon(args.receipt)
        else:
            value = os.environ.get('PRIME_API_URL') or DEFAULT_ORIGIN
            try:
                origin = validate_origin(value, args.allow_origin)
            except PrimeError as error:
                if error.code != 'origin_not_approved':
                    raise
                origin = validate_origin(value, args.allow_origin, load_approved_origins())
            token = resolve_token()
            workflow = DeveloperWorkflow(Client(origin, token), args.repo)
            command = args.command
            if command == 'guidance':
                result = load_context(workflow.client, args.remote or git_remote(args.repo), args.repo)
            elif command == 'settings':
                result = workflow.settings().response
            elif command == 'resolve':
                result = workflow.resolve(args.remote or git_remote(args.repo))
            elif command in ('guardrails', 'context', 'plan-register'):
                if not args.repository_id or not args.module_id:
                    raise PrimeError('missing_scope', 'Specify resolved --repository-id and --module-id; ambiguous scope must be selected explicitly.')
                if command == 'guardrails':
                    result = workflow.guardrails(args.repository_id, args.module_id)
                elif command == 'context':
                    result = workflow.context(args.repository_id, args.module_id, args.path, args.intent)
                else:
                    names = ('title', 'client', 'client_version', 'session_id', 'plan_key', 'submission_id')
                    values = vars(args)
                    if args.plan_file is None or any(not values[name] for name in names):
                        raise PrimeError('missing_input', 'Registration requires plan file, title, actual host client/version, session, plan key and submission ID.')
                    payload = {name: values[name] for name in names}
                    payload.update(repository_id=args.repository_id, module_id=args.module_id, paths=args.path, branch=args.branch, base_sha=args.base_sha)
                    result = workflow.register(args.plan_file, payload)
            elif command == 'plan-complete':
                if args.receipt is None or args.result_file is None:
                    raise PrimeError('missing_input', 'Completion requires --receipt and --result-file from a separate reviewer.')
                result = workflow.complete(args.receipt, args.result_file)
            elif command == 'resume':
                if args.receipt is None:
                    raise PrimeError('missing_input', 'Explicit resume requires --receipt.')
                result = workflow.resume(args.receipt)
            elif command == 'plan-list':
                result = workflow.history(args.limit, args.offset)
            else:
                if args.plan_id is None or args.plan_id <= 0:
                    raise PrimeError('missing_input', 'History detail/deletion requires a positive --plan-id.')
                result = workflow.get(args.plan_id) if command == 'plan-get' else workflow.delete(args.plan_id)
            result['api_origin'] = origin
        if args.output:
            output_path = args.output.absolute()
            private_directory(output_path.parent, args.repo)
            data = json.dumps(result, ensure_ascii=True, indent=2)
            if token:
                data = data.replace(json.dumps(token)[1:-1], '[REDACTED]')
            durable_write(output_path, data.encode())
            result = {'status': result.get('status', 'loaded'), 'output_path': str(output_path),
                      'receipt': result.get('receipt'), 'plan_id': (result.get('plan') or {}).get('id')}
        exit_code = 0
    except PrimeError as error:
        result = {'status': 'error', 'code': error.code, 'message': str(error), 'ordinary_coding': 'available'}
        if error.receipt:
            result['receipt'] = error.receipt
        exit_code = 1
    output = json.dumps(result, ensure_ascii=True)
    if token:
        output = output.replace(json.dumps(token)[1:-1], '[REDACTED]')
    print(output)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
