# prime-security-dev

Bring Prime Security into coding agents in **Claude Code, Codex, GitHub Copilot, Cursor, OpenCode, or Pi**. The `prime-developer-security` skill uses the Prime MCP server's developer tools:

| Feature | When | MCP tools |
|---|---|---|
| Security map | Session start (hook) or once | `get_developer_security_map` |
| File security cards | Each file read or edited (hook), or before changing it | `get_developer_security_files` |
| Details and guardrail rules | For items the change touches | `get_developer_security_details`, `report_developer_security_context_outcome` |
| Security plan review | On request | `create_developer_security_plan`, `get_developer_security_plan` |
| PR security review | On request | `start_developer_pr_review`, `get_developer_pr_review` |

Plugin hooks push the map and cards automatically and keep them small; the MCP tools are the fallback and give the full text. Version `1.5.0-alpha.5` is an unpublished alpha.

This is policy guidance, not a sandbox or compliance certification. Hooks and reminders are advisory; they do not prove policies were applied. No edit telemetry is collected.

## Requirements

- A Prime Security account with developer security enabled.
- HTTPS access to the Prime API and a browser for the MCP login.
- Git, so the agent can read the repository's `origin` remote.
- `python3` 3.9+ for the Claude Code, Codex, Copilot and Cursor hooks, plus a Prime token for them (see [setup](skills/prime-developer-security/references/setup.md#security-context-hooks)).
- Node.js 22.20+ and `npx` when using the Skills CLI.
- Start with macOS/Linux for the optional adapters. Windows host integration has not been validated.

## Plugin or skill?

Install the **plugin** for your client. It contains the skill, the Prime MCP server connection, and hooks that push the security map and per-file security cards into the agent's context without being asked.

The **skill alone** does not run automatically and does not connect the MCP server. Use it only for clients without a plugin, such as Copilot agent mode in IDEs.

| Client | Plugin hooks | MCP server | Skill only |
|---|---|---|---|
| Claude Code | Map at session start, resume, compaction; cards on Read, Edit, Write | Plugin | Yes |
| Codex | Map at session start, resume, compaction; cards on `apply_patch` | Plugin | Yes |
| GitHub Copilot CLI | Map at session start and resume; cards on view, edit, create | Plugin | Yes (also IDE agent mode) |
| Cursor | Map at session start; cards on Read, Write | Plugin | Yes |
| OpenCode 2.x | Every model request | Manual | Yes |
| Pi | Every agent run | MCP extension | Yes |

Hooks send only the repository identity and relative paths, spend at most three seconds on the network and time out after five; each file gets one card per session. Without a hook token or on any failure, the session hook adds a static reminder and file hooks add nothing. The OpenCode and Pi reminders make no API requests.

Install the plugin **or** the skill for a given client, not both; both together duplicate the skill.

## Install the plugin

### Claude Code

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-dev@prime
```

### Codex

For Codex CLI versions with plugin support:

```bash
codex plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
codex plugin add prime-security-dev@prime
```

Start a new session and trust the plugin hooks with `/hooks`. Installing a plugin does not automatically trust its hooks. The Codex manifest selects `hooks/codex.json`.

### GitHub Copilot CLI

```bash
copilot plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
copilot plugin install prime-security-dev@prime
```

Copilot reads `.github/plugin/plugin.json`, which registers the skill, `hooks/copilot.json` and the MCP server. Copilot has no post-compaction hook event, so after a long session invoke the skill again if the security map was compacted away.

### Cursor

The plugin bundles the skill, the MCP server and the hooks from `hooks/cursor.json`. Install it as described in [Cursor Plugin](../../README.md#cursor-plugin).

### OpenCode

The adapter targets OpenCode 2.x (`@opencode/cli`); OpenCode 1.x plugins use a different API and are not supported. OpenCode 2.x has no plugin marketplace, so install the skill, add a local plugin file, and connect the MCP server.

1. Install the skill: `npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime-developer-security --global --agent opencode --yes`.
2. Create `~/.config/opencode/plugins/prime-security-dev.js` (or the corresponding directory under your `XDG_CONFIG_HOME`):

   ```javascript
   export { default } from "/absolute/path/to/prime-developer-security/adapters/opencode.js";
   ```

   Replace the absolute path with the installed skill location, normally `~/.agents/skills/prime-developer-security` expanded to an absolute path. Preserve the skill's `adapters/package.json`.
3. [Connect the MCP server](../../README.md#opencode) and run `opencode mcp auth prime`.
4. Restart OpenCode.

The adapter is self-contained JavaScript with no npm dependencies. It uses the `context` session hook to add one reminder to each freshly built system prompt, including tool continuations and the first request after compaction, without appending messages to the conversation history.

### Pi

```bash
pi install git:github.com/PrimeSecurityAI/prime-security-ai-plugins
```

The repository root is a Pi package that loads the `prime-developer-security` skill and `pi/extension.js`. The extension adds a `prime_developer_security` system-prompt section before each agent run while the skill is enabled. Pi patches only changed sections, so the reminder does not invalidate the prompt cache. Pi has no built-in MCP client: connect `https://api.primesec.ai/mcp` through a Pi MCP extension. Append `@<tag>` or `@<full-commit-sha>` to pin a reviewed release, and add `-l` for a project installation. Do not also install the skill for Pi with `npx skills`.

## Install the skill only

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime-developer-security --global
```

Without `--agent`, the Skills CLI detects installed clients and asks which to use. For one client, add `--agent <client> --yes` with `claude-code`, `codex`, `github-copilot`, `cursor`, `opencode`, or `pi`; repeat `--agent` for several. Omit `--global` for a project installation. For controlled rollouts, pin a reviewed release tag or full 40-character commit SHA: `PrimeSecurityAI/prime-security-ai-plugins#<sha>`. Then [connect the MCP server](../../README.md#mcp-server) yourself.

## Connect and log in

Follow [setup](skills/prime-developer-security/references/setup.md). Each client logs in to the MCP server through the browser once; the plugin hooks additionally read a Prime token. Only the Claude Code plugin reads `PRIME_API_URL` for a custom origin.

## Use it

| Client | Explicit invocation |
|---|---|
| Claude standalone | `/prime-developer-security implement this change` |
| Claude plugin | `/prime-security-dev:prime-developer-security implement this change` |
| Codex | `$prime-developer-security implement this change` |
| GitHub Copilot | `/prime-developer-security implement this change` |
| OpenCode | `Use the prime-developer-security skill before implementing this change` |
| Cursor | `/prime-developer-security implement this change` |
| Pi | `/skill:prime-developer-security implement this change` |

Ask for the other features in plain words, for example "security-review this plan with Prime" or "get Prime's security review of PR 42". The agent reports Prime's PR review results; it does not review the diff itself.

## Data and limitations

- Tools send repository identity and relative paths; source files are not uploaded. A plan review uploads the plan Markdown and creates a Prime security design review.
- The security map, cards and details enter the agent's context and are subject to your AI provider's data handling.
- Security context is stored analysis; it does not verify uncommitted code.
- Mitigation reports record only developer-confirmed issue ids and do not close findings.
- Hooks and reminders are advisory; there is no "loaded" marker that could falsely certify success.

## Update and remove

For the standalone skill:

```bash
npx skills update prime-developer-security --global --yes
npx skills remove prime-developer-security --global
```

Earlier alphas installed the skill as `prime-code-guardrails`; remove it with `npx skills remove prime-code-guardrails --global`.

For plugins:

| Client | Update | Remove |
|---|---|---|
| Claude Code | `claude plugin marketplace update prime && claude plugin update prime-security-dev@prime` | `claude plugin uninstall prime-security-dev@prime` |
| Codex | Refresh/reinstall the reviewed version through the plugin manager | `codex plugin remove prime-security-dev@prime` |
| GitHub Copilot CLI | `copilot plugin update prime-security-dev` | `copilot plugin uninstall prime-security-dev` |
| Cursor (local) | Copy the new plugin directory | Delete `~/.cursor/plugins/local/prime-security-dev` |
| OpenCode | Update the skill | Delete `~/.config/opencode/plugins/prime-security-dev.js`, then remove the skill |
| Pi | `pi update` (pinned refs stay pinned; reinstall with the next reviewed ref) | `pi remove git:github.com/PrimeSecurityAI/prime-security-ai-plugins` |

Restart affected clients.

## Release validation

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test tests/opencode.test.mjs tests/pi.test.mjs
for p in plugins/prime-security-dev plugins/prime-security-operator .; do claude plugin validate "$p"; done
```

See [the release checklist](../../docs/prime-security-dev-release.md) for real-client acceptance checks.

## License

MIT
