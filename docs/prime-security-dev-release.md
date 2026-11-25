# Prime Security Dev release checklist

Proposed unpublished version: **1.5.0-alpha.5**. Record the immutable commit, client/model versions, OS and API origin with results. Operator behavior and version stay unchanged.

## What changed in alpha.5

Hooks push context instead of asking for a whole-repository dump: `prime_hooks.py session` injects a small security map at session start, resume and compaction, and `prime_hooks.py file` injects one security card per file read or edited, once per session. They use the hook token (`PRIME_PAT_TOKEN`, then the token file), send it only to the default or an approved origin, and fall back to the static reminder. The skill uses the new MCP tools `get_developer_security_map`, `get_developer_security_files` and `get_developer_security_details`; `get_developer_guardrails` and `get_developer_security_context` are gone.

## What changed in alpha.4

The skill is renamed `prime-developer-security` and calls the Prime MCP server's developer tools instead of the bundled Python REST helper, which is removed. The Codex and Copilot plugins now connect the MCP server like the Claude Code and Cursor plugins. The version advances because native Claude updates report an unchanged version as up to date and keep the cached skill.

## Local checks

- `python3 -m unittest discover -s tests -v`, `node --test tests/opencode.test.mjs tests/pi.test.mjs`, and `claude plugin validate` for dev, operator and root marketplace.
- Dev manifests, marketplaces and the Pi `package.json` share one version; each plugin MCP server logs in with its client id.

## Real-client acceptance

Deploy front-service with the developer MCP tools and the `developer-security` flag on for the test account first. For each client:

1. Install the plugin (or skill plus manual MCP for OpenCode/Pi), log in to the MCP server, and confirm the `get_developer_*` tools are listed. Configure the hook token and, for a dev origin, approve it with `prime_hooks.py --approve-origin`; trust the hooks in Codex with `/hooks`. For dev, launch Claude Code with `PRIME_API_URL` set to the dev front-service origin; other clients need a manual MCP entry for that origin.
2. Confirm the security map reaches the model at startup, resume and compaction (the reminder without a token), and that a card arrives once for each file the agent reads or edits, within the client's hook context limit.
3. In a connected repository, ask for a change: the agent uses the pushed map and cards, calls `get_developer_security_files` for uncarded files and `get_developer_security_details` only for touched items, applies guardrails and names them. In an unconnected repository it discloses account-wide guardrails.
4. Ask for a plan review: `create_developer_security_plan`, polling `get_developer_security_plan` until `COMPLETED`, findings presented, plan revised; the review appears in the Prime UI.
5. Ask for a PR review: `start_developer_pr_review` starts Prime's PR review flow, `get_developer_pr_review` is polled to `COMPLETED`, and the agent reports Prime's issues without reviewing the diff itself.
6. Confirm a mitigation report is sent only after explicit developer confirmation.
7. Turn the `developer-security` flag off (403) and one feature off in account settings (409 `developer_feature_disabled`): the agent tells the user once and continues ordinary coding without other API workarounds.
8. Validate update/uninstall/restart without duplicate skills or MCP servers, including when the operator plugin is also installed.

## Publication

Publish only the client subset that passed acceptance, pinned to a reviewed immutable reference. Older backends without the developer MCP tools cannot serve this version.
