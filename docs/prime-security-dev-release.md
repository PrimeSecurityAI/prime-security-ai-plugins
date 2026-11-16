# Prime Security Dev release checklist

Proposed unpublished version: **1.5.0-alpha.1**. Record immutable commit, actual client/model versions, OS and verified dev API origin with results. Operator behavior/version stays unchanged. Local checks cover synthetic helper behavior and reminder packaging; the current canonical alpha has no completed real-client certification.

## Local implementation checks

- Run `python3 -m unittest discover -s tests -v`, `node --test tests/opencode.test.mjs tests/pi.test.mjs`, and `claude plugin validate` for dev, operator and root marketplace.
- Run Python tests with an available Python 3.9 interpreter; if unavailable, mark compatibility CI-only rather than deriving it from modern Python.
- All feature requests use public front-service `/dev`; canonical repository/code references replace numeric repository/module selection. Scoped guardrails uses POST. List filters are explicit canonical trios and queries are encoded.
- Current `dev_guardrails_enabled` and `security_plan_enabled` are independent. Guidance/context need guidance; register/save need plans; PR creation has no switch gate. Settings/auth failures pause new security work while history/get/delete/PR history remain direct.
- Synthetic HTTP checks cover register `{id,context_snapshot}`, GET normalized Markdown/snapshot, separate-review JSON citation validation, PUT saved result plus aware `saved_at`, requested history/delete, native PR acceptance/list and explicit context outcomes.
- Optional review arrays default empty. Findings use CMS severity, snapshot evidence/policy IDs and exact evidence code references, including foreign repositories/revisions. Preserve source coverage and **Developer-agent review · Client-reported advisory**.
- Each write sends once. Uncertain registration/save uses history inspection before explicit repetition. Every registration creates another row and fresh context; PUT replaces the result. There is no local recovery state machine.
- Preserve credential precedence, exact approved HTTPS origins, refused redirects, 30-second requests/120-second invocation budget, context/request byte bounds, safe diagnostics, private artifacts and overwrite protection. Keep the tested hidden PAT setup block unchanged.
- Dev manifest/marketplace/package/helper versions agree. Host client/model identifiers are truthful and independent from package versions.

## Real-client acceptance gates

Root owns deployment, dev credentials/browser authorization, installation, actual reviewer execution and live validation. Use an explicit verified `PRIME_API_URL="$publicF"` and `--allow-origin "$publicF"` for every helper invocation. Launch Claude with that same origin so bundled MCP targets dev too. Helper PAT and MCP browser OAuth are separate.

1. Verify matching public `/dev` deployment and default settings (guidance on/plans off). Install this corrected local checkout through the task-local Claude marketplace; restart and verify actual installed path/version and explicit skill invocation. Preserve unrelated plugins/settings and shared credentials.
2. Exercise settings → scoped guardrails → context → register → GET → **actual separate Claude reviewer** → save → GET/list. Read complete private policies. Check the same review/model/summary/evidence/server `saved_at` in the UI. Preserve actual reviewer invocation/result evidence; reminder discovery and main-agent self-review do not establish this gate.
3. Toggle guidance off/plans on and confirm registration/review works with non-policy context. Toggle both off; gated work stops while history/get/delete/PR history remain accessible. A changed guidance setting alone does not block saving the registered plan. Reenable only for explicit new work, without replaying a backlog.
4. Exercise fresh/expired/renewed environment/file credentials and exact-origin trust. For uncertain registration/save, inspect server history before choosing an explicit repeated write. Verify server deletion separately from local artifact cleanup and disclose backup retention.
5. Explicitly create a real dev PR review: accepted native job ID → receipt list. Check CMS-owned results through its proper workflow; receipt history is not live job status. Explicitly report an actually addressed issue using the original context UUID and numeric `code_issue.source_entity_id`; verify developer-reported mitigation activity without changing the CMS finding.
6. Verify actual supported owner/admin boundaries and account-closure purge via proper operator/UI flow. Usage/activity/settings mutation are not required helper commands.
7. For every additional host (Codex, OpenCode, Cursor, Copilot, Pi), prove installation/authentication/skill selection and one separate reviewer with truthful client/model before claiming that capability. All remain pending for this canonical alpha. Unsupported reviewers truthfully record `reviewer_unavailable` or leave plans registered.
8. Hooks/adapters are reminders. Prove startup/resume/compaction context reaches each model without accumulating messages. Automatic Claude ExitPlanMode capture is a separate unpassed gate; preserve human approval and verify actual host payloads before implementing it. Windows remains unverified.
9. Validate update/uninstall/restart without duplicates. Remove only task-owned output/review/guidance files while preserving original plans. Legacy receipt files require deliberate user cleanup; shared credentials and approvals persist.

## Publication and rollback

Publish only the proven client subset after installation, authentication, recovery, separate-review and data-retention gates pass. Pin a reviewed immutable release reference. Older plugin/server contracts cannot honor this managed flow; mismatches fail safely without generic fallback. Unit tests and manifests alone do not establish customer release readiness.
