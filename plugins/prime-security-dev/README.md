# prime-security-dev

Load your organization's security guardrails before coding in **Claude Code, Codex, GitHub Copilot, Cursor, OpenCode, or Pi**. The proposed unpublished `1.5.0-alpha.1` checks account capabilities on each invocation. Explicit false preserves stable account-wide guardrails with optional repository summary and no Git/connected-repository requirement; true uses account-controlled `/dev` guidance, canonical scoped guidance/context, saved advisory plan reviews, explicit PR requests and mitigation reporting. The helper requires Python 3.9+. Dedicated reviewer support must pass a separate real-client release gate for each advertised host; automatic Claude plan capture remains disabled.

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

For alpha dev acceptance, set `PRIME_API_URL="$publicF"` to the verified, user-authorized HTTPS dev front-service origin in the environment launching the client and pass `--allow-origin "$publicF"` on every helper invocation. The distributed default origin remains unchanged. Custom origins support per-invocation approval or explicitly saved trust, as described in setup. The skill does not edit client settings.

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

The agent saves complete policy JSON to a private temporary file using `--output`, reads all policies in bounded chunks, applies relevant policies, and reports the titles that influenced its changes. Before each meaningful coding action, including a continued implementation step, it checks `capabilities`. Only explicit false selects stable account-wide guidance; no advanced commands are available in that mode. Missing/malformed/auth-failed capabilities stop security work. With capabilities enabled, it checks fresh settings (`dev_guardrails_enabled`, `security_plan_enabled`). Gated guidance/context/register/save operations read settings again; reviewer dispatch also requires a fresh host check. HTTP 409 pauses the operation and refreshes settings without replay. Guidance and plan controls are independent. Confirmed disable discards reusable guidance; settings failure pauses security operations while ordinary coding continues. Empty policies and failed loading are different outcomes.

## MCP connection

The Claude and Cursor plugins connect to the Prime MCP server; see [MCP configuration](../../README.md#mcp-server). The MCP login is separate from the helper's PAT. The helper's exact-origin approval applies to its requests. Independently configured MCP tools use the client's permissions; managed developer features always use `/dev`, including recovery.

## Data and limitations

- The helper reads account-wide policies and optional repository summaries in stable mode, or scoped guidance in managed mode; explicit plan registration uploads Markdown and review saving uploads JSON. Scope/context requests send canonical code references and intent; source files and credential-bearing remotes are not uploaded. Explicit PR-review requests ask CMS to start/reuse its job; the accepted job ID does not establish review completion. Explicit outcome reporting records only developer-confirmed issue IDs from the original context. The helper does not modify account settings.
- Policies and summaries enter the agent's context and are subject to your AI provider's data handling. `--output` saves a task artifact, not an automatically reused policy cache. Use a private temporary directory outside the repository and delete the artifact after the task.
- Reminders are advisory; there is no “loaded” marker that could falsely certify success.
- In managed mode, supported GitHub/GitLab/Bitbucket Cloud remotes derive canonical repository identity locally, preserving spelling and GitLab subgroups. Uploaded/self-hosted scope requires explicit organization/repository/platform. The server resolves connected repositories/modules; the helper never guesses module IDs. Revisions are explicit or use the server default branch.

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

Removing the plugin/skill preserves shared credentials, saved origin approvals and task artifacts. Legacy files under `${XDG_STATE_HOME:-$HOME/.local/state}/prime-security/developer-receipts` are no longer consumed or modified; explicitly inspect/remove only old task-owned files you no longer need. Server history requires authorized deletion. Delete the shared token only when no other integration needs it. Legacy `.claude/state/guardrails-loaded-*` markers and older edit logs are no longer consulted.

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

`1.5.0-alpha.1` remains proposed and unpublished. It requires GET `/dev/capabilities` returning an exact boolean `developer_security_enabled`. False selects the existing stable policy loader, including optional repository metadata; true requires the current canonical `/dev` backend. Dev guardrails defaults on and Security plan defaults off; their persisted booleans are independent. Older servers or capability failures stop security work. Managed API/settings failures never trigger stable mode.

The direct plan sequence is register → GET normalized Markdown/snapshot → one actual separate host reviewer → save advisory with server `saved_at` → requested history/delete. Every registration creates another row and fresh context; review PUT replaces the result. After uncertain writes inspect history before explicitly repeating them. Guidance can change while a registered plan remains reviewable with plans enabled. See [the workflow contract](skills/prime-code-guardrails/references/api-contract.md) for exact commands, reviewer JSON, PR acceptance, outcomes and recovery.

Local Python/Node tests cover the helper's synthetic HTTP contract and reminder adapters; manifest validation covers packaging. Earlier Claude/Codex managed-workflow acceptance is historical evidence in the release checklist; this capability-selection rollout has not passed fresh native-host acceptance. OpenCode, Cursor, Copilot and Pi have their own pending real-client gates. Automatic Claude plan capture remains disabled. No self-review or security approval is implied. Server records remain until owner/admin deletion; backup retention is separate. Operator behavior/version is unchanged.
