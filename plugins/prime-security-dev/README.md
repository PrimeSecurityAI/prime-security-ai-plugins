# prime-security-dev

Load your organization's security guardrails before coding in **Claude Code, Codex, GitHub Copilot, Cursor, OpenCode, or Pi**. The proposed unpublished `1.5.0-alpha.1` uses account-controlled `/dev` guidance, bounded stored safeguards/KB and recoverable explicit plan reviews. The helper requires Python 3.9+. Dedicated reviewer support must pass a separate real-client release gate for each advertised host; automatic Claude plan capture remains disabled.

This is policy guidance, not a sandbox or compliance certification. Optional client integrations add lifecycle reminders; they do not prove policies were applied. No edit telemetry is collected.

## Requirements

- Python 3.9+ on macOS/Linux available as `python3` in the client's execution environment.
- A Prime Security PAT and HTTPS access to the configured Prime API.
- Git for optional repository context.
- Node.js 22.20+ and `npx` when using the Skills CLI.
- Start with macOS/Linux for the optional adapters. Windows host integration has not been validated.

## Plugin or skill?

Install the **plugin** for your client. It contains the `prime-code-guardrails` skill plus a reminder that the client injects at session start, so the agent loads your guardrails before changing code without being asked.

The **skill alone** does not run automatically. The agent uses it only when it decides the skill is relevant or when you invoke it explicitly. Use the skill alone only for clients without a plugin, such as Copilot agent mode in IDEs, or when you will always invoke it yourself.

| Client | Plugin reminder | Skill only |
|---|---|---|
| Claude Code | Session start, resume, compaction | Yes |
| Codex | Session start, resume, compaction | Yes |
| GitHub Copilot CLI | Session start and resume | Yes (also IDE agent mode) |
| Cursor | Session start | Yes |
| OpenCode 2.x | Every model request | Yes |
| Pi | Every agent run | Yes |

Reminders make no API requests and do not load policies; hook commands time out after five seconds. Ordinary user prompts do not add transcript reminders.

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

Start a new session and review/trust the plugin hooks through the client's hook trust flow. Installing a plugin does not automatically trust its hooks. The Codex manifest selects `hooks/codex.json`.

### GitHub Copilot CLI

```bash
copilot plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
copilot plugin install prime-security-dev@prime
```

Copilot reads `.github/plugin/plugin.json`, which registers the skill and `hooks/copilot.json` without an MCP server. Copilot has no post-compaction hook event, so after a long session invoke the skill again if policy text was compacted away.

### Cursor

