# Credential and origin setup

Use browser login when available, or create a PAT in Prime Security under **Settings → Access → API Token → Create Token**. Never paste a token into an agent conversation.

## Browser login and re-login

The operator skill's `scripts/prime_login.py` writes the same private token file this helper reads. If `prime` is already installed, locate its installed directory and run in your terminal:

```bash
python3 "<installed-prime-skill-directory>/scripts/prime_login.py"
```

Use the same `PRIME_API_URL` for login and guardrail requests. Complete the browser authorization yourself. Login tokens expire after 30 days; re-run this command to renew them. A 403 can also mean missing permissions, which re-login alone does not fix.

The standalone dev skill does **not** bundle the operator's login script. If it is absent, install the operator skill using the [repository installation guide](https://github.com/PrimeSecurityAI/prime-security-ai-plugins#install-the-portable-skill), or run `plugins/prime-security-operator/skills/prime/scripts/prime_login.py` from a reviewed checkout of that repository. Use the PAT setup below if you do not want the operator skill or cannot open a browser. Do not assume a sibling operator directory exists in an installed dev skill.

## Credential resolution and terminal PAT setup

The helper resolves credentials on each invocation:

1. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`.
2. Non-empty `PRIME_PAT_TOKEN` inherited by the agent process, only when the token file does not exist.

The token file works across clients and does not depend on exports surviving between shell tool calls. The helper reads the current file on each invocation, including after browser re-login. An unsafe or invalid token file is an error and never falls back to `PRIME_PAT_TOKEN`. On POSIX systems it must be owned by the current user, readable only by that user, and not a symlink. Use a current-user-only ACL on Windows.

Paste this into **Bash or zsh** on macOS/Linux. It runs an isolated Bash process and saves the token without echoing it or recording it in shell history. It removes surrounding spaces/tabs and a trailing carriage return, accepts a non-empty final line without a newline, and rejects empty or invalid input before replacing the existing token:

```bash
bash -c '
set -e
LC_ALL=C
IFS= read -r -s -p "Prime PAT: " prime_pat || {
  [ "$?" -eq 1 ] && [ -n "$prime_pat" ]
} || {
  printf "\nNo token entered; existing token unchanged.\n" >&2
  exit 1
}
printf "\n"
prime_pat="${prime_pat%"$(printf "\r")"}"
prime_pat="${prime_pat#"${prime_pat%%[![:blank:]]*}"}"
prime_pat="${prime_pat%"${prime_pat##*[![:blank:]]}"}"
if [[ -z "$prime_pat" || "$prime_pat" == *[![:graph:]]* ]]; then
  printf "Invalid token; existing token unchanged.\n" >&2
  exit 1
fi
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/prime-security"
umask 077
mkdir -p "$config_dir"
chmod 700 "$config_dir"
token_tmp=$(mktemp "$config_dir/token.XXXXXX")
trap "rm -f -- \"\$token_tmp\"" EXIT
printf "%s\n" "$prime_pat" > "$token_tmp"
mv -f -- "$token_tmp" "$config_dir/token"
'
```

The Claude plugin's MCP `headersHelper` reads the shared file on each connection, falling back to `PRIME_PAT_TOKEN` only when the file does not exist. After login or PAT replacement, open `/mcp` and reconnect the Prime server; a missing token does not prevent using the skill to complete setup. This was validated with Claude Code **2.1.312**. The standalone dev skill includes neither an MCP connection nor operator browser login.

Other MCP clients require a process environment token; see the [MCP launch instructions](https://github.com/PrimeSecurityAI/prime-security-ai-plugins#environment-based-mcp-clients). Fully quit and relaunch those clients after replacement.

## Custom API origin

`PRIME_API_URL` defaults to `https://api.primesec.ai`. Custom deployments must use an HTTPS origin, optionally with a port, without a path, embedded credentials, query, or fragment.

Before sending credentials to a custom origin, show the user that origin and obtain their approval unless they already explicitly approved it in the task. Then invoke:

```bash
PRIME_API_URL=https://prime.example.com python3 "<skill-directory>/scripts/prime_guardrails.py" --allow-origin https://prime.example.com --repo "<repository>"
```

The flag must exactly match the normalized origin. Approval already given for the task can be reused by passing the flag again without asking the user again.

For a deployment you want to trust across sessions, explicitly save that **exact** origin once:

```bash
python3 "<skill-directory>/scripts/prime_guardrails.py" --approve-origin https://prime.example.com
```

This only writes `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/approved-origins.json`; it performs no login or API request. Future runs with that origin need no flag. Saved approvals are read only when needed: a broken approval file does not block the default origin or a matching explicit `--allow-origin`. The configuration directory must be private (mode 700) and the approval file is mode 600 on POSIX. Wildcards and sibling domains are not trusted. Remove an origin from that JSON list to revoke saved approval. Agents should save approval only when the user explicitly asks to trust that destination across sessions.

Redirects are refused, including same-origin redirects. Configure the final API origin directly.

## Troubleshooting

| Code | Recovery |
|---|---|
| `missing_credentials`, `invalid_credentials` | Configure the PAT using hidden terminal input. |
| `unsafe_token_file`, `unreadable_token_file` | Check ownership, regular-file status, and mode 600. |
| `authentication_failed` | Re-run browser login or replace the PAT in the token file; delete a stale token file to use `PRIME_PAT_TOKEN`. Check account permissions for 403 errors. |
| `origin_not_approved`, `invalid_origin` | Correct the origin and explicitly approve a custom deployment. |
| `invalid_approval_file` | Check the owner-only configuration directory, approval-file permissions, and JSON list of exact origins. |
| `file_write_failed` | Choose a new output filename in an existing private directory. Existing files are never overwritten. |
| `rate_limited`, `network_error`, `timeout` | Check service/connectivity and retry later; do not use stale policy data. |
| Pagination or schema errors | Check the current unauthenticated API docs and report the contract mismatch. |

Diagnostics never need the token, authorization header, raw HTTP error body, or private repository source.
