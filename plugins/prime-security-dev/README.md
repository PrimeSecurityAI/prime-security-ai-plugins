# prime-security-dev

Enforce security guardrails at code-writing time. Fetches your organization's security instructions and repository context from Prime Security before any code is written, and tracks file modifications during the session.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `PRIME_PAT_TOKEN` | Yes | Prime Security Personal Access Token |

To generate a PAT token, go to the Prime Security platform: **Settings > Access > API Token > Create Token**.

## Skill: `prime-code-guardrails`

Automatically invoked before any coding task — adding features, fixing bugs, refactoring, creating endpoints, writing tests, etc. Invoke once per session; the guardrails apply to all subsequent code changes.

**What it does:**

1. **Fetches guardrails** — Retrieves active security instructions and policies for your account (`GET /instructions`). Every instruction is treated as a hard constraint.
2. **Fetches repo context** — Matches the current repository against Prime Security's registered repos and retrieves architecture overviews, component descriptions, and security notes.
3. **Enforces policies** — All code produced in the session conforms to the fetched security instructions.

## Hook: PostToolUse

Tracks which files Claude modifies during a session for post-generation analysis.

## License

MIT
