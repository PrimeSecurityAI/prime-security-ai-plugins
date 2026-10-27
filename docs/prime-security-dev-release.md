# Prime Security Dev 1.2.0 release checklist

This is a release candidate. Do not describe it as customer-certified until the remaining acceptance checks are recorded below. Publishing and customer rollout are separate from implementation.

## Automated and local validation

- [x] Python suite: credentials, origin validation, redirect refusal, pagination completeness, repository identity, safe errors, hook state and payload handling.
- [x] Node suite: OpenCode system/compaction reminders and local edit telemetry.
- [x] Claude plugin and marketplace validation.
- [x] Codex installation from the local marketplace using an isolated `CODEX_HOME`.
- [x] Standalone skill installation into an isolated home includes helpers, references, and adapter resources.
- [x] OpenCode discovers the skill and loads the adapter in an isolated configuration.
- [x] Independent review completed; material findings resolved and covered by tests.

## Customer acceptance before publishing

Run against an authorized test account, with disposable repositories and no production mutations. Record exact client versions, OS, API environment, and result. Do not attach raw policies, PATs, or source to public artifacts.

| Check | Claude Code | Codex | OpenCode |
|---|---|---|---|
| Fresh install and explicit invocation | Pending | Pending | Pending |
| Automatic selection for a coding request | Pending | Pending | Pending |
| Configured PAT: complete policy load and meaningful application | Pending | Pending | Pending |
| Missing/expired PAT: no secret in chat and no false success | Pending | Pending | Pending |
| New task and repository switch: policies reload | Pending | Pending | Pending |
| Compaction/resume: policies reload when context is lost | Pending | Pending | Pending |
| Optional hooks enabled/trusted: reminder and supported edit tracking | Pending | Pending | Pending |
| Optional hooks disabled: explicit standalone workflow still works | Pending | Pending | Pending |
| Update, uninstall, restart: no duplicate skill or broken adapter | Pending | Pending | Pending |

Verify empty-policy accounts separately from unavailable service responses. Test a repository with no Prime registration, a unique SSH/HTTPS match, and duplicate registrations. Run the OS CI matrix before claiming Linux support; Windows adapters are not certified by this release.

## Publication

- [ ] Reconcile version `1.2.0` across Claude, Codex, universal manifest, and both marketplace entries.
- [ ] Confirm supported API contracts and client versions have not drifted.
- [ ] Add an approved brand icon if submitting to a directory that requires one.
- [ ] Tag the reviewed commit and test installation from that immutable reference.
- [ ] Publish/release only after the acceptance matrix passes; roll out to a pilot customer first.
- [ ] For rollback, reinstall the previous reviewed version and remove the optional OpenCode wrapper if reverting to a version without its adapter. Shared token files remain usable by the operator skill.

## Evidence

API documentation was fetched without credentials on 2026-10-27. Installed local CLI versions at implementation start: Claude Code 2.1.311, Codex CLI 0.164.0, OpenCode 1.19.3. Adapter shape checked against the published `@opencode-ai/plugin` 1.19.4 definitions. These observations are not evidence of a live model session applying policies.

Reference documentation:

- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/hooks
- https://developers.openai.com/plugins/build/plugins
- https://code.claude.com/docs/en/hooks
- https://opencode.ai/docs/skills/
- https://opencode.ai/docs/plugins/

Local validation on macOS completed: 20 Python tests and 2 Node tests; Claude skill/plugin/marketplace validation; universal plugin JSON Schema validation; isolated Codex marketplace installation of 1.1.0; Skills CLI 1.7.4 installation targeting all three clients with helper/reference/adapter files preserved; OpenCode 1.19.3 discovery and adapter initialization verified with an isolated wrapper probe. Temporary homes and configurations were removed afterward.

Independent review found an unsanitized HTTP protocol-exception path. `BadStatusLine` and `IncompleteRead` now become static, credential-free errors, with regression tests. Pagination also continues past short pages when completion metadata is absent.

Live authenticated API validation remains pending: the configured origin is `https://api.primesec.dev`, and the helper correctly refused it without explicit custom-origin approval. No authenticated request was sent by that attempted smoke test. No live model sessions, Linux CI jobs, immutable release installs, or public publishing have been performed. Claude directory validation reports a missing optional listing icon; the approved brand asset remains a publication task.

PR preparation: rebased onto upstream MCP/browser-login changes and retained the existing `.mcp.json`. Candidate version advanced to 1.2.0 because upstream already uses 1.1.0. The helper approval boundary is documented separately from client-managed MCP connections.
