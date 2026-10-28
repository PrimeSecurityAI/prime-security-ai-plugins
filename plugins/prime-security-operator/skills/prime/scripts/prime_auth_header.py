#!/usr/bin/env python3
"""Print the Prime Authorization header for `curl -H @-`. Its stdout contains credentials; pipe it, never display it.

Exit code 2 means no token is configured; exit code 1 means the token file is unsafe or invalid.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import sys


def main() -> int:
    path = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "prime-security/token"
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
                raise ValueError("Unsafe token file")
            token = stream.read(16385).removesuffix("\n").removesuffix("\r")
    except FileNotFoundError:
        token = os.environ.get("PRIME_PAT_TOKEN", "")
        if not token:
            print("No Prime token is configured.", file=sys.stderr)
            return 2
    except (OSError, ValueError, UnicodeError):
        token = ""
    if not token or len(token) > 16384 or any(ord(char) < 33 or ord(char) > 126 for char in token):
        print("Prime token file or PRIME_PAT_TOKEN is unsafe or invalid. Replace the token file with a valid PAT in a private file (mode 600).", file=sys.stderr)
        return 1
    print("Authorization: Bearer " + token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
