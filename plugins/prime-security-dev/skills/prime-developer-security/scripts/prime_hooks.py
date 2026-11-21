#!/usr/bin/env python3
"""Advisory context on session start/resume/compaction. No state or API calls.

Usage: prime_hooks.py reminder [--format copilot]

Without a format, the event name selects the output: Claude Code and Codex send
`SessionStart` and read `hookSpecificOutput`; Cursor sends `sessionStart` and reads
`additional_context`. GitHub Copilot sends camelCase payloads without an event name
and reads a top-level `additionalContext`, so its hook passes `--format copilot`.
"""

import json
import sys

REMINDER = ('Use the prime-developer-security skill before meaningful coding actions: call the Prime MCP tools '
            'get_developer_guardrails and get_developer_security_context for the files you will change. '
            'Use create_developer_security_plan and start_developer_pr_review only when requested. '
            'If the tools are unavailable or disabled, tell the user and continue ordinary coding. This reminder makes no API calls.')


def parse_format(args):
    if args == ['reminder']:
        return None
    if args == ['reminder', '--format', 'copilot']:
        return 'copilot'
    raise ValueError('Unsupported arguments')


def reminder(payload, output_format):
    if output_format == 'copilot':
        return {'additionalContext': REMINDER}
    if payload.get('hook_event_name') == 'SessionStart':
        return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': REMINDER}}
    if payload.get('hook_event_name') == 'sessionStart':
        return {'additional_context': REMINDER}
    return {}


def main(args):
    try:
        output_format = parse_format(args)
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Payload too large')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Invalid payload')
        print(json.dumps(reminder(payload, output_format)))
    except (ValueError, TypeError):
        print('{}')
        print('Prime reminder unavailable; use the skill before editing.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
