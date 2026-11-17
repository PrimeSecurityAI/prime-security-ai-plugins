# Prime Security Dev release checklist

Proposed unpublished version: **1.5.0-alpha.2**. Record immutable commit, actual client/model versions, OS and verified dev API origin with results. Operator behavior/version stays unchanged. Local checks cover synthetic helper behavior and reminder packaging; the current canonical alpha has no completed real-client certification.

## Local implementation checks

- Run `python3 -m unittest discover -s tests -v`, `node --test tests/opencode.test.mjs tests/pi.test.mjs`, and `claude plugin validate` for dev, operator and root marketplace.
- Run Python tests with an available Python 3.9 interpreter; if unavailable, mark compatibility CI-only rather than deriving it from modern Python.
- Every API invocation reads exact-boolean GET `/dev/capabilities` first. False permits only stable account-wide guidance and optional repository summary, including without Git or connected scope; all advanced commands stop. Invalid/unavailable/auth-failed capabilities and failed core policy/managed requests never select another mode. Optional summary failure preserves valid stable policies. Managed requests use public front-service `/dev`; canonical repository/code references replace numeric repository/module selection. Scoped guardrails uses POST. List filters are explicit canonical trios and queries are encoded.
- Current `dev_guardrails_enabled` and `security_plan_enabled` are independent. Guidance/context need guidance; register/save need plans; PR creation requires the managed capability but neither per-account switch. Settings failures pause new security work while history/get/delete/PR history remain direct only when capability negotiation succeeds as enabled. Capability/auth errors stop without selecting stable mode.
- Synthetic HTTP checks cover register `{id,context_snapshot}`, GET normalized Markdown/snapshot, separate-review JSON citation validation, PUT saved result plus aware `saved_at`, requested history/delete, native PR acceptance/list and explicit context outcomes.
- Optional review arrays default empty. Findings use CMS severity, snapshot evidence/policy IDs and exact evidence code references, including foreign repositories/revisions. Preserve source coverage and **Developer-agent review · Client-reported advisory**.
- Each write sends once. Uncertain registration/save uses history inspection before explicit repetition. Every registration creates another row and fresh context; PUT replaces the result. There is no local recovery state machine.
- Preserve credential precedence, exact approved HTTPS origins, refused redirects, 30-second requests/120-second invocation budget, context/request byte bounds, safe diagnostics, private artifacts and overwrite protection. Keep the tested hidden PAT setup block unchanged.
- Dev manifest/marketplace/package/helper versions agree. Host client/model identifiers are truthful and independent from package versions.

## Real-client acceptance gates

Root owns deployment, dev credentials/browser authorization, installation, actual reviewer execution and live validation. Use an explicit verified `PRIME_API_URL="$publicF"` and `--allow-origin "$publicF"` for every helper invocation. Launch Claude with that same origin so bundled MCP targets dev too. Helper PAT and MCP browser OAuth are separate.

