#!/usr/bin/env python3
"""Advisory context on session start/resume/compaction. No state or API calls."""

import json
import sys

REMINDER = ('Use the prime-code-guardrails skill before changing code. Load policies once for an '
            'independent coding task; follow-up messages in that task reuse the full policy context. '
            'Reload after repository, account, or API origin changes, or when compaction loses policy text. '
            'This reminder does not mean policies have been loaded.')


def main():
    try:
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Payload too large')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('Invalid payload')
        if payload.get('hook_event_name') == 'SessionStart':
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': REMINDER}}))
        else:
            print('{}')
    except (ValueError, TypeError):
        print('{}')
        print('Prime reminder unavailable; use the skill before editing.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
