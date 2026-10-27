#!/usr/bin/env python3
"""Read-only Prime policy/context loader. Python 3.10+, standard library only."""

import argparse
from datetime import datetime, timezone
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
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_ORIGIN = 'https://api.primesec.ai'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 1000


class PrimeError(Exception):
    """Only static, credential-free messages cross the CLI boundary."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


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


def write_private(path, text, replace=False):
    """Publish a complete owner-only file, refusing existing output destinations."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text + '\n')
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    except OSError:
        raise PrimeError('file_write_failed', 'Cannot save the private file; ensure its parent directory exists and an output destination does not already exist.') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
    write_private(path, json.dumps(sorted(set(origins + [origin])), indent=2), replace=True)
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

    def get(self, path):
        if not path.startswith('/') or path.startswith('//'):
            raise PrimeError('invalid_path', 'API path must be relative to the configured origin.')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise PrimeError('timeout', 'Prime context loading exceeded its time limit; retry the task.')
        request = Request(self.origin + path, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/json',
            'User-Agent': 'prime-security-dev/1.2.0',
        })
        try:
            with self.opener.open(request, timeout=min(30, remaining)) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            code = error.code
            error.close()
            if code in (401, 403):
                raise PrimeError('authentication_failed', 'Prime rejected the credential or its permissions; re-run browser login or configure a valid PAT in your terminal. See references/setup.md; an environment token overrides the token file.') from None
            if code == 429:
                raise PrimeError('rate_limited', 'Prime rate limit reached; retry later.') from None
            if 300 <= code < 400:
                raise PrimeError('redirect_refused', 'Prime returned a redirect; credentials were not forwarded.') from None
            raise PrimeError('http_error', f'Prime returned HTTP {code}; check the API contract or retry later.') from None
        except (OSError, URLError, HTTPException, ValueError):
            raise PrimeError('network_error', 'Prime request failed; check connectivity, TLS, and the configured API origin.') from None
        if len(data) > MAX_RESPONSE_BYTES:
            raise PrimeError('response_too_large', 'Prime response exceeded the supported size; no partial policies were loaded.')
        try:
            result = json.loads(data)
        except (ValueError, UnicodeError):
            raise PrimeError('invalid_response', 'Prime returned invalid JSON; no partial policies were loaded.') from None
        if not isinstance(result, dict):
            raise PrimeError('invalid_response', 'Prime returned an unexpected response shape; check the API contract.')
        return result


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


def match_repo(repositories, remote):
    identity = repo_identity(remote)
    if identity is None:
        return None
    matches = [repo for repo in repositories if repo_identity(repo.get('repo_url')) == identity]
    if len(matches) > 1:
        raise PrimeError('ambiguous_repository', 'Multiple Prime registrations match this remote; repository context was skipped.')
    return matches[0] if matches else None


def repository_context(client, remote):
    if repo_identity(remote) is None:
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


def git_remote(directory):
    try:
        result = subprocess.run(['git', '-C', directory, 'remote', 'get-url', 'origin'],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='.', help='Local repository directory (default: current directory)')
    parser.add_argument('--allow-origin', help='Exact custom HTTPS origin explicitly approved by the user')
    parser.add_argument('--approve-origin', help='Save approval for this exact HTTPS origin and exit without an API call')
    parser.add_argument('--output', type=Path, help='Save complete JSON to a new private file and print only a short receipt')
    args = parser.parse_args()
    token = None
    try:
        if args.approve_origin:
            print(json.dumps(approve_origin(args.approve_origin)))
            return 0
        value = os.environ.get('PRIME_API_URL') or DEFAULT_ORIGIN
        try:
            origin = validate_origin(value, args.allow_origin)
        except PrimeError as error:
            if error.code != 'origin_not_approved':
                raise
            origin = validate_origin(value, args.allow_origin, load_approved_origins())
        token = resolve_token()
        result = load_context(Client(origin, token), git_remote(args.repo))
        result['api_origin'] = origin
        result['repository_directory'] = str(Path(args.repo).resolve())
        if args.output:
            output_path = args.output.absolute()
            data = json.dumps(result, ensure_ascii=True, indent=2).replace(json.dumps(token)[1:-1], '[REDACTED]')
            write_private(output_path, data)
            result = {'status': 'loaded', 'guardrail_count': len(result['guardrails']),
                      'repository_status': result['repository']['status'], 'output_path': str(output_path),
                      'api_origin': origin}
        exit_code = 0
    except PrimeError as error:
        result = {'status': 'error', 'code': error.code, 'message': str(error)}
        exit_code = 1
    output = json.dumps(result, ensure_ascii=True)
    # Also redact a credential echoed by a server inside an otherwise valid response.
    if token:
        output = output.replace(json.dumps(token)[1:-1], '[REDACTED]')
    print(output)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
