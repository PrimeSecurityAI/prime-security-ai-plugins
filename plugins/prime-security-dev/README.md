# prime-security-dev

Enforce security guardrails at code-writing time. Fetches your organization's security guardrails and repository context from Prime Security before any code is written, and tracks file modifications during the session.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `PRIME_PAT_TOKEN` | Yes | Prime Security Personal Access Token |
| `PRIME_API_URL` | No | Prime API base URL, defaults to `https://api.primesec.ai` |

To generate a PAT token, go to the Prime Security platform: **Settings > Access > API Token > Create Token**.

## Skill: `prime-code-guardrails`

Automatically invoked before any coding task — adding features, fixing bugs, refactoring, creating endpoints, writing tests, etc. Invoke once per session; the guardrails apply to all subsequent code changes.

**What it does:**

1. **Fetches guardrails** — Retrieves active security guardrails and policies for your account (`GET /guardrails`). Every guardrail is treated as a hard constraint.
2. **Fetches repo context** — Matches the current repository against Prime Security's registered repos and retrieves architecture overviews, component descriptions, and security notes.
3. **Enforces policies** — All code produced in the session conforms to the fetched security guardrails.

## Hooks

- **UserPromptSubmit**: on the first prompt of a session, tells Claude to load the `prime-code-guardrails` skill before any code work.
- **PostToolUse**: tracks which files Claude modifies during a session for post-generation analysis.

## MCP Server

The plugin also connects Claude Code to the Prime MCP server through `.mcp.json`, using `PRIME_PAT_TOKEN` and `PRIME_API_URL` when set. See the [MCP Server section](../../README.md#mcp-server) of the repository README for its tools. If `prime-security-operator` is installed too, Claude Code connects to the server once.

## License

MIT
