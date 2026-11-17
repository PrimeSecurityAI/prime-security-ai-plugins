# Credential and origin setup

Use browser login when available, or create a PAT in Prime Security under **Settings → Access → API Token → Create Token**. Never paste a token into an agent conversation.

## Browser login and re-login

The operator skill's `scripts/prime_login.py` writes the same private token file this helper reads. If `prime` is already installed, locate its installed directory and run in your terminal:

```bash
python3 "<installed-prime-skill-directory>/scripts/prime_login.py"
```

Complete the browser authorization yourself. Login tokens expire after 30 days; re-run this command to renew them. A 403 can also mean missing permissions, which re-login alone does not fix.

The standalone dev skill does **not** bundle the operator's login script. If it is absent, install the operator plugin or skill using the [repository installation guide](https://github.com/PrimeSecurityAI/prime-security-ai-plugins#plugin-or-skill), or run `plugins/prime-security-operator/skills/prime/scripts/prime_login.py` from a reviewed checkout of that repository. Use the PAT setup below if you do not want the operator skill or cannot open a browser. Do not assume a sibling operator directory exists in an installed dev skill.

## Credential resolution and terminal PAT setup

The helper resolves credentials on each invocation:

1. Non-empty `PRIME_PAT_TOKEN` inherited by the agent process.
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`.

The token file works across clients and does not depend on exports surviving between shell tool calls. On POSIX systems it must be owned by the current user, readable only by that user, and not a symlink. Use a current-user-only ACL on Windows.

Paste this into **Bash or zsh** on macOS/Linux. Input is hidden and stays out of shell history. Empty or invalid input leaves the existing token unchanged:

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

If replacing an environment credential, restart the agent from the updated environment. A non-empty environment variable takes precedence over the token file, including an expired token.

## Custom API origin

`PRIME_API_URL` defaults to `https://api.primesec.ai`. Custom deployments must use an HTTPS origin, optionally with a port, without a path, embedded credentials, query, or fragment.

Before sending credentials to a custom origin, show the user that origin and obtain their approval unless they already explicitly approved it in the task. Then invoke (replace the example origin with that approved origin):

```bash
PRIME_API_URL="https://approved.example.invalid" python3 "<skill-directory>/scripts/prime_guardrails.py" --allow-origin "https://approved.example.invalid" --repo "<repository>"
```

The flag must exactly match the normalized origin. Approval already given for the task can be reused by passing the flag again without asking the user again.

For a deployment you want to trust across sessions, explicitly save that **exact** origin once:

```bash
python3 "<skill-directory>/scripts/prime_guardrails.py" --approve-origin "https://approved.example.invalid"
```

This only writes `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/approved-origins.json`; it performs no login or API request. Future runs with that origin need no flag. Saved approvals are read only when needed: a broken approval file does not block the default origin or a matching explicit `--allow-origin`. The configuration directory must be private (mode 700) and the approval file is mode 600 on POSIX. Wildcards and sibling domains are not trusted. Remove an origin from that JSON list to revoke saved approval. Agents should save approval only when the user explicitly asks to trust that destination across sessions.

For dev acceptance, use the verified, user-authorized HTTPS dev front-service origin explicitly for login, helper calls and the environment launching the host; follow the [release checklist](https://github.com/PrimeSecurityAI/prime-security-ai-plugins/blob/main/docs/prime-security-dev-release.md).

Redirects are refused, including same-origin redirects. Configure the final API origin directly.

## Troubleshooting

| Code | Recovery |
|---|---|
| `missing_credentials`, `invalid_credentials` | Configure the PAT using hidden terminal input. |
| `unsafe_token_file`, `unreadable_token_file` | Check ownership, regular-file status, and mode 600. |
| `authentication_failed` | Re-run browser login or replace the PAT; unset/replace any expired environment override. Inspect plan/PR history before explicitly repeating an uncertain write. |
| `origin_not_approved`, `invalid_origin` | Correct the origin and explicitly approve a custom deployment. |
| `invalid_approval_file` | Check the owner-only configuration directory, approval-file permissions, and JSON list of exact origins. |
| `file_write_failed` | Before dispatch, choose a new output filename in a private directory outside the Git repository. Existing entries are never overwritten. On late storage failure, preserve reported IDs and inspect the existing record/history before repeating a write. |
| `rate_limited`, `network_error`, `timeout` | Check service/connectivity and retry later; do not use stale policy data. |
| `permission_denied` | Request required access; a renewed credential alone may not fix 403. |
| `feature_disabled` | Managed commands are unavailable while capabilities are false; use account-wide guidance. If capabilities are true, honor the independent guidance/plan setting. |
| `invalid_capabilities`, `invalid_settings`, `unavailable` | Pause security work and retry explicitly after the failed capability/settings/API read recovers. Errors never select another mode; ordinary coding continues. |
| `conflict` | Pause the attempted operation; read fresh settings and choose an explicit next step. |
| Schema/contract errors | Report the mismatch against [the reviewed contract](api-contract.md); update/test the helper before use. |

Diagnostics never need the token, authorization header, raw HTTP error body, or private repository source.

## Work after renewal

Each helper API call checks capabilities; gated work checks fresh settings. Before reusing cached guidance without a gated helper call, check capabilities and enabled-mode settings again. Enabled guidance without supported identity can load account-wide policies only after fresh guidance=true and valid selectors; API errors never permit this branch. Inspect `plan-list`/`plan-get` after an uncertain registration and inspect `review_result` after an uncertain review save before explicitly repeating either operation. Every successful registration creates a new row; review PUT replaces the current result. History and authorized deletion remain available when per-account controls are off or settings cannot be read, provided fresh capabilities are enabled. Capability errors stop security work without selecting stable mode. See [explicit recovery and cleanup](api-contract.md#explicit-recovery-and-cleanup) for legacy artifact cleanup.
