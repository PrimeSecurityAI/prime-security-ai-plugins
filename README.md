# Prime Security Tools

Agent Skills, Claude Code plugins, and an MCP server for working with Prime Security from AI agents: security design reviews, policy search, repository analysis, code reviews, security posture, and AI-assisted security conversations.

## What's Included

| Component | What it does | Clients |
|---|---|---|
| `prime` skill | Calls the Prime API using its published route documentation | Claude Code, Codex, OpenCode, Cursor |
| Prime MCP server | Exposes Prime as MCP tools | Claude (web, Desktop, mobile), Claude Code, any MCP client |
| `prime-security-operator` plugin | The `prime` skill and the MCP server connection | Claude Code |
| `prime-security-dev` plugin | Code guardrails skill and hooks, and the MCP server connection | Claude Code |

## Prerequisites

- A Prime Security account and a Personal Access Token (PAT). Create one in the Prime Security platform under **Settings > Access > API Token > Create Token**.
- HTTPS access to the Prime Security API.
- For the Skills CLI installation only: Node.js 22.20.0 or later with `npx`, and HTTPS access to GitHub and npm.

## Install The Portable Skill

Use the Skills CLI for the primary cross-client installation:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global
```

For a non-interactive installation targeting all four supported clients explicitly:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global --agent claude-code --agent codex --agent opencode --agent cursor --yes
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

The skill resolves credentials in this order:

1. `PRIME_PAT_TOKEN`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`

`PRIME_API_URL` is optional and defaults to `https://api.primesec.ai`.

Never paste a PAT into an agent chat. To store it without terminal echo or shell history from Bash:

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

The MCP configurations below read only the `PRIME_PAT_TOKEN` environment variable, not the token file. Export it in the shell profile or environment that starts your agent, for example from the token file:

```bash
export PRIME_PAT_TOKEN="$(cat "${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token")"
```

If it is unset, the server rejects the connection with `401`.

## MCP Server

Prime exposes a remote MCP server over Streamable HTTP at `https://api.primesec.ai/mcp`. Its tools act as the signed-in user, within that user's account and permissions.

| Tools | Purpose |
|---|---|
| `get_design_docs`, `get_design_doc_by_id` | Security design reviews |
| `get_repositories`, `get_repository_by_id`, `get_repository_code_issues` | Code repositories and their findings |
| `get_posture_metrics` | Security posture metrics |
| `get_all_products` | Products |
| `start_prime_ai_conversation`, `ask_prime_ai`, `get_prime_ai_answer` | Ask Prime's security AI a free-form question, then poll `get_prime_ai_answer` until the answer is complete |
| `search_prime_operations`, `call_prime_operation` | Find and run any other Prime API operation |

`call_prime_operation` can run operations that change data in your Prime account. Review those calls before approving them.

### Claude (Web, Desktop, Mobile)

1. Go to **Customize > Connectors**, select **+ Add**, then **Add custom connector**.
2. Enter `https://api.primesec.ai/mcp` as the URL.
3. In the OAuth client settings, use your own OAuth client with Client ID `claude` and no client secret.
4. Connect and sign in with your Prime account.

On Team and Enterprise plans, an organization Owner adds the connector, and each member connects and signs in. The connector is then available in Claude on the web, Desktop, and mobile, and in Claude Code.

### Claude Code

Installing either Claude Code plugin connects the server, using `PRIME_PAT_TOKEN` and `PRIME_API_URL` when set. Installing both plugins still connects to it once.

Without a plugin, add it at user scope. This stores the token in your Claude Code configuration:

```bash
claude mcp add --transport http --scope user prime https://api.primesec.ai/mcp --header "Authorization: Bearer $PRIME_PAT_TOKEN"
```

### Codex

```bash
codex mcp add prime --url https://api.primesec.ai/mcp --bearer-token-env-var PRIME_PAT_TOKEN
```

Or add it to `~/.codex/config.toml`:

```toml
[mcp_servers.prime]
url = "https://api.primesec.ai/mcp"
bearer_token_env_var = "PRIME_PAT_TOKEN"
```

### OpenCode

Add it to `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "prime": {
      "type": "remote",
      "url": "https://api.primesec.ai/mcp",
      "oauth": false,
      "headers": {
        "Authorization": "Bearer {env:PRIME_PAT_TOKEN}"
      }
    }
  }
}
```

### Cursor

Add it to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "prime": {
      "url": "https://api.primesec.ai/mcp",
      "headers": {
        "Authorization": "Bearer ${env:PRIME_PAT_TOKEN}"
      }
    }
  }
}
```

### Other MCP Clients

Connect to `https://api.primesec.ai/mcp` over Streamable HTTP and send `Authorization: Bearer <PAT>`. Keep the PAT in the client's secret or environment configuration, never in a chat.

## Skill Invocation

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

The Claude marketplace remains available for backward compatibility, and its plugins also connect the MCP server:

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-operator@prime
```

Inside Claude Code, the equivalents are `/plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins` and `/plugin install prime-security-operator@prime`.

The plugin skill is invoked as `/prime-security-operator:prime` in Claude Code. Install `prime-security-dev@prime` separately only if you need its code guardrails and hooks.

## Plugins

### prime-security-operator

The cross-client Prime API skill packaged for Claude Code, plus the MCP server connection. Its only canonical skill source is `plugins/prime-security-operator/skills/prime/SKILL.md`.

### prime-security-dev

Claude Code-only code guardrails: the `prime-code-guardrails` skill, a `UserPromptSubmit` hook that has the agent load the guardrails once per session, a `PostToolUse` hook that records the files edited in the session, and the MCP server connection. It is versioned independently of the operator plugin and is not part of the portable installation.

## Structure

```text
.claude-plugin/marketplace.json
plugins/
|-- prime-security-operator/
|   |-- .claude-plugin/plugin.json
|   |-- .mcp.json
|   `-- skills/prime/SKILL.md
`-- prime-security-dev/
    |-- .claude-plugin/plugin.json
    |-- .mcp.json
    |-- skills/prime-code-guardrails/SKILL.md
    |-- hooks/hooks.json
    `-- scripts/
```

## License

MIT
