# prime-security-dev

Load your organization's security guardrails before coding in **Claude Code, Codex, or OpenCode**. The portable `prime-code-guardrails` skill fetches current policies and optional repository architecture context, then guides implementation and diff review.

This is policy guidance, not a sandbox or compliance certification. Optional client integrations add lifecycle reminders; they do not prove policies were applied. No edit telemetry is collected.

## Requirements

- Python 3.10+ available as `python3` in the client's execution environment.
- A Prime Security PAT and HTTPS access to the configured Prime API.
- Git for optional repository context.
- Node.js 22.20+ and `npx` when using the Skills CLI.
- Start with macOS/Linux for the optional adapters. Windows host integration has not been validated.

## Install the portable skill

Choose standalone skill installation **or** a native plugin for a given client. Installing both duplicates the skill. The standalone skill includes its Python helper and references but does not register lifecycle hooks.

```bash
npx skills add https://github.com/PrimeSecurityAI/prime-security-ai-plugins/tree/main/plugins/prime-security-dev/skills/prime-code-guardrails --global --agent claude-code --agent codex --agent opencode --yes
```

Omit unwanted `--agent` options. Omit `--global` for a project installation. Restart clients if discovery does not refresh. For controlled rollouts, replace `main` in the URL with your reviewed release tag or full 40-character commit SHA. Short commit IDs are not supported by the Skills CLI.

Manual alternative: copy the **entire** `skills/prime-code-guardrails` directory to `~/.agents/skills/prime-code-guardrails` for Codex/OpenCode or `~/.claude/skills/prime-code-guardrails` for Claude. Keep one canonical copy when sharing across clients. Do not copy only `SKILL.md`.

Cursor is not certified for this development skill in this release. The operator skill's Cursor support is unchanged. This Codex marketplace entry intentionally packages dev only; use the separate operator installation when needed.

## Configure credentials

Follow [the terminal-only setup instructions](skills/prime-code-guardrails/references/setup.md). Credentials resolve from `PRIME_PAT_TOKEN`, then the private shared token file. Never paste a PAT into chat or put it in a repository.

`PRIME_API_URL` is optional. Custom HTTPS origins support one-time invocation approval or saved trust for an exact origin, as described in the setup instructions. No client settings files are edited by the skill.

## Use it

| Client | Explicit invocation |
|---|---|
| Claude standalone | `/prime-code-guardrails implement this change using our policies` |
| Claude plugin | `/prime-security-dev:prime-code-guardrails implement this change` |
| Codex | `$prime-code-guardrails implement this change using our policies` |
| OpenCode | `Use the prime-code-guardrails skill before implementing this change` |

The description also allows automatic skill selection, but selection is model-dependent. For team workflows, add a repository instruction in the client's supported rules file requiring `prime-code-guardrails` before code changes, or use the optional reminders below. Explicit invocation is the most direct way to request it.

The agent saves complete policy JSON to a private temporary file using `--output`, reads all policies in bounded chunks, applies relevant policies, and reports the titles that influenced its changes. Follow-up messages reuse policies within the ongoing task. It reloads for a new independent task, repository/account change, or loss of policy context. Empty policies and failed loading are different outcomes; failed loading never authorizes proceeding as if there were no requirements.

## Optional Claude plugin

```bash
claude plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
claude plugin install prime-security-dev@prime
```

This bundles the same skill plus session-start/resume/compaction reminders. Ordinary user prompts do not add reminders. Hook timeouts are five seconds. No API requests run inside hooks.

## Existing MCP connection

The Claude plugin retains its `.mcp.json` connection to the Prime MCP server. See [MCP configuration](../../README.md#mcp-server) for the tools and other clients. MCP authentication reads `PRIME_PAT_TOKEN` from the client environment, independently of the helper's token-file fallback. The helper's custom-origin approval and read-only behavior apply to the helper, not to independently configured MCP tools; review MCP destinations and calls through the client's permissions.

## Optional Codex plugin

For Codex CLI versions with plugin support:

```bash
codex plugin marketplace add PrimeSecurityAI/prime-security-ai-plugins
codex plugin add prime-security-dev@prime
```

Start a new session and review/trust the plugin hooks through the client's hook trust flow. Installing a plugin does not automatically trust its hooks. The Codex manifest selects `hooks/codex.json`, which handles session-start/resume/compaction reminders without tracking tool calls. Standalone skills remain available where plugin hooks are unsupported.

## Optional OpenCode adapter

After installing the standalone skill, add a small local plugin file at `~/.config/opencode/plugins/prime-security-dev.js` (or the corresponding directory under your `XDG_CONFIG_HOME`):

```javascript
export { PrimeSecurityDev } from "/absolute/path/to/prime-code-guardrails/adapters/opencode.js";
```

Replace the absolute path with the canonical installed skill location, normally `~/.agents/skills/prime-code-guardrails` expanded to an absolute path. Preserve the skill's `adapters/package.json`. The adapter is self-contained JavaScript; it does not run Python at startup. Python is required when the agent runs the API helper. Restart OpenCode.

The adapter includes one reminder in each freshly built OpenCode system prompt, including tool continuations and post-compaction requests. It does not append repeated messages to the conversation history. These experimental APIs require revalidation when upgrading OpenCode. No npm runtime dependencies are required.

## Data and limitations

- The helper performs read-only policy/repository requests. It does not upload source, start scans, or modify Prime configuration.
- Policies and summaries enter the agent's context and are subject to your AI provider's data handling. `--output` saves a task artifact, not an automatically reused policy cache. Use a private temporary directory outside the repository and delete the artifact after the task.
- Reminders are advisory; there is no “loaded” marker that could falsely certify success.
- Unregistered, ambiguous, or unsupported repository remotes produce no repository summary. Policies still apply.

## Update and remove

For the standalone skill:

```bash
npx skills update prime-code-guardrails --global --yes
npx skills remove prime-code-guardrails --global --agent claude-code --agent codex --agent opencode --yes
```

For a commit-pinned installation, `skills update` keeps that pin. To advance it, repeat the install command with the next reviewed full commit SHA.

For Claude plugins, use `claude plugin update prime-security-dev@prime` or `claude plugin uninstall prime-security-dev@prime`. For Codex plugins, use the plugin manager to refresh/reinstall the reviewed version, or `codex plugin remove prime-security-dev@prime`. Remove the OpenCode wrapper when removing its skill. Restart affected clients.

Removing the plugin/skill does not delete shared credentials, saved origin approvals, or task output files. Delete the Prime token file only when no other Prime integration needs it. Existing legacy `.claude/state/guardrails-loaded-*` markers are no longer consulted; they can be removed after upgrading. Older versions' `~/.local/state/prime-security` edit logs are no longer produced or consumed; remove them if no longer needed.

## Release validation

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test tests/opencode.test.mjs
claude plugin validate plugins/prime-security-dev
```

See [the release checklist](../../docs/prime-security-dev-release.md) for required acceptance checks; the PR records results and tested versions. The presence of adapter code alone is not a claim of end-to-end client certification.

## License

MIT
