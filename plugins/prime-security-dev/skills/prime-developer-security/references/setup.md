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

## Custom API origin

Only the Claude Code plugin reads `PRIME_API_URL` (default `https://api.primesec.ai`) from the environment that starts it. Other clients always use the default origin; for another deployment, add the server manually with that origin's `/mcp` URL.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No `get_developer_*` tools | Connect the server as above and restart the client. |
| 401 | Log in again with the client's command above. |
| 403 developer security not enabled | Ask the Prime account admin to enable developer security. |
| 409 `developer_feature_disabled` | Ask the account admin to enable that feature. |