The plugin bundles the same skill plus a session-start reminder from `hooks/cursor.json`. Install it as described in [Cursor Plugin](../../README.md#cursor-plugin).

### OpenCode

The adapter targets OpenCode 2.x (`@opencode/cli`); OpenCode 1.x plugins use a different API and are not supported. OpenCode 2.x has no plugin marketplace, so install the skill, then add a local plugin file.

1. Install the skill: `npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime-code-guardrails --global --agent opencode --yes`.
2. Create `~/.config/opencode/plugins/prime-security-dev.js` (or the corresponding directory under your `XDG_CONFIG_HOME`):

   ```javascript
   export { default } from "/absolute/path/to/prime-code-guardrails/adapters/opencode.js";
   ```

   Replace the absolute path with the installed skill location, normally `~/.agents/skills/prime-code-guardrails` expanded to an absolute path. Preserve the skill's `adapters/package.json`. If you set up the earlier 1.x adapter, replace its `export { PrimeSecurityDev } ...` line with this one.
3. Restart OpenCode.

The adapter is self-contained JavaScript with no npm dependencies, and it does not run Python at startup. It uses the `context` session hook to add one reminder to each freshly built system prompt, including tool continuations and the first request after compaction, without appending messages to the conversation history.

### Pi

```bash
pi install git:github.com/PrimeSecurityAI/prime-security-ai-plugins
```

The repository root is a Pi package that loads the `prime-code-guardrails` skill and `pi/extension.js`. The extension adds a `prime_guardrails` system-prompt section before each agent run while the skill is enabled. Pi patches only changed sections, so the reminder does not invalidate the prompt cache. Append `@<tag>` or `@<full-commit-sha>` to pin a reviewed release, and add `-l` for a project installation. Do not also install the skill for Pi with `npx skills`.

## Install the skill only

```bash
npx skills add PrimeSecurityAI/prime-security-ai-plugins --skill prime-code-guardrails --global
```

Without `--agent`, the Skills CLI detects installed clients and asks which to use. For one client, add `--agent <client> --yes` with `claude-code`, `codex`, `github-copilot`, `cursor`, `opencode`, or `pi`; repeat `--agent` for several. Omit `--global` for a project installation. Restart clients if discovery does not refresh. For controlled rollouts, pin a reviewed release tag or full 40-character commit SHA: `PrimeSecurityAI/prime-security-ai-plugins#<sha>`. Short commit IDs are not supported by the Skills CLI.

Manual alternative: copy the **entire** `skills/prime-code-guardrails` directory to `~/.agents/skills/prime-code-guardrails` for Codex/Copilot/OpenCode/Cursor/Pi or `~/.claude/skills/prime-code-guardrails` for Claude. Keep one canonical copy when sharing across clients. Do not copy only `SKILL.md`.

## Configure credentials

Follow [the terminal-only setup instructions](skills/prime-code-guardrails/references/setup.md). Credentials resolve from `PRIME_PAT_TOKEN`, then the private shared token file. Never paste a PAT into chat or put it in a repository.

`PRIME_API_URL` is optional. Custom HTTPS origins support one-time invocation approval or saved trust for an exact origin, as described in the setup instructions. No client settings files are edited by the skill.

## Use it

| Client | Explicit invocation |
|---|---|
| Claude standalone | `/prime-code-guardrails implement this change using our policies` |
| Claude plugin | `/prime-security-dev:prime-code-guardrails implement this change` |
| Codex | `$prime-code-guardrails implement this change using our policies` |
| GitHub Copilot | `/prime-code-guardrails implement this change using our policies` |
| OpenCode | `Use the prime-code-guardrails skill before implementing this change` |
| Cursor | `/prime-code-guardrails implement this change using our policies` |
| Pi | `/skill:prime-code-guardrails implement this change using our policies` |

The description also allows automatic skill selection, but selection is model-dependent. The plugin reminders make selection reliable; without a plugin, add a repository instruction in the client's supported rules file requiring `prime-code-guardrails` before code changes, or invoke it explicitly.

The agent saves complete policy JSON to a private temporary file using `--output`, reads all policies in bounded chunks, applies relevant policies, and reports the titles that influenced its changes. Before each meaningful coding action, including a continued implementation step, it checks fresh effective settings. It checks again before every guidance/context/plan/retry/completion and after HTTP 409. Guidance and plan controls are independent. Confirmed disable discards reusable guidance; settings failure pauses security operations while ordinary coding continues. Empty policies and failed loading are different outcomes.

## MCP connection

The Claude and Cursor plugins connect to the Prime MCP server; see [MCP configuration](../../README.md#mcp-server). The MCP login is separate from the helper's PAT. The helper's exact-origin approval applies to its requests. Independently configured MCP tools use the client's permissions; managed developer features always use `/dev`, including recovery.

## Data and limitations

- The helper reads managed guidance; explicit plan registration uploads Markdown and completion uploads review JSON. Scope/context requests send normalized remote, IDs, relative paths and intent. It starts no scans and does not modify account settings.
- Policies and summaries enter the agent's context and are subject to your AI provider's data handling. `--output` saves a task artifact, not an automatically reused policy cache. Use a private temporary directory outside the repository and delete the artifact after the task.
- Reminders are advisory; there is no “loaded” marker that could falsely certify success.
- Unregistered or ambiguous scope requires explicit connect/select and retry; unsupported remotes require explicit registered scope. The helper never guesses a module or falls back to account-wide policies.

## Update and remove

For the standalone skill:

```bash
npx skills update prime-code-guardrails --global --yes
npx skills remove prime-code-guardrails --global
```

`remove` asks which clients to remove the skill from; add `--agent <client> --yes` to choose them non-interactively.

For a commit-pinned installation, `skills update` keeps that pin. To advance it, repeat the install command with the next reviewed full commit SHA.

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

Removing the plugin/skill does not delete shared credentials, saved origin approvals, task output files, or private pending receipts under `${XDG_STATE_HOME:-$HOME/.local/state}/prime-security/developer-receipts`. Before removal, explicitly resume pending submissions or use `resume --receipt <path> --abandon` to remove their local payloads. Server history requires separate authorized deletion. Delete the Prime token file only when no other Prime integration needs it. Existing legacy `.claude/state/guardrails-loaded-*` markers are no longer consulted; they can be removed after upgrading. Older versions' `~/.local/state/prime-security` edit logs are no longer produced or consumed; remove them if no longer needed.

## Release validation

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test tests/opencode.test.mjs tests/pi.test.mjs
for p in plugins/prime-security-dev plugins/prime-security-operator .; do claude plugin validate "$p"; done
```

See [the release checklist](../../docs/prime-security-dev-release.md) for required acceptance checks; the PR records results and tested versions. The presence of adapter code alone is not a claim of end-to-end client certification.

## License

MIT

## Managed alpha compatibility

`1.5.0-alpha.1` is proposed and unpublished. It requires the reviewed `/dev` backend; an older server or settings failure has no generic API fallback. Older plugin versions cannot honor account controls, so rollback loses that behavior. Dev guardrails defaults on and Security plan defaults off; use effective settings, including internal plan availability restrictions.

Explicit plan review registers immutable Markdown/context, invokes one separate host reviewer, validates its typed findings and records **Developer-agent review · Client-reported advisory**. No self-review substitute or security approval is implied. See [the managed workflow contract](skills/prime-code-guardrails/references/api-contract.md) for commands and exact-byte restart/credential-renewal recovery. All adapters remain reminders until their separate execution/capture gates pass. Server records remain until owner/admin deletion; backup retention is separate. Operator behavior and version are unchanged.
