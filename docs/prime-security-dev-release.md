# Prime Security Dev release checklist

Proposed unpublished version: **1.5.0-alpha.1**. Record immutable commit, client/model versions, OS and approved API environment with each result. Local unit tests and manifest validation establish neither real reviewer execution nor customer release readiness. Operator version/behavior stays unchanged.

## Local implementation checks

- `python3 -m unittest discover -s tests -v` and `node --test tests/opencode.test.mjs tests/pi.test.mjs` pass, including Python 3.9 compatibility.
- Feature request inventory uses only `/dev`; settings failure/disable never falls back to generic APIs or documentation.
- Fresh settings before guidance/context/plan/retry/completion and after 409; two effective controls are independent. Ordinary coding continues on disable/settings failure; history/deletion remain possible.
- Synthetic HTTP boundary checks prove complete private pre-send plan/request/result artifacts, original caller/origin/scope identity, exact replay after lost response/restart/changed files/credential renewal, three explicit recovery attempts and cleanup.
- Registered hashes, evidence IDs and exact stored locations bind typed review findings; plan-only findings work without evidence. Preserve coverage/limitations and **Developer-agent review · Client-reported advisory**.
- Claude plugin and marketplace validation accepts prerelease SemVer. Manifest/package/marketplace versions and helper User-Agent agree; host binary versions are separately truthful.
- Entire skill folder/helper/reference resources install; no token/error bodies leak. Hidden PAT setup passes Bash and interactive zsh tests.

## Separately authorized integration gates

Use disposable synthetic plans and approved dev data. `/dev` deployment, live PAT calls, model execution, data upload and first namespace deployment require the session's authorization. No production request is implied.

- Verify public `/dev` contract, gateway timeout, admin defaults (guardrails on/plans off), persistent settings/history and independent internal plan availability.
- Exercise fresh/expired/renewed environment and file credentials, exact-origin approvals, redirects, unregistered/ambiguous scope and full private policy artifact reads.
- For each advertised host (Claude Code, Codex, OpenCode, Cursor, Copilot, Pi), prove explicit skill selection and **one separate** reviewer invocation returning the registered hashes/typed actionable findings and truthful client/model. A main-agent final diff review or choosing a session-wide alternate agent does not establish this gate. Ship only verified capabilities; report reviewer unavailable where unsupported.
- Change settings during reviewer execution; verify completion stops, historical snapshots are not reused for new guidance, explicit resume/new revision is required and pending receipts survive. Exercise lost POST/PUT responses and renewal across a real restart.
- Hooks/adapters currently emit reminders only. Prove their context reaches the model on startup/resume/compaction; OpenCode/Pi do not accumulate messages. Hook fixtures do not prove settings fetch or review.
- **Automatic Claude capture is a distinct unpassed gate.** Probe actual documented ExitPlanMode event payload in a real interactive approval flow before implementing capture. Preserve human approval, never guess plan paths/modules, block coding, auto-approve or certify review. Other adapters remain reminders unless independently validated.
- Pin final immutable client installation, update/uninstall/restart with no duplicates. Copilot verifies plugin-root variable and working directory; Pi skill disable removes reminder; OpenCode wrapper loads/disposes correctly. Windows is unverified.
- Complete account-closure purge before credential removal; verify server history deletion and disclose separate backup retention. Pending local receipts need explicit completion/deletion/abandonment; uninstall must preserve shared operator credentials.

## Publication and rollback

Publish only after the proven client subset and data-handling/retention policy are accepted. Old plugins call generic APIs and cannot honor account controls; rollback to them loses managed behavior. An undeployed/older backend yields a safe failure, never generic fallback. Keep an immutable reviewed release reference and pilot with a small group.