1. Verify matching public `/dev/capabilities` deployment. With explicit false, exercise complete stable guidance without Git and with optional repository summary; verify advanced commands stop and errors never change modes. With true, verify default settings (guidance on/plans off). Install this corrected local checkout through the task-local Claude marketplace; restart and verify actual installed path/version and explicit skill invocation. Preserve unrelated plugins/settings and shared credentials.
2. Exercise settings → scoped guardrails → context → register → GET → **actual separate Claude reviewer** → save → GET/list. Read complete private policies. Check the same review/model/summary/evidence/server `saved_at` in the UI. Preserve actual reviewer invocation/result evidence; reminder discovery and main-agent self-review do not establish this gate.
3. Toggle guidance off/plans on and confirm registration/review works with non-policy context. Toggle both per-account controls off while the managed capability remains enabled; gated work stops while history/get/delete/PR history remain accessible. A changed guidance setting alone does not block saving the registered plan. Reenable only for explicit new work, without replaying a backlog.
4. Exercise fresh/expired/renewed environment/file credentials and exact-origin trust. For uncertain registration/save, inspect server history before choosing an explicit repeated write. Verify server deletion separately from local artifact cleanup and disclose backup retention.
5. Explicitly create a real dev PR review: accepted native job ID → receipt list. Check CMS-owned results through its proper workflow; receipt history is not live job status. Explicitly report an actually addressed issue using the original context UUID and numeric `code_issue.source_entity_id`; verify developer-reported mitigation activity without changing the CMS finding.
6. Verify actual supported owner/admin boundaries and account-closure purge via proper operator/UI flow. Usage/activity/settings mutation are not required helper commands.
7. For every additional host (Codex, OpenCode, Cursor, Copilot, Pi), prove installation/authentication/skill selection and one separate reviewer with truthful client/model before claiming that capability. The targeted Codex result is recorded below; the other additional hosts remain pending. Unsupported reviewers truthfully record `reviewer_unavailable` or leave plans registered.
8. Hooks/adapters are reminders. Prove startup/resume/compaction context reaches each model without accumulating messages. Automatic Claude ExitPlanMode capture is a separate unpassed gate; preserve human approval and verify actual host payloads before implementing it. Windows remains unverified.
9. Validate update/uninstall/restart without duplicates. Remove only task-owned output/review/guidance files while preserving original plans. Legacy receipt files require deliberate user cleanup; shared credentials and approvals persist.

## Publication and rollback

Deploy the rollout backend exposing authenticated GET `/dev/capabilities` before distributing this plugin update. Missing or incompatible capabilities stop security work, including stable guidance; older backends do not support this rollout.

The dev plugin version advances to `1.5.0-alpha.2` because native Claude updates can report an unchanged `1.5.0-alpha.1` as up to date while retaining the previous cached helper and skill. A version increment is required for this native update path. Update through the client and verify its installed version and files; do not manually modify plugin caches. Historical `1.5.0-alpha.1` acceptance below remains evidence for that earlier installation only.

Publish only the proven client subset after installation, authentication, recovery, separate-review and data-retention gates pass. Pin a reviewed immutable release reference. Older plugin/server contracts cannot honor this managed flow; mismatches fail safely without generic fallback. Unit tests and manifests alone do not establish customer release readiness.

## Historical managed-workflow verification, November 17, 2026

These results predate capability selection. They do not establish native-host acceptance of this rollout; fresh flag-off/flag-on acceptance is still required.

The installed `1.5.0-alpha.1` plugin completed the explicit managed workflow against a personal DEV deployment in both clients below. This verifies the named workflow, not full customer certification.

| Client | Verified workflow | Remaining boundaries |
| --- | --- | --- |
| Claude Code `2.1.325` | Installed skill discovery, authenticated settings/guidance/context, one synthetic plan, actual separate read-only reviewer, save, authoritative GET and history | Startup/resume hooks, automatic plan capture, MCP OAuth, expired/renewed credentials, provider PR workflow and browser acceptance were not established |
| Codex CLI `0.169.0` | Native installed skill discovery, authenticated settings/guidance/context, one synthetic plan, native separate reviewer, save, authoritative GET and history; actual model `gpt-6.1-sol` | SessionStart execution and persisted hook trust remain unverified; no automatic-review or separate OS-sandbox guarantee is made |

Both workflows kept account settings unchanged, used explicit approved DEV origins and retained private artifacts. No source scan, PR job or mitigation report was generated. Counts came from actual returned arrays, rather than summed package membership counts. Original evidence scope and stored-analysis limitations were retained.

Codex acceptance used per-run isolation and a narrow reviewer role as test hardening. An ephemeral native launch failed before child creation; a normal persistent continuation reviewed the same registered plan without another registration. The failed launch is not a second review. Ephemeral reviewer execution is not certified by this result.

The target URL must be configured for each host: Claude project environment settings do not configure Codex. Codex can use the project's `shell_environment_policy.set.PRIME_API_URL`, or an explicit inherited environment value; helper invocations still pass the exact matching `--allow-origin`. Never infer that installing the plugin changes its API origin or grants broader permissions.
