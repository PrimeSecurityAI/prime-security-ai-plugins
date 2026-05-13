# Prime Security Tools

Claude Code plugin marketplace for Prime Security API integration.

## What is Prime Security

Prime Security is a platform that enables AI-assisted security reviews, policy and knowledge base search, code repository analysis, and code guardrails enforcement.

## Installation

```bash
# Add the marketplace
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins

# Install plugins
claude plugin install prime-security-operator@prime
claude plugin install prime-security-dev@prime
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `PRIME_PAT_TOKEN` | Yes | Prime Security Personal Access Token |

To generate a PAT token, go to the Prime Security platform: **Settings → Access → API Token → Create Token**.

## Plugins

### prime-security-operator

Security reviews, knowledge base search, code analysis, and AI conversations via the Prime API.

Examples:
- "Run a security review on this design doc"
- "Search the knowledge base for our password policy"
- "Analyze the authentication service repository"

### prime-security-dev

Code guardrails enforcement via a skill and hooks. Fetches security instructions and repo context before code is written, and analyzes diffs after each turn.

- **Skill** (`prime-code-guardrails`) — Fetches guardrails and repo summary before coding
- **PostToolUse hook** — Tracks which files are modified during a session

## Structure

```
plugins/
├── prime-security-operator/          # Prime API skill
│   └── skills/prime/SKILL.md
└── prime-security-dev/      # Guardrails skill + hooks
    ├── skills/prime-code-guardrails/SKILL.md
    ├── hooks/hooks.json
    └── scripts/
        └── track_touched_files.sh
```

## License

MIT
