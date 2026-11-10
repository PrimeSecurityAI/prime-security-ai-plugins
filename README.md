# Prime Security Tools

Plugins, Agent Skills, and an MCP server for working with Prime Security from AI agents: security design reviews, policy search, repository analysis, code reviews, security posture, and AI-assisted security conversations.

## What's Included

| Component | What it does | Clients |
|---|---|---|
| `prime-security-operator` plugin | The `prime` skill plus the Prime MCP server connection | Claude Code, Codex, GitHub Copilot CLI, Cursor |
| `prime-security-dev` plugin | The code guardrails skill plus a session reminder that tells the agent to use it | Claude Code, Codex, GitHub Copilot CLI, Cursor, OpenCode, Pi |
| `prime` skill | Calls the Prime API using its published route documentation | Any Agent Skills client, including OpenCode, Pi, and Copilot agent mode in IDEs |
| Prime MCP server | Exposes Prime as MCP tools | Claude (web, Desktop, mobile), Claude Code, any MCP client |

## Prerequisites

- A Prime Security account.
- HTTPS access to the Prime Security API and GitHub.
- For the `prime` skill's browser login: `python3` 3.9 or later.
- For the skill-only installation: Node.js 22.20.0 or later with `npx`, and HTTPS access to npm.

On first use the `prime` skill opens your browser to log in to Prime Security, so the skill needs a Personal Access Token (PAT) only on machines without a browser. The development guardrails helper reads `PRIME_PAT_TOKEN` or the shared token file. The plugins' MCP connections and the Claude connector log in through the browser; manual MCP configurations read `PRIME_PAT_TOKEN`, see [Configure Credentials](#configure-credentials).

## Plugin Or Skill?

Install the **plugin** for your client when it has one. Use the skill-only installation for clients without plugin support, or where your organization does not allow plugins.

A **skill** is instructions the agent loads when it decides the skill is relevant, or when you invoke it. A **plugin** bundles the skill with the pieces the client runs on its own, and the client's plugin manager keeps them updated together.

