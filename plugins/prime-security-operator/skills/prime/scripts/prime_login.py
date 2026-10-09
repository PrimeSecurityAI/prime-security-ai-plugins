#!/usr/bin/env python3
"""Log in to Prime Security in the browser and save a token for the prime skill.

Runs the OAuth authorization code + PKCE flow against PRIME_API_URL (default https://api.primesec.ai) and writes
the issued 30-day token to ${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token. The token is never printed.
Exit code 0 means the token file was written.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CLIENT_ID = "prime-cli"
LOGIN_TIMEOUT = 300
TOKEN_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "prime-security" / "token"
DONE_PAGE = "<html><body style='font-family:sans-serif;text-align:center;margin-top:20vh'><h2>{}</h2><p>You can close this tab and return to your terminal.</p></body></html>"


def wait_for_callback(server: HTTPServer, state: str) -> dict:
    result = {}

    class Handler(BaseHTTPRequestHandler):
        timeout = 10

        def do_GET(self) -> None:
            url = urllib.parse.urlparse(self.path)
            params = dict(urllib.parse.parse_qsl(url.query))
            # Ignore requests without our state so another local process or web page cannot end the login.
            if url.path != "/callback" or params.get("state") != state:
                self.send_error(404)
                return
            result.update(params)
            title = "Login failed" if "error" in result else "Login approved"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DONE_PAGE.format(title).encode())

        def log_message(self, *args: object) -> None:
            pass

    server.RequestHandlerClass = Handler
    server.timeout = 1
    deadline = time.monotonic() + LOGIN_TIMEOUT
    while not result and time.monotonic() < deadline:
        server.handle_request()
    return result


def save_token(token: str) -> None:
    TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    TOKEN_FILE.parent.chmod(0o700)
    # Rename a new file over the old one so readers never see a partial token and an existing looser mode or symlink is never reused.
    tmp = TOKEN_FILE.with_name(f".token.{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", newline="\n") as f:
        f.write(token + "\n")
    os.replace(tmp, TOKEN_FILE)


def main() -> int:
    api_url = (os.environ.get("PRIME_API_URL") or "https://api.primesec.ai").rstrip("/")
    parts = urllib.parse.urlsplit(api_url)
    if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc or parts.query or parts.fragment:
        print("Login failed: PRIME_API_URL must be an https URL without user information, a query or a fragment.", file=sys.stderr)
        return 1
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
    params = {"response_type": "code", "client_id": CLIENT_ID, "redirect_uri": redirect_uri, "code_challenge": challenge, "code_challenge_method": "S256", "state": state}
    authorize_url = f"{api_url}/oauth/authorize?{urllib.parse.urlencode(params)}"

    print(f"Opening the browser to log in to Prime Security. If it does not open, visit:\n{authorize_url}", file=sys.stderr)
    if not webbrowser.open(authorize_url):
        server.server_close()
        print("Login failed: no browser could be opened. Create a token under Settings > Access > API Token instead.", file=sys.stderr)
        return 1
    callback = wait_for_callback(server, state)
    server.server_close()

    if not callback:
        print("Login timed out.", file=sys.stderr)
        return 1
    # RFC 9207: the response must come from the server we log in to, or the code and verifier could go elsewhere.
    if callback.get("iss") != api_url:
        print("Login failed: the response came from an unexpected server.", file=sys.stderr)
        return 1
    if "error" in callback:
        print(f"Login failed: {callback['error']}", file=sys.stderr)
        return 1

    form = {"grant_type": "authorization_code", "client_id": CLIENT_ID, "code": callback["code"], "redirect_uri": redirect_uri, "code_verifier": verifier}
    request = urllib.request.Request(f"{api_url}/oauth/token", data=urllib.parse.urlencode(form).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token = json.load(response)
    except urllib.error.HTTPError as e:
        print(f"Login failed: the token request returned HTTP {e.code}.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"Login failed: the token request did not complete ({e}).", file=sys.stderr)
        return 1

    save_token(token["access_token"])
    expires = time.strftime("%Y-%m-%d", time.localtime(time.time() + token["expires_in"]))
    print(f"Logged in to {api_url}. Token saved to {TOKEN_FILE} (expires {expires}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
