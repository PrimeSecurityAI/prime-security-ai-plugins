# Connect the Prime MCP server

The developer tools live on the Prime MCP server, `https://api.primesec.ai/mcp`. Users log in through the browser; never ask for a token in chat.

## Plugin installations

The Claude Code, Codex, GitHub Copilot CLI and Cursor plugins connect the server as `prime`. Log in once:

| Client | Log in |
|---|---|
| Claude Code | `/mcp`, select the Prime server, then **Authenticate** |
| Codex | `codex mcp login prime` |
| GitHub Copilot CLI | `/mcp auth prime` |
| Cursor | **Cursor Settings** → MCP → log in to `prime` |

## Other clients

OpenCode, Pi and skill-only installations do not connect the server. Add it yourself as described in [MCP Server](https://github.com/PrimeSecurityAI/prime-security-ai-plugins#mcp-server); for OpenCode, run `opencode mcp auth prime` afterwards. Pi has no built-in MCP client and needs an MCP extension.

## Security context hooks

The Claude Code, Codex, GitHub Copilot CLI and Cursor plugins run `scripts/prime_hooks.py` (`python3`, Git) to push context: a small security map at session start, resume and compaction, and one security card per file the agent reads or edits (Codex: files changed with `apply_patch`). Each hook sends only the repository identity and relative paths, has a 3-second network budget and prints nothing on failure; at session start it falls back to a static reminder.

The hooks call the Prime API with a token, separate from the MCP login, resolved in this order:

1. `PRIME_PAT_TOKEN` in the environment that starts the client.
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`, written by the operator skill's browser login or by the [terminal PAT setup](https://github.com/PrimeSecurityAI/prime-security-ai-plugins#configure-credentials). It must be a regular file owned by you with mode 600.

Never paste a token into chat. Without a token the hooks only add the session reminder, and the agent uses the MCP tools instead.

In Codex, run `/hooks` and trust the Prime hooks; installing the plugin does not trust them. Per-session state (context id, files already carded) is kept in `${XDG_CACHE_HOME:-$HOME/.cache}/prime-security/sessions/`.

## Custom API origin

Only the Claude Code plugin's MCP connection reads `PRIME_API_URL` (default `https://api.primesec.ai`) from the environment that starts it. Other clients always use the default origin; for another deployment, add the server manually with that origin's `/mcp` URL.

The hooks also read `PRIME_API_URL`, but send the token only to `https://api.primesec.ai` or to an origin you approved. This is defense in depth against a cloned repository's project settings pointing the hooks elsewhere; project settings can also define their own hooks, so review a repository's agent settings before trusting it. To trust a deployment, check the exact HTTPS origin and save it once from a terminal:

```bash
python3 "<skill-directory>/scripts/prime_hooks.py" --approve-origin https://prime.example.com
```

This only writes `~/.config/prime-security/approved-origins.json` in your account's home directory (mode 600 in a mode 700 directory), ignoring `XDG_CONFIG_HOME` and `HOME` so project environment cannot swap it; it makes no API request. Wildcards and sibling domains are not trusted, redirects are refused, and removing an origin from that JSON list revokes it. Unapproved origins get the reminder only. The hooks honor the standard proxy (`HTTPS_PROXY`, `NO_PROXY`) and CA bundle (`SSL_CERT_FILE`) variables.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No `get_developer_*` tools | Connect the server as above and restart the client. |
| 401 | Log in again with the client's command above. |
| Only the reminder, no map or cards | Configure the hook token, approve a custom origin, trust the hooks, and check the repository has an `origin` remote on GitHub, GitLab or Bitbucket. |
| 403 developer security not enabled | Ask the Prime account admin to enable developer security. |
| 409 `developer_feature_disabled` | Ask the account admin to enable that feature. |
