#!/usr/bin/env python3
"""Optional lifecycle reminders and local edit telemetry; never a compliance gate."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


REMINDER = ('Before changing code, use the prime-code-guardrails skill to load current Prime policies '
            'for this task and repository. Reuse them only within the same task while their full text '
            'remains in context and the account, API origin, and repository have not changed. '
            'After compaction, reload them. This reminder does not mean policies have been loaded.')


def touched_paths(payload):
    inputs = payload.get('tool_input')
    if not isinstance(inputs, dict):
        return []
    paths = [inputs.get('file_path'), inputs.get('notebook_path'), inputs.get('filePath')]
    if payload.get('tool_name') in ('apply_patch', 'applypatch'):
        command = inputs.get('command') or inputs.get('patchText')
        if isinstance(command, str):
            paths.extend(re.findall(r'^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$', command, re.MULTILINE))
    cwd = payload.get('cwd')
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        return []
    return sorted({os.path.abspath(os.path.join(cwd, path)) for path in paths
                   if isinstance(path, str) and path and len(path) <= 8192 and '\x00' not in path})


def track(payload):
    session = payload.get('session_id')
    paths = touched_paths(payload)
    if not isinstance(session, str) or not session or len(session) > 1024 or not paths:
        return
    root = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'prime-security'
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
        raise OSError('Unsafe state directory')
    key = hashlib.sha256((payload['cwd'] + '\0' + session).encode()).hexdigest()
    path = root / (key + '.jsonl')
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise OSError('Unsafe state file')
        if info.st_size > 5 * 1024 * 1024:
            return
        stream.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'paths': paths}) + '\n')


def main():
    try:
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Payload too large')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Invalid payload')
        action = sys.argv[1] if len(sys.argv) > 1 else ''
        if action == 'reminder':
            event = payload.get('hook_event_name', 'UserPromptSubmit')
            if event not in ('UserPromptSubmit', 'SessionStart'):
                raise ValueError('Unsupported reminder event')
            print(json.dumps({'hookSpecificOutput': {'hookEventName': event, 'additionalContext': REMINDER}}))
        elif action == 'track':
            track(payload)
            print('{}')
        else:
            raise ValueError('Unknown action')
    except (OSError, ValueError, TypeError):
        print('{}')
        print('Prime lifecycle hook unavailable; load policies through the skill before editing.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
