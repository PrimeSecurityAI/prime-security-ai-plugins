# prime-security-operator

The portable `prime` Agent Skill interacts with Prime Security for security design reviews, knowledge base and policy search, repository analysis, code reviews, and AI-assisted security conversations.

## Prerequisites

- Node.js 22.20.0 or later with `npx`
- Claude Code, Codex, OpenCode, or Cursor
- A Prime Security account and PAT
- HTTPS access to GitHub, npm, and the Prime Security API

Create a PAT under **Settings > Access > API Token > Create Token** in the Prime Security platform.

## Install

The primary cross-client installation is:

```bash
npx skills add https://github.com/PrimeSecurityAI/prime-security-ai-plugins/tree/main/plugins/prime-security-operator/skills/prime --global
```

Use this command to target all supported clients without prompts:

```bash
npx skills add https://github.com/PrimeSecurityAI/prime-security-ai-plugins/tree/main/plugins/prime-security-operator/skills/prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Choose one installation path. Do not install both this plain skill and the Claude marketplace plugin in the same client.

When Claude Code and OpenCode are targeted together, OpenCode may log a duplicate-source warning because it scans both `~/.agents/skills` and Claude's compatibility directory. Both paths resolve to the Skills CLI's same canonical copy, and OpenCode exposes one `prime` skill.

### Update Or Remove

```bash
npx skills update prime --global --yes
npx skills remove prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
```

Restart a client if it does not detect the change.

## Credentials

Credential precedence is:

1. `PRIME_PAT_TOKEN`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`

`PRIME_API_URL` is optional and defaults to `https://api.primesec.ai`.

Never paste a PAT into chat. Store it from Bash using hidden input and restrictive permissions:

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

On other systems, use hidden terminal input and grant only the current user access to the same logical token path. Never print or log the token.

## Invocation

Natural-language requests can activate the skill automatically.

| Client | Explicit invocation | Example |
|---|---|---|
| Claude Code | `/prime` | `/prime review this design for security risks` |
| Codex | `$prime` | `$prime search policies for password requirements` |
| OpenCode | Ask it to use `prime` | `Use the prime skill to review this design` |
| Cursor | Ask it to use `prime` | `Use the prime skill to analyze this repository` |

The skill fetches `/llm.txt` as a route-group index, loads only relevant `/llm/<group>` documentation, follows each endpoint's authentication contract, and polls only documented asynchronous responses.

## Pre-Approving Network Access

The skill needs outbound HTTPS access to `*.primesec.*` (or your configured `PRIME_API_URL` host). There is no shared setting for this across clients — each has its own allowlist mechanism, so configure the ones you use:

| Client | Where | Notes |
|---|---|---|
| Claude Code | `permissions.allow`/`deny` in `settings.json` | Allow `WebFetch(domain:*.primesec.*)`. Do not try to domain-scope `Bash(curl ...)` — Claude Code's own docs note it's bypassable via redirects, protocol swaps, or flags before the URL; deny `Bash(curl *)` and `Bash(wget *)` instead. |
| OpenCode | `permission` in `opencode.json`/`opencode.jsonc` | Both `bash` and `webfetch` support per-pattern rules, e.g. `"webfetch": {"https://*.primesec.*/*": "allow"}`. |
| Cursor | `.cursor/permissions.json` / Agent settings | `terminalAllowlist` prefix-matches the command name only, not the URL — there is no domain-scoped fetch allowlist. Leave `curl` in ask-mode unless you accept that limitation. |
| Codex CLI | `~/.codex/config.toml` | Network access is controlled via `sandbox_mode` / `[sandbox_workspace_write] network_access`, with proxy-based domain allowlisting on some versions. Check the current Codex config reference for exact field names before relying on it. |

Skipping this is safe: without it, the client just prompts for approval on the skill's requests as usual.

## Manual Install Alternative

Copy the canonical `skills/prime` directory to the client user directory as a folder named `prime`:

| Client | User skill directory |
|---|---|
| Claude Code | `~/.claude/skills/prime` |
| Codex | `~/.agents/skills/prime` |
| OpenCode | `~/.agents/skills/prime` |
| Cursor | `~/.agents/skills/prime` |

For multiple clients, keep one copy at `~/.agents/skills/prime` and link it into `~/.claude/skills/prime`. Do not combine manual, Skills CLI, and marketplace installations.

## Claude Marketplace Alternative

For backward-compatible Claude Code plugin installation:

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-operator@prime
```

Invoke the plugin skill as `/prime-security-operator:prime`. Do not also install the plain `/prime` skill.

## Canonical Source

`skills/prime/SKILL.md` is the only canonical Prime operator skill. There is no root-level copy or installer script.

## License

MIT
