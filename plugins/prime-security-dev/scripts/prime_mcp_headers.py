#!/usr/bin/env python3
"""Claude MCP protocol helper. Its stdout contains credentials; never run in chat."""
import json
import os
from pathlib import Path
import stat
import sys


def main():
    path = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'prime-security/token'
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'r', encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name == 'posix' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
                raise ValueError('Unsafe token file')
            token = stream.read(16385).removesuffix('\n').removesuffix('\r')
        if not token or len(token) > 16384 or any(ord(char) < 33 or ord(char) > 126 for char in token):
            raise ValueError('Invalid token')
    except FileNotFoundError:
        # Claude strips PRIME_PAT_TOKEN from plugin helpers; returning no header keeps the static environment header.
        print('{}')
        return 0
    except (OSError, ValueError, UnicodeError):
        print('Prime token file is unsafe or invalid. Replace it with a valid PAT in a private file (mode 600), or delete it to use PRIME_PAT_TOKEN, then reconnect Prime in /mcp.', file=sys.stderr)
        # An empty header replaces the static environment header, so a broken file never falls back to another credential.
        print(json.dumps({'Authorization': ''}))
        return 0
    print(json.dumps({'Authorization': 'Bearer ' + token}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
