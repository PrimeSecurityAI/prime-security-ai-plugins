# Prime Security Tools

Agent Skills and Claude Code plugins for interacting with Prime Security. The portable `prime` skill supports security reviews, policy search, repository analysis, code reviews, and AI-assisted security conversations.

## Prerequisites

- Node.js 22.20.0 or later with `npx`
- Claude Code, Codex, OpenCode, or Cursor
- A Prime Security account
- `python3` 3.9 or later for the browser login
- HTTPS access to GitHub, npm, and the Prime Security API

On first use the `prime` skill opens your browser to log in to Prime Security. A Personal Access Token (PAT) is needed only on machines without a browser, and for the `prime-security-dev` plugin.

## Install The Portable Skill

Use the Skills CLI for the primary cross-client installation:

```bash
npx skills add https://github.com/PrimeSecurityAI/prime-security-ai-plugins/tree/main/plugins/prime-security-operator/skills/prime --global
```

For a non-interactive installation targeting all four supported clients explicitly:

```bash
npx skills add https://github.com/PrimeSecurityAI/prime-security-ai-plugins/tree/main/plugins/prime-security-operator/skills/prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Choose one installation path. Do not install both the plain `prime` skill and the `prime-security-operator` Claude plugin for the same client; duplicate skills can produce ambiguous invocation and updates.

When Claude Code and OpenCode are targeted together, OpenCode may log a duplicate-source warning because it scans both `~/.agents/skills` and Claude's compatibility directory. The Skills CLI links both paths to the same canonical installed copy, and OpenCode exposes one `prime` skill.

### Update Or Remove

```bash
npx skills update prime --global --yes
npx skills remove prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Restart a client if it does not detect a newly installed, updated, or removed skill.

## Configure Credentials

No setup is needed on a machine with a browser. When no credential is configured, the skill runs its browser login. After you log in and click **Authorize**, it saves a 30-day token to the token file below. The token appears under **Settings > Access > API Token**, where you can revoke it.

The skill resolves credentials in this order:

1. `PRIME_PAT_TOKEN`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`

`PRIME_API_URL` is optional and defaults to `https://api.primesec.ai`.

On machines without a browser (SSH, CI, containers), create a PAT under **Settings > Access > API Token > Create Token** instead. Never paste a PAT into an agent chat. To store it without terminal echo or shell history from Bash:

```bash
config_root="${XDG_CONFIG_HOME:-$HOME/.config}"
config_dir="$config_root/prime-security"
mkdir -p "$config_dir"
chmod 700 "$config_dir"
umask 077
read -r -s -p "Prime PAT: " prime_pat
printf '\n'
printf '%s\n' "$prime_pat" > "$config_dir/token"
chmod 600 "$config_dir/token"
unset prime_pat
```

On other systems, use hidden terminal input and a current-user-only ACL for the same logical token path. Do not print or log the token.

## Supported Clients

All clients can select `prime` automatically from a natural-language request.

| Client | Explicit invocation | Example |
|---|---|---|
| Claude Code | `/prime` | `/prime review this design for security risks` |
| Codex | `$prime` | `$prime search our policies for password requirements` |
| OpenCode | Ask it to use `prime` | `Use the prime skill to review this design` |
| Cursor | Ask it to use `prime` | `Use the prime skill to analyze this repository` |

## Manual Install Alternative

If the Skills CLI is unavailable, copy the canonical directory at `plugins/prime-security-operator/skills/prime` into the skill directory as a folder named `prime`:

| Client | User skill directory |
|---|---|
| Claude Code | `~/.claude/skills/prime` |
| Codex | `~/.agents/skills/prime` |
| OpenCode | `~/.agents/skills/prime` |
| Cursor | `~/.agents/skills/prime` |

For several clients, keep one copy at `~/.agents/skills/prime` and link `~/.claude/skills/prime` to it for Claude Code. On systems without links, use the client-specific directories. Do not combine manual installation with the Skills CLI or marketplace installation.

## Claude Marketplace Alternative

The existing Claude marketplace remains available for backward compatibility:

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-operator@prime
```

The plugin skill is invoked as `/prime-security-operator:prime` in Claude Code. Install `prime-security-dev@prime` separately only if you need its Claude-specific code guardrails and hooks.

## Plugins

### prime-security-operator

The cross-client Prime API skill. Its only canonical skill source is `plugins/prime-security-operator/skills/prime/SKILL.md`.

### prime-security-dev

Claude-specific code guardrails enforcement through a skill and hooks. It remains version `1.0.0` and is not part of the portable operator installation.

## Structure

```text
plugins/
|-- prime-security-operator/
|   `-- skills/prime/SKILL.md
`-- prime-security-dev/
    |-- skills/prime-code-guardrails/SKILL.md
    |-- hooks/hooks.json
    `-- scripts/
```

## License

MIT