| | Plugin | Skill only (`npx skills add`) |
|---|---|---|
| `prime` or `prime-code-guardrails` skill | Included | Included |
| Prime MCP server | Connected | Configure it yourself; see [MCP Server](#mcp-server) |
| Guardrails reminder (dev) | Injected by the client | None: the agent uses the skill only when it chooses to or you invoke it |
| Updates | The client's plugin manager | `npx skills update` |
| Clients | Operator: Claude Code, Codex, GitHub Copilot CLI, Cursor. Dev: also OpenCode and Pi | Any Agent Skills client |

`npx skills add` installs only skills, even from this repository's plugin manifests; it never installs hooks or MCP servers. Install the plugin **or** the skill for a client, never both: duplicate skills make invocation and updates ambiguous.

For development guardrails, follow the [prime-security-dev guide](plugins/prime-security-dev/README.md). The rest of this page covers the operator.

## Install The Operator Plugin

The plugin bundles the `prime` skill and the Prime MCP server, each with its own browser login; see [MCP Server](#mcp-server).

### Claude Code Plugin

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-operator@prime
```

Inside Claude Code, the equivalents are `/plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins` and `/plugin install prime-security-operator@prime`. Invoke the plugin skill as `/prime-security-operator:prime`.

### Codex Plugin

```bash
codex plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
codex plugin add prime-security-operator@prime
```

Start a new session. The Codex marketplace is `.agents/plugins/marketplace.json`. The Codex plugin always connects to `https://api.primesec.ai/mcp`, because Codex does not expand `PRIME_API_URL` in plugin MCP URLs.

### GitHub Copilot CLI Plugin

```bash
copilot plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
copilot plugin install prime-security-operator@prime
```

Copilot CLI reads the Claude marketplace and the operator's `.github/plugin/plugin.json`, which registers the skill and the MCP server. Copilot agent mode in VS Code, Visual Studio, and JetBrains IDEs uses the [skill-only installation](#install-the-skill-only).

### Cursor Plugin

`.cursor-plugin/marketplace.json` lists both plugins. Team admins can import this repository as a team marketplace. For a local install, copy the plugin directory (for example `plugins/prime-security-operator`) to `~/.cursor/plugins/local/<plugin-name>`, then run **Developer: Reload Window**.

### Update Or Remove The Plugin

| Client | Update | Remove |
|---|---|---|
| Claude Code | `claude plugin marketplace update prime && claude plugin update prime-security-operator@prime` | `claude plugin uninstall prime-security-operator@prime` |
| Codex | Refresh or reinstall the reviewed version through the plugin manager | `codex plugin remove prime-security-operator@prime` |
| GitHub Copilot CLI | `copilot plugin update prime-security-operator` | `copilot plugin uninstall prime-security-operator` |
| Cursor (local) | Copy the new plugin directory | Delete `~/.cursor/plugins/local/prime-security-operator` |

Restart the client after updating or removing.

## Install The Skill Only

For OpenCode, Pi, Copilot agent mode in IDEs, and other Agent Skills clients without a Prime plugin. In OpenCode, also [connect the MCP server](#opencode). Without `--agent`, the Skills CLI detects installed clients and asks which to use:

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global
```

For one client, pick its command:

| Client | Command |
|---|---|
| OpenCode | `npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global --agent opencode --yes` |
| Pi | `npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global --agent pi --yes` |
| GitHub Copilot (IDE agent mode) | `npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime --global --agent github-copilot --yes` |

Repeat `--agent` to target several clients in one command. For a controlled rollout, pin a reviewed release tag or full 40-character commit SHA: `PrimeSecurityAI/prime-security-ai-plugins#<sha>`.

The skill-only installation does not connect the MCP server; add it yourself as described in [MCP Server](#mcp-server) if you need it.

When Claude Code and OpenCode are targeted together, OpenCode may log a duplicate-source warning because it scans both `~/.agents/skills` and Claude's compatibility directory. The Skills CLI links both paths to the same canonical installed copy, and OpenCode exposes one `prime` skill.

### Update Or Remove The Skill

```bash
npx skills update prime --global --yes
npx skills remove prime --global
```

`remove` asks which clients to remove the skill from; add `--agent <client> --yes` to choose them non-interactively. Restart a client if it does not detect a newly installed, updated, or removed skill.

### Manual Skill Install

If the Skills CLI is unavailable, copy the canonical directory at `plugins/prime-security-operator/skills/prime` into the skill directory as a folder named `prime`:

| Client | User skill directory |
|---|---|
| Claude Code | `~/.claude/skills/prime` |
| Codex | `~/.agents/skills/prime` |
| GitHub Copilot | `~/.agents/skills/prime` or `~/.copilot/skills/prime` |
| OpenCode | `~/.agents/skills/prime` |
| Cursor | `~/.agents/skills/prime` |
| Pi | `~/.agents/skills/prime` |

For several clients, keep one copy at `~/.agents/skills/prime` and link `~/.claude/skills/prime` to it for Claude Code. On systems without links, use the client-specific directories. Do not combine a manual installation with the Skills CLI or a plugin.

### GitHub Copilot Cloud Agent

The cloud agent has no browser and restricts outbound network access. To use the skill there, add the Prime API host to the repository's Copilot firewall allowlist and provide `PRIME_PAT_TOKEN` as a secret in the repository's `copilot` environment.

## Configure Credentials

No setup is needed on a machine with a browser. When no credential is configured, the skill runs its browser login. After you log in and click **Authorize**, it saves a 30-day token to the token file below. The token appears under **Settings > Access > API Token**, where you can revoke it.

The skill resolves credentials in this order:

1. `PRIME_PAT_TOKEN`
2. `${XDG_CONFIG_HOME:-$HOME/.config}/prime-security/token`

`PRIME_API_URL` is optional and defaults to `https://api.primesec.ai`.

On machines without a browser (SSH, CI, containers), create a PAT under **Settings > Access > API Token > Create Token** instead and set it as the `PRIME_PAT_TOKEN` environment variable of the process that starts your agent, for example from your CI secret store. Never paste a PAT into an agent chat.

The manual MCP configurations below read only `PRIME_PAT_TOKEN`, not the token file. If it is unset, the server rejects the connection with `401`.

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

The plugins connect the server for you, and OpenCode connects it from its configuration below. Log in once through the browser; the client then refreshes the login silently. When the login ends or is revoked, log in again the same way. This connection does not use `PRIME_PAT_TOKEN`.

| Client | Log in |
|---|---|
| Claude Code | Run `/mcp`, select the Prime server, then **Authenticate** |
| Codex | `codex mcp login prime` |
| GitHub Copilot CLI | `/mcp auth prime` |
| Cursor | In **Cursor Settings**, open MCP and log in to `prime` |
| OpenCode | `opencode mcp auth prime` |

### Claude (Web, Desktop, Mobile)

1. Go to **Customize > Connectors**, select **+ Add**, then **Add custom connector**.
2. Enter `https://api.primesec.ai/mcp` as the URL.
3. In the OAuth client settings, use your own OAuth client with Client ID `claude` and no client secret.
4. Connect and sign in with your Prime account.

On Team and Enterprise plans, an organization Owner adds the connector, and each member connects and signs in. The connector is then available in Claude on the web, Desktop, and mobile, and in Claude Code.

### Claude Code

Installing either Claude Code plugin connects the server, using `PRIME_API_URL` when set. Installing both plugins still connects to it once; see [Claude Code Plugin](#claude-code-plugin).

Without a plugin, add it at user scope. This stores the token in your Claude Code configuration:

```bash
claude mcp add --transport http --scope user prime https://api.primesec.ai/mcp --header "Authorization: Bearer $PRIME_PAT_TOKEN"
```

### Codex

The operator Codex plugin connects the server; see [Codex Plugin](#codex-plugin). Without a plugin:

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

For OpenCode 2.x. Add it to `~/.config/opencode/opencode.json`, then run `opencode mcp auth prime`:

```json
{
  "mcp": {
    "servers": {
      "prime": {
        "type": "remote",
        "url": "https://api.primesec.ai/mcp",
        "oauth": {
          "client_id": "prime-opencode"
        }
      }
    }
  }
}
```

On a machine without a browser, replace `"oauth": {...}` with `"headers": {"Authorization": "Bearer {env:PRIME_PAT_TOKEN}"}`.

### GitHub Copilot CLI

The `prime-security-operator` Copilot plugin connects the server; see [GitHub Copilot CLI Plugin](#github-copilot-cli-plugin). Without a plugin, add it at user scope. This stores the token in `~/.copilot/mcp-config.json`:

```bash
copilot mcp add --transport http --header "Authorization: Bearer $PRIME_PAT_TOKEN" prime https://api.primesec.ai/mcp
```

### Cursor

The Cursor plugins connect the server; see [Cursor Plugin](#cursor-plugin). Without a plugin, add it to `~/.cursor/mcp.json`:

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
| Claude Code plugin | `/prime-security-operator:prime` | `/prime-security-operator:prime review this design for security risks` |
| Claude Code skill only | `/prime` | `/prime review this design for security risks` |
| Codex | `$prime` | `$prime search our policies for password requirements` |
| GitHub Copilot | `/prime` | `/prime review this design for security risks` |
| OpenCode | Ask it to use `prime` | `Use the prime skill to review this design` |
| Cursor | Ask it to use `prime` | `Use the prime skill to analyze this repository` |
| Pi | `/skill:prime` | `/skill:prime review this design for security risks` |

## Plugins

### prime-security-operator

The recommended installation of the cross-client Prime API skill for Claude Code, Codex, GitHub Copilot CLI, and Cursor, plus the MCP server connection. Its only canonical skill source is `plugins/prime-security-operator/skills/prime/SKILL.md`.

### prime-security-dev

The `prime-code-guardrails` skill with safe shared credentials and a bundled API helper, packaged with a session reminder for Claude Code, Codex, GitHub Copilot CLI, Cursor, OpenCode, and Pi. Install the plugin for your client, not only the skill, when guardrails should apply to every coding task. Install separately from the operator skill; see the [installation and support guide](plugins/prime-security-dev/README.md).

## Structure

```text
.claude-plugin/marketplace.json      Claude marketplace
.agents/plugins/marketplace.json     Codex marketplace
.cursor-plugin/marketplace.json      Cursor marketplace
package.json                         Pi package (prime-security-dev)
plugins/
|-- prime-security-operator/
|   |-- .claude-plugin/ .codex-plugin/ .cursor-plugin/ .github/plugin/
|   `-- skills/prime/SKILL.md
`-- prime-security-dev/
    |-- .claude-plugin/ .codex-plugin/ .cursor-plugin/ .github/plugin/
    |-- hooks/hooks.json codex.json cursor.json copilot.json
    |-- pi/extension.js
    `-- skills/prime-code-guardrails/   (adapters/opencode.js)
```

## License

MIT
