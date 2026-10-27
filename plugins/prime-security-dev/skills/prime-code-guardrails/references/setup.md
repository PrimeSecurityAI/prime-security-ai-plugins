# Credential and origin setup

Create a PAT in Prime Security under **Settings → Access → API Token → Create Token**. Configure it yourself in a terminal; never paste it into an agent conversation.

The helper resolves credentials on each invocation:

1. Non-empty `PRIME_PAT_TOKEN` inherited by the agent process.
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`.

The token file works across clients and does not depend on exports surviving between shell tool calls. On POSIX systems it must be owned by the current user, readable only by that user, and not a symlink. Use a current-user-only ACL on Windows.

Run this in **Bash** to create or replace the token file without echoing the token or recording it in shell history:

```bash
config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/prime-security"
mkdir -p "$config_dir"
chmod 700 "$config_dir"
umask 077
read -r -s -p "Prime PAT: " prime_pat
printf '\n'
printf '%s\n' "$prime_pat" > "$config_dir/token"
chmod 600 "$config_dir/token"
unset prime_pat
```

If replacing an environment credential, restart the agent from the updated environment. A non-empty environment variable takes precedence over the token file, including an expired token.

## Custom API origin

`PRIME_API_URL` defaults to `https://api.primesec.ai`. Custom deployments must use an HTTPS origin, optionally with a port, without a path, embedded credentials, query, or fragment.

Before sending credentials to a custom origin, show the user that origin and obtain their approval unless they already explicitly approved it in the task. Then invoke:

```bash
PRIME_API_URL=https://prime.example.com python3 "<skill-directory>/scripts/prime_guardrails.py" --allow-origin https://prime.example.com --repo "<repository>"
```

The flag must exactly match the normalized origin. It authorizes only that invocation. Redirects are refused, including same-origin redirects. Configure the final API origin directly.

## Troubleshooting

| Code | Recovery |
|---|---|
| `missing_credentials`, `invalid_credentials` | Configure the PAT using hidden terminal input. |
| `unsafe_token_file`, `unreadable_token_file` | Check ownership, regular-file status, and mode 600. |
| `authentication_failed` | Replace expired credentials or request the required account permissions. |
| `origin_not_approved`, `invalid_origin` | Correct the origin and explicitly approve a custom deployment. |
| `rate_limited`, `network_error`, `timeout` | Check service/connectivity and retry later; do not use stale policy data. |
| Pagination or schema errors | Check the current unauthenticated API docs and report the contract mismatch. |

Diagnostics never need the token, authorization header, raw HTTP error body, or private repository source.
